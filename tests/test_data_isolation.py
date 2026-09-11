# -*- coding: utf-8 -*-
"""User A must never be able to read or mutate User B's portfolio, orders,
transactions, watchlist or alerts — enforced by scoping every query to the
caller's own account/user id, not by hiding UI elements.

Order/position isolation is exercised with LIMIT orders and a directly
inserted Position row rather than MARKET fills, so these tests don't depend
on a live network call to Yahoo Finance.
"""

from __future__ import annotations

from backend.db import SessionLocal
from backend.models import Account, Position


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _two_users(register_user):
    alice = register_user(username="alice")
    bob = register_user(username="bob")
    return alice, bob


def test_positions_are_isolated(client, register_user):
    alice, bob = _two_users(register_user)

    db = SessionLocal()
    try:
        alice_account = db.query(Account).filter(Account.user_id == alice["user"]["id"]).one()
        db.add(Position(account_id=alice_account.id, ticker="PSI", quantity=10.0, avg_price=50.0))
        db.commit()
    finally:
        db.close()

    alice_positions = client.get("/portfolio/positions", headers=_headers(alice["access_token"])).json()
    bob_positions = client.get("/portfolio/positions", headers=_headers(bob["access_token"])).json()

    assert any(p["ticker"] == "PSI" for p in alice_positions)
    assert bob_positions == []


def test_orders_are_isolated(client, register_user):
    alice, bob = _two_users(register_user)

    order = client.post("/portfolio/orders", json={
        "ticker": "PSI", "side": "BUY", "quantity": 5, "order_type": "LIMIT", "limit_price": 10.0,
    }, headers=_headers(alice["access_token"]))
    assert order.status_code == 201
    order_id = order.json()["id"]

    bob_orders = client.get("/portfolio/orders", headers=_headers(bob["access_token"])).json()
    assert bob_orders == []

    alice_orders = client.get("/portfolio/orders", headers=_headers(alice["access_token"])).json()
    assert any(o["id"] == order_id for o in alice_orders)


def test_cannot_cancel_another_users_order(client, register_user):
    alice, bob = _two_users(register_user)

    order = client.post("/portfolio/orders", json={
        "ticker": "PSI", "side": "BUY", "quantity": 5, "order_type": "LIMIT", "limit_price": 10.0,
    }, headers=_headers(alice["access_token"]))
    order_id = order.json()["id"]

    response = client.post(
        f"/portfolio/orders/{order_id}/cancel", headers=_headers(bob["access_token"]),
    )
    # 404, not 403: existence of another user's order must not be leaked.
    assert response.status_code == 404

    # And it must still be cancellable by its actual owner.
    own_cancel = client.post(
        f"/portfolio/orders/{order_id}/cancel", headers=_headers(alice["access_token"]),
    )
    assert own_cancel.status_code == 200
    assert own_cancel.json()["status"] == "CANCELLED"


def test_transactions_are_isolated(client, register_user):
    alice, bob = _two_users(register_user)

    alice_tx = client.get("/portfolio/transactions", headers=_headers(alice["access_token"])).json()
    bob_tx = client.get("/portfolio/transactions", headers=_headers(bob["access_token"])).json()

    assert len(alice_tx) == 1  # the initial deposit, and nothing of Bob's
    alice_ids = {t["id"] for t in alice_tx}
    bob_ids = {t["id"] for t in bob_tx}
    assert alice_ids.isdisjoint(bob_ids)


def test_watchlist_is_isolated(client, register_user):
    alice, bob = _two_users(register_user)

    add = client.post("/portfolio/watchlist/PSI", headers=_headers(alice["access_token"]))
    assert add.status_code == 201
    assert add.json()["tickers"] == ["PSI"]

    bob_watchlist = client.get("/portfolio/watchlist", headers=_headers(bob["access_token"])).json()
    assert bob_watchlist["tickers"] == []


def test_alerts_are_isolated(client, register_user):
    alice, bob = _two_users(register_user)

    alert = client.post("/portfolio/alerts", json={
        "ticker": "PSI", "direction": "above", "threshold": 123.0, "note": "test",
    }, headers=_headers(alice["access_token"]))
    assert alert.status_code == 201
    alert_id = alert.json()["id"]

    bob_alerts = client.get("/portfolio/alerts", headers=_headers(bob["access_token"])).json()
    assert bob_alerts == []


def test_cannot_delete_or_reset_another_users_alert(client, register_user):
    alice, bob = _two_users(register_user)

    alert = client.post("/portfolio/alerts", json={
        "ticker": "PSI", "direction": "above", "threshold": 123.0,
    }, headers=_headers(alice["access_token"]))
    alert_id = alert.json()["id"]

    delete_attempt = client.delete(
        f"/portfolio/alerts/{alert_id}", headers=_headers(bob["access_token"]),
    )
    assert delete_attempt.status_code == 404

    reset_attempt = client.post(
        f"/portfolio/alerts/{alert_id}/reset", headers=_headers(bob["access_token"]),
    )
    assert reset_attempt.status_code == 404

    # Still there, untouched, for its actual owner.
    alice_alerts = client.get("/portfolio/alerts", headers=_headers(alice["access_token"])).json()
    assert any(a["id"] == alert_id for a in alice_alerts)


def test_account_cash_is_isolated(client, register_user):
    alice, bob = _two_users(register_user)

    db = SessionLocal()
    try:
        alice_account = db.query(Account).filter(Account.user_id == alice["user"]["id"]).one()
        alice_account.cash = 999.0
        db.commit()
    finally:
        db.close()

    alice_view = client.get("/portfolio/account", headers=_headers(alice["access_token"])).json()
    bob_view = client.get("/portfolio/account", headers=_headers(bob["access_token"])).json()

    assert alice_view["cash"] == 999.0
    assert bob_view["cash"] == 250_000.0


def test_portfolio_summary_is_isolated(client, register_user):
    """The consolidated `/portfolio/summary` endpoint (added to cut six
    sequential requests down to one) must respect the exact same per-user
    scoping as the individual endpoints it replaces — nothing about
    combining the response into one payload should let it skip a filter."""
    alice, bob = _two_users(register_user)

    client.post("/portfolio/watchlist/PSI", headers=_headers(alice["access_token"]))
    client.post("/portfolio/alerts", json={
        "ticker": "PSI", "direction": "above", "threshold": 50.0,
    }, headers=_headers(alice["access_token"]))
    client.post("/portfolio/orders", json={
        "ticker": "PSI", "side": "BUY", "quantity": 1,
        "order_type": "LIMIT", "limit_price": 10.0,
    }, headers=_headers(alice["access_token"]))

    bob_summary = client.get("/portfolio/summary", headers=_headers(bob["access_token"])).json()

    assert bob_summary["watchlist"] == []
    assert bob_summary["alerts"] == []
    assert bob_summary["orders"] == []
    assert bob_summary["positions"] == []
    assert len(bob_summary["transactions"]) == 1  # only Bob's own initial deposit
    assert bob_summary["account"]["cash"] == 250_000.0

    alice_summary = client.get("/portfolio/summary", headers=_headers(alice["access_token"])).json()
    assert alice_summary["watchlist"] == ["PSI"]
    assert len(alice_summary["alerts"]) == 1
    assert len(alice_summary["orders"]) == 1
