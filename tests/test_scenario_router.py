# -*- coding: utf-8 -*-
"""API-layer tests for `POST /analytics/scenario` — auth gating, response
wiring, and the critical guarantee that this stateless what-if calculation
never touches the database (no position/order/transaction is ever created,
and the caller's real portfolio is unaffected no matter what hypothetical
holdings are analyzed). Risk-calculation correctness itself is already
covered by `test_risk.py` (same `compute_portfolio_risk` function, reused
here, not reimplemented).
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fake_prices(tickers: list[str], n: int = 300, seed: int = 0) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=n, name="Date")
    rng = np.random.default_rng(seed)
    data = {}
    for i, ticker in enumerate(tickers):
        steps = rng.normal(loc=0.0003 + 0.0001 * i, scale=0.01, size=n)
        data[ticker] = 100.0 * np.cumprod(1 + steps)
    return pd.DataFrame(data, index=dates)


def test_requires_auth(client):
    response = client.post("/analytics/scenario", json={"holdings": [], "cash": 1000.0})
    assert response.status_code == 401


def test_empty_holdings_returns_empty_status(client, register_user):
    user = register_user(username="scenuser1")
    response = client.post(
        "/analytics/scenario", headers=_headers(user["access_token"]),
        json={"holdings": [], "cash": 50_000.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "empty"
    assert body["cash"] == 50_000.0


def test_valid_scenario_returns_risk_and_expected_return(client, register_user):
    user = register_user(username="scenuser2")
    frame = _fake_prices(["PSI", "IYW", "SPY"])
    with patch("backend.risk.fetch_etf_data", return_value=frame), \
         patch("backend.routers.analytics.get_expected_returns", return_value=np.array([0.08, 0.05])):
        response = client.post(
            "/analytics/scenario", headers=_headers(user["access_token"]),
            json={
                "holdings": [{"ticker": "PSI", "dollar_value": 6000.0}, {"ticker": "IYW", "dollar_value": 4000.0}],
                "cash": 1000.0, "benchmark_ticker": "SPY",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["expected_return_pct"] is not None
    assert body["invested_value"] == pytest.approx(10_000.0)
    assert len(body["positions"]) == 2


def test_scenario_never_creates_a_position_order_or_transaction(client, register_user):
    """The core safety guarantee: analyzing any hypothetical portfolio must
    leave the real account completely untouched."""
    user = register_user(username="scenuser3")
    headers = _headers(user["access_token"])

    before = client.get("/portfolio/summary", headers=headers).json()
    assert before["positions"] == []
    assert len(before["transactions"]) == 1  # just the initial deposit

    frame = _fake_prices(["PSI", "QQQ", "SPY"])
    with patch("backend.risk.fetch_etf_data", return_value=frame), \
         patch("backend.routers.analytics.get_expected_returns", return_value=np.array([0.1, 0.06])):
        for _ in range(3):  # repeated analysis, as a real UI would do while adjusting inputs
            r = client.post(
                "/analytics/scenario", headers=headers,
                json={
                    "holdings": [{"ticker": "PSI", "dollar_value": 50_000.0}, {"ticker": "QQQ", "dollar_value": 30_000.0}],
                    "cash": 170_000.0, "benchmark_ticker": "SPY",
                },
            )
            assert r.status_code == 200

    after = client.get("/portfolio/summary", headers=headers).json()
    assert after["positions"] == []
    assert after["orders"] == []
    assert len(after["transactions"]) == 1
    assert after["account"]["cash"] == before["account"]["cash"] == 250_000.0


def test_scenario_ignores_negative_or_zero_dollar_values(client, register_user):
    user = register_user(username="scenuser4")
    response = client.post(
        "/analytics/scenario", headers=_headers(user["access_token"]),
        json={"holdings": [{"ticker": "PSI", "dollar_value": 0.0}], "cash": 10_000.0},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "empty"


def test_invalid_negative_dollar_value_is_rejected_by_validation(client, register_user):
    user = register_user(username="scenuser5")
    response = client.post(
        "/analytics/scenario", headers=_headers(user["access_token"]),
        json={"holdings": [{"ticker": "PSI", "dollar_value": -500.0}], "cash": 10_000.0},
    )
    assert response.status_code == 422


def test_market_data_failure_maps_to_400(client, register_user):
    user = register_user(username="scenuser6")
    with patch("backend.risk.fetch_etf_data", side_effect=ValueError("no data")):
        response = client.post(
            "/analytics/scenario", headers=_headers(user["access_token"]),
            json={"holdings": [{"ticker": "PSI", "dollar_value": 1000.0}], "cash": 0.0},
        )
    assert response.status_code == 400
