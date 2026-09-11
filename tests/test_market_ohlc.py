# -*- coding: utf-8 -*-
"""GET /market/ohlc — real OHLCV bars for one ticker, feeding the Markets
page candlestick chart (React can't call yfinance directly, unlike
Streamlit's in-process `services/market.py`)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from backend.market_cache import ohlc_cache


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_ohlc_cache():
    ohlc_cache.clear()
    yield
    ohlc_cache.clear()


def _fake_ohlcv() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    return pd.DataFrame(
        {
            "Open": [100.0, 102.0, 103.0],
            "High": [103.0, 104.0, 106.0],
            "Low": [99.0, 101.0, 102.0],
            "Close": [102.0, 103.0, 105.0],
            "Volume": [1_000_000.0, 1_200_000.0, 900_000.0],
        },
        index=dates,
    )


def test_requires_auth(client):
    response = client.get("/market/ohlc?ticker=SPY")
    assert response.status_code == 401


@patch("backend.pricing.yf.download")
def test_returns_real_ohlcv_bars(mock_download, client, register_user):
    mock_download.return_value = _fake_ohlcv()
    user = register_user(username="alice")
    response = client.get("/market/ohlc?ticker=SPY&period=1mo", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "SPY"
    assert body["period"] == "1mo"
    assert len(body["bars"]) == 3
    first = body["bars"][0]
    assert first["time"] == "2024-01-01"
    assert first["open"] == 100.0
    assert first["high"] == 103.0
    assert first["low"] == 99.0
    assert first["close"] == 102.0
    assert first["volume"] == 1_000_000.0


def test_invalid_period_rejected(client, register_user):
    user = register_user(username="alice")
    response = client.get("/market/ohlc?ticker=SPY&period=3days", headers=_headers(user["access_token"]))
    assert response.status_code == 400


def test_empty_ticker_rejected(client, register_user):
    user = register_user(username="alice")
    response = client.get("/market/ohlc?ticker=&period=6mo", headers=_headers(user["access_token"]))
    assert response.status_code == 400


@patch("backend.pricing.yf.download")
def test_unknown_ticker_returns_empty_bars_not_error(mock_download, client, register_user):
    mock_download.return_value = pd.DataFrame()  # yfinance found nothing
    user = register_user(username="alice")
    response = client.get("/market/ohlc?ticker=ZZZFAKE&period=6mo", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    assert response.json()["bars"] == []


@patch("backend.pricing.yf.download")
def test_ohlc_is_cached_per_ticker_and_period(mock_download, client, register_user):
    mock_download.return_value = _fake_ohlcv()
    user = register_user(username="alice")
    headers = _headers(user["access_token"])

    client.get("/market/ohlc?ticker=SPY&period=1mo", headers=headers)
    client.get("/market/ohlc?ticker=SPY&period=1mo", headers=headers)
    assert mock_download.call_count == 1

    # A different period is a cache miss, not reused from the first call.
    client.get("/market/ohlc?ticker=SPY&period=3mo", headers=headers)
    assert mock_download.call_count == 2
