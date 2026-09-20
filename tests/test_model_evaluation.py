# -*- coding: utf-8 -*-
"""Model evaluation pipeline tests. Real trained `.keras`/`scalers.pkl`
artifacts are gitignored and not guaranteed to exist in every environment
this test suite runs in, so model loading and price history are mocked at
`backend.model_evaluation`'s own import boundary (the same "mock at the
nearest external dependency" approach `test_forecast_context.py` already
uses for the forecaster) — these tests exercise the split/scale/metric
pipeline itself, not real LSTM inference or Yahoo Finance.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend import model_evaluation as me


class _DummyScaler:
    """Identity scaler — the pipeline under test doesn't need a real fit,
    only that `.transform` is called with the right numeric columns."""

    def transform(self, arr):
        return arr


class _DummyModel:
    """Deterministic, cheap stand-in for a loaded Keras model: same shape
    contract (`predict(X, verbose=0) -> (N, 1)`), no TensorFlow involved."""

    def predict(self, X, verbose=0):
        return (np.mean(X[:, :, 0], axis=1, keepdims=True) * 0.01).astype(float)


def _fake_long_frame(tickers: list[str], n: int = 900, seed: int = 0) -> pd.DataFrame:
    """A `fetch_etf_data`-shaped frame with genuine variation/correlation
    structure — long enough (>= 252 + 10 warmup) for `compute_features` to
    produce many non-NaN rows per ticker."""
    dates = pd.bdate_range("2012-01-01", periods=n, name="Date")
    rng = np.random.default_rng(seed)
    data = {}
    for i, ticker in enumerate(tickers):
        drift = 0.0002 + 0.0001 * i
        steps = rng.normal(loc=drift, scale=0.012, size=n)
        data[ticker] = 100.0 * np.cumprod(1 + steps)
    return pd.DataFrame(data, index=dates)


@pytest.fixture(autouse=True)
def _clear_eval_cache():
    me._evaluation_cache.clear()
    yield
    me._evaluation_cache.clear()


@pytest.fixture()
def fake_model_dir(tmp_path):
    """Real (empty) files so `Path.exists()` checks pass without needing a
    real `.keras` archive — `load_model_with_weights` itself is mocked, so
    the file's content is never read."""
    for ticker in me.TRAINED_TICKERS:
        (tmp_path / f"{ticker}_model.keras").write_bytes(b"placeholder")
    return tmp_path


def _patched(frame, scalers, model_dir):
    return (
        patch("backend.model_evaluation.fetch_etf_data", return_value=frame),
        patch("backend.model_evaluation.load_model_with_weights", return_value=_DummyModel()),
        patch("backend.model_evaluation.load_scalers", return_value=scalers),
        patch("backend.model_evaluation.resolve_model_dir", return_value=model_dir),
    )


def test_evaluate_universe_ok_with_chronological_non_overlapping_periods(fake_model_dir):
    tickers = me.TRAINED_TICKERS
    frame = _fake_long_frame(tickers)
    scalers = {t: _DummyScaler() for t in tickers}

    p1, p2, p3, p4 = _patched(frame, scalers, fake_model_dir)
    with p1, p2, p3, p4:
        results = me.evaluate_universe(tickers)

    assert set(results.keys()) == set(tickers)
    for ticker, result in results.items():
        assert result["status"] == "ok", result
        train_end = result["train_period"]["end"]
        val_start = result["validation_period"]["start"]
        val_end = result["validation_period"]["end"]
        test_start = result["test_period"]["start"]

        # Chronological, non-overlapping: each split's period is built from
        # its own prediction-target dates only (see model_evaluation.py's
        # comment on why this differs from the sequence input window).
        assert train_end < val_start
        assert val_end < test_start

        assert result["test_metrics"]["mae"] >= 0
        assert result["test_metrics"]["rmse"] >= 0
        assert result["test_metrics"]["observations"] == result["test_period"]["rows"]


def test_evaluate_universe_is_reproducible(fake_model_dir):
    """Same inputs -> byte-identical metrics on a second, independent run —
    no hidden randomness in the evaluation pipeline itself."""
    tickers = ["PSI", "IYW"]
    frame = _fake_long_frame(tickers, seed=3)
    scalers = {t: _DummyScaler() for t in tickers}

    p1, p2, p3, p4 = _patched(frame, scalers, fake_model_dir)
    with p1, p2, p3, p4:
        first = me.evaluate_universe(tickers)
        me._evaluation_cache.clear()  # force a genuine recomputation, not a cache hit
        second = me.evaluate_universe(tickers)

    assert first["PSI"]["test_metrics"] == second["PSI"]["test_metrics"]
    assert first["PSI"]["test_series"] == second["PSI"]["test_series"]


def test_missing_model_file_reported_not_fabricated(fake_model_dir):
    (fake_model_dir / "PSI_model.keras").unlink()
    tickers = ["PSI", "IYW"]
    frame = _fake_long_frame(tickers)
    scalers = {t: _DummyScaler() for t in tickers}

    p1, p2, p3, p4 = _patched(frame, scalers, fake_model_dir)
    with p1, p2, p3, p4:
        results = me.evaluate_universe(tickers)

    assert results["PSI"]["status"] == "model_unavailable"
    assert "test_metrics" not in results["PSI"] or results["PSI"].get("test_metrics") is None
    assert results["IYW"]["status"] == "ok"


def test_ticker_outside_trained_universe_is_reported_unavailable():
    result = me.evaluate_ticker("NOTATRAINEDTICKER")
    assert result["status"] == "model_unavailable"


def test_mape_omitted_when_actual_returns_are_too_small_to_divide_by():
    y_true = np.full(20, 1e-5)
    y_pred = np.full(20, 2e-5)
    metrics = me._regression_metrics(y_true, y_pred)
    assert metrics["mape"] is None
    assert metrics["mae"] > 0


def test_mape_present_when_actual_returns_are_large_enough():
    rng = np.random.default_rng(1)
    y_true = rng.uniform(0.02, 0.05, size=20)
    y_pred = y_true * 1.1
    metrics = me._regression_metrics(y_true, y_pred)
    assert metrics["mape"] is not None
    assert metrics["mape"] == pytest.approx(10.0, rel=1e-6)


def test_directional_accuracy_is_100_percent_when_signs_always_match():
    y_true = np.array([0.01, -0.02, 0.03, -0.04])
    y_pred = np.array([0.02, -0.01, 0.05, -0.02])
    metrics = me._regression_metrics(y_true, y_pred)
    assert metrics["directional_accuracy"] == 100.0
