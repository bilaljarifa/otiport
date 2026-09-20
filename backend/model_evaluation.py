# -*- coding: utf-8 -*-
"""Out-of-sample evaluation of the existing per-ticker LSTM models.

This module never trains anything. It reuses `backend/forecaster.py`'s own
data-fetching, feature-computation and model-loading code (`fetch_etf_data`,
`compute_features`, `prepare_dataset`, `load_scalers`,
`load_model_with_weights`, `FEATURE_COLS`) and `train_model.py`'s own
chronological train/val/test split and sequence-building
(`create_ticker_sequences`, `MIN_ROWS_REQUIRED`) so evaluation runs through
exactly the pipeline the models were trained and are served with — no
parallel/duplicated feature or scaling logic.

Because `fetch_etf_data` always fetches history up to *today*, the
train/val/test split computed here is recomputed against however much
history is currently available, not frozen at the moment the model was
originally trained. As new trading days accumulate, the split boundaries
(and therefore the test window) drift forward slightly — this is standard
for time-series model monitoring and is reported explicitly via the actual
computed period date ranges below, never hidden or hardcoded.

Nothing here fabricates a metric: a split that doesn't have enough rows, a
missing model file, or a missing scaler is reported as unavailable
(`status` != "ok"), never silently defaulted to a number.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backend.forecaster import (
    DEFAULT_MODEL_DIR,
    FEATURE_COLS,
    NUMERIC_FEATURES_INDICES,
    REGION_MAPPING,
    compute_features,
    create_sequences_for_prediction,
    fetch_etf_data,
    load_model_with_weights,
    load_scalers,
    prepare_dataset,
    resolve_model_dir,
)
from backend.ttl_cache import TTLCache
from train_model import MIN_ROWS_REQUIRED, SEQ_LENGTH, START_DATE, create_ticker_sequences

# All 12 ETFs the shipped models were actually trained for (same set
# `train_model.py` trains by default) — the universe this module evaluates
# unless the caller narrows it.
TRAINED_TICKERS = list(REGION_MAPPING.keys())

# Same 0.70 / 0.85 chronological cut points `train_model.py::train_ticker_model`
# uses to build train/val/test — kept in sync deliberately: this module
# evaluates the model against the same test window it was actually tested on
# at training time (modulo the forward drift described above).
_TRAIN_FRACTION = 0.70
_VAL_FRACTION = 0.85

# A full evaluation loads 12 Keras models from disk and walks the whole
# 2010-present feature history — not something to redo on every dashboard
# render. 30 minutes is short enough that a freshly retrained/redeployed
# model set is picked up the same day, long enough to absorb repeat views.
_CACHE_TTL_SECONDS = 1800
_evaluation_cache = TTLCache(ttl_seconds=_CACHE_TTL_SECONDS)

# MAPE divides by the actual value — meaningless (and numerically explosive)
# for near-zero 22-day returns. Only rows where the actual move was at least
# this large in magnitude are included; below the minimum-row count, MAPE is
# reported as unavailable for that split rather than computed on too little
# or too unstable a sample.
_MAPE_MIN_ABS_ACTUAL = 0.005
_MAPE_MIN_ROWS = 5


def _split_bounds(n: int) -> tuple[int, int]:
    """Row indices [0:train_end), [train_end:val_end), [val_end:n) — the
    same split `train_model.py` computes, extracted here so both modules
    call one formula instead of two copies of `int(n * 0.70)`."""
    return int(n * _TRAIN_FRACTION), int(n * _VAL_FRACTION)


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """MAE / RMSE (always defined) and MAPE (only when mathematically
    stable — see `_MAPE_MIN_ABS_ACTUAL`), plus directional accuracy (sign
    agreement between predicted and actual 22-day return)."""
    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    mape: Optional[float] = None
    mape_rows = 0
    mask = np.abs(y_true) >= _MAPE_MIN_ABS_ACTUAL
    if mask.sum() >= _MAPE_MIN_ROWS:
        mape = float(np.mean(np.abs(errors[mask] / y_true[mask])) * 100.0)
        mape_rows = int(mask.sum())

    nonzero = y_true != 0
    directional_accuracy: Optional[float] = None
    if nonzero.sum() > 0:
        directional_accuracy = float(
            np.mean(np.sign(y_pred[nonzero]) == np.sign(y_true[nonzero])) * 100.0
        )

    return {
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "mape_observations": mape_rows,
        "directional_accuracy": directional_accuracy,
        "observations": int(len(y_true)),
    }


def _predict_split(model, scaled_df: pd.DataFrame) -> dict:
    """Run the model over one split and pair predictions with actuals/dates,
    using the exact same windowing `train_model.py` used at training time."""
    X, y = create_ticker_sequences(scaled_df, SEQ_LENGTH)
    if len(X) == 0:
        return {"dates": [], "actual": [], "predicted": []}
    y_pred = model.predict(X, verbose=0).reshape(-1)
    dates = scaled_df["Date"].values[SEQ_LENGTH:]
    return {
        "dates": [str(d)[:10] for d in dates],
        "actual": y.tolist(),
        "predicted": y_pred.tolist(),
    }


def _evaluate_one(ticker: str, dataset: pd.DataFrame, model_dir, scalers: dict) -> dict:
    ticker_df = dataset[dataset["Ticker"] == ticker].sort_values("Date").reset_index(drop=True)

    if len(ticker_df) < MIN_ROWS_REQUIRED:
        return {
            "ticker": ticker,
            "status": "insufficient_data",
            "detail": f"only {len(ticker_df)} usable rows (need at least {MIN_ROWS_REQUIRED})",
        }

    model_file = model_dir / f"{ticker}_model.keras"
    scaler = scalers.get(ticker)
    if not model_file.exists() or scaler is None:
        return {
            "ticker": ticker,
            "status": "model_unavailable",
            "detail": f"no trained model/scaler found for {ticker} in {model_dir}",
        }

    n = len(ticker_df)
    train_end, val_end = _split_bounds(n)
    train_df = ticker_df.iloc[:train_end].copy()
    val_df = ticker_df.iloc[max(0, train_end - SEQ_LENGTH):val_end].copy()
    test_df = ticker_df.iloc[max(0, val_end - SEQ_LENGTH):].copy()

    numeric_cols = [FEATURE_COLS[i] for i in NUMERIC_FEATURES_INDICES]

    def _scaled(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out[numeric_cols] = scaler.transform(out[numeric_cols].values)
        return out

    def _period(df: pd.DataFrame) -> dict:
        if df.empty:
            return {"start": None, "end": None, "rows": 0}
        return {
            "start": str(df["Date"].iloc[0])[:10],
            "end": str(df["Date"].iloc[-1])[:10],
            "rows": int(len(df)),
        }

    try:
        model = load_model_with_weights(str(model_file))
    except Exception as exc:  # noqa: BLE001 - isolate one bad model file
        return {
            "ticker": ticker,
            "status": "model_load_error",
            "detail": f"{type(exc).__name__}: {exc}",
        }

    val_pred = _predict_split(model, _scaled(val_df))
    test_pred = _predict_split(model, _scaled(test_df))

    # Reported periods describe each split's *prediction targets*
    # (ticker_df[:train_end] / [train_end:val_end] / [val_end:]) — contiguous
    # and non-overlapping. `train_df`/`val_df`/`test_df` above additionally
    # carry `SEQ_LENGTH` rows of look-back *input* history borrowed from the
    # previous split (needed to build that split's first input sequence,
    # exactly as `train_model.py` does at training time) — real and
    # intentional, but reporting it as the "period" would make an
    # information-window overlap look like a data leak it isn't. No target
    # value is ever predicted using a later split's own history.
    result = {
        "ticker": ticker,
        "status": "ok",
        "train_period": _period(ticker_df.iloc[SEQ_LENGTH:train_end]),
        "validation_period": _period(ticker_df.iloc[train_end:val_end]),
        "test_period": _period(ticker_df.iloc[val_end:]),
    }

    for split_name, split_pred in (("validation", val_pred), ("test", test_pred)):
        if len(split_pred["actual"]) == 0:
            result[f"{split_name}_metrics"] = None
        else:
            result[f"{split_name}_metrics"] = _regression_metrics(
                np.array(split_pred["actual"]), np.array(split_pred["predicted"]),
            )
    result["validation_series"] = val_pred
    result["test_series"] = test_pred

    return result


def evaluate_universe(
    tickers: Optional[list[str]] = None,
    model_path: Optional[str] = None,
    start_date: str = START_DATE,
) -> dict[str, dict]:
    """Evaluate every ticker's shipped model against a freshly-recomputed
    chronological test split. `tickers` defaults to all 12 trained ETFs.

    The full universe's features are computed once, jointly — `corr_3m` (and
    every other feature) is defined over the whole ETF universe at training
    time (`train_model.py` calls `compute_features` once for all tickers
    together), so evaluating a ticker in isolation would silently change
    what its own features mean. Per-ticker filtering happens only after
    `prepare_dataset`, mirroring `train_model.py` exactly.
    """
    tickers = tickers or TRAINED_TICKERS
    cache_key = f"{','.join(sorted(tickers))}|{start_date}|{model_path or ''}"
    cached = _evaluation_cache.get(cache_key)
    if cached is not None:
        return cached

    model_dir = resolve_model_dir(model_path or DEFAULT_MODEL_DIR)
    scalers = load_scalers(str(model_dir))

    close_prices = fetch_etf_data(tickers, start_date)
    features = compute_features(close_prices)
    dataset = prepare_dataset(features, tickers)
    dataset = dataset.sort_values(["Ticker", "Date"])

    results = {t: _evaluate_one(t, dataset, model_dir, scalers) for t in tickers}
    _evaluation_cache.set(cache_key, results)
    return results


def evaluate_ticker(
    ticker: str,
    model_path: Optional[str] = None,
    start_date: str = START_DATE,
) -> dict:
    """Single-ticker convenience wrapper. Always evaluates through the full
    12-ticker universe (see `evaluate_universe`'s docstring on why features
    can't be computed for one ticker in isolation) — the other 11 tickers'
    results are a byproduct kept in the same cache entry, not wasted work: a
    later call for a different ticker hits the same cache.

    A ticker outside the trained universe has no model to evaluate by
    construction, so it's reported as unavailable without running the
    pipeline at all.
    """
    if ticker not in TRAINED_TICKERS:
        return {
            "ticker": ticker,
            "status": "model_unavailable",
            "detail": f"{ticker} is not one of the {len(TRAINED_TICKERS)} trained ETFs.",
        }
    return evaluate_universe(TRAINED_TICKERS, model_path, start_date)[ticker]
