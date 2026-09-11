# -*- coding: utf-8 -*-
"""Role enforcement: normal users cannot reach admin endpoints, admins can,
and role changes take effect immediately — all enforced server-side,
independent of whatever a client claims about itself."""

from __future__ import annotations


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_normal_user_cannot_list_users(client, register_user):
    alice = register_user(username="alice")
    response = client.get("/admin/users", headers=_headers(alice["access_token"]))
    assert response.status_code == 403


def test_normal_user_cannot_change_roles(client, register_user):
    alice = register_user(username="alice")
    bob = register_user(username="bob")
    response = client.patch(
        f"/admin/users/{bob['user']['id']}", json={"role": "admin"},
        headers=_headers(alice["access_token"]),
    )
    assert response.status_code == 403
    # And the attempted privilege escalation must not have taken effect.
    me = client.get("/auth/me", headers=_headers(bob["access_token"])).json()
    assert me["role"] == "user"


def test_normal_user_cannot_delete_users(client, register_user):
    alice = register_user(username="alice")
    bob = register_user(username="bob")
    response = client.delete(
        f"/admin/users/{bob['user']['id']}", headers=_headers(alice["access_token"]),
    )
    assert response.status_code == 403


def test_admin_can_list_users(client, register_user, make_admin):
    register_user(username="alice")
    make_admin(username="root")
    login = client.post("/auth/login", json={"username": "root", "password": "adminpass123"})
    response = client.get("/admin/users", headers=_headers(login.json()["access_token"]))
    assert response.status_code == 200
    usernames = {u["username"] for u in response.json()}
    assert {"alice", "root"} <= usernames


def test_admin_can_promote_a_user(client, register_user, make_admin):
    alice = register_user(username="alice")
    make_admin(username="root")
    login = client.post("/auth/login", json={"username": "root", "password": "adminpass123"})
    admin_headers = _headers(login.json()["access_token"])

    response = client.patch(
        f"/admin/users/{alice['user']['id']}", json={"role": "admin"}, headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_cannot_demote_or_disable_self(client, make_admin):
    make_admin(username="root")
    login = client.post("/auth/login", json={"username": "root", "password": "adminpass123"})
    payload = login.json()
    admin_headers = _headers(payload["access_token"])
    admin_id = payload["user"]["id"]

    demote = client.patch(f"/admin/users/{admin_id}", json={"role": "user"}, headers=admin_headers)
    assert demote.status_code == 400
    disable = client.patch(f"/admin/users/{admin_id}", json={"is_active": False}, headers=admin_headers)
    assert disable.status_code == 400
    delete = client.delete(f"/admin/users/{admin_id}", headers=admin_headers)
    assert delete.status_code == 400


def test_compute_endpoints_require_auth(client):
    response = client.post("/chart-data", json={"tickers": ["PSI"]})
    assert response.status_code == 401


def test_health_is_public(client):
    assert client.get("/health").status_code == 200
