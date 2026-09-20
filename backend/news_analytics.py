# -*- coding: utf-8 -*-
"""Quantitative statistics layer for the News Impact Analytics feature.

Every function here consumes the same `analyzed_articles` shape already
produced by `backend.news_pipeline.analyze_articles` (title, description,
source, url, publishedAt, sentiment, market_impact, recency_weight,
_impact_score). This module adds no second scoring system: it only
aggregates, buckets and presents values `news_aggregator`, `market_impact`
and `news_recency` already compute — reusing `news_aggregator.aggregate`'s
exact recency+impact-weighted formula everywhere a "weighted sentiment" or
"impact score" is needed, including per-day and per-window slices of it.

Every function returns an explicit `status` ("ok" | "insufficient_data" |
"empty") instead of a fabricated value when the real sample is too small or
missing — mirroring the pattern already established by
`backend.performance_metrics.InsufficientHistoryError` and
`backend.news_aggregator.empty_summary`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np

from backend.news_aggregator import aggregate, _signed_sentiment
from backend.news_recency import _parse_timestamp as parse_timestamp

MIN_ARTICLES_FOR_TREND = 2
MIN_ARTICLES_FOR_VOLUME_COMPARISON = 4
MIN_OBSERVATIONS_FOR_CORRELATION = 8

# (label, window) — a window is only reported as "available" once enough
# dated articles actually fall inside it; see `sentiment_trend`.
_TREND_WINDOWS: list[tuple[str, timedelta]] = [
    ("24H", timedelta(hours=24)),
    ("3D", timedelta(days=3)),
    ("7D", timedelta(days=7)),
    ("30D", timedelta(days=30)),
]


def _dated_articles(analyzed_articles: list[dict[str, Any]]) -> list[tuple[datetime, dict[str, Any]]]:
    """Articles with a parseable `publishedAt`, paired with the parsed
    timestamp. Articles without one are excluded from anything
    time-bucketed — never assumed to be "now"."""
    out = []
    for a in analyzed_articles:
        ts = parse_timestamp(a.get("publishedAt"))
        if ts is not None:
            out.append((ts, a))
    return out


def _impact_score(article: dict[str, Any]) -> float:
    """The same internal per-article magnitude `news_aggregator` weights
    by — public `market_impact.confidence` is used as a fallback only for
    articles that somehow lack the internal field."""
    return article.get("_impact_score", article["market_impact"]["confidence"])


# --------------------------------------------------------------------------
# 1. Overview / KPIs
# --------------------------------------------------------------------------

def build_overview(analyzed_articles: list[dict[str, Any]]) -> dict[str, Any]:
    """KPI-card numbers for a ticker. `average_sentiment_score` is the plain,
    unweighted mean of signed sentiment across articles; `aggregate_impact_score`
    is the existing recency+impact-weighted aggregate (`weighted_sentiment`) —
    these are two genuinely different statistics, not a duplicate."""
    summary = aggregate(analyzed_articles)
    news_count = summary["news_count"]

    if news_count == 0:
        return {
            "status": "empty",
            "articles_analyzed": 0,
            "positive_pct": None,
            "neutral_pct": None,
            "negative_pct": None,
            "average_sentiment_score": None,
            "aggregate_impact_score": None,
            "overall_sentiment": summary["overall_sentiment"],
            "overall_market_impact": summary["overall_market_impact"],
        }

    def pct(n: int) -> float:
        return round(n / news_count * 100, 1)

    average_sentiment = sum(_signed_sentiment(a) for a in analyzed_articles) / news_count

    return {
        "status": "ok",
        "articles_analyzed": news_count,
        "positive_pct": pct(summary["positive_news_count"]),
        "neutral_pct": pct(summary["neutral_news_count"]),
        "negative_pct": pct(summary["negative_news_count"]),
        "average_sentiment_score": round(average_sentiment, 4),
        "aggregate_impact_score": summary["weighted_sentiment"],
        "overall_sentiment": summary["overall_sentiment"],
        "overall_market_impact": summary["overall_market_impact"],
    }


# --------------------------------------------------------------------------
# 2. Sentiment distribution
# --------------------------------------------------------------------------

def sentiment_distribution(analyzed_articles: list[dict[str, Any]]) -> dict[str, Any]:
    news_count = len(analyzed_articles)
    if news_count == 0:
        return {"status": "empty", "total": 0, "distribution": []}

    buckets: dict[str, list[float]] = {"POSITIVE": [], "NEUTRAL": [], "NEGATIVE": []}
    for a in analyzed_articles:
        buckets[a["sentiment"]["label"]].append(a["sentiment"]["score"])

    distribution = []
    for label in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
        scores = buckets[label]
        distribution.append({
            "label": label,
            "count": len(scores),
            "pct": round(len(scores) / news_count * 100, 1),
            "average_score": round(sum(scores) / len(scores), 4) if scores else None,
        })

    return {"status": "ok", "total": news_count, "distribution": distribution}


# --------------------------------------------------------------------------
# 3. Sentiment trend (+ volume over time, same buckets)
# --------------------------------------------------------------------------

def sentiment_trend(
    analyzed_articles: list[dict[str, Any]], *, now: Optional[datetime] = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    dated = _dated_articles(analyzed_articles)
    if not dated:
        return {
            "status": "insufficient_data",
            "reason": "No articles have a parseable publish timestamp.",
            "ranges": [],
        }

    oldest = min(ts for ts, _ in dated)
    data_span_hours = round((now - oldest).total_seconds() / 3600, 1)

    ranges = []
    for label, window in _TREND_WINDOWS:
        in_window = [(ts, a) for ts, a in dated if now - ts <= window]
        if len(in_window) < MIN_ARTICLES_FOR_TREND:
            ranges.append({
                "range": label,
                "available": False,
                "reason": f"Fewer than {MIN_ARTICLES_FOR_TREND} articles published within this window.",
                "points": [],
            })
            continue

        bucket_fmt = "%Y-%m-%dT%H:00" if label == "24H" else "%Y-%m-%d"
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ts, a in in_window:
            buckets[ts.strftime(bucket_fmt)].append(a)

        points = []
        for key in sorted(buckets):
            arts = buckets[key]
            signed = [_signed_sentiment(a) for a in arts]
            points.append({
                "bucket": key,
                "article_count": len(arts),
                "average_sentiment": round(sum(signed) / len(signed), 4),
            })

        ranges.append({
            "range": label, "available": True, "article_count": len(in_window), "points": points,
        })

    return {"status": "ok", "data_span_hours": data_span_hours, "ranges": ranges}


# --------------------------------------------------------------------------
# 4. News volume analysis
# --------------------------------------------------------------------------

def volume_analysis(
    analyzed_articles: list[dict[str, Any]], *, now: Optional[datetime] = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    dated = _dated_articles(analyzed_articles)
    if not dated:
        return {"status": "insufficient_data", "reason": "No articles have a parseable publish timestamp."}

    oldest = min(ts for ts, _ in dated)
    span_days = max((now - oldest).total_seconds() / 86400, 0.0)

    per_day: dict[str, int] = defaultdict(int)
    for ts, _ in dated:
        per_day[ts.strftime("%Y-%m-%d")] += 1
    daily_series = [{"date": d, "count": c} for d, c in sorted(per_day.items())]

    # The "current period" is whatever span we actually have, capped at a
    # week — never a fixed 7 days pretending to be backed by 2 days of data.
    period_days = 7 if span_days >= 7 else max(int(span_days), 1)
    current_start = now - timedelta(days=period_days)
    current_count = sum(1 for ts, _ in dated if ts >= current_start)

    result: dict[str, Any] = {
        "status": "ok",
        "daily_series": daily_series,
        "data_span_days": round(span_days, 1),
        "current_period_days": period_days,
        "current_period_count": current_count,
        "previous_period_available": False,
        "previous_period_count": None,
        "pct_change": None,
        "insufficient_history_reason": None,
    }

    enough_history = span_days >= 2 * period_days and len(dated) >= MIN_ARTICLES_FOR_VOLUME_COMPARISON
    if enough_history:
        previous_start = current_start - timedelta(days=period_days)
        previous_count = sum(1 for ts, _ in dated if previous_start <= ts < current_start)
        result["previous_period_available"] = True
        result["previous_period_count"] = previous_count
        result["pct_change"] = (
            round((current_count - previous_count) / previous_count * 100, 1)
            if previous_count > 0 else None
        )
    else:
        result["insufficient_history_reason"] = (
            "Not enough historical coverage to compare against a prior period of equal length."
        )

    return result


# --------------------------------------------------------------------------
# 5. Market impact score breakdown
# --------------------------------------------------------------------------

def market_impact_breakdown(analyzed_articles: list[dict[str, Any]]) -> dict[str, Any]:
    """Decomposes the EXISTING `news_aggregator.aggregate` weighted-average
    formula into its positive/negative shares — not a second scoring system.
    `positive_contribution + negative_contribution == aggregate_score`
    (NEUTRAL articles contribute exactly 0, by construction)."""
    summary = aggregate(analyzed_articles)
    if summary["news_count"] == 0:
        return {"status": "empty", "aggregate_score": None}

    weight_total = 0.0
    signed_weights: list[float] = []
    for a in analyzed_articles:
        weight = a["recency_weight"] * max(_impact_score(a), 1e-6)
        weight_total += weight
        signed_weights.append(_signed_sentiment(a) * weight)

    positive_contribution = 0.0
    negative_contribution = 0.0
    if weight_total > 0:
        for signed_weight in signed_weights:
            share = signed_weight / weight_total
            if share > 0:
                positive_contribution += share
            elif share < 0:
                negative_contribution += share

    avg_recency = sum(a["recency_weight"] for a in analyzed_articles) / summary["news_count"]
    avg_impact_score = sum(_impact_score(a) for a in analyzed_articles) / summary["news_count"]

    return {
        "status": "ok",
        "aggregate_score": summary["weighted_sentiment"],
        "scale_min": -1.0,
        "scale_max": 1.0,
        "overall_sentiment": summary["overall_sentiment"],
        "overall_market_impact": summary["overall_market_impact"],
        "positive_contribution": round(positive_contribution, 4),
        "negative_contribution": round(negative_contribution, 4),
        "average_recency_weight": round(avg_recency, 4),
        "average_article_impact_score": round(avg_impact_score, 4),
        "articles_considered": summary["news_count"],
    }


# --------------------------------------------------------------------------
# 6. Top impactful news
# --------------------------------------------------------------------------

def top_impactful_news(analyzed_articles: list[dict[str, Any]], *, limit: int = 10) -> dict[str, Any]:
    """Ranked by the existing internal impact score — the exact magnitude
    `news_aggregator` weights each article's sentiment by. No new ranking
    formula."""
    if not analyzed_articles:
        return {"status": "empty", "items": []}

    ranked = sorted(analyzed_articles, key=_impact_score, reverse=True)[:limit]
    items = [{
        "title": a["title"],
        "source": a["source"],
        "url": a["url"],
        "publishedAt": a["publishedAt"],
        "sentiment": a["sentiment"],
        "market_impact": a["market_impact"],
        "impact_score": round(_impact_score(a), 4),
        "recency_weight": a["recency_weight"],
    } for a in ranked]
    return {"status": "ok", "items": items}


# --------------------------------------------------------------------------
# 7. News vs. price movement
# --------------------------------------------------------------------------

def news_vs_price(
    analyzed_articles: list[dict[str, Any]],
    price_bars: list[dict[str, Any]],
) -> dict[str, Any]:
    """Observed statistical association only — every field name and the
    methodology string are written to never imply causation. Correlates each
    day's news-weighted sentiment (the same weighting `aggregate` uses) with
    that day's realized closing-price return, using real OHLC bars from
    `backend.pricing.get_ohlc`."""
    dated = _dated_articles(analyzed_articles)
    if not dated or len(price_bars) < 2:
        return {
            "status": "insufficient_data",
            "reason": "Not enough dated news articles or price history to compare.",
        }

    closes = {bar["time"]: bar["close"] for bar in price_bars}
    sorted_dates = sorted(closes)
    daily_return: dict[str, float] = {}
    for i in range(1, len(sorted_dates)):
        prev_date, cur_date = sorted_dates[i - 1], sorted_dates[i]
        if closes[prev_date] > 0:
            daily_return[cur_date] = (closes[cur_date] - closes[prev_date]) / closes[prev_date]

    per_day_articles: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ts, a in dated:
        per_day_articles[ts.strftime("%Y-%m-%d")].append(a)

    observations = []
    for day, arts in sorted(per_day_articles.items()):
        if day not in daily_return:
            continue
        day_summary = aggregate(arts)
        observations.append({
            "date": day,
            "sentiment": day_summary["weighted_sentiment"],
            "article_count": len(arts),
            "daily_return_pct": round(daily_return[day] * 100, 3),
        })

    if len(observations) < MIN_OBSERVATIONS_FOR_CORRELATION:
        return {
            "status": "insufficient_data",
            "reason": (
                f"Only {len(observations)} day(s) have both news and matching price data; "
                f"at least {MIN_OBSERVATIONS_FOR_CORRELATION} are needed for a reliable correlation."
            ),
            "observations": observations,
        }

    xs = np.array([o["sentiment"] for o in observations], dtype=float)
    ys = np.array([o["daily_return_pct"] for o in observations], dtype=float)
    correlation: Optional[float] = None
    if xs.std() > 0 and ys.std() > 0:
        correlation = round(float(np.corrcoef(xs, ys)[0, 1]), 4)

    return {
        "status": "ok",
        "methodology": (
            "Pearson correlation between each day's news-weighted sentiment "
            "(the same recency+impact weighting used for the aggregate impact "
            "score) and that day's realized closing-price return. Describes a "
            "historical association only — not predictive and not causal."
        ),
        "observation_count": len(observations),
        "correlation_coefficient": correlation,
        "observations": observations,
    }


# --------------------------------------------------------------------------
# 9. News impact history
# --------------------------------------------------------------------------

def impact_history(analyzed_articles: list[dict[str, Any]]) -> dict[str, Any]:
    dated = _dated_articles(analyzed_articles)
    if len(dated) < MIN_ARTICLES_FOR_TREND:
        return {
            "status": "insufficient_data",
            "reason": "Not enough dated articles to build a news impact history.",
            "points": [],
        }

    per_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ts, a in dated:
        per_day[ts.strftime("%Y-%m-%d")].append(a)

    points = []
    for day in sorted(per_day):
        arts = per_day[day]
        day_summary = aggregate(arts)
        points.append({
            "date": day,
            "article_count": len(arts),
            "aggregate_impact_score": day_summary["weighted_sentiment"],
            "overall_market_impact": day_summary["overall_market_impact"],
        })

    return {"status": "ok", "points": points}


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def build_news_analytics(
    ticker: str,
    analyzed_articles: list[dict[str, Any]],
    price_bars: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assembles every section from the same single `analyzed_articles`
    fetch — one wide-window pass through the existing pipeline, not one
    fetch per section."""
    return {
        "ticker": ticker,
        "overview": build_overview(analyzed_articles),
        "sentiment_distribution": sentiment_distribution(analyzed_articles),
        "sentiment_trend": sentiment_trend(analyzed_articles),
        "volume_analysis": volume_analysis(analyzed_articles),
        "market_impact": market_impact_breakdown(analyzed_articles),
        "top_news": top_impactful_news(analyzed_articles),
        "news_vs_price": news_vs_price(analyzed_articles, price_bars),
        "impact_history": impact_history(analyzed_articles),
    }
