# -*- coding: utf-8 -*-
"""Financial sentiment classification.

Pipeline position: Preprocessed News -> Sentiment Analysis -> {POSITIVE,
NEGATIVE, NEUTRAL} + confidence in [0, 1].

Model choice: the project has no NLP dependency yet and `tensorflow` is
already a hard dependency for the LSTM forecaster, so this tries **FinBERT**
(`ProsusAI/finbert`) loaded through `transformers` with its TensorFlow
weights — no `torch` install needed. FinBERT is purpose-trained on financial
text, which matters here (e.g. "shares tumbled on light volume" reads very
differently in finance vs. general-purpose sentiment models).

If `transformers` is not installed, or the model cannot be downloaded (no
network on first run, since Hugging Face weights are fetched lazily and
cached under `~/.cache/huggingface`), this falls back automatically to a
small financial lexicon scorer. Both paths return the same shape, and the
active backend is reported so it never claims to be FinBERT when it isn't.

The model — whichever backend is active — is loaded exactly once per process
via `get_sentiment_analyzer()` and reused for every request.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Literal

logger = logging.getLogger(__name__)

Label = Literal["POSITIVE", "NEGATIVE", "NEUTRAL"]

FINBERT_MODEL_NAME = "ProsusAI/finbert"

# ---------------------------------------------------------------------------
#  Lexicon fallback
# ---------------------------------------------------------------------------

_POSITIVE_WORDS = {
    "beat", "beats", "beating", "surge", "surged", "surging", "soar", "soared",
    "rally", "rallied", "gain", "gains", "gained", "record", "strong",
    "stronger", "growth", "upgrade", "upgraded", "outperform", "bullish",
    "profit", "profits", "profitable", "exceed", "exceeds", "exceeded",
    "rise", "rises", "rose", "rising", "jump", "jumped", "boost", "boosted",
    "optimistic", "robust", "upbeat", "raised", "raise", "expansion",
    "breakthrough", "success", "successful", "win", "wins", "won",
}

_NEGATIVE_WORDS = {
    "miss", "misses", "missed", "plunge", "plunged", "plunging", "crash",
    "crashed", "slump", "slumped", "loss", "losses", "downgrade",
    "downgraded", "underperform", "bearish", "decline", "declines",
    "declined", "fall", "falls", "fell", "falling", "drop", "dropped",
    "cut", "cuts", "weak", "weakness", "layoffs", "lawsuit", "fraud",
    "investigation", "recall", "warning", "concern", "concerns", "risk",
    "risks", "sued", "fine", "fined", "bankruptcy", "default", "scandal",
    "probe", "tumble", "tumbled", "shortfall",
}

_WORD_RE = re.compile(r"[a-zA-Z']+")

# Below this many sentiment-bearing words, confidence is capped — a single
# hit either way is weak evidence.
_NEUTRAL_DEFAULT_CONFIDENCE = 0.55


def _lexicon_analyze(text: str) -> dict:
    tokens = _WORD_RE.findall(text.lower())
    pos_hits = sum(1 for t in tokens if t in _POSITIVE_WORDS)
    neg_hits = sum(1 for t in tokens if t in _NEGATIVE_WORDS)
    total_hits = pos_hits + neg_hits

    if total_hits == 0:
        return {"label": "NEUTRAL", "score": _NEUTRAL_DEFAULT_CONFIDENCE, "backend": "lexicon"}

    net = (pos_hits - neg_hits) / total_hits
    if net > 0.15:
        label: Label = "POSITIVE"
    elif net < -0.15:
        label = "NEGATIVE"
    else:
        label = "NEUTRAL"

    # More hits and a more one-sided ratio both raise confidence, capped
    # below 1.0 since this is a bag-of-words heuristic, not a trained model.
    confidence = 0.5 + abs(net) * 0.35 + min(total_hits, 5) * 0.03
    return {"label": label, "score": round(min(confidence, 0.95), 4), "backend": "lexicon"}


# ---------------------------------------------------------------------------
#  FinBERT backend
# ---------------------------------------------------------------------------

class _FinBertBackend:
    def __init__(self) -> None:
        from transformers import AutoTokenizer, TFAutoModelForSequenceClassification

        self._tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL_NAME)
        self._model = TFAutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL_NAME)

    def analyze(self, text: str) -> dict:
        import numpy as np

        inputs = self._tokenizer(text, return_tensors="tf", truncation=True,
                                  max_length=256, padding=True)
        outputs = self._model(**inputs)
        logits = outputs.logits[0].numpy()
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()

        idx = int(np.argmax(probs))
        raw_label = self._model.config.id2label[idx].upper()
        # FinBERT's own labels already are positive/negative/neutral.
        label = raw_label if raw_label in ("POSITIVE", "NEGATIVE", "NEUTRAL") else "NEUTRAL"
        return {"label": label, "score": float(round(probs[idx], 4)), "backend": "finbert"}


# ---------------------------------------------------------------------------
#  Public analyzer
# ---------------------------------------------------------------------------

class SentimentAnalyzer:
    """Loads its backend once at construction time; `analyze()` never
    reloads anything."""

    def __init__(self, prefer_finbert: bool = True) -> None:
        self._finbert: _FinBertBackend | None = None
        self.backend_name = "lexicon"

        if prefer_finbert:
            try:
                self._finbert = _FinBertBackend()
                self.backend_name = "finbert"
                logger.info("Sentiment analyzer: FinBERT loaded.")
            except Exception as exc:  # ImportError, network error, OSError, ...
                logger.warning(
                    "FinBERT unavailable (%s); falling back to the lexicon "
                    "sentiment scorer.", exc,
                )

    def analyze(self, text: str) -> dict:
        """`{"label": "POSITIVE"|"NEGATIVE"|"NEUTRAL", "score": float, "backend": str}`."""
        text = (text or "").strip()
        if not text:
            return {"label": "NEUTRAL", "score": 0.5, "backend": self.backend_name}

        if self._finbert is not None:
            try:
                return self._finbert.analyze(text)
            except Exception as exc:  # a bad single request shouldn't kill the process
                logger.warning("FinBERT inference failed (%s); using lexicon fallback "
                               "for this request only.", exc)
                return _lexicon_analyze(text)

        return _lexicon_analyze(text)


@lru_cache(maxsize=1)
def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Process-wide singleton — the model (if any) loads on first call only."""
    return SentimentAnalyzer(prefer_finbert=True)
