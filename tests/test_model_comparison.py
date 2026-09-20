# -*- coding: utf-8 -*-
"""Model Comparison Lab tests. Mirrors `test_model_evaluation.py`'s own
mocking approach (mock at the `fetch_etf_data`/model-loading boundary, no
real Yahoo Finance or TensorFlow) since `backend.model_comparison` reuses
that exact pipeline plus `backend.model_evaluation.evaluate_ticker` for the
LSTM's own numbers.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend import model_comparison as mc
from backend import model_evaluation as me


class _DummyScaler:
    def transform(self, arr):
        return arr


class _DummyModel:
    def predict(self, X, verbose=0):
        return (np.mean(X[:, :, 0], axis=1, keepdims=True) * 0.01).astype(float)


def _fake_long_frame(tickers: list[str], n: int = 900, seed: int = 0) -> pd.DataFrame:
    dates = pd.bdate_range("2012-01-01", periods=n, name="Date")
    rng = np.random.default_rng(seed)
    data = {}
    for i, ticker in enumerate(tickers):
        drift = 0.0002 + 0.0001 * i
        steps = rng.normal(loc=drift, scale=0.012, size=n)
        data[ticker] = 100.0 * np.cumprod(1 + steps)
    return pd.DataFrame(data, index=dates)


@pytest.fixture(autouse=True)
def _clear_caches():
    mc._comparison_cache.clear()
    me._evaluation_cache.clear()
    yield
    mc._comparison_cache.clear()
    me._evaluation_cache.clear()


@pytest.fixture()
def fake_model_dir(tmp_path):
    for ticker in me.TRAINED_TICKERS:
        (tmp_path / f"{ticker}_model.keras").write_bytes(b"placeholder")
    return tmp_path


def _patched(frame, scalers, model_dir):
    return (
        patch("backend.model_comparison.fetch_etf_data", return_value=frame),
        patch("backend.model_evaluation.fetch_etf_data", return_value=frame),
        patch("backend.model_evaluation.load_model_with_weights", return_value=_DummyModel()),
        patch("backend.model_evaluation.load_scalers", return_value=scalers),
        patch("backend.model_evaluation.resolve_model_dir", return_value=model_dir),
    )


def test_compare_models_returns_all_four_models_ok(fake_model_dir):
    tickers = me.TRAINED_TICKERS
    frame = _fake_long_frame(tickers)
    scalers = {t: _DummyScaler() for t in tickers}

    patches = _patched(frame, scalers, fake_model_dir)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = mc.compare_models("PSI")

    assert result["status"] == "ok"
    names = [m["model"] for m in result["models"]]
    assert names == ["naive", "moving_average", "linear_regression", "lstm"]
    for m in result["models"]:
        assert m["status"] == "ok", m


def test_real_metric_structure_is_well_formed(fake_model_dir):
    tickers = me.TRAINED_TICKERS
    frame = _fake_long_frame(tickers)
    scalers = {t: _DummyScaler() for t in tickers}

    patches = _patched(frame, scalers, fake_model_dir)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = mc.compare_models("PSI")

    for m in result["models"]:
        assert m["mae"] >= 0
        assert m["rmse"] >= 0
        assert m["observations"] > 0
        assert m["directional_accuracy"] is None or 0.0 <= m["directional_accuracy"] <= 100.0
    assert result["test_period"]["observations"] == result["models"][0]["observations"]
    assert result["methodology"]["target"] == "22-trading-day forward return (return_22d)"
    assert result["methodology"]["sequence_length"] == mc.SEQ_LENGTH


def test_lstm_integration_matches_evaluate_ticker_exactly(fake_model_dir):
    """The comparison's `lstm` row must be the *same* numbers
    `evaluate_ticker` already reports — proof this reuses that pipeline
    rather than running a second, possibly-diverging evaluation."""
    tickers = me.TRAINED_TICKERS
    frame = _fake_long_frame(tickers)
    scalers = {t: _DummyScaler() for t in tickers}

    patches = _patched(frame, scalers, fake_model_dir)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = mc.compare_models("IYW")
        me._evaluation_cache.clear()
        direct_eval = me.evaluate_ticker("IYW")

    lstm_row = next(m for m in result["models"] if m["model"] == "lstm")
    assert lstm_row["mae"] == direct_eval["test_metrics"]["mae"]
    assert lstm_row["rmse"] == direct_eval["test_metrics"]["rmse"]
    assert lstm_row["observations"] == direct_eval["test_metrics"]["observations"]
    assert lstm_row["observations"] == result["test_period"]["observations"]


def test_deterministic_and_reproducible(fake_model_dir):
    tickers = me.TRAINED_TICKERS
    frame = _fake_long_frame(tickers, seed=7)
    scalers = {t: _DummyScaler() for t in tickers}

    patches = _patched(frame, scalers, fake_model_dir)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        first = mc.compare_models("RING")
        mc._comparison_cache.clear()
        me._evaluation_cache.clear()
        second = mc.compare_models("RING")

    assert first["models"] == second["models"]


def test_chronological_split_test_dates_are_the_latest_15_percent(fake_model_dir):
    tickers = ["PSI", "IYW"]
    frame = _fake_long_frame(tickers, n=900)
    scalers = {t: _DummyScaler() for t in tickers}

    patches = _patched(frame, scalers, fake_model_dir)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = mc.compare_models("PSI")

    all_dates = sorted(frame.index.strftime("%Y-%m-%d").tolist())
    cutoff = all_dates[int(len(all_dates) * 0.80)]  # generous margin below the true 0.85 split
    assert result["test_period"]["start"] >= cutoff
    assert result["test_period"]["start"] < result["test_period"]["end"]


def test_transient_fetch_failure_is_never_cached(fake_model_dir):
    """Regression test: a transient data-provider hiccup must not be
    memorized for the cache's full TTL — once the underlying fetch
    recovers, the very next call must succeed, not keep replaying the
    old failure."""
    tickers = me.TRAINED_TICKERS
    frame = _fake_long_frame(tickers)
    scalers = {t: _DummyScaler() for t in tickers}

    with patch("backend.model_comparison.fetch_etf_data", side_effect=ValueError("transient hiccup")):
        first = mc.compare_models("PSI")
    assert first["status"] == "insufficient_data"

    patches = _patched(frame, scalers, fake_model_dir)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        second = mc.compare_models("PSI")
    assert second["status"] == "ok", "a recovered data source must not be shadowed by a cached failure"


def test_invalid_ticker_is_reported_as_model_unavailable():
    result = mc.compare_models("NOTATRAINEDTICKER")
    assert result["status"] == "model_unavailable"
    assert result["models"] == []


def test_insufficient_data_never_fabricates_a_metric(fake_model_dir):
    tickers = ["PSI"]
    frame = _fake_long_frame(tickers, n=20)  # far below MIN_ROWS_REQUIRED
    scalers = {t: _DummyScaler() for t in tickers}

    with patch("backend.model_comparison.fetch_etf_data", return_value=frame), \
         patch("backend.model_comparison.TRAINED_TICKERS", ["PSI"]):
        result = mc.compare_models("PSI")

    assert result["status"] == "insufficient_data"
    assert result["models"] == []


def test_naive_prediction_is_the_immediately_preceding_value():
    target = np.array([0.01, 0.02, -0.01, 0.03, 0.00, 0.04, -0.02, 0.01, 0.02, 0.03, -0.01, 0.02])
    seq_length = 5
    preds = mc._naive_predictions(target, seq_length)
    expected = np.array([target[i + seq_length - 1] for i in range(len(target) - seq_length)])
    assert np.array_equal(preds, expected)
    # Sanity: first prediction is exactly target[seq_length - 1].
    assert preds[0] == target[seq_length - 1]


def test_moving_average_prediction_is_the_trailing_mean():
    target = np.array([0.01, 0.02, -0.01, 0.03, 0.00, 0.04, -0.02, 0.01])
    seq_length = 4
    preds = mc._moving_average_predictions(target, seq_length)
    assert preds[0] == pytest.approx(np.mean(target[0:4]))
    assert preds[-1] == pytest.approx(np.mean(target[len(target) - seq_length - 1:len(target) - 1]))


def test_naive_and_moving_average_never_look_at_future_target_values():
    """Shocking the target array strictly *after* index `t` must never
    change the naive/MA prediction *for* index `t` — both only read
    `target[:t]`."""
    rng = np.random.default_rng(9)
    target = rng.normal(0, 0.02, size=60)
    seq_length = 10
    cutoff = 40  # predictions for i < cutoff must be unaffected by anything at/after it

    shocked = target.copy()
    shocked[cutoff:] = shocked[cutoff:] * 5 + 1.0  # large, obvious shock

    naive_base = mc._naive_predictions(target, seq_length)
    naive_shocked = mc._naive_predictions(shocked, seq_length)
    ma_base = mc._moving_average_predictions(target, seq_length)
    ma_shocked = mc._moving_average_predictions(shocked, seq_length)

    # Prediction i forecasts target[i + seq_length]; it must be unaffected
    # by the shock as long as its own inputs (target[i : i + seq_length])
    # are entirely before the shocked region.
    unaffected = [i for i in range(len(naive_base)) if i + seq_length <= cutoff]
    assert len(unaffected) > 0
    for i in unaffected:
        assert naive_base[i] == naive_shocked[i]
        assert ma_base[i] == pytest.approx(ma_shocked[i])

    # Sanity: the shock did change *something* later on, so this isn't
    # vacuously passing because nothing ever diverged.
    affected = [i for i in range(len(naive_base)) if i + seq_length > cutoff]
    assert any(naive_base[i] != naive_shocked[i] for i in affected)


def test_linear_regression_prediction_for_a_row_never_depends_on_later_rows():
    """Shocking an eval row's own feature snapshot must only change *that*
    row's prediction — earlier rows' predictions, and the model itself
    (fit once on `train_df`, entirely separate from `eval_df`), must be
    byte-identical."""
    rng = np.random.default_rng(3)
    n_train, n_eval = 200, 30
    seq_length = 10

    def _synthetic_df(n, seed):
        r = np.random.default_rng(seed)
        data = {col: r.normal(0, 1, size=n) for col in mc.FEATURE_COLS}
        data["return_22d"] = r.normal(0, 0.02, size=n)
        return pd.DataFrame(data)

    train_df = _synthetic_df(n_train, 1)
    eval_df = _synthetic_df(n_eval, 2)

    shocked_eval_df = eval_df.copy()
    shock_row = 20  # strictly after the rows checked below
    shocked_eval_df.loc[shock_row, mc.FEATURE_COLS] = shocked_eval_df.loc[shock_row, mc.FEATURE_COLS] * 100 + 50

    base_preds = mc._linear_regression_predictions(train_df, eval_df, seq_length)
    shocked_preds = mc._linear_regression_predictions(train_df, shocked_eval_df, seq_length)

    # Prediction i reads eval_df row (i + seq_length - 1); only the
    # prediction whose row *is* shock_row should move.
    shocked_pred_index = shock_row - (seq_length - 1)
    for i in range(len(base_preds)):
        if i == shocked_pred_index:
            continue
        assert base_preds[i] == pytest.approx(shocked_preds[i]), f"prediction {i} must not depend on row {shock_row}"
    assert base_preds[shocked_pred_index] != pytest.approx(shocked_preds[shocked_pred_index])
