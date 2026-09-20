# -*- coding: utf-8 -*-
"""Risk Center calculation tests. Market data is mocked at `backend.risk`'s
own import boundary (same approach as `test_backtester.py`) — these test the
risk-metric wiring itself, not real Yahoo Finance data."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend import risk


def _fake_prices(tickers: list[str], n: int = 300, seed: int = 0) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=n, name="Date")
    rng = np.random.default_rng(seed)
    data = {}
    for i, ticker in enumerate(tickers):
        steps = rng.normal(loc=0.0003 + 0.0001 * i, scale=0.01, size=n)
        data[ticker] = 100.0 * np.cumprod(1 + steps)
    return pd.DataFrame(data, index=dates)


def test_empty_positions_returns_empty_status():
    result = risk.compute_portfolio_risk(tickers=[], dollar_values=[], cash=10_000.0)
    assert result["status"] == "empty"
    assert result["cash"] == 10_000.0


def test_zero_invested_value_is_treated_as_empty():
    result = risk.compute_portfolio_risk(tickers=["PSI"], dollar_values=[0.0], cash=5_000.0)
    assert result["status"] == "empty"


def test_mismatched_lengths_raise():
    with pytest.raises(risk.RiskAnalysisError):
        risk.compute_portfolio_risk(tickers=["PSI", "IYW"], dollar_values=[100.0], cash=0.0)


def test_single_ticker_has_full_risk_contribution_and_no_correlation_matrix():
    frame = _fake_prices(["PSI", "SPY"])
    with patch("backend.risk.fetch_etf_data", return_value=frame):
        result = risk.compute_portfolio_risk(
            tickers=["PSI"], dollar_values=[10_000.0], cash=1_000.0, benchmark_ticker="SPY",
        )
    assert result["status"] == "ok"
    assert result["correlation_matrix"] is None  # needs >= 2 tickers
    assert result["positions"][0]["risk_contribution_pct"] == pytest.approx(100.0, abs=0.5)
    assert result["cash_pct"] == pytest.approx(1000.0 / 11000.0 * 100, abs=0.01)


def test_multi_ticker_risk_contributions_sum_to_100(fake_positions_frame=None):
    tickers = ["PSI", "IYW", "RING"]
    frame = _fake_prices(tickers + ["SPY"])
    with patch("backend.risk.fetch_etf_data", return_value=frame):
        result = risk.compute_portfolio_risk(
            tickers=tickers, dollar_values=[5000.0, 3000.0, 2000.0], cash=0.0, benchmark_ticker="SPY",
        )
    assert result["status"] == "ok"
    total_contrib = sum(p["risk_contribution_pct"] for p in result["positions"])
    assert total_contrib == pytest.approx(100.0, abs=0.5)
    total_weight = sum(p["weight_pct"] for p in result["positions"])
    assert total_weight == pytest.approx(100.0, abs=0.01)
    assert result["correlation_matrix"] is not None
    assert set(result["correlation_matrix"]["tickers"]) == set(tickers)
    assert result["beta"] is not None
    assert result["var"] is not None
    assert result["var"]["var_pct"] < 0  # a loss, by convention negative


def test_concentration_and_diversification_are_consistent():
    tickers = ["PSI", "IYW"]
    frame = _fake_prices(tickers + ["SPY"])
    with patch("backend.risk.fetch_etf_data", return_value=frame):
        result = risk.compute_portfolio_risk(
            tickers=tickers, dollar_values=[10_000.0, 10_000.0], cash=0.0, benchmark_ticker="SPY",
        )
    assert result["concentration_hhi"] + result["diversification_score"] == pytest.approx(1.0)


def test_no_benchmark_skips_beta_but_still_returns_other_metrics():
    tickers = ["PSI", "IYW"]
    frame = _fake_prices(tickers)
    with patch("backend.risk.fetch_etf_data", return_value=frame):
        result = risk.compute_portfolio_risk(
            tickers=tickers, dollar_values=[6000.0, 4000.0], cash=0.0, benchmark_ticker=None,
        )
    assert result["status"] == "ok"
    assert result["beta"] is None
    assert result["volatility_pct"] is not None


def test_market_data_failure_raises_risk_analysis_error():
    with patch("backend.risk.fetch_etf_data", side_effect=ValueError("no data")):
        with pytest.raises(risk.RiskAnalysisError):
            risk.compute_portfolio_risk(tickers=["PSI"], dollar_values=[1000.0], cash=0.0)
