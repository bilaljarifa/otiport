# -*- coding: utf-8 -*-
from backend.news_aggregator import aggregate, empty_summary


def _article(label, score, *, impact_score=0.8, recency=1.0, level="HIGH"):
    return {
        "sentiment": {"label": label, "score": score},
        "market_impact": {"direction": label, "level": level, "confidence": impact_score},
        "recency_weight": recency,
        "_impact_score": impact_score,
    }


def test_empty_article_list_returns_honest_empty_summary():
    assert aggregate([]) == empty_summary()
    assert empty_summary()["news_count"] == 0


def test_counts_per_label():
    articles = [
        _article("POSITIVE", 0.9),
        _article("POSITIVE", 0.7),
        _article("NEGATIVE", 0.8),
        _article("NEUTRAL", 0.5),
    ]
    summary = aggregate(articles)
    assert summary["news_count"] == 4
    assert summary["positive_news_count"] == 2
    assert summary["negative_news_count"] == 1
    assert summary["neutral_news_count"] == 1


def test_mostly_positive_news_yields_positive_overall_sentiment():
    articles = [_article("POSITIVE", 0.9) for _ in range(4)] + [_article("NEGATIVE", 0.3)]
    summary = aggregate(articles)
    assert summary["overall_sentiment"] == "POSITIVE"
    assert summary["weighted_sentiment"] > 0


def test_recent_news_outweighs_old_news_of_opposite_sign():
    articles = [
        _article("POSITIVE", 0.9, recency=1.0),   # published now
        _article("NEGATIVE", 0.9, recency=0.01),  # published long ago
    ]
    summary = aggregate(articles)
    assert summary["overall_sentiment"] == "POSITIVE"


def test_all_neutral_news_does_not_produce_an_extreme_reading():
    articles = [_article("NEUTRAL", 0.6) for _ in range(5)]
    summary = aggregate(articles)
    assert summary["overall_sentiment"] == "NEUTRAL"
    assert summary["overall_market_impact"] == "NEUTRAL"
    assert summary["weighted_sentiment"] == 0.0
