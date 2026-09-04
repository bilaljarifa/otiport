# -*- coding: utf-8 -*-
"""Turn a ticker's analyzed news into a flat, numeric feature dict the
forecasting context layer (`forecast_context.py`) can consume.

This is deliberately a thin adapter over `news_aggregator.aggregate()` plus
two averages the aggregator doesn't expose (`impact_score`, `recency_weight`)
— it exists so the forecast layer depends on one small, stable contract
instead of reaching into aggregation internals or per-article fields.
"""

from __future__ import annotations

from typing import Any

from backend.news_aggregator import aggregate

NEWS_FEATURE_KEYS = (
    "sentiment_score", "sentiment_confidence", "impact_score", "impact_confidence",
    "news_count", "positive_news_count", "negative_news_count", "neutral_news_count",
    "weighted_sentiment", "recency_weight",
)


def empty_news_features() -> dict[str, Any]:
    return {
        "sentiment_score": 0.0, "sentiment_confidence": 0.0,
        "impact_score": 0.0, "impact_confidence": 0.0,
        "news_count": 0, "positive_news_count": 0,
        "negative_news_count": 0, "neutral_news_count": 0,
        "weighted_sentiment": 0.0, "recency_weight": 0.0,
    }


def build_news_features(analyzed_articles: list[dict[str, Any]]) -> dict[str, Any]:
    if not analyzed_articles:
        return empty_news_features()

    summary = aggregate(analyzed_articles)

    impact_scores = [a.get("_impact_score", a["market_impact"]["confidence"])
                      for a in analyzed_articles]
    recency_weights = [a["recency_weight"] for a in analyzed_articles]

    return {
        "sentiment_score": summary["weighted_sentiment"],
        "sentiment_confidence": summary["average_confidence"],
        "impact_score": round(sum(impact_scores) / len(impact_scores), 4),
        "impact_confidence": summary["overall_confidence"],
        "news_count": summary["news_count"],
        "positive_news_count": summary["positive_news_count"],
        "negative_news_count": summary["negative_news_count"],
        "neutral_news_count": summary["neutral_news_count"],
        "weighted_sentiment": summary["weighted_sentiment"],
        "recency_weight": round(sum(recency_weights) / len(recency_weights), 4),
    }
