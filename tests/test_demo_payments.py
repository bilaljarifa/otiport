# -*- coding: utf-8 -*-
"""PAYMENT_MODE=demo — the simulated checkout used when a real Stripe
account isn't available. No Stripe SDK involved at all here; this exercises
the actual validation/activation logic in `backend.demo_payments` and
`backend.crud.activate_demo_subscription` through the real API.
"""

from __future__ import annotations

from backend import demo_payments


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


DEMO_CARD = {
    "card_number": "4242 4242 4242 4242",
    "exp": "12/30",
    "cvc": "123",
    "cardholder_name": "Alice Anderson",
}


def _checkout(client, token: str, plan: str, **overrides) -> dict:
    payload = {"plan": plan, **DEMO_CARD, **overrides}
    return client.post("/billing/demo-checkout", headers=_headers(token), json=payload)


# ---------------------------------------------------------------------------
#  Payment mode defaulting
# ---------------------------------------------------------------------------

def test_defaults_to_demo_when_stripe_not_configured(client, register_user):
    user = register_user(username="modeuser1")
    response = client.get("/billing/status", headers=_headers(user["access_token"]))
    assert response.json()["payment_mode"] == "demo"


def test_defaults_to_stripe_once_stripe_is_configured(client, register_user, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_PRO_PRICE_ID", "price_pro")
    monkeypatch.setenv("STRIPE_PREMIUM_PRICE_ID", "price_premium")
    user = register_user(username="modeuser2")
    response = client.get("/billing/status", headers=_headers(user["access_token"]))
    assert response.json()["payment_mode"] == "stripe"


def test_explicit_payment_mode_overrides_inference(client, register_user, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_PRO_PRICE_ID", "price_pro")
    monkeypatch.setenv("STRIPE_PREMIUM_PRICE_ID", "price_premium")
    monkeypatch.setenv("PAYMENT_MODE", "demo")
    user = register_user(username="modeuser3")
    response = client.get("/billing/status", headers=_headers(user["access_token"]))
    assert response.json()["payment_mode"] == "demo"


# ---------------------------------------------------------------------------
#  /billing/demo-checkout
# ---------------------------------------------------------------------------

def test_demo_checkout_requires_auth(client):
    assert client.post("/billing/demo-checkout", json={"plan": "pro", **DEMO_CARD}).status_code == 401


def test_demo_checkout_disabled_when_payment_mode_is_stripe(client, register_user, monkeypatch):
    monkeypatch.setenv("PAYMENT_MODE", "stripe")
    user = register_user(username="demouser1")
    response = _checkout(client, user["access_token"], "pro")
    assert response.status_code == 400


def test_free_to_pro_demo_upgrade(client, register_user):
    user = register_user(username="demouser2")
    response = _checkout(client, user["access_token"], "pro")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["plan"] == "pro"
    assert body["subscription_status"] == "active"
    assert body["current_period_end"] is not None
    assert body["has_billing_account"] is False  # no real Stripe customer behind a demo sub


def test_free_to_premium_demo_upgrade(client, register_user):
    user = register_user(username="demouser3")
    response = _checkout(client, user["access_token"], "premium")
    assert response.status_code == 200, response.text
    assert response.json()["plan"] == "premium"


def test_invalid_demo_card_number_is_rejected_and_plan_unchanged(client, register_user):
    user = register_user(username="demouser4")
    response = _checkout(client, user["access_token"], "pro", card_number="4111 1111 1111 1111")
    assert response.status_code == 400
    status = client.get("/billing/status", headers=_headers(user["access_token"]))
    assert status.json()["plan"] == "free"


def test_invalid_expiry_format_is_rejected(client, register_user):
    user = register_user(username="demouser5")
    response = _checkout(client, user["access_token"], "pro", exp="13/99")
    assert response.status_code == 400


def test_invalid_cvc_is_rejected(client, register_user):
    user = register_user(username="demouser6")
    response = _checkout(client, user["access_token"], "pro", cvc="12")
    assert response.status_code == 422  # fails schema min_length before it even reaches validation


def test_missing_cardholder_name_is_rejected(client, register_user):
    user = register_user(username="demouser7")
    response = _checkout(client, user["access_token"], "pro", cardholder_name="   ")
    assert response.status_code == 400


def test_demo_subscription_persists_across_logout_and_login(client, register_user):
    user = register_user(username="demouser8", password="password123")
    _checkout(client, user["access_token"], "premium")

    client.post("/auth/logout", headers=_headers(user["access_token"]))
    login = client.post("/auth/login", json={"username": "demouser8", "password": "password123"})
    assert login.status_code == 200
    new_token = login.json()["access_token"]

    status = client.get("/billing/status", headers=_headers(new_token))
    assert status.json()["plan"] == "premium"
    assert status.json()["subscription_status"] == "active"


def test_demo_subscription_id_is_obviously_fake(client, register_user):
    """Never a real-looking Stripe id — easy to spot in the database as a
    simulation, and impossible to confuse with a real `sub_...` id."""
    from backend.db import SessionLocal
    from backend import crud

    user = register_user(username="demouser9")
    _checkout(client, user["access_token"], "pro")

    db = SessionLocal()
    try:
        db_user = crud.get_user_by_username(db, "demouser9")
        assert db_user.stripe_subscription_id.startswith("demo_")
    finally:
        db.close()


# ---------------------------------------------------------------------------
#  backend.demo_payments — pure validation, exercised directly
# ---------------------------------------------------------------------------

def test_validate_and_charge_accepts_the_demo_card():
    demo_payments.validate_and_charge(
        card_number="4242-4242-4242-4242", exp="01/28", cvc="999", cardholder_name="Bob",
    )  # must not raise


def test_validate_and_charge_rejects_non_demo_card():
    try:
        demo_payments.validate_and_charge(
            card_number="5555555555554444", exp="01/28", cvc="999", cardholder_name="Bob",
        )
        assert False, "expected DemoPaymentError"
    except demo_payments.DemoPaymentError as exc:
        assert "4242" in str(exc)
