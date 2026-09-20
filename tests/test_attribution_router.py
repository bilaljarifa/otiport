# -*- coding: utf-8 -*-
"""API-layer tests for `GET /portfolio/attribution` — auth gating, real
wiring through the actual order-fill/transaction pipeline, and per-user
isolation. Calculation correctness is covered by
`test_performance_attribution.py`."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from backend.market_cache import last_price_cache


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_last_price_cache():
    # `pricing.get_last_prices` caches per-ticker across the whole test
    # session (prices aren't user-scoped) — without clearing it, an earlier
    # test's mocked price for the same ticker (e.g. "PSI") would leak into
    # this one instead of the freshly-mocked value below.
    last_price_cache.clear()
    yield
    last_price_cache.clear()


def test_requires_auth(client):
    assert client.get("/portfolio/attribution").status_code == 401


def test_new_account_with_no_trades_is_insufficient_history(client, register_user):
    user = register_user(username="attruser1")
    response = client.get("/portfolio/attribution", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_history"
    assert body["holdings"] == []
    assert body["total_return"] is None


@patch("backend.pricing.yf.download")
def test_real_trade_produces_real_attribution(mock_download, client, register_user):
    user = register_user(username="attruser2")
    headers = _headers(user["access_token"])

    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    frame = pd.DataFrame({"PSI": [100.0, 100.0, 115.0]}, index=dates)
    frame.columns = pd.MultiIndex.from_product([["Close"], ["PSI"]])
    mock_download.return_value = frame

    order = client.post(
        "/portfolio/orders", headers=headers,
        json={"ticker": "PSI", "side": "BUY", "quantity": 10, "order_type": "MARKET"},
    )
    assert order.status_code == 201, order.text
    fill_price = order.json()["fill_price"]

    response = client.get("/portfolio/attribution", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert len(body["holdings"]) == 1
    psi = body["holdings"][0]
    assert psi["ticker"] == "PSI"
    assert psi["is_open_position"] is True
    # Real reconciliation: contribution == -cost + current market value == qty * (last_price - fill_price)
    assert psi["market_value"] == pytest.approx(10 * 115.0)  # last close in the mocked frame is 115.0
    assert body["total_return"] == pytest.approx(10 * (115.0 - fill_price), abs=0.01)


def test_a_second_user_never_sees_the_first_users_attribution(client, register_user):
    alice = register_user(username="attralice")
    bob = register_user(username="attrbob")
    r_alice = client.get("/portfolio/attribution", headers=_headers(alice["access_token"]))
    r_bob = client.get("/portfolio/attribution", headers=_headers(bob["access_token"]))
    assert r_alice.status_code == 200 and r_bob.status_code == 200
    assert r_alice.json()["status"] == "insufficient_history"
    assert r_bob.json()["status"] == "insufficient_history"


def test_wraps_unexpected_errors_as_500_not_a_bare_crash(client, register_user):
    user = register_user(username="attruser3")
    with patch("backend.routers.portfolio.compute_attribution", side_effect=RuntimeError("boom")):
        response = client.get("/portfolio/attribution", headers=_headers(user["access_token"]))
    assert response.status_code == 500
