# -*- coding: utf-8 -*-
"""Pydantic request/response models for auth, admin and portfolio endpoints.

Kept separate from `api.py`'s inline models (which cover the stateless
forecast/optimize/news surface) purely to keep that already-large file from
growing further — same `BaseModel`/`Field` style throughout.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

Role = Literal["user", "admin"]
Side = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]
OrderStatus = Literal["OPEN", "FILLED", "CANCELLED", "REJECTED"]
AlertDirection = Literal["above", "below"]
AlertStatus = Literal["ACTIVE", "TRIGGERED"]


# ---------------------------------------------------------------------------
#  Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=120)

    @field_validator("username")
    @classmethod
    def _valid_username(cls, v: str) -> str:
        v = v.strip()
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "3 à 32 caractères : lettres, chiffres, points, tirets ou underscores."
            )
        return v

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Adresse e-mail invalide.")
        return v.lower()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

    @field_validator("username")
    @classmethod
    def _strip_username(cls, v: str) -> str:
        # A username can never legitimately contain leading/trailing
        # whitespace (see RegisterRequest._valid_username) — trimming it
        # here means an accidental space from copy-paste or browser autofill
        # never turns into a spurious "wrong username or password".
        return v.strip()


class GoogleAuthRequest(BaseModel):
    code: str = Field(..., min_length=1)
    redirect_uri: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    job_title: str
    desk: str
    role: Role
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=120)
    job_title: Optional[str] = Field(None, max_length=120)
    desk: Optional[str] = Field(None, max_length=120)


# ---------------------------------------------------------------------------
#  Admin
# ---------------------------------------------------------------------------

class UpdateUserRoleRequest(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
#  Billing
# ---------------------------------------------------------------------------

Plan = Literal["free", "pro", "premium"]
PaidPlan = Literal["pro", "premium"]


class CreateCheckoutSessionRequest(BaseModel):
    plan: PaidPlan


class CheckoutSessionResponse(BaseModel):
    url: str


class PortalSessionResponse(BaseModel):
    url: str


PaymentMode = Literal["demo", "stripe"]


class BillingStatusResponse(BaseModel):
    plan: Plan
    subscription_status: Optional[str] = None
    current_period_end: Optional[datetime] = None
    stripe_configured: bool
    has_billing_account: bool
    payment_mode: PaymentMode


class DemoCheckoutRequest(BaseModel):
    """Simulated card details for `PAYMENT_MODE=demo` — validated and then
    discarded by `backend/demo_payments.py`; never persisted or logged.
    Format-checked here so a malformed request never even reaches that
    validation (a genuinely wrong-but-well-formed value, like a card number
    that isn't the demo one, is `demo_payments`'s job to reject, not this
    schema's)."""

    plan: PaidPlan
    card_number: str = Field(..., min_length=8, max_length=32)
    exp: str = Field(..., min_length=4, max_length=5)
    cvc: str = Field(..., min_length=3, max_length=4)
    cardholder_name: str = Field(..., min_length=1, max_length=120)


class SystemStats(BaseModel):
    total_users: int
    active_users: int
    disabled_users: int
    admin_users: int
    total_accounts: int
    total_cash: float
    total_orders: int
    total_open_orders: int
    backend_version: str


# ---------------------------------------------------------------------------
#  Portfolio
# ---------------------------------------------------------------------------

class AccountOut(BaseModel):
    cash: float
    initial_cash: float
    created_at: datetime

    model_config = {"from_attributes": True}


class PositionOut(BaseModel):
    ticker: str
    quantity: float
    avg_price: float

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    ticker: str
    side: Side
    quantity: float
    type: OrderType
    limit_price: Optional[float]
    status: OrderStatus
    fill_price: Optional[float]
    reject_reason: Optional[str]
    created_at: datetime
    filled_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PlaceOrderRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    side: Side
    quantity: float = Field(..., gt=0)
    order_type: OrderType = "MARKET"
    limit_price: Optional[float] = Field(None, gt=0)

    @field_validator("ticker")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class TransactionOut(BaseModel):
    id: int
    type: str
    ticker: Optional[str]
    quantity: Optional[float]
    price: Optional[float]
    amount: float
    note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchlistOut(BaseModel):
    tickers: list[str]


class AddAlertRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    direction: AlertDirection
    threshold: float = Field(..., gt=0)
    note: str = ""

    @field_validator("ticker")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class AlertOut(BaseModel):
    id: int
    ticker: str
    direction: AlertDirection
    threshold: float
    note: str
    status: AlertStatus
    created_at: datetime
    triggered_at: Optional[datetime]
    triggered_price: Optional[float]

    model_config = {"from_attributes": True}


class PortfolioSummaryOut(BaseModel):
    """Everything `services.store.sync_portfolio()` needs in one response,
    instead of the six separate round trips it used to make on every page
    render. Same data, same per-request DB scoping as the individual
    endpoints below (still user-scoped, still computed fresh every call —
    this response is never cached, only the request count is reduced)."""

    account: AccountOut
    positions: list[PositionOut]
    orders: list[OrderOut]
    transactions: list[TransactionOut]
    watchlist: list[str]
    alerts: list[AlertOut]


# ---------------------------------------------------------------------------
#  AI Assistant
# ---------------------------------------------------------------------------

class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class AssistantChatRequest(BaseModel):
    # Prior turns of the conversation plus the new user message, oldest
    # first — the caller resends the whole visible history each time since
    # this endpoint keeps no server-side conversation state.
    messages: list[AssistantMessage] = Field(..., min_length=1, max_length=20)


class AssistantChatResponse(BaseModel):
    reply: str


class AssistantStatusOut(BaseModel):
    available: bool
    # Additive, backwards-compatible: existing clients that only read
    # `available` are unaffected. Not currently surfaced by the React page
    # (which shows its own static message) — useful for diagnosing *why*
    # over curl/the API directly.
    provider: str | None = None
    reason: str | None = None
