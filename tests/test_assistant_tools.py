# -*- coding: utf-8 -*-
"""Tests for `backend/assistant_tools.py` — the real-data functions the AI
Assistant calls via tool/function calling. Only `get_portfolio_risk` is new
here; the other tools are already exercised indirectly through the chat
endpoint's own request/response contract, which doesn't change in this pass.
"""

from __future__ import annotations

from unittest.mock import patch

from backend import assistant_tools as tools
from backend import crud
from backend.db import SessionLocal


def test_get_portfolio_risk_returns_empty_status_with_no_positions(client, register_user):
    register_user(username="airiskuser1")
    db = SessionLocal()
    try:
        user = crud.get_user_by_username(db, "airiskuser1")
        result = tools.get_portfolio_risk(db, user)
    finally:
        db.close()
    assert result["status"] == "empty"
    assert result["cash"] == 250_000.0
    assert result["invested_value"] == 0.0


@patch("backend.pricing.yf.download")
def test_get_portfolio_risk_reflects_real_positions(mock_download, client, register_user):
    import pandas as pd

    user_out = register_user(username="airiskuser2")
    headers = {"Authorization": f"Bearer {user_out['access_token']}"}

    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    frame = pd.DataFrame({"PSI": [100.0, 100.0, 105.0]}, index=dates)
    frame.columns = pd.MultiIndex.from_product([["Close"], ["PSI"]])
    mock_download.return_value = frame

    order = client.post(
        "/portfolio/orders", headers=headers,
        json={"ticker": "PSI", "side": "BUY", "quantity": 10, "order_type": "MARKET"},
    )
    assert order.status_code == 201, order.text

    db = SessionLocal()
    try:
        user = crud.get_user_by_username(db, "airiskuser2")
        result = tools.get_portfolio_risk(db, user)
    finally:
        db.close()

    assert result["status"] == "ok"
    assert result["positions"][0]["ticker"] == "PSI"


def test_get_portfolio_risk_never_raises_on_bad_input(client, register_user):
    """A tool failure must degrade to an `{"error": ...}` dict (dispatched
    the same way as the other tools) — never an unhandled exception that
    would 500 the whole chat turn."""
    register_user(username="airiskuser3")
    db = SessionLocal()
    try:
        user = crud.get_user_by_username(db, "airiskuser3")
        result = tools.get_portfolio_risk(db, user, benchmark_ticker="")
    finally:
        db.close()
    assert "error" in result or result.get("status") in ("empty", "ok")
