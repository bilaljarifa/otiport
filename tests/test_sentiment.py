# -*- coding: utf-8 -*-
"""Sentiment tests run against the lexicon backend deliberately
(`prefer_finbert=False`): FinBERT requires downloading weights on first use,
which must not be a precondition for the test suite to pass offline/in CI.
"""

from backend.sentiment import SentimentAnalyzer


def _analyzer() -> SentimentAnalyzer:
    return SentimentAnalyzer(prefer_finbert=False)


def test_positive_news_is_classified_positive():
    result = _analyzer().analyze(
        "Company beats earnings expectations and shares surge on record profit growth"
    )
    assert result["label"] == "POSITIVE"
    assert 0.0 <= result["score"] <= 1.0


def test_negative_news_is_classified_negative():
    result = _analyzer().analyze(
        "Company misses earnings, shares plunge amid investigation and bankruptcy fears"
    )
    assert result["label"] == "NEGATIVE"
    assert 0.0 <= result["score"] <= 1.0


def test_neutral_news_is_classified_neutral():
    result = _analyzer().analyze(
        "The company will hold its annual shareholder meeting next Tuesday"
    )
    assert result["label"] == "NEUTRAL"


def test_empty_text_is_neutral_and_does_not_raise():
    result = _analyzer().analyze("")
    assert result["label"] == "NEUTRAL"


def test_backend_is_reported_and_lexicon_never_reloads_state():
    analyzer = _analyzer()
    assert analyzer.backend_name == "lexicon"
    first = analyzer.analyze("shares surge on record profit")
    second = analyzer.analyze("shares surge on record profit")
    assert first == second
