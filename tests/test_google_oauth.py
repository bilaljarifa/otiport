# -*- coding: utf-8 -*-
"""Google OAuth — token exchange and ID-token verification are always
mocked (no real Google credentials needed to run this suite); the
account-linking/creation *logic* they feed into is exercised for real
against the test database.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend import crud
from backend.db import SessionLocal
from backend.google_oauth import GoogleOAuthError, GoogleProfile


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
#  /auth/google/config — never leaks the client secret, honest about state
# ---------------------------------------------------------------------------

def test_google_config_reports_disabled_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    response = client.get("/auth/google/config")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["client_id"] is None


def test_google_config_reports_enabled_and_client_id_only(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:5173/auth/google/callback")
    response = client.get("/auth/google/config")
    body = response.json()
    assert body["enabled"] is True
    assert body["client_id"] == "test-client-id"
    assert "secret" not in str(body).lower()


# ---------------------------------------------------------------------------
#  POST /auth/google — the actual sign-in flow
# ---------------------------------------------------------------------------

@patch("backend.routers.auth.exchange_code_for_profile")
def test_google_login_creates_a_new_user_with_simulated_account(mock_exchange, client):
    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-123", email="newperson@example.com",
        email_verified=True, full_name="New Person",
    )
    response = client.post("/auth/google", json={"code": "fake-code"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "newperson@example.com"
    assert body["user"]["role"] == "user"
    assert "password" not in body["user"]

    account = client.get("/portfolio/account", headers=_headers(body["access_token"])).json()
    assert account["cash"] == 250_000.0


@patch("backend.routers.auth.exchange_code_for_profile")
def test_google_session_me_logout_and_revocation_work_like_a_password_session(mock_exchange, client):
    """Items 9-11 of a full Google login test, made explicit: /auth/me
    returns the right user, logout revokes the token, and the revoked
    token is then rejected — the same JWT/blocklist mechanism a
    password-based session uses, exercised here via the Google entry
    point specifically rather than assumed from shared code."""
    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-session-check", email="sessioncheck@example.com",
        email_verified=True, full_name="Session Check",
    )
    login = client.post("/auth/google", json={"code": "fake-code"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = _headers(token)

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "sessioncheck@example.com"

    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 204

    after_logout = client.get("/auth/me", headers=headers)
    assert after_logout.status_code == 401


@patch("backend.routers.auth.exchange_code_for_profile")
def test_google_login_is_idempotent_for_the_same_google_account(mock_exchange, client):
    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-456", email="repeat@example.com",
        email_verified=True, full_name="Repeat User",
    )
    first = client.post("/auth/google", json={"code": "fake-code-1"}).json()
    second = client.post("/auth/google", json={"code": "fake-code-2"}).json()
    assert first["user"]["id"] == second["user"]["id"]


@patch("backend.routers.auth.exchange_code_for_profile")
def test_google_login_links_an_existing_verified_email(mock_exchange, client, register_user):
    local = register_user(username="alice", email="alice@example.com")
    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-789", email="alice@example.com",
        email_verified=True, full_name="Alice Anderson",
    )
    response = client.post("/auth/google", json={"code": "fake-code"})
    assert response.status_code == 200
    assert response.json()["user"]["id"] == local["user"]["id"]


@patch("backend.routers.auth.exchange_code_for_profile")
def test_google_login_refuses_to_link_an_unverified_email(mock_exchange, client, register_user):
    register_user(username="bob", email="bob@example.com")
    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-999", email="bob@example.com",
        email_verified=False, full_name="Someone Claiming To Be Bob",
    )
    response = client.post("/auth/google", json={"code": "fake-code"})
    assert response.status_code == 409


@patch("backend.routers.auth.exchange_code_for_profile")
def test_google_login_rejects_a_disabled_account(mock_exchange, client, register_user, make_admin):
    alice = register_user(username="alice", email="alice@example.com")
    make_admin(username="root")
    admin_login = client.post("/auth/login", json={"username": "root", "password": "adminpass123"})
    admin_headers = _headers(admin_login.json()["access_token"])
    client.patch(f"/admin/users/{alice['user']['id']}", json={"is_active": False}, headers=admin_headers)

    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-alice", email="alice@example.com",
        email_verified=True, full_name="Alice Anderson",
    )
    response = client.post("/auth/google", json={"code": "fake-code"})
    assert response.status_code == 403


def test_google_login_surfaces_upstream_failure_as_502(client):
    with patch("backend.routers.auth.exchange_code_for_profile") as mock_exchange:
        mock_exchange.side_effect = GoogleOAuthError("Google rejected the authorization code.")
        response = client.post("/auth/google", json={"code": "bad-code"})
    assert response.status_code == 502


def test_google_login_never_returns_a_password_hash(client):
    with patch("backend.routers.auth.exchange_code_for_profile") as mock_exchange:
        mock_exchange.return_value = GoogleProfile(
            sub="google-sub-clean", email="clean@example.com",
            email_verified=True, full_name="Clean User",
        )
        response = client.post("/auth/google", json={"code": "fake-code"})
    assert "password_hash" not in response.text


# ---------------------------------------------------------------------------
#  GET /auth/google/callback — the browser-redirect entry point Google
#  itself lands on (the Authorized redirect URI registered on the OAuth
#  client is this backend route, not a frontend page — see
#  backend/routers/auth.py::google_callback's docstring).
# ---------------------------------------------------------------------------

@patch("backend.routers.auth.exchange_code_for_profile")
def test_google_callback_redirects_with_token_in_fragment_on_success(mock_exchange, client):
    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-cb-1", email="callback1@example.com",
        email_verified=True, full_name="Callback Person",
    )
    response = client.get("/auth/google/callback", params={"code": "fake-code"}, follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith("http://localhost:5173/auth/google/callback#access_token=")
    assert "error" not in location


def test_google_callback_redirects_with_error_when_google_denies(client):
    response = client.get(
        "/auth/google/callback", params={"error": "access_denied"}, follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith("http://localhost:5173/auth/google/callback?")
    assert "error=access_denied" in location
    assert "access_token" not in location


def test_google_callback_redirects_with_error_when_code_missing(client):
    response = client.get("/auth/google/callback", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "error=missing_code" in response.headers["location"]


@patch("backend.routers.auth.exchange_code_for_profile")
def test_google_callback_redirects_with_error_on_upstream_failure(mock_exchange, client):
    mock_exchange.side_effect = GoogleOAuthError("Google rejected the authorization code.")
    response = client.get("/auth/google/callback", params={"code": "bad-code"}, follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith("http://localhost:5173/auth/google/callback?")
    assert "access_token" not in location


@patch("backend.routers.auth.exchange_code_for_profile")
def test_google_callback_redirects_with_error_for_disabled_account(mock_exchange, client, register_user, make_admin):
    alice = register_user(username="alice", email="alice@example.com")
    make_admin(username="root")
    admin_login = client.post("/auth/login", json={"username": "root", "password": "adminpass123"})
    admin_headers = _headers(admin_login.json()["access_token"])
    client.patch(f"/admin/users/{alice['user']['id']}", json={"is_active": False}, headers=admin_headers)

    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-cb-disabled", email="alice@example.com",
        email_verified=True, full_name="Alice Anderson",
    )
    response = client.get("/auth/google/callback", params={"code": "fake-code"}, follow_redirects=False)
    location = response.headers["location"]
    assert "access_token" not in location
    assert "error=" in location


# ---------------------------------------------------------------------------
#  Username collision handling for auto-created Google accounts
# ---------------------------------------------------------------------------

def test_unique_username_from_email_avoids_collisions(client, register_user):
    register_user(username="sameperson", email="sameperson@work.com")
    db = SessionLocal()
    try:
        username = crud._unique_username_from_email(db, "sameperson@personal.com")
        assert username != "sameperson"
        assert crud.get_user_by_username(db, username) is None
    finally:
        db.close()
