# -*- coding: utf-8 -*-
"""Tests for `backend/market_regime.py` — transparent trend/volatility
classification from real (mocked-in-test) price history. No ML, no
prediction: fixed thresholds applied to already-observed returns."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend import market_regime as mr


def _flat_then_rally_frame(n=300):
    """~250 flat/noisy days, then a strong rally in the trailing 63 —
    should classify as POSITIVE_TREND at the end."""
    dates = pd.bdate_range("2024-01-01", periods=n, name="Date")
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 0.003, n)
    prices = np.concatenate([
        100 * np.cumprod(1 + noise[: n - 63]),
    ])
    last_base = prices[-1]
    rally = last_base * np.cumprod(1 + np.full(63, 0.006))
    prices = np.concatenate([prices, rally])[:n]
    return pd.DataFrame({"SPY": prices}, index=dates)


def test_classify_market_regime_detects_positive_trend():
    frame = _flat_then_rally_frame()
    with patch("backend.market_regime.fetch_etf_data", return_value=frame):
        result = mr.classify_market_regime("SPY")

    assert result["ticker"] == "SPY"
    assert result["current_regime"]["trend"] == "POSITIVE_TREND"
    assert result["current_regime"]["cumulative_return_pct"] > 0
    assert result["observations"] == len(frame)
    assert len(result["timeline"]) > 0
    assert result["methodology"]["trend_window_days"] == mr.TREND_WINDOW_DAYS


def test_classify_market_regime_detects_high_volatility():
    n = 300
    dates = pd.bdate_range("2024-01-01", periods=n, name="Date")
    rng = np.random.default_rng(1)
    calm = rng.normal(0, 0.002, n - 21)
    turbulent = rng.normal(0, 0.05, 21)  # last month much more volatile
    steps = np.concatenate([calm, turbulent])
    prices = 100 * np.cumprod(1 + steps)
    frame = pd.DataFrame({"SPY": prices}, index=dates)

    with patch("backend.market_regime.fetch_etf_data", return_value=frame):
        result = mr.classify_market_regime("SPY")

    assert result["current_regime"]["volatility_regime"] == "HIGH_VOLATILITY"


def test_classify_market_regime_raises_on_insufficient_history():
    dates = pd.bdate_range("2024-01-01", periods=10, name="Date")
    frame = pd.DataFrame({"SPY": np.full(10, 100.0)}, index=dates)
    with patch("backend.market_regime.fetch_etf_data", return_value=frame):
        with pytest.raises(mr.MarketRegimeError):
            mr.classify_market_regime("SPY")


def test_classify_market_regime_never_fabricates_on_fetch_failure():
    with patch("backend.market_regime.fetch_etf_data", side_effect=ValueError("no data")):
        with pytest.raises(mr.MarketRegimeError):
            mr.classify_market_regime("SPY")
