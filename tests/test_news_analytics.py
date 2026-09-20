# -*- coding: utf-8 -*-
"""Tests for `backend/news_analytics.py` — the statistics layer behind the
News Impact Analytics feature. Every function must either compute a real
statistic from the given articles or report an explicit insufficient-data /
empty status; never a fabricated number."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.news_analytics import (
    build_news_analytics,
    build_overview,
    impact_history,
    market_impact_breakdown,
    news_vs_price,
    sentiment_distribution,
    sentiment_trend,
    top_impactful_news,
    volume_analysis,
)

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


def _article(label, score, *, impact_score=0.8, recency=1.0, published_at=None,
             title="Headline", source="Reuters", url="https://example.com/a"):
    return {
        "title": title,
        "description": "desc",
        "source": source,
        "url": url,
        "publishedAt": published_at,
        "sentiment": {"label": label, "score": score},
        "market_impact": {"direction": label, "level": "HIGH", "confidence": impact_score},
        "recency_weight": recency,
        "_impact_score": impact_score,
    }


def _ago(hours=0, days=0):
    return NOW - timedelta(hours=hours, days=days)


# --------------------------------------------------------------------------
# Overview / KPIs
# --------------------------------------------------------------------------

def test_overview_reports_empty_status_without_fabricating_numbers():
    result = build_overview([])
    assert result["status"] == "empty"
    assert result["articles_analyzed"] == 0
    assert result["average_sentiment_score"] is None
    assert result["aggregate_impact_score"] is None


def test_overview_percentages_sum_to_100():
    articles = [
        _article("POSITIVE", 0.9), _article("POSITIVE", 0.7),
        _article("NEGATIVE", 0.6), _article("NEUTRAL", 0.5),
    ]
    result = build_overview(articles)
    assert result["status"] == "ok"
    assert result["articles_analyzed"] == 4
    assert round(result["positive_pct"] + result["negative_pct"] + result["neutral_pct"], 1) == 100.0


def test_overview_average_and_aggregate_are_distinct_when_recency_differs():
    """average_sentiment_score is an unweighted mean; aggregate_impact_score
    is recency+impact weighted — they must not silently collapse to the
    same computation."""
    articles = [
        _article("POSITIVE", 0.9, recency=1.0, impact_score=0.9),
        _article("NEGATIVE", 0.9, recency=0.01, impact_score=0.9),
    ]
    result = build_overview(articles)
    assert result["average_sentiment_score"] == 0.0  # +0.9 and -0.9 average out
    assert result["aggregate_impact_score"] > 0  # recent positive article dominates


# --------------------------------------------------------------------------
# Sentiment distribution
# --------------------------------------------------------------------------

def test_sentiment_distribution_empty():
    result = sentiment_distribution([])
    assert result["status"] == "empty"
    assert result["distribution"] == []


def test_sentiment_distribution_counts_and_average_score():
    articles = [_article("POSITIVE", 0.8), _article("POSITIVE", 0.6), _article("NEGATIVE", 0.9)]
    result = sentiment_distribution(articles)
    by_label = {b["label"]: b for b in result["distribution"]}
    assert by_label["POSITIVE"]["count"] == 2
    assert by_label["POSITIVE"]["average_score"] == 0.7
    assert by_label["NEGATIVE"]["count"] == 1
    assert by_label["NEUTRAL"]["count"] == 0
    assert by_label["NEUTRAL"]["average_score"] is None


# --------------------------------------------------------------------------
# Sentiment trend
# --------------------------------------------------------------------------

def test_sentiment_trend_insufficient_data_without_timestamps():
    result = sentiment_trend([_article("POSITIVE", 0.8, published_at=None)], now=NOW)
    assert result["status"] == "insufficient_data"
    assert result["ranges"] == []


def test_sentiment_trend_only_marks_windows_with_enough_coverage_as_available():
    # All articles are 10 days old — well outside 24H/3D/7D, inside 30D.
    articles = [
        _article("POSITIVE", 0.8, published_at=_ago(days=10)),
        _article("NEGATIVE", 0.7, published_at=_ago(days=10, hours=1)),
    ]
    result = sentiment_trend(articles, now=NOW)
    assert result["status"] == "ok"
    by_range = {r["range"]: r for r in result["ranges"]}
    assert by_range["24H"]["available"] is False
    assert by_range["3D"]["available"] is False
    assert by_range["7D"]["available"] is False
    assert by_range["30D"]["available"] is True
    assert by_range["30D"]["article_count"] == 2


def test_sentiment_trend_buckets_by_hour_for_24h_window():
    articles = [
        _article("POSITIVE", 0.9, published_at=_ago(hours=1)),
        _article("POSITIVE", 0.7, published_at=_ago(hours=1, days=0)),
        _article("NEGATIVE", 0.5, published_at=_ago(hours=12)),
    ]
    result = sentiment_trend(articles, now=NOW)
    range_24h = next(r for r in result["ranges"] if r["range"] == "24H")
    assert range_24h["available"] is True
    assert sum(p["article_count"] for p in range_24h["points"]) == 3


# --------------------------------------------------------------------------
# Volume analysis
# --------------------------------------------------------------------------

def test_volume_analysis_insufficient_data_without_timestamps():
    result = volume_analysis([_article("POSITIVE", 0.8)], now=NOW)
    assert result["status"] == "insufficient_data"


def test_volume_analysis_no_previous_period_when_history_is_short():
    articles = [_article("POSITIVE", 0.8, published_at=_ago(hours=h)) for h in (1, 5, 10)]
    result = volume_analysis(articles, now=NOW)
    assert result["status"] == "ok"
    assert result["previous_period_available"] is False
    assert result["insufficient_history_reason"] is not None


def test_volume_analysis_computes_period_over_period_change_with_enough_history():
    # 4 articles this week, 2 the week before -> +100% change, 60 days of span.
    articles = (
        [_article("POSITIVE", 0.8, published_at=_ago(days=d)) for d in (1, 2, 3, 4)]
        + [_article("NEGATIVE", 0.6, published_at=_ago(days=d)) for d in (10, 12)]
        + [_article("NEUTRAL", 0.5, published_at=_ago(days=59))]
    )
    result = volume_analysis(articles, now=NOW)
    assert result["status"] == "ok"
    assert result["previous_period_available"] is True
    assert result["current_period_count"] == 4
    assert result["previous_period_count"] == 2
    assert result["pct_change"] == 100.0


# --------------------------------------------------------------------------
# Market impact breakdown
# --------------------------------------------------------------------------

def test_market_impact_breakdown_empty():
    result = market_impact_breakdown([])
    assert result["status"] == "empty"


def test_market_impact_breakdown_contributions_sum_to_aggregate_score():
    articles = [
        _article("POSITIVE", 0.9, impact_score=0.8, recency=1.0),
        _article("NEGATIVE", 0.6, impact_score=0.5, recency=0.8),
        _article("NEUTRAL", 0.4, impact_score=0.3, recency=0.5),
    ]
    result = market_impact_breakdown(articles)
    assert result["status"] == "ok"
    assert result["positive_contribution"] + result["negative_contribution"] == \
        pytest.approx(result["aggregate_score"], abs=1e-3)
    assert result["scale_min"] == -1.0
    assert result["scale_max"] == 1.0


# --------------------------------------------------------------------------
# Top impactful news
# --------------------------------------------------------------------------

def test_top_impactful_news_ranks_by_existing_impact_score_not_sentiment():
    articles = [
        _article("POSITIVE", 0.99, impact_score=0.2, title="mild positive"),
        _article("NEGATIVE", 0.3, impact_score=0.95, title="high-impact negative"),
    ]
    result = top_impactful_news(articles)
    assert result["status"] == "ok"
    assert result["items"][0]["title"] == "high-impact negative"
    assert result["items"][0]["impact_score"] == 0.95


def test_top_impactful_news_respects_limit():
    articles = [_article("NEUTRAL", 0.5, impact_score=i / 10, title=f"a{i}") for i in range(15)]
    result = top_impactful_news(articles, limit=5)
    assert len(result["items"]) == 5


# --------------------------------------------------------------------------
# News vs. price
# --------------------------------------------------------------------------

def test_news_vs_price_insufficient_data_with_no_price_bars():
    articles = [_article("POSITIVE", 0.8, published_at=_ago(days=1))]
    result = news_vs_price(articles, [])
    assert result["status"] == "insufficient_data"


def test_news_vs_price_computes_positive_correlation_for_aligned_data():
    price_bars = []
    articles = []
    price = 100.0
    for d in range(10, 0, -1):  # oldest -> newest
        day = (NOW - timedelta(days=d)).strftime("%Y-%m-%d")
        # Alternate: positive sentiment days go up, negative days go down.
        up_day = d % 2 == 0
        price = price * (1.01 if up_day else 0.99)
        price_bars.append({"time": day, "open": price, "high": price, "low": price,
                            "close": price, "volume": 1000})
        label = "POSITIVE" if up_day else "NEGATIVE"
        articles.append(_article(label, 0.8, published_at=_ago(days=d)))

    result = news_vs_price(articles, price_bars)
    assert result["status"] == "ok"
    assert result["observation_count"] >= 8
    assert result["correlation_coefficient"] > 0
    assert "not" in result["methodology"].lower()  # states non-causality


# --------------------------------------------------------------------------
# Impact history
# --------------------------------------------------------------------------

def test_impact_history_insufficient_data_with_too_few_dated_articles():
    result = impact_history([_article("POSITIVE", 0.8, published_at=_ago(hours=1))])
    assert result["status"] == "insufficient_data"


def test_impact_history_builds_daily_points():
    articles = [
        _article("POSITIVE", 0.9, published_at=_ago(days=2)),
        _article("NEGATIVE", 0.8, published_at=_ago(days=1)),
        _article("NEGATIVE", 0.7, published_at=_ago(days=1, hours=2)),
    ]
    result = impact_history(articles)
    assert result["status"] == "ok"
    assert len(result["points"]) == 2
    assert all("aggregate_impact_score" in p for p in result["points"])


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def test_build_news_analytics_assembles_every_section():
    articles = [_article("POSITIVE", 0.8, published_at=_ago(hours=1))]
    result = build_news_analytics("SPY", articles, [])
    assert result["ticker"] == "SPY"
    for key in (
        "overview", "sentiment_distribution", "sentiment_trend", "volume_analysis",
        "market_impact", "top_news", "news_vs_price", "impact_history",
    ):
        assert key in result
