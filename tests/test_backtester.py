# -*- coding: utf-8 -*-
"""Backtesting engine tests. As in `test_model_evaluation.py`, price history
and model loading are mocked at `backend.backtester`'s own import boundary —
these tests exercise the walk-forward simulation, rebalancing, and stats
math itself, not real LSTM inference or Yahoo Finance.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend import backtester as bt


class _DummyScaler:
    def transform(self, arr):
        return arr


class _DummyModel:
    def predict(self, X, verbose=0):
        return (np.mean(X[:, :, 0], axis=1, keepdims=True) * 0.01).astype(float)


def _fake_frame(tickers: list[str], n: int = 700, seed: int = 0) -> pd.DataFrame:
    dates = pd.bdate_range("2015-01-01", periods=n, name="Date")
    rng = np.random.default_rng(seed)
    data = {}
    for i, ticker in enumerate(tickers):
        drift = 0.0002 + 0.0001 * i
        steps = rng.normal(loc=drift, scale=0.012, size=n)
        data[ticker] = 100.0 * np.cumprod(1 + steps)
    return pd.DataFrame(data, index=dates)


@pytest.fixture(autouse=True)
def _clear_backtest_cache():
    bt._backtest_cache.clear()
    yield
    bt._backtest_cache.clear()


@pytest.fixture()
def fake_model_dir(tmp_path):
    for ticker in bt.TRAINED_TICKERS:
        (tmp_path / f"{ticker}_model.keras").write_bytes(b"placeholder")
    return tmp_path


def _patched(frame, model_dir):
    scalers = {t: _DummyScaler() for t in bt.TRAINED_TICKERS}
    return (
        patch("backend.backtester.fetch_etf_data", return_value=frame),
        patch("backend.backtester.load_model_with_weights", return_value=_DummyModel()),
        patch("backend.backtester.load_scalers", return_value=scalers),
        patch("backend.backtester.resolve_model_dir", return_value=model_dir),
    )


def test_run_backtest_produces_a_full_equity_curve_and_stats(fake_model_dir):
    tickers = ["PSI", "IYW"]
    frame = _fake_frame(tickers)
    start = str(frame.index[280].date())
    end = str(frame.index[600].date())

    p1, p2, p3, p4 = _patched(frame, fake_model_dir)
    with p1, p2, p3, p4:
        result = bt.run_backtest(
            tickers=tickers, start_date=start, end_date=end,
            initial_capital=100_000.0, strategy="equal_weight",
            benchmark_ticker="PSI",
        )

    assert result["equity_curve"][0]["strategy_equity"] == pytest.approx(100_000.0, rel=1e-6)
    assert len(result["equity_curve"]) > 0
    assert result["strategy_metrics"]["trading_days"] == len(result["equity_curve"]) - 1
    assert result["num_trades"] == len(result["trades"])
    assert result["num_trades"] > 0
    assert result["benchmark_metrics"] is not None
    # equal_weight with 2 tickers should trade close to 50/50 at each rebalance
    for trade in result["trades"][:2]:
        assert trade["notional"] > 0


def test_invalid_date_range_is_rejected():
    with pytest.raises(bt.BacktestError):
        bt.run_backtest(
            tickers=["PSI"], start_date="2020-06-01", end_date="2020-01-01",
            initial_capital=10_000.0,
        )


def test_non_positive_capital_is_rejected():
    with pytest.raises(bt.BacktestError):
        bt.run_backtest(
            tickers=["PSI"], start_date="2020-01-01", end_date="2020-06-01",
            initial_capital=0.0,
        )


def test_timezone_aware_date_does_not_crash_the_comparison():
    """Regression test: a client-supplied ISO datetime with a timezone (e.g.
    a trailing "Z") used to raise `TypeError: Cannot compare tz-naive and
    tz-aware timestamps` deep inside pandas — an unhandled 500 at the API
    layer. Mixed tz-aware/naive inputs must normalize cleanly instead."""
    with pytest.raises(bt.BacktestError):
        bt.run_backtest(
            tickers=["PSI"], start_date="2024-06-01T00:00:00Z", end_date="2020-01-01",
            initial_capital=10_000.0,
        )


def test_no_lookahead_bias_early_decisions_unaffected_by_later_prices(fake_model_dir):
    """The concrete guarantee behind the module's no-lookahead claim: shock
    one ticker's prices strictly *after* a cutoff date and confirm every
    trade dated on or before that cutoff is byte-identical to a run where
    the shock never happens. If a rebalance decision ever depended on future
    rows, this would fail."""
    tickers = ["PSI", "IYW"]
    base = _fake_frame(tickers, n=700, seed=5)
    cutoff = base.index[450]

    shocked = base.copy()
    shocked.loc[shocked.index > cutoff, "IYW"] = shocked.loc[shocked.index > cutoff, "IYW"] * 1.8

    start = str(base.index[280].date())
    end = str(base.index[650].date())

    p1, p2, p3, p4 = _patched(base, fake_model_dir)
    with p1, p2, p3, p4:
        result_base = bt.run_backtest(
            tickers=tickers, start_date=start, end_date=end,
            initial_capital=100_000.0, strategy="max_sharpe", benchmark_ticker=None,
        )

    bt._backtest_cache.clear()
    p1, p2, p3, p4 = _patched(shocked, fake_model_dir)
    with p1, p2, p3, p4:
        result_shocked = bt.run_backtest(
            tickers=tickers, start_date=start, end_date=end,
            initial_capital=100_000.0, strategy="max_sharpe", benchmark_ticker=None,
        )

    cutoff_str = str(cutoff.date())
    trades_base_before = [t for t in result_base["trades"] if t["date"] <= cutoff_str]
    trades_shocked_before = [t for t in result_shocked["trades"] if t["date"] <= cutoff_str]
    assert trades_base_before == trades_shocked_before
    assert len(trades_base_before) > 0

    equity_base_before = [
        p for p in result_base["equity_curve"] if p["date"] <= cutoff_str
    ]
    equity_shocked_before = [
        p for p in result_shocked["equity_curve"] if p["date"] <= cutoff_str
    ]
    assert equity_base_before == equity_shocked_before

    # Sanity check the shock actually did something later on, so this test
    # isn't vacuously passing because nothing ever diverged.
    assert result_base["equity_curve"][-1] != result_shocked["equity_curve"][-1]


def test_predict_mu_all_dates_matches_one_call_per_date_per_ticker(fake_model_dir):
    """Regression test for the walk-forward performance fix: batching every
    rebalance date's sequence into one `model.predict()` call per ticker
    must produce numerically identical expected returns to calling predict
    once per (ticker, date) pair — only the call count should change."""
    tickers = ["PSI", "IYW"]
    frame = _fake_frame(tickers, n=700, seed=1)
    features_close = frame[tickers]

    from backend.forecaster import compute_features, prepare_dataset, create_sequences_for_prediction
    features = compute_features(features_close)
    dataset = prepare_dataset(features, tickers).sort_values(["Ticker", "Date"])
    all_dates = sorted(dataset["Date"].unique())
    rebalance_dates = all_dates[280:600:22]

    scalers = {t: _DummyScaler() for t in tickers}
    models = {t: _DummyModel() for t in tickers}

    batched = bt._predict_mu_all_dates(dataset, rebalance_dates, tickers, models, scalers)

    for date in rebalance_dates:
        ds_upto_t = dataset[dataset["Date"] <= date]
        one_at_a_time = []
        for ticker in tickers:
            X, _info = create_sequences_for_prediction(ds_upto_t, ticker, scalers[ticker], seq_length=10)
            pred = float(models[ticker].predict(X, verbose=0)[0][0])
            one_at_a_time.append(bt.annualize_22d_return(pred))
        one_at_a_time = np.clip(np.array(one_at_a_time), -0.5, 2.0)
        assert np.allclose(batched[date], one_at_a_time), f"mismatch at {date}"


def test_backtest_reports_real_progress_per_rebalance(fake_model_dir):
    """`on_progress` must fire once per real completed rebalance (never a
    fabricated/interpolated tick), end at (total, total), and report a
    plausible period date range."""
    tickers = ["PSI", "IYW"]
    frame = _fake_frame(tickers)
    start = str(frame.index[280].date())
    end = str(frame.index[600].date())

    events: list[tuple] = []

    def on_progress(phase, completed, total, period_start, period_end):
        events.append((phase, completed, total, period_start, period_end))

    p1, p2, p3, p4 = _patched(frame, fake_model_dir)
    with p1, p2, p3, p4:
        result = bt.run_backtest(
            tickers=tickers, start_date=start, end_date=end,
            initial_capital=100_000.0, strategy="equal_weight",
            benchmark_ticker=None, on_progress=on_progress,
        )

    simulating_events = [e for e in events if e[0] == "simulating"]
    assert len(simulating_events) == len(result["rebalance_dates"])
    # Monotonically increasing completed count, ending at the true total.
    completed_counts = [e[1] for e in simulating_events]
    assert completed_counts == sorted(completed_counts)
    assert completed_counts[-1] == simulating_events[-1][2]  # completed == total on the last tick
    for _phase, _completed, _total, period_start, period_end in simulating_events:
        assert period_start is not None and period_end is not None
        assert period_start <= period_end
    assert events[-1] == ("done", events[-1][1], events[-1][1], None, None)


def test_winning_losing_periods_are_disjoint_and_sum_to_rebalance_count(fake_model_dir):
    tickers = ["PSI", "IYW"]
    frame = _fake_frame(tickers)
    start = str(frame.index[280].date())
    end = str(frame.index[600].date())

    p1, p2, p3, p4 = _patched(frame, fake_model_dir)
    with p1, p2, p3, p4:
        result = bt.run_backtest(
            tickers=tickers, start_date=start, end_date=end,
            initial_capital=50_000.0, strategy="min_volatility", benchmark_ticker=None,
        )

    total_periods = result["winning_periods"] + result["losing_periods"] + result["flat_periods"]
    assert total_periods == len(result["rebalance_dates"])
