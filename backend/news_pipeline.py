# -*- coding: utf-8 -*-
"""Wires preprocessing -> sentiment -> market impact -> recency into a single
per-article analysis step, so `api.py` and `news_aggregator.py` share one
definition of what an "analyzed article" looks like.
"""

from __future__ import annotations

from typing import Any

from backend.market_impact import compute_market_impact
from backend.news_preprocessing import preprocess_article, preprocess_articles
from backend.news_recency import recency_weight
from backend.sentiment import get_sentiment_analyzer


def analyze_article(article: dict[str, Any]) -> dict[str, Any] | None:
    """Full pipeline for one raw article. `None` if it has no usable text."""
    preprocessed = preprocess_article(article)
    if preprocessed is None:
        return None
    return _analyze_preprocessed(preprocessed)


def _analyze_preprocessed(preprocessed: dict[str, Any]) -> dict[str, Any]:
    sentiment = get_sentiment_analyzer().analyze(preprocessed["analysis_text"])
    impact = compute_market_impact(
        sentiment["label"], sentiment["score"], preprocessed["analysis_text"],
    )
    weight = recency_weight(preprocessed.get("publishedAt"))

    return {
        "title": preprocessed["title"],
        "description": preprocessed["description"],
        "source": preprocessed["source"],
        "url": preprocessed["url"],
        "publishedAt": preprocessed.get("publishedAt"),
        "sentiment": {"label": sentiment["label"], "score": sentiment["score"]},
        "market_impact": {
            "direction": impact["direction"],
            "level": impact["level"],
            "confidence": impact["confidence"],
        },
        "recency_weight": round(weight, 4),
        "_impact_score": impact["score"],  # internal: consumed by the aggregator only
    }


def analyze_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preprocess + analyze a batch of raw NewsAPI articles, dropping any
    with no usable text. Order is preserved (callers sort by recency)."""
    return [_analyze_preprocessed(a) for a in preprocess_articles(articles)]
