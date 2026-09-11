# -*- coding: utf-8 -*-
"""Performance fixes: no redundant Yahoo Finance calls within a single
request, short-TTL caching for repeat requests, and the consolidated
portfolio summary endpoint. Yahoo Finance is always mocked — no real network
access and no dependency on market hours/availability.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend import forecaster, pricing
from backend.market_cache import chart_data_cache, last_price_cache, price_history_cache


@pytest.fixture(autouse=True)
def _clear_market_caches():
    price_history_cache.clear()
    last_price_cache.clear()
    chart_data_cache.clear()
    yield
    price_history_cache.clear()
    last_price_cache.clear()
    chart_data_cache.clear()


def _fake_history(tickers: list[str], sessions: int = 300) -> pd.DataFrame:
    """A minimal but shaped-correctly multi-ticker daily-close frame — enough
    rows for `compute_features`'s rolling windows (252 sessions) to produce
    at least one complete row."""
    dates = pd.date_range("2019-01-01", periods=sessions, freq="B")
    data = {t: np.linspace(100.0, 130.0, sessions) + i for i, t in enumerate(tickers)}
    frame = pd.DataFrame(data, index=dates)
    frame.columns = pd.MultiIndex.from_product([["Close"], tickers])
    frame.index.name = "Date"
    return frame


# ---------------------------------------------------------------------------
#  Forecasting: no duplicate downloads within one request
# ---------------------------------------------------------------------------

@patch("backend.forecaster.yf.download")
def test_get_portfolio_data_fetches_history_only_once(mock_download):
    tickers = ["PSI", "IYW"]
    mock_download.return_value = _fake_history(tickers)

    forecaster.get_portfolio_data(tickers, model_path="does-not-exist-so-falls-back")

    # Before the fix: `get_expected_returns` -> `predict_returns` and
    # `compute_covariance_matrix` each called `fetch_etf_data` independently
    # — two identical downloads for the same (tickers, start_date). Now the
    # data is fetched once and shared between both.
    assert mock_download.call_count == 1


@patch("backend.forecaster.yf.download")
def test_fetch_etf_data_is_cached_across_calls_with_the_same_args(mock_download):
    tickers = ["PSI", "IYW"]
    mock_download.return_value = _fake_history(tickers)

    forecaster.fetch_etf_data(tickers, "2010-01-01")
    forecaster.fetch_etf_data(tickers, "2010-01-01")
    forecaster.fetch_etf_data(list(reversed(tickers)), "2010-01-01")  # same set, different order

    assert mock_download.call_count == 1


@patch("backend.forecaster.yf.download")
def test_fetch_etf_data_cache_hit_returns_an_independent_copy(mock_download):
    """A caller mutating its own frame must never corrupt what the next
    caller gets back from the cache."""
    mock_download.return_value = _fake_history(["PSI"])

    first = forecaster.fetch_etf_data(["PSI"], "2010-01-01")
    first.iloc[0, 0] = -999.0

    second = forecaster.fetch_etf_data(["PSI"], "2010-01-01")
    assert second.iloc[0, 0] != -999.0


@patch("backend.forecaster.yf.download")
def test_fetch_etf_data_cache_expires(mock_download):
    mock_download.return_value = _fake_history(["PSI"])
    forecaster.fetch_etf_data(["PSI"], "2010-01-01")
    assert mock_download.call_count == 1

    price_history_cache.clear()  # simulate TTL expiry without sleeping in a test
    forecaster.fetch_etf_data(["PSI"], "2010-01-01")
    assert mock_download.call_count == 2


# ---------------------------------------------------------------------------
#  Order-fill / settlement pricing: per-ticker cache
# ---------------------------------------------------------------------------

def _fake_quote_frame(tickers: list[str]) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    frame = pd.DataFrame({t: [100.0] * 5 for t in tickers}, index=dates)
    frame.columns = pd.MultiIndex.from_product([["Close"], tickers])
    return frame


@patch("backend.pricing.yf.download")
def test_get_last_prices_is_cached_per_ticker(mock_download):
    mock_download.side_effect = lambda tickers, **kw: _fake_quote_frame(sorted(tickers))

    first = pricing.get_last_prices(["PSI", "IYW"])
    assert first == {"PSI": 100.0, "IYW": 100.0}
    assert mock_download.call_count == 1

    # Fully cached — identical ticker set, no new download.
    pricing.get_last_prices(["PSI", "IYW"])
    assert mock_download.call_count == 1

    # Partial overlap: only the *uncached* ticker should be fetched.
    pricing.get_last_prices(["PSI", "NLR"])
    assert mock_download.call_count == 2
    (called_tickers,), _ = mock_download.call_args
    assert list(called_tickers) == ["NLR"]


# ---------------------------------------------------------------------------
#  /portfolio/summary — one request, same data as the individual endpoints
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_portfolio_summary_matches_individual_endpoints(client, register_user):
    user = register_user(username="alice")
    headers = _headers(user["access_token"])

    client.post("/portfolio/watchlist/PSI", headers=headers)
    client.post("/portfolio/alerts", json={
        "ticker": "PSI", "direction": "above", "threshold": 100.0,
    }, headers=headers)
    client.post("/portfolio/orders", json={
        "ticker": "PSI", "side": "BUY", "quantity": 1,
        "order_type": "LIMIT", "limit_price": 10.0,
    }, headers=headers)

    summary = client.get("/portfolio/summary", headers=headers).json()
    assert summary["account"] == client.get("/portfolio/account", headers=headers).json()
    assert summary["positions"] == client.get("/portfolio/positions", headers=headers).json()
    assert summary["orders"] == client.get("/portfolio/orders", headers=headers).json()
    assert summary["transactions"] == client.get("/portfolio/transactions", headers=headers).json()
    assert summary["watchlist"] == client.get("/portfolio/watchlist", headers=headers).json()["tickers"]
    assert summary["alerts"] == client.get("/portfolio/alerts", headers=headers).json()
