# -*- coding: utf-8 -*-
"""Registration, login, /auth/me, logout and disabled-account behaviour."""

from __future__ import annotations


def test_register_returns_token_and_user(client, register_user):
    body = register_user(username="alice")
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "alice"
    assert body["user"]["role"] == "user"
    assert body["user"]["is_active"] is True
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_register_duplicate_username_is_rejected(client, register_user):
    register_user(username="alice", email="alice@example.com")
    response = client.post("/auth/register", json={
        "username": "alice", "email": "someone-else@example.com",
        "password": "password123", "full_name": "Someone Else",
    })
    assert response.status_code == 409


def test_register_duplicate_email_is_rejected(client, register_user):
    register_user(username="alice", email="shared@example.com")
    response = client.post("/auth/register", json={
        "username": "bob", "email": "shared@example.com",
        "password": "password123", "full_name": "Bob Bobson",
    })
    assert response.status_code == 409


def test_register_rejects_short_password(client):
    response = client.post("/auth/register", json={
        "username": "shortpw", "email": "shortpw@example.com",
        "password": "short", "full_name": "Short Pw",
    })
    assert response.status_code == 422


def test_login_success(client, register_user):
    register_user(username="alice", password="password123")
    response = client.post("/auth/login", json={"username": "alice", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_wrong_password_is_rejected(client, register_user):
    register_user(username="alice", password="password123")
    response = client.post("/auth/login", json={"username": "alice", "password": "wrong-password"})
    assert response.status_code == 401


def test_login_unknown_user_is_rejected(client):
    response = client.post("/auth/login", json={"username": "ghost", "password": "whatever123"})
    assert response.status_code == 401


def test_login_trims_leading_and_trailing_username_whitespace(client, register_user):
    """A stray space from copy-paste or browser autofill around the
    *username* must not turn a correct login into "wrong credentials" —
    regression test for a real report of this happening with the admin
    account created via `backend.create_admin`."""
    register_user(username="alice", password="password123")
    response = client.post(
        "/auth/login", json={"username": " alice ", "password": "password123"},
    )
    assert response.status_code == 200


def test_register_trims_username_and_email_whitespace(client):
    response = client.post("/auth/register", json={
        "username": " whitespace ", "email": " whitespace@example.com ",
        "password": "password123", "full_name": "Whitespace Test",
    })
    assert response.status_code == 201
    assert response.json()["user"]["username"] == "whitespace"
    assert response.json()["user"]["email"] == "whitespace@example.com"


def test_me_requires_a_token(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_returns_own_profile_without_password_hash(client, register_user):
    body = register_user(username="alice")
    token = body["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "alice"
    assert "password" not in payload
    assert "password_hash" not in payload


def test_update_profile_persists(client, register_user):
    body = register_user(username="alice")
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    response = client.patch("/auth/me", json={
        "full_name": "Alice Updated", "job_title": "Head of Trading", "desk": "Macro",
    }, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["full_name"] == "Alice Updated"
    assert payload["job_title"] == "Head of Trading"
    assert payload["desk"] == "Macro"


def test_logout_revokes_the_token(client, register_user):
    body = register_user(username="alice")
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 204
    # The same token must now be rejected — logout actually revokes it,
    # not just discarded client-side.
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_disabled_user_cannot_login(client, register_user, make_admin):
    alice = register_user(username="alice")
    admin_id = make_admin(username="root")
    admin_login = client.post("/auth/login", json={"username": "root", "password": "adminpass123"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    disable = client.patch(
        f"/admin/users/{alice['user']['id']}", json={"is_active": False}, headers=admin_headers,
    )
    assert disable.status_code == 200

    login_attempt = client.post("/auth/login", json={"username": "alice", "password": "password123"})
    assert login_attempt.status_code == 403


def test_disabling_a_live_token_locks_it_out_immediately(client, register_user, make_admin):
    """A user's *existing, unexpired* token must stop working the moment an
    admin disables the account — role/active status is re-read from the DB
    on every request, never trusted from the token payload."""
    alice = register_user(username="alice")
    alice_headers = {"Authorization": f"Bearer {alice['access_token']}"}
    make_admin(username="root")
    admin_login = client.post("/auth/login", json={"username": "root", "password": "adminpass123"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    assert client.get("/auth/me", headers=alice_headers).status_code == 200

    client.patch(f"/admin/users/{alice['user']['id']}", json={"is_active": False}, headers=admin_headers)

    assert client.get("/auth/me", headers=alice_headers).status_code == 401
