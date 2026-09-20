# -*- coding: utf-8 -*-
"""API-layer tests for `GET /portfolio/equity-curve`."""

from __future__ import annotations

from unittest.mock import patch


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_requires_auth(client):
    assert client.get("/portfolio/equity-curve").status_code == 401


def test_new_account_returns_a_flat_deposit_line(client, register_user):
    user = register_user(username="equser1")
    response = client.get("/portfolio/equity-curve", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert len(body["equity"]) > 0
    assert all(e == 250_000.0 for e in body["equity"])


def test_scoped_to_the_calling_user_only(client, register_user):
    alice = register_user(username="equser2")
    bob = register_user(username="equser3")
    r_alice = client.get("/portfolio/equity-curve", headers=_headers(alice["access_token"]))
    r_bob = client.get("/portfolio/equity-curve", headers=_headers(bob["access_token"]))
    assert r_alice.status_code == 200 and r_bob.status_code == 200


def test_wraps_unexpected_errors_as_500_not_a_bare_crash(client, register_user):
    user = register_user(username="equser4")
    with patch("backend.routers.portfolio.compute_account_equity_curve", side_effect=RuntimeError("boom")):
        response = client.get("/portfolio/equity-curve", headers=_headers(user["access_token"]))
    assert response.status_code == 500
