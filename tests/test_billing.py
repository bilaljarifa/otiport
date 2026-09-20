# -*- coding: utf-8 -*-
"""Subscription billing — Checkout/Portal session creation and the Stripe
webhook. Every real Stripe API call is mocked at the `backend.stripe_service`
boundary (no real network call, no real Stripe account needed); the webhook
tests verify this app's own event-to-plan logic in `backend.crud`, which is
exactly the part a mocked Stripe SDK can't verify for us.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend import stripe_service


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _configure_stripe(monkeypatch, *, webhook_secret: str = "whsec_test") -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_PRO_PRICE_ID", "price_pro_123")
    monkeypatch.setenv("STRIPE_PREMIUM_PRICE_ID", "price_premium_456")
    if webhook_secret:
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", webhook_secret)


# ---------------------------------------------------------------------------
#  /billing/status
# ---------------------------------------------------------------------------

def test_status_requires_auth(client):
    assert client.get("/billing/status").status_code == 401


def test_new_user_defaults_to_free_plan(client, register_user):
    user = register_user(username="billinguser1")
    response = client.get("/billing/status", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "free"
    assert body["subscription_status"] is None
    assert body["current_period_end"] is None
    assert body["has_billing_account"] is False


def test_status_reports_stripe_not_configured_by_default(client, register_user):
    user = register_user(username="billinguser2")
    response = client.get("/billing/status", headers=_headers(user["access_token"]))
    assert response.json()["stripe_configured"] is False


def test_status_reports_stripe_configured_once_env_is_set(client, register_user, monkeypatch):
    _configure_stripe(monkeypatch)
    user = register_user(username="billinguser3")
    response = client.get("/billing/status", headers=_headers(user["access_token"]))
    assert response.json()["stripe_configured"] is True


# ---------------------------------------------------------------------------
#  /billing/checkout
# ---------------------------------------------------------------------------

def test_checkout_requires_auth(client):
    assert client.post("/billing/checkout", json={"plan": "pro"}).status_code == 401


def test_checkout_returns_503_when_stripe_not_configured(client, register_user):
    user = register_user(username="checkoutuser1")
    response = client.post(
        "/billing/checkout", headers=_headers(user["access_token"]), json={"plan": "pro"},
    )
    assert response.status_code == 503


def test_checkout_creates_customer_then_session(client, register_user, monkeypatch):
    _configure_stripe(monkeypatch)
    user = register_user(username="checkoutuser2")

    with patch("backend.stripe_service.create_customer", return_value="cus_abc") as mock_customer, \
         patch("backend.stripe_service.create_checkout_session", return_value="https://checkout.stripe.com/pay/cs_test_abc") as mock_session:
        response = client.post(
            "/billing/checkout", headers=_headers(user["access_token"]), json={"plan": "pro"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["url"] == "https://checkout.stripe.com/pay/cs_test_abc"
    mock_customer.assert_called_once()
    mock_session.assert_called_once()
    assert mock_session.call_args.kwargs["plan"] == "pro"

    # The customer id is persisted — a second checkout must not create a
    # second Stripe Customer for the same user.
    status_response = client.get("/billing/status", headers=_headers(user["access_token"]))
    assert status_response.json()["has_billing_account"] is True

    with patch("backend.stripe_service.create_customer") as mock_customer_again, \
         patch("backend.stripe_service.create_checkout_session", return_value="https://checkout.stripe.com/pay/cs_test_def"):
        client.post("/billing/checkout", headers=_headers(user["access_token"]), json={"plan": "premium"})
    mock_customer_again.assert_not_called()


def test_checkout_rejects_invalid_plan(client, register_user, monkeypatch):
    _configure_stripe(monkeypatch)
    user = register_user(username="checkoutuser3")
    response = client.post(
        "/billing/checkout", headers=_headers(user["access_token"]), json={"plan": "free"},
    )
    assert response.status_code == 422  # not a PaidPlan


# ---------------------------------------------------------------------------
#  /billing/portal
# ---------------------------------------------------------------------------

def test_portal_requires_auth(client):
    assert client.post("/billing/portal").status_code == 401


def test_portal_requires_existing_billing_account(client, register_user, monkeypatch):
    _configure_stripe(monkeypatch)
    user = register_user(username="portaluser1")
    response = client.post("/billing/portal", headers=_headers(user["access_token"]))
    assert response.status_code == 400


def test_portal_returns_url_once_customer_exists(client, register_user, monkeypatch):
    _configure_stripe(monkeypatch)
    user = register_user(username="portaluser2")
    with patch("backend.stripe_service.create_customer", return_value="cus_xyz"), \
         patch("backend.stripe_service.create_checkout_session", return_value="https://checkout.stripe.com/pay/cs_test"):
        client.post("/billing/checkout", headers=_headers(user["access_token"]), json={"plan": "pro"})

    with patch("backend.stripe_service.create_portal_session", return_value="https://billing.stripe.com/session/abc") as mock_portal:
        response = client.post("/billing/portal", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    assert response.json()["url"] == "https://billing.stripe.com/session/abc"
    mock_portal.assert_called_once_with(customer_id="cus_xyz")


# ---------------------------------------------------------------------------
#  /billing/webhook
# ---------------------------------------------------------------------------

def _subscription(*, status: str, price_id: str, sub_id: str = "sub_123",
                   customer_id: str = "cus_abc", period_end: int = 1893456000) -> dict:
    return {
        "id": sub_id,
        "customer": customer_id,
        "status": status,
        "current_period_end": period_end,
        "items": {"data": [{"price": {"id": price_id}}]},
    }


def test_webhook_returns_503_when_stripe_not_configured(client):
    response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})
    assert response.status_code == 503


def test_webhook_rejects_bad_signature(client, monkeypatch):
    _configure_stripe(monkeypatch)
    response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=bad"})
    assert response.status_code == 400


def test_checkout_completed_webhook_upgrades_user_to_pro(client, register_user, monkeypatch):
    _configure_stripe(monkeypatch)
    user = register_user(username="webhookuser1")

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_1",
            "client_reference_id": str(user["user"]["id"]),
            "customer": "cus_new",
            "subscription": "sub_new",
        }},
    }
    subscription = _subscription(status="active", price_id="price_pro_123", sub_id="sub_new", customer_id="cus_new")

    with patch("backend.stripe_service.construct_webhook_event", return_value=event), \
         patch("backend.stripe_service.retrieve_subscription", return_value=subscription):
        response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=ok"})
    assert response.status_code == 200

    status_response = client.get("/billing/status", headers=_headers(user["access_token"]))
    body = status_response.json()
    assert body["plan"] == "pro"
    assert body["subscription_status"] == "active"
    assert body["current_period_end"] is not None


def test_subscription_updated_webhook_reflects_premium_upgrade(client, register_user, monkeypatch):
    _configure_stripe(monkeypatch)
    user = register_user(username="webhookuser2")

    # First get the user onto a real Stripe customer id (as checkout would).
    with patch("backend.stripe_service.create_customer", return_value="cus_mid"), \
         patch("backend.stripe_service.create_checkout_session", return_value="https://checkout.stripe.com/x"):
        client.post("/billing/checkout", headers=_headers(user["access_token"]), json={"plan": "pro"})

    event = {
        "type": "customer.subscription.updated",
        "data": {"object": _subscription(status="active", price_id="price_premium_456", customer_id="cus_mid")},
    }
    with patch("backend.stripe_service.construct_webhook_event", return_value=event):
        response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=ok"})
    assert response.status_code == 200

    body = client.get("/billing/status", headers=_headers(user["access_token"])).json()
    assert body["plan"] == "premium"


def test_subscription_deleted_webhook_downgrades_to_free(client, register_user, monkeypatch):
    _configure_stripe(monkeypatch)
    user = register_user(username="webhookuser3")

    with patch("backend.stripe_service.create_customer", return_value="cus_del"), \
         patch("backend.stripe_service.create_checkout_session", return_value="https://checkout.stripe.com/x"):
        client.post("/billing/checkout", headers=_headers(user["access_token"]), json={"plan": "pro"})

    activate_event = {
        "type": "customer.subscription.updated",
        "data": {"object": _subscription(status="active", price_id="price_pro_123", customer_id="cus_del")},
    }
    with patch("backend.stripe_service.construct_webhook_event", return_value=activate_event):
        client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=ok"})
    assert client.get("/billing/status", headers=_headers(user["access_token"])).json()["plan"] == "pro"

    delete_event = {
        "type": "customer.subscription.deleted",
        "data": {"object": _subscription(status="canceled", price_id="price_pro_123", customer_id="cus_del")},
    }
    with patch("backend.stripe_service.construct_webhook_event", return_value=delete_event):
        response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=ok"})
    assert response.status_code == 200

    body = client.get("/billing/status", headers=_headers(user["access_token"])).json()
    assert body["plan"] == "free"
    assert body["subscription_status"] == "canceled"


def test_payment_failed_webhook_resyncs_from_live_subscription_state(client, register_user, monkeypatch):
    _configure_stripe(monkeypatch)
    user = register_user(username="webhookuser4")

    with patch("backend.stripe_service.create_customer", return_value="cus_fail"), \
         patch("backend.stripe_service.create_checkout_session", return_value="https://checkout.stripe.com/x"):
        client.post("/billing/checkout", headers=_headers(user["access_token"]), json={"plan": "premium"})

    activate_event = {
        "type": "customer.subscription.updated",
        "data": {"object": _subscription(status="active", price_id="price_premium_456", customer_id="cus_fail", sub_id="sub_fail")},
    }
    with patch("backend.stripe_service.construct_webhook_event", return_value=activate_event):
        client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=ok"})

    invoice_event = {
        "type": "invoice.payment_failed",
        "data": {"object": {"customer": "cus_fail", "subscription": "sub_fail"}},
    }
    past_due_subscription = _subscription(
        status="past_due", price_id="price_premium_456", customer_id="cus_fail", sub_id="sub_fail",
    )
    with patch("backend.stripe_service.construct_webhook_event", return_value=invoice_event), \
         patch("backend.stripe_service.retrieve_subscription", return_value=past_due_subscription):
        response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=ok"})
    assert response.status_code == 200

    body = client.get("/billing/status", headers=_headers(user["access_token"])).json()
    assert body["subscription_status"] == "past_due"
    # past_due is not active/trialing — the cached plan falls back to free
    # rather than keeping the user on a paid plan a failed invoice no
    # longer actually backs.
    assert body["plan"] == "free"


def test_unresolvable_customer_in_webhook_is_ignored_not_500(client, monkeypatch):
    _configure_stripe(monkeypatch)
    event = {
        "type": "customer.subscription.updated",
        "data": {"object": _subscription(status="active", price_id="price_pro_123", customer_id="cus_unknown")},
    }
    with patch("backend.stripe_service.construct_webhook_event", return_value=event):
        response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=ok"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
#  plan_from_price_id — pure mapping, exercised directly
# ---------------------------------------------------------------------------

def test_plan_from_price_id_maps_configured_prices(monkeypatch):
    _configure_stripe(monkeypatch)
    assert stripe_service.plan_from_price_id("price_pro_123") == "pro"
    assert stripe_service.plan_from_price_id("price_premium_456") == "premium"
    assert stripe_service.plan_from_price_id("price_unknown") is None
    assert stripe_service.plan_from_price_id(None) is None
