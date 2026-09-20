# -*- coding: utf-8 -*-
"""Simulated payment validation for `PAYMENT_MODE=demo` — a stand-in for
Stripe Checkout when a real Stripe account isn't available (e.g. this PFE
demo's Morocco-based account), so the Pricing → Checkout → Billing flow can
still be presented convincingly, honestly labeled as a simulation.

No card data is ever persisted or logged: the fields below are validated
against this module's own in-memory rules and then discarded — nothing
here writes them to the database, a log line, or any other durable store.
`backend/routers/billing.py` only ever calls `validate_and_charge`, which
returns `None` on success or raises `DemoPaymentError`; it never returns or
otherwise exposes the fields it was given.

The one "valid" card number is the well-known 4242 4242 4242 4242 test
pattern — reusing that specific number is a deliberate nod to how payment
sandboxes conventionally signal "this is a test card", not a claim that
this integrates with any real payment network.
"""

from __future__ import annotations

import re

DEMO_CARD_NUMBER = "4242424242424242"

_EXP_RE = re.compile(r"^(0[1-9]|1[0-2])/(\d{2})$")
_CVC_RE = re.compile(r"^\d{3,4}$")


class DemoPaymentError(Exception):
    """A demo payment was rejected — always a user-facing-safe message,
    never anything derived from logging the actual input."""


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def validate_and_charge(*, card_number: str, exp: str, cvc: str, cardholder_name: str) -> None:
    """Validates the simulated payment details and "charges" the demo card
    — there is no external call here at all; a passing validation *is* the
    simulated charge. Raises `DemoPaymentError` with a clear, presentable
    reason on any failure."""
    if not cardholder_name.strip():
        raise DemoPaymentError("Enter the cardholder name.")

    number = _digits_only(card_number)
    if len(number) < 13 or len(number) > 19:
        raise DemoPaymentError("Enter a valid card number.")
    if number != DEMO_CARD_NUMBER:
        raise DemoPaymentError(
            "This demo only accepts the demo card 4242 4242 4242 4242 — no other card number is valid here."
        )

    if not _EXP_RE.match(exp.strip()):
        raise DemoPaymentError("Enter the expiry date as MM/YY.")

    if not _CVC_RE.match(cvc.strip()):
        raise DemoPaymentError("Enter a valid 3 or 4 digit CVC.")
