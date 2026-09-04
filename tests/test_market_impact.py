# -*- coding: utf-8 -*-
from backend.market_impact import compute_market_impact


def test_high_confidence_high_materiality_news_is_high_impact():
    result = compute_market_impact(
        "POSITIVE", 0.9, "Company beats quarterly earnings and raises guidance",
    )
    assert result["level"] == "HIGH"
    assert result["direction"] == "POSITIVE"


def test_moderate_confidence_medium_materiality_news_is_medium_impact():
    result = compute_market_impact(
        "POSITIVE", 0.6, "Company announces a new partnership with a supplier",
    )
    assert result["level"] == "MEDIUM"


def test_low_materiality_generic_news_is_low_impact_even_with_high_confidence():
    """A confidently positive but low-stakes headline must not read as HIGH
    impact — sentiment confidence alone should not drive the impact level."""
    result = compute_market_impact(
        "POSITIVE", 0.95, "The company's office received new furniture this week",
    )
    assert result["level"] == "LOW"


def test_neutral_sentiment_never_produces_high_impact_even_on_material_news():
    result = compute_market_impact(
        "NEUTRAL", 0.9, "Company will host its quarterly earnings call next week",
    )
    assert result["level"] == "LOW"
    assert result["direction"] == "NEUTRAL"


def test_confidence_and_score_are_bounded_between_0_and_1():
    result = compute_market_impact("NEGATIVE", 1.5, "lawsuit and fraud investigation")
    assert 0.0 <= result["confidence"] <= 1.0
    assert 0.0 <= result["score"] <= 1.0
