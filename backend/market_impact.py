# -*- coding: utf-8 -*-
"""Market impact engine.

Pipeline position: Sentiment -> Market Impact -> {direction, level,
confidence}.

Deliberately **not** `impact = sentiment`: a strongly-worded but low-stakes
headline ("Apple app gets a minor UI refresh, reviewers pleased") should not
register the same impact as an earnings beat. This module estimates a
*materiality* score from the kind of news (earnings, M&A, regulatory/legal,
guidance, ratings actions, leadership changes, security incidents count as
high-materiality; partnerships/launches/analyst notes as medium; everything
else as low), then combines it with the sentiment confidence — a high-impact
category with weak sentiment confidence, or a confident sentiment on a
low-materiality story, both land in the middle rather than at the extremes.

What this does *not* do: it does not look at historical price reactions to
similar headlines for the specific ticker (no backtesting store exists in
this project), and it does not use recency — that is handled separately by
`news_recency.py` at the aggregation stage, since one article's materiality
does not change with its age even though its *weight in an aggregate* should.
"""

from __future__ import annotations

import re
from typing import Literal

Direction = Literal["POSITIVE", "NEGATIVE", "NEUTRAL"]
Level = Literal["LOW", "MEDIUM", "HIGH"]

_WORD_RE = re.compile(r"[a-zA-Z']+")

# Keyword categories used only to estimate how *material* a story is likely
# to be to the market's view of the company — not its sentiment.
_HIGH_MATERIALITY_KEYWORDS = {
    "earnings", "guidance", "merger", "acquisition", "acquire", "acquires",
    "lawsuit", "sec", "fda", "recall", "bankruptcy", "layoffs", "buyback",
    "dividend", "upgrade", "downgrade", "outlook", "investigation", "fraud",
    "resign", "resignation", "breach", "hack", "sanction", "sanctions",
    "tariff", "tariffs", "ceo", "cfo", "restatement", "delisting", "default",
    "profit warning", "guidance cut", "antitrust",
}
_MEDIUM_MATERIALITY_KEYWORDS = {
    "partnership", "launch", "launches", "expansion", "contract", "deal",
    "stake", "investment", "hire", "hires", "appoint", "appoints", "rating",
    "analyst", "price target", "supply", "shortage", "collaboration",
    "patent", "product",
}

_HIGH_MATERIALITY_SCORE = 1.0
_MEDIUM_MATERIALITY_SCORE = 0.6
_LOW_MATERIALITY_SCORE = 0.3

_LEVEL_HIGH_THRESHOLD = 0.66
_LEVEL_MEDIUM_THRESHOLD = 0.35


def _materiality_score(text: str) -> float:
    lower = text.lower()
    if any(kw in lower for kw in _HIGH_MATERIALITY_KEYWORDS):
        return _HIGH_MATERIALITY_SCORE
    if any(kw in lower for kw in _MEDIUM_MATERIALITY_KEYWORDS):
        return _MEDIUM_MATERIALITY_SCORE
    return _LOW_MATERIALITY_SCORE


def _level_from_score(score: float) -> Level:
    if score >= _LEVEL_HIGH_THRESHOLD:
        return "HIGH"
    if score >= _LEVEL_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def compute_market_impact(sentiment_label: Direction, sentiment_confidence: float,
                           text: str) -> dict:
    """`{"direction", "level", "confidence", "materiality_score"}`.

    `direction` mirrors the sentiment label (impact has no direction of its
    own independent of sentiment), but `level` and `confidence` are shaped by
    materiality, not by sentiment confidence alone.
    """
    materiality = _materiality_score(text or "")
    sentiment_confidence = max(0.0, min(1.0, sentiment_confidence))

    if sentiment_label == "NEUTRAL":
        # A neutral read carries no directional impact regardless of how
        # "important" the story's category looks.
        impact_score = materiality * 0.3
    else:
        impact_score = sentiment_confidence * materiality

    confidence = 0.6 * sentiment_confidence + 0.4 * materiality

    return {
        "direction": sentiment_label,
        "level": _level_from_score(impact_score),
        "confidence": round(min(max(confidence, 0.0), 1.0), 4),
        "score": round(min(max(impact_score, 0.0), 1.0), 4),
        "materiality_score": round(materiality, 2),
    }
