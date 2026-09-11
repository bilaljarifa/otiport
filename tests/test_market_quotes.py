# -*- coding: utf-8 -*-
"""GET /market/quotes — the REST endpoint the React frontend uses for
current price + day change (Streamlit's `services/market.py` fetches this
in-process, which a separate frontend can't do)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from backend.market_cache import quote_cache


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_quote_cache():
    quote_cache.clear()
    yield
    quote_cache.clear()


def _fake_frame(tickers: list[str]) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    frame = pd.DataFrame({t: [100.0, 100.0, 105.0] for t in tickers}, index=dates)
    frame.columns = pd.MultiIndex.from_product([["Close"], tickers])
    return frame


def test_requires_auth(client):
    response = client.get("/market/quotes?tickers=SPY")
    assert response.status_code == 401


@patch("backend.pricing.yf.download")
def test_returns_price_and_day_change(mock_download, client, register_user):
    mock_download.return_value = _fake_frame(["SPY"])
    user = register_user(username="alice")
    response = client.get("/market/quotes?tickers=SPY", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    quote = response.json()["quotes"]["SPY"]
    assert quote["price"] == 105.0
    assert quote["previous_close"] == 100.0
    assert quote["change_abs"] == 5.0
    assert quote["change_pct"] == pytest.approx(5.0)
    assert response.json()["missing"] == []


@patch("backend.pricing.yf.download")
def test_unknown_ticker_reported_as_missing_not_error(mock_download, client, register_user):
    mock_download.return_value = _fake_frame(["SPY"])  # doesn't include the requested ticker
    user = register_user(username="alice")
    response = client.get(
        "/market/quotes?tickers=SPY,ZZZFAKE", headers=_headers(user["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert "SPY" in body["quotes"]
    assert body["missing"] == ["ZZZFAKE"]


def test_empty_tickers_rejected(client, register_user):
    user = register_user(username="alice")
    response = client.get("/market/quotes?tickers=", headers=_headers(user["access_token"]))
    assert response.status_code == 400


@patch("backend.pricing.yf.download")
def test_quotes_are_cached_per_ticker(mock_download, client, register_user):
    mock_download.return_value = _fake_frame(["SPY"])
    user = register_user(username="alice")
    headers = _headers(user["access_token"])

    client.get("/market/quotes?tickers=SPY", headers=headers)
    client.get("/market/quotes?tickers=SPY", headers=headers)
    assert mock_download.call_count == 1
