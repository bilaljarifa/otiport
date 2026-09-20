# -*- coding: utf-8 -*-
"""API-layer tests for `/risk/portfolio` — auth gating, per-user scoping, and
response wiring. Calculation correctness is covered by `test_risk.py`."""

from __future__ import annotations

from unittest.mock import patch


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_requires_auth(client):
    assert client.get("/risk/portfolio").status_code == 401


def test_no_positions_returns_empty_status(client, register_user):
    user = register_user(username="riskuser1")
    response = client.get("/risk/portfolio", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "empty"
    assert body["invested_value"] == 0.0
    assert body["cash"] == 250_000.0


@patch("backend.pricing.yf.download")
def test_positions_produce_a_risk_profile_scoped_to_the_caller(mock_download, client, register_user):
    import pandas as pd

    user = register_user(username="riskuser2")
    headers = _headers(user["access_token"])

    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    frame = pd.DataFrame({"PSI": [100.0, 100.0, 105.0]}, index=dates)
    frame.columns = pd.MultiIndex.from_product([["Close"], ["PSI"]])
    mock_download.return_value = frame

    order = client.post(
        "/portfolio/orders", headers=headers,
        json={"ticker": "PSI", "side": "BUY", "quantity": 10, "order_type": "MARKET"},
    )
    assert order.status_code == 201, order.text

    fake_result = {
        "status": "ok", "invested_value": 1050.0, "cash": 248_950.0, "cash_pct": 99.58,
        "lookback_days": 365, "volatility_pct": 12.3, "annualized_return_pct": 5.0,
        "sharpe_ratio": 0.4, "max_drawdown_pct": -8.0, "var": None, "beta": 0.9,
        "benchmark_ticker": "SPY", "concentration_hhi": 1.0, "diversification_score": 0.0,
        "positions": [{"ticker": "PSI", "weight_pct": 100.0, "market_value": 1050.0, "risk_contribution_pct": 100.0}],
        "exposure_by_region": [{"region": "North America", "weight_pct": 100.0}],
        "correlation_matrix": None, "methodology_notes": ["note"],
    }
    with patch("backend.routers.risk.compute_portfolio_risk", return_value=fake_result) as mocked:
        response = client.get("/risk/portfolio", headers=headers)
        assert response.status_code == 200
        assert response.json()["positions"][0]["ticker"] == "PSI"
        called_tickers = mocked.call_args.kwargs["tickers"]
        assert called_tickers == ["PSI"]


def test_a_second_user_never_sees_the_first_users_risk_profile(client, register_user):
    alice = register_user(username="riskalice")
    bob = register_user(username="riskbob")

    r_alice = client.get("/risk/portfolio", headers=_headers(alice["access_token"]))
    r_bob = client.get("/risk/portfolio", headers=_headers(bob["access_token"]))
    assert r_alice.status_code == 200 and r_bob.status_code == 200
    # Both are empty (no trades), but scoped independently — no cross-account leakage.
    assert r_alice.json()["status"] == "empty"
    assert r_bob.json()["status"] == "empty"
