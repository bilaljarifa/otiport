# -*- coding: utf-8 -*-
"""Stripe API wrapper — Checkout, the Customer Portal, and webhook signature
verification. Mirrors `backend/google_oauth.py`'s shape: this module only
ever talks to Stripe's API, never touches the database (that's
`backend/crud.py`'s job, driven by `backend/routers/billing.py`), and never
lets a raw Stripe error escape as anything other than `StripeError`.

`stripe.api_key` is set lazily on every call rather than once at import time
— `backend.config.stripe_secret_key()` reads the environment fresh each
time, which matters for tests that monkeypatch it per-test.
"""

from __future__ import annotations

from typing import Literal

import stripe

from backend.config import frontend_url, stripe_price_id, stripe_secret_key, stripe_webhook_secret

Plan = Literal["pro", "premium"]


class StripeError(Exception):
    """Anything that goes wrong talking to Stripe, or calling in here before
    Stripe is configured. Always mapped to a generic-enough HTTP error by
    the router — never exposes a raw Stripe error body to the client."""


def _require_api_key() -> None:
    key = stripe_secret_key()
    if not key:
        raise StripeError("Stripe is not configured on this server.")
    stripe.api_key = key


def plan_from_price_id(price_id: str | None) -> str | None:
    """Maps a Stripe Price id back to "pro"/"premium" using this
    deployment's own configured price ids — never trusts a price id's
    nickname/metadata, since only the env-configured ids are ours."""
    if not price_id:
        return None
    if price_id == stripe_price_id("pro"):
        return "pro"
    if price_id == stripe_price_id("premium"):
        return "premium"
    return None


def create_customer(*, email: str, full_name: str, user_id: int) -> str:
    """Creates a new Stripe Customer and returns its id. Called at most once
    per user — the caller persists the id so every later call reuses it."""
    _require_api_key()
    try:
        customer = stripe.Customer.create(
            email=email, name=full_name, metadata={"user_id": str(user_id)},
        )
    except stripe.error.StripeError as exc:
        raise StripeError(str(exc)) from exc
    return customer["id"]


def create_checkout_session(*, customer_id: str, plan: Plan, user_id: int) -> str:
    """Creates a subscription Checkout Session and returns its hosted URL.
    Stripe itself decides which payment methods to offer (card networks,
    Apple Pay, Google Pay, Link, ...) based on the Dashboard's payment
    method configuration — this never hardcodes a method list."""
    _require_api_key()
    price_id = stripe_price_id(plan)
    if not price_id:
        raise StripeError(f"No Stripe price is configured for the '{plan}' plan.")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{frontend_url()}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url()}/billing/cancel",
            client_reference_id=str(user_id),
            metadata={"user_id": str(user_id), "plan": plan},
            subscription_data={"metadata": {"user_id": str(user_id), "plan": plan}},
        )
    except stripe.error.StripeError as exc:
        raise StripeError(str(exc)) from exc
    return session["url"]


def create_portal_session(*, customer_id: str) -> str:
    """Creates a Customer Portal session — the one place a subscriber
    updates their payment method, views invoices, or cancels. Stripe hosts
    all of that; nothing here re-implements it."""
    _require_api_key()
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id, return_url=f"{frontend_url()}/app/billing",
        )
    except stripe.error.StripeError as exc:
        raise StripeError(str(exc)) from exc
    return session["url"]


def retrieve_subscription(subscription_id: str) -> dict:
    """`checkout.session.completed` only carries the subscription *id* — the
    full object (status, current price, period end) needs this extra
    round trip. `customer.subscription.*` events already carry the full
    object and never need this."""
    _require_api_key()
    try:
        return stripe.Subscription.retrieve(subscription_id)
    except stripe.error.StripeError as exc:
        raise StripeError(str(exc)) from exc


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verifies the `Stripe-Signature` header against the raw request body
    — the only thing standing between this endpoint and anyone on the
    internet POSTing a forged "subscription activated" event."""
    secret = stripe_webhook_secret()
    if not secret:
        raise StripeError("Stripe webhook secret is not configured on this server.")
    try:
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise StripeError("Invalid Stripe webhook payload or signature.") from exc
