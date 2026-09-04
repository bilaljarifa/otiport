# -*- coding: utf-8 -*-
"""News-context forecasting layer.

This sits **on top of** the existing LSTM forecaster
(`backend.forecaster.predict_returns`) without modifying it: the "Base
Forecast" is exactly what that function already returns. This module only
adds a second, clearly-labelled number — the "News-Context Forecast" — by
nudging the base 22-day return with a small, capped adjustment derived from
`news_features` (see `news_features.py`).

Adjustment formula (documented, not an arbitrary multiplier):

    combined_signal = sentiment_score * impact_score * impact_confidence
    adjustment_22d  = MAX_NEWS_ADJUSTMENT_22D * combined_signal

`sentiment_score` (a.k.a. `weighted_sentiment`) is in [-1, 1], `impact_score`
and `impact_confidence` are both in [0, 1], so `combined_signal` is always in
[-1, 1] and `adjustment_22d` is always in
[-MAX_NEWS_ADJUSTMENT_22D, +MAX_NEWS_ADJUSTMENT_22D] — at most a ±2
percentage-point nudge to the 22-day return, applied only when sentiment,
materiality *and* confidence all agree. A single very confident but
low-materiality article, or a materially important but low-confidence one,
both produce a small `combined_signal` and therefore a small adjustment —
by construction, not by a special case.

This is a heuristic context layer, not a retrained model: retraining the
LSTM to take news features as an input would require new labelled data and a
new training run (`train_model.py`), which is out of scope here and left as
a documented possible next step in the README.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.forecaster import predict_returns

logger = logging.getLogger(__name__)

MAX_NEWS_ADJUSTMENT_22D = 0.02  # +/- 2 percentage points on the 22-day return
DISCLAIMER = (
    "News sentiment and market impact are probabilistic estimates. "
    "They do not guarantee future market movements."
)
_POTENTIAL_DIRECTION_THRESHOLD = 0.05


def _fetch_current_price(ticker: str) -> float | None:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        price = info.get("lastPrice") or info.get("last_price")
        return float(price) if price else None
    except Exception as exc:
        logger.info("Could not fetch current price for %s: %s", ticker, exc)
        return None


def get_base_forecast(ticker: str, *, model_path: str | None = None,
                       start_date: str = "2010-01-01") -> dict[str, Any]:
    """The existing model's forecast for one ticker — untouched pass-through
    of `predict_returns`, just narrowed to a single ticker's entry."""
    predictions = predict_returns(tickers=[ticker], model_path=model_path, start_date=start_date)
    return predictions.get(ticker, {
        "predicted_return_22d": None,
        "last_actual_return_22d": 0.0,
        "prediction_date": "N/A",
        "note": "No data available",
    })


def compute_news_adjustment(news_features: dict[str, Any]) -> dict[str, float]:
    sentiment_score = float(news_features.get("sentiment_score", 0.0))
    impact_score = float(news_features.get("impact_score", 0.0))
    impact_confidence = float(news_features.get("impact_confidence", 0.0))

    combined_signal = sentiment_score * impact_score * impact_confidence
    adjustment_22d = MAX_NEWS_ADJUSTMENT_22D * combined_signal

    return {
        "combined_signal": round(combined_signal, 4),
        "adjustment_22d": round(adjustment_22d, 6),
    }


def _potential_direction(combined_signal: float) -> str:
    if combined_signal > _POTENTIAL_DIRECTION_THRESHOLD:
        return "POTENTIAL_POSITIVE_IMPACT"
    if combined_signal < -_POTENTIAL_DIRECTION_THRESHOLD:
        return "POTENTIAL_NEGATIVE_IMPACT"
    return "NEUTRAL"


def build_forecast_context(
    ticker: str,
    news_features: dict[str, Any],
    *,
    model_path: str | None = None,
    current_price: float | None = None,
) -> dict[str, Any]:
    """Base forecast + news-context forecast for one ticker, ready for the
    API response and the comparison UI."""
    base_prediction = get_base_forecast(ticker, model_path=model_path)
    base_return = base_prediction.get("predicted_return_22d")
    model_loaded = base_return is not None
    used_return = base_return if base_return is not None else base_prediction.get(
        "last_actual_return_22d", 0.0)

    adjustment = compute_news_adjustment(news_features)
    news_context_return = used_return + adjustment["adjustment_22d"]

    price = current_price if current_price is not None else _fetch_current_price(ticker)
    base_forecast_price = price * (1 + used_return) if price is not None else None
    news_context_forecast_price = (
        price * (1 + news_context_return) if price is not None else None
    )

    return {
        "ticker": ticker,
        "current_price": price,
        "base_forecast": {
            "predicted_return_22d": base_return,
            "used_return_22d": round(used_return, 6),
            "forecast_price": round(base_forecast_price, 2) if base_forecast_price is not None else None,
            "model_loaded": model_loaded,
            "note": base_prediction.get("note"),
            "prediction_date": base_prediction.get("prediction_date"),
        },
        "news_context_forecast": {
            "predicted_return_22d": round(news_context_return, 6),
            "forecast_price": round(news_context_forecast_price, 2) if news_context_forecast_price is not None else None,
            "adjustment_22d": adjustment["adjustment_22d"],
            "combined_news_signal": adjustment["combined_signal"],
            "max_adjustment_22d": MAX_NEWS_ADJUSTMENT_22D,
        },
        "potential_direction": _potential_direction(adjustment["combined_signal"]),
        "news_features": news_features,
        "disclaimer": DISCLAIMER,
    }
