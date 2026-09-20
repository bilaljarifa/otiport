# -*- coding: utf-8 -*-
"""Model Comparison Lab — benchmarks the existing per-ticker LSTM against
transparent, non-ML forecasting baselines (naive/last-value, moving
average, linear regression) over the *exact same* chronological test
split, target definition and evaluation metrics the LSTM is already
evaluated with in `backend/model_evaluation.py`. This module deliberately
reuses that module's own split-boundary function (`_split_bounds`) and
metrics function (`_regression_metrics`) — this is not a second evaluation
methodology, it is the same one applied to three additional, much simpler
predictors, so every model's MAE/RMSE/directional-accuracy is computed
over the identical target dates and is directly comparable.

Target: `return_22d` (the same 22-trading-day return the LSTM predicts,
already a real column from `backend.forecaster.compute_features`).
Sequence length: `SEQ_LENGTH` (10), matching the LSTM's own lookback.

No look-ahead in any baseline:
- Naive: predicts return_22d[t] = return_22d[t-1] — pure persistence,
  using only the immediately preceding observation.
- Moving average: predicts return_22d[t] = mean(return_22d[t-10:t]) —
  the trailing 10 observations, never a future one.
- Linear regression: a plain `sklearn.linear_model.LinearRegression` fit
  ONCE on the chronological TRAIN split only (rows strictly before the
  test/validation boundary), then applied to each test row's own
  already-observed feature snapshot. Zero peeking at validation/test data
  during fitting.

Nothing here fabricates a metric: an untrained/missing LSTM model, a
ticker outside the trained universe, or too little history is reported as
unavailable (`status` != "ok" for that model), never silently defaulted.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from backend.forecaster import (
    DEFAULT_MODEL_DIR,
    FEATURE_COLS,
    compute_features,
    fetch_etf_data,
    prepare_dataset,
    resolve_model_dir,
)
from backend.model_evaluation import (
    TRAINED_TICKERS,
    _regression_metrics,
    _split_bounds,
    evaluate_ticker,
)
from backend.ttl_cache import TTLCache
from train_model import MIN_ROWS_REQUIRED, SEQ_LENGTH, START_DATE

_CACHE_TTL_SECONDS = 1800
_comparison_cache = TTLCache(ttl_seconds=_CACHE_TTL_SECONDS)

MODEL_LABELS = {
    "naive": "Naive / Last Value",
    "moving_average": "Moving Average",
    "linear_regression": "Linear Regression",
    "lstm": "LSTM (existing model)",
}


def _actuals(target: np.ndarray, seq_length: int) -> np.ndarray:
    return np.array([target[i + seq_length] for i in range(len(target) - seq_length)])


def _naive_predictions(target: np.ndarray, seq_length: int) -> np.ndarray:
    return np.array([target[i + seq_length - 1] for i in range(len(target) - seq_length)])


def _moving_average_predictions(target: np.ndarray, seq_length: int) -> np.ndarray:
    return np.array([float(np.mean(target[i:i + seq_length])) for i in range(len(target) - seq_length)])


def _linear_regression_predictions(
    train_df: pd.DataFrame, eval_df: pd.DataFrame, seq_length: int,
) -> np.ndarray:
    X_train = train_df[FEATURE_COLS].values
    y_train = train_df["return_22d"].values
    model = LinearRegression()
    model.fit(X_train, y_train)

    features = eval_df[FEATURE_COLS].values
    rows = np.array([features[i + seq_length - 1] for i in range(len(features) - seq_length)])
    return model.predict(rows)


def compare_models(ticker: str, model_path: Optional[str] = None, start_date: str = START_DATE) -> dict:
    """Naive / Moving Average / Linear Regression / LSTM, all evaluated
    against the identical test-split target dates for `ticker`."""
    ticker = ticker.strip().upper()
    if ticker not in TRAINED_TICKERS:
        return {
            "ticker": ticker,
            "status": "model_unavailable",
            "detail": f"{ticker} is not one of the {len(TRAINED_TICKERS)} trained ETFs.",
            "models": [],
            "test_period": None,
            "methodology": None,
        }

    cache_key = f"{ticker}|{start_date}|{model_path or ''}"
    cached = _comparison_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        close_prices = fetch_etf_data(TRAINED_TICKERS, start_date)
        features = compute_features(close_prices)
        dataset = prepare_dataset(features, TRAINED_TICKERS).sort_values(["Ticker", "Date"])
    except ValueError as exc:
        # Either too little raw price history for `compute_features`'s
        # rolling windows to produce even one row, or a transient data-
        # provider hiccup (`fetch_etf_data` itself never caches a failure —
        # see its own docstring). Deliberately NOT cached here either: unlike
        # the two branches below (a stable fact about this ticker's real
        # history), a fetch failure is often transient, and caching it would
        # keep reporting "insufficient data" for up to 30 minutes after the
        # data source has already recovered.
        return {
            "ticker": ticker, "status": "insufficient_data", "detail": str(exc),
            "models": [], "test_period": None, "methodology": None,
        }

    ticker_df = dataset[dataset["Ticker"] == ticker].sort_values("Date").reset_index(drop=True)

    if len(ticker_df) < MIN_ROWS_REQUIRED:
        result = {
            "ticker": ticker,
            "status": "insufficient_data",
            "detail": f"only {len(ticker_df)} usable rows (need at least {MIN_ROWS_REQUIRED})",
            "models": [],
            "test_period": None,
            "methodology": None,
        }
        _comparison_cache.set(cache_key, result)
        return result

    n = len(ticker_df)
    train_end, val_end = _split_bounds(n)
    train_df = ticker_df.iloc[:train_end].copy()
    test_df = ticker_df.iloc[max(0, val_end - SEQ_LENGTH):].copy()

    test_target = test_df["return_22d"].values
    test_dates = test_df["Date"].values
    actual = _actuals(test_target, SEQ_LENGTH)
    dates_out = [str(d)[:10] for d in test_dates[SEQ_LENGTH:]]

    if len(actual) == 0:
        result = {
            "ticker": ticker,
            "status": "insufficient_data",
            "detail": "not enough rows in the test split to form even one prediction window",
            "models": [],
            "test_period": None,
            "methodology": None,
        }
        _comparison_cache.set(cache_key, result)
        return result

    models: list[dict] = []

    naive_pred = _naive_predictions(test_target, SEQ_LENGTH)
    models.append({"model": "naive", "label": MODEL_LABELS["naive"], "status": "ok",
                    **_regression_metrics(actual, naive_pred)})

    ma_pred = _moving_average_predictions(test_target, SEQ_LENGTH)
    models.append({"model": "moving_average", "label": MODEL_LABELS["moving_average"], "status": "ok",
                    **_regression_metrics(actual, ma_pred)})

    try:
        lr_pred = _linear_regression_predictions(train_df, test_df, SEQ_LENGTH)
        models.append({"model": "linear_regression", "label": MODEL_LABELS["linear_regression"], "status": "ok",
                        **_regression_metrics(actual, lr_pred)})
    except Exception as exc:  # noqa: BLE001 - one baseline failing must not sink the comparison
        models.append({
            "model": "linear_regression", "label": MODEL_LABELS["linear_regression"],
            "status": "error", "detail": f"{type(exc).__name__}: {exc}",
            "mae": None, "rmse": None, "mape": None, "mape_observations": 0,
            "directional_accuracy": None, "observations": 0,
        })

    lstm_eval = evaluate_ticker(ticker, model_path, start_date)
    if lstm_eval["status"] == "ok" and lstm_eval.get("test_metrics"):
        models.append({"model": "lstm", "label": MODEL_LABELS["lstm"], "status": "ok",
                        **lstm_eval["test_metrics"]})
    else:
        models.append({
            "model": "lstm", "label": MODEL_LABELS["lstm"],
            "status": lstm_eval["status"], "detail": lstm_eval.get("detail"),
            "mae": None, "rmse": None, "mape": None, "mape_observations": 0,
            "directional_accuracy": None, "observations": 0,
        })

    result = {
        "ticker": ticker,
        "status": "ok",
        "models": models,
        "test_period": {
            "start": dates_out[0],
            "end": dates_out[-1],
            "observations": len(dates_out),
        },
        "methodology": {
            "target": "22-trading-day forward return (return_22d)",
            "forecast_horizon_days": 22,
            "sequence_length": SEQ_LENGTH,
            "train_fraction_pct": 70.0,
            "validation_fraction_pct": 15.0,
            "test_fraction_pct": 15.0,
        },
    }
    _comparison_cache.set(cache_key, result)
    return result
