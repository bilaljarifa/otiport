# -*- coding: utf-8 -*-
"""Aggregate a ticker's analyzed news into one overall read.

Pipeline position: per-article {sentiment, market_impact, recency_weight} ->
this module -> {overall_sentiment, overall_market_impact, overall_confidence,
weighted_sentiment, per-label counts, average_confidence}.

Weighting: each article contributes
    signed_sentiment(article) * recency_weight(article) * impact_score(article)
to the aggregate, where `signed_sentiment` is +score for POSITIVE, -score for
NEGATIVE, and 0 for NEUTRAL. This means a confidently negative, highly
material, just-published article dominates the aggregate far more than an
old, low-materiality, weakly-confident one — matching the brief's "recent
news should weigh more" and "positive sentiment != automatically high
impact" requirements simultaneously, instead of averaging sentiment alone.
"""

from __future__ import annotations

from typing import Any, Literal

OverallSentiment = Literal["POSITIVE", "NEGATIVE", "NEUTRAL"]
OverallImpact = Literal[
    "STRONGLY_POSITIVE", "MODERATELY_POSITIVE", "NEUTRAL",
    "MODERATELY_NEGATIVE", "STRONGLY_NEGATIVE",
]

_OVERALL_SENTIMENT_THRESHOLD = 0.08
_STRONG_IMPACT_THRESHOLD = 0.35
_MODERATE_IMPACT_THRESHOLD = 0.1


def _signed_sentiment(article: dict[str, Any]) -> float:
    label = article["sentiment"]["label"]
    score = article["sentiment"]["score"]
    if label == "POSITIVE":
        return score
    if label == "NEGATIVE":
        return -score
    return 0.0


def empty_summary() -> dict[str, Any]:
    """Returned when there is no news to aggregate — an honest "no data"
    state rather than a fabricated neutral reading."""
    return {
        "news_count": 0,
        "positive_news_count": 0,
        "negative_news_count": 0,
        "neutral_news_count": 0,
        "weighted_sentiment": 0.0,
        "overall_sentiment": "NEUTRAL",
        "overall_market_impact": "NEUTRAL",
        "overall_confidence": 0.0,
        "average_confidence": 0.0,
    }


def aggregate(analyzed_articles: list[dict[str, Any]]) -> dict[str, Any]:
    if not analyzed_articles:
        return empty_summary()

    counts = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
    weighted_sum = 0.0
    weight_total = 0.0
    confidence_sum = 0.0

    for article in analyzed_articles:
        counts[article["sentiment"]["label"]] += 1
        confidence_sum += article["sentiment"]["score"]

        impact_score = article.get("_impact_score", article["market_impact"]["confidence"])
        weight = article["recency_weight"] * max(impact_score, 1e-6)
        weighted_sum += _signed_sentiment(article) * weight
        weight_total += weight

    news_count = len(analyzed_articles)
    weighted_sentiment = weighted_sum / weight_total if weight_total > 0 else 0.0
    average_confidence = confidence_sum / news_count

    if weighted_sentiment > _OVERALL_SENTIMENT_THRESHOLD:
        overall_sentiment: OverallSentiment = "POSITIVE"
    elif weighted_sentiment < -_OVERALL_SENTIMENT_THRESHOLD:
        overall_sentiment = "NEGATIVE"
    else:
        overall_sentiment = "NEUTRAL"

    magnitude = abs(weighted_sentiment)
    if magnitude >= _STRONG_IMPACT_THRESHOLD:
        strength = "STRONGLY"
    elif magnitude >= _MODERATE_IMPACT_THRESHOLD:
        strength = "MODERATELY"
    else:
        strength = None

    if overall_sentiment == "NEUTRAL" or strength is None:
        overall_market_impact: OverallImpact = "NEUTRAL"
    else:
        overall_market_impact = f"{strength}_{overall_sentiment}"  # type: ignore[assignment]

    return {
        "news_count": news_count,
        "positive_news_count": counts["POSITIVE"],
        "negative_news_count": counts["NEGATIVE"],
        "neutral_news_count": counts["NEUTRAL"],
        "weighted_sentiment": round(weighted_sentiment, 4),
        "overall_sentiment": overall_sentiment,
        "overall_market_impact": overall_market_impact,
        "overall_confidence": round(min(abs(weighted_sentiment) + 0.5, 1.0)
                                     if overall_sentiment != "NEUTRAL" else
                                     max(0.5 - abs(weighted_sentiment), 0.0), 4),
        "average_confidence": round(average_confidence, 4),
    }
