# -*- coding: utf-8 -*-
"""Subscription billing — Stripe Checkout, the Customer Portal, and the
Stripe webhook. The webhook is the *only* authoritative writer of
`User.plan`/`subscription_status`/`current_period_end`: `POST
/billing/checkout` never marks a user as upgraded itself (Checkout can be
abandoned, a card can be declined after redirect, ...) — it only starts a
Stripe Checkout Session and lets Stripe tell this server, via the webhook,
once a subscription actually exists.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend import crud, stripe_service
from backend.config import payment_mode, stripe_configured, stripe_secret_key
from backend.db import get_db
from backend.demo_payments import DemoPaymentError, validate_and_charge
from backend.deps import get_current_user
from backend.models import User
from backend.schemas import (
    BillingStatusResponse,
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    DemoCheckoutRequest,
    PortalSessionResponse,
)
from backend.stripe_service import StripeError

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)


def _status_for(user: User) -> BillingStatusResponse:
    return BillingStatusResponse(
        plan=user.plan,
        subscription_status=user.subscription_status,
        current_period_end=user.current_period_end,
        stripe_configured=stripe_configured(),
        has_billing_account=bool(user.stripe_customer_id),
        payment_mode=payment_mode(),
    )


@router.get("/status", response_model=BillingStatusResponse)
def billing_status(user: User = Depends(get_current_user)) -> BillingStatusResponse:
    return _status_for(user)


@router.post("/demo-checkout", response_model=BillingStatusResponse)
def demo_checkout(
    req: DemoCheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingStatusResponse:
    """The `PAYMENT_MODE=demo` equivalent of Stripe Checkout + its webhook,
    collapsed into one request since there's no external redirect or async
    confirmation to wait on: a passing `validate_and_charge` call *is* the
    simulated payment, and the plan is activated immediately. Refuses to run
    at all outside demo mode, so the two payment paths can never blend."""
    if payment_mode() != "demo":
        raise HTTPException(status_code=400, detail="Demo payment mode is not enabled on this server.")

    try:
        validate_and_charge(
            card_number=req.card_number, exp=req.exp, cvc=req.cvc, cardholder_name=req.cardholder_name,
        )
    except DemoPaymentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    crud.activate_demo_subscription(db, user, req.plan)
    return _status_for(user)


@router.post("/checkout", response_model=CheckoutSessionResponse)
def create_checkout(
    req: CreateCheckoutSessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutSessionResponse:
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Billing is not configured on this server yet.")

    try:
        customer_id = user.stripe_customer_id
        if not customer_id:
            customer_id = stripe_service.create_customer(
                email=user.email, full_name=user.full_name, user_id=user.id,
            )
            crud.set_stripe_customer_id(db, user, customer_id)

        url = stripe_service.create_checkout_session(
            customer_id=customer_id, plan=req.plan, user_id=user.id,
        )
    except StripeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return CheckoutSessionResponse(url=url)


@router.post("/portal", response_model=PortalSessionResponse)
def create_portal(user: User = Depends(get_current_user)) -> PortalSessionResponse:
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Billing is not configured on this server yet.")
    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No billing account yet — subscribe to a plan first.",
        )
    try:
        url = stripe_service.create_portal_session(customer_id=user.stripe_customer_id)
    except StripeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return PortalSessionResponse(url=url)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Not behind `get_current_user` — Stripe is the caller, authenticated
    by the `Stripe-Signature` header instead of a bearer token. Always
    returns 200 for a recognized-but-unhandled or already-applied event so
    Stripe stops retrying; only a bad signature or malformed payload is
    rejected."""
    if not stripe_secret_key():
        raise HTTPException(status_code=503, detail="Billing is not configured on this server yet.")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except StripeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(db, data)
    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        _handle_subscription_change(db, data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db, data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(db, data)
    # Every other event type (invoice.paid, payment_method.attached, ...) is
    # simply acknowledged — this endpoint only cares about the plan itself.

    return {"received": True}


def _user_for_customer(db: Session, customer_id: str | None) -> User | None:
    if not customer_id:
        return None
    user = crud.get_user_by_stripe_customer_id(db, customer_id)
    if user is None:
        logger.warning("Stripe webhook referenced unknown customer id %s", customer_id)
    return user


def _handle_checkout_completed(db: Session, session: dict) -> None:
    subscription_id = session.get("subscription")
    if not subscription_id:
        return  # not a subscription checkout (shouldn't happen — this app only creates that kind)

    user = None
    user_id = (session.get("client_reference_id") or session.get("metadata", {}).get("user_id"))
    if user_id:
        try:
            user = crud.get_user_by_id(db, int(user_id))
        except (TypeError, ValueError):
            user = None
    if user is None:
        user = _user_for_customer(db, session.get("customer"))
    if user is None:
        logger.warning("checkout.session.completed with no resolvable user (session %s)", session.get("id"))
        return

    try:
        subscription = stripe_service.retrieve_subscription(subscription_id)
    except StripeError as exc:
        logger.warning("Could not retrieve subscription %s after checkout: %s", subscription_id, exc)
        return
    crud.apply_subscription_state(db, user, subscription)


def _handle_subscription_change(db: Session, subscription: dict) -> None:
    user = _user_for_customer(db, subscription.get("customer"))
    if user is None:
        return
    crud.apply_subscription_state(db, user, subscription)


def _handle_subscription_deleted(db: Session, subscription: dict) -> None:
    user = _user_for_customer(db, subscription.get("customer"))
    if user is None:
        return
    crud.downgrade_to_free(db, user)


def _handle_payment_failed(db: Session, invoice: dict) -> None:
    """Doesn't guess a status — re-syncs from the subscription's own
    current state, since Stripe's retry schedule means "failed" doesn't
    necessarily mean "canceled" yet (that's its own, separate event)."""
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return
    user = _user_for_customer(db, invoice.get("customer"))
    if user is None:
        return
    try:
        subscription = stripe_service.retrieve_subscription(subscription_id)
    except StripeError as exc:
        logger.warning("Could not retrieve subscription %s after payment failure: %s", subscription_id, exc)
        return
    crud.apply_subscription_state(db, user, subscription)
