# -*- coding: utf-8 -*-
"""Forecast-context tests. `backend.forecaster.predict_returns` — the
existing, untouched LSTM forecaster — is mocked so these tests exercise only
the news-adjustment layer, not model inference or Yahoo Finance."""

from unittest.mock import patch

from backend.forecast_context import (
    MAX_NEWS_ADJUSTMENT_22D,
    build_forecast_context,
    compute_news_adjustment,
)
from backend.news_features import empty_news_features


def _base_prediction(predicted=0.03):
    return {"AAPL": {
        "predicted_return_22d": predicted,
        "last_actual_return_22d": 0.02,
        "prediction_date": "2026-08-28",
        "note": None,
    }}


def test_existing_forecast_pipeline_still_works_and_is_untouched():
    """The base forecast returned to callers must be exactly what
    `predict_returns` produced — no post-hoc modification."""
    with patch("backend.forecast_context.predict_returns", return_value=_base_prediction(0.03)):
        context = build_forecast_context(
            "AAPL", empty_news_features(), current_price=100.0,
        )
    assert context["base_forecast"]["predicted_return_22d"] == 0.03
    assert context["base_forecast"]["model_loaded"] is True


def test_neutral_news_does_not_move_the_forecast():
    with patch("backend.forecast_context.predict_returns", return_value=_base_prediction(0.03)):
        context = build_forecast_context("AAPL", empty_news_features(), current_price=100.0)
    assert context["news_context_forecast"]["adjustment_22d"] == 0.0
    assert (context["news_context_forecast"]["predicted_return_22d"]
            == context["base_forecast"]["used_return_22d"])
    assert context["potential_direction"] == "NEUTRAL"


def test_adjustment_is_always_bounded_even_for_extreme_news_features():
    extreme_features = {
        "sentiment_score": 1.0, "sentiment_confidence": 1.0,
        "impact_score": 1.0, "impact_confidence": 1.0,
        "news_count": 50, "positive_news_count": 50,
        "negative_news_count": 0, "neutral_news_count": 0,
        "weighted_sentiment": 1.0, "recency_weight": 1.0,
    }
    adjustment = compute_news_adjustment(extreme_features)
    assert abs(adjustment["adjustment_22d"]) <= MAX_NEWS_ADJUSTMENT_22D + 1e-9


def test_positive_news_shifts_forecast_up_not_down():
    positive_features = {
        "sentiment_score": 0.8, "sentiment_confidence": 0.9,
        "impact_score": 0.7, "impact_confidence": 0.8,
        "news_count": 3, "positive_news_count": 3,
        "negative_news_count": 0, "neutral_news_count": 0,
        "weighted_sentiment": 0.8, "recency_weight": 0.9,
    }
    with patch("backend.forecast_context.predict_returns", return_value=_base_prediction(0.03)):
        context = build_forecast_context("AAPL", positive_features, current_price=100.0)
    assert context["news_context_forecast"]["adjustment_22d"] > 0
    assert context["news_context_forecast"]["forecast_price"] > context["base_forecast"]["forecast_price"]
    assert context["potential_direction"] == "POTENTIAL_POSITIVE_IMPACT"


def test_falls_back_to_last_actual_return_when_model_not_loaded():
    unloaded = {"AAPL": {
        "predicted_return_22d": None,
        "last_actual_return_22d": 0.01,
        "prediction_date": "2026-08-28",
        "note": "Model not found for AAPL",
    }}
    with patch("backend.forecast_context.predict_returns", return_value=unloaded):
        context = build_forecast_context("AAPL", empty_news_features(), current_price=100.0)
    assert context["base_forecast"]["model_loaded"] is False
    assert context["base_forecast"]["used_return_22d"] == 0.01
