# -*- coding: utf-8 -*-
"""SQLAlchemy ORM models.

`User` 1—1 `Account` (the simulated paper-trading wallet); `Account` 1—*
`Position` / `Order` / `Transaction`. `WatchlistItem` and `Alert` belong
directly to the user (they are not financial instruments, just preferences).

Every user-owned table carries an indexed foreign key back to its owner and
cascades on delete, so removing a user cleanly removes everything they own.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Always set, even for Google-created accounts: those get a random,
    # never-shared, unusable hash instead of a NULL column — avoids an
    # ALTER TABLE ... to relax a NOT NULL constraint (SQLite can't do that
    # in place) while still making password login correctly impossible for
    # an OAuth-only account.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Google's stable per-account id ("sub" claim). NULL for accounts that
    # have never linked Google. Added via an additive migration in
    # backend/db.py for databases created before this existed.
    google_sub: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    job_title: Mapped[str] = mapped_column(String(120), nullable=False, default="Investisseur")
    desk: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Subscription — Stripe is authoritative for all of this (see
    # backend/routers/billing.py's webhook handler); these columns are a
    # cache of Stripe's own state so every other request can read the
    # user's plan without calling the Stripe API. "free" needs no Stripe
    # objects at all, so a brand-new user has every column below at its
    # default/NULL until they start a checkout for the first time.
    plan: Mapped[str] = mapped_column(String(16), nullable=False, default="free", index=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    # Stripe's own subscription status string (active/trialing/past_due/
    # canceled/unpaid/incomplete/incomplete_expired) — never invented here.
    subscription_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Every authenticated request touches `.account` (see backend/deps.py and
    # backend/routers/portfolio.py) — eager-load it via a JOIN instead of a
    # separate lazy-load query on first access, so each request costs one
    # query instead of two. Pure query-plan change: same rows, same values.
    account: Mapped["Account"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan",
        lazy="joined",
    )
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_users_role_active", "role", "is_active"),)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    cash: Mapped[float] = mapped_column(Float, nullable=False, default=250_000.0)
    initial_cash: Mapped[float] = mapped_column(Float, nullable=False, default=250_000.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="account")
    positions: Mapped[list["Position"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    account: Mapped["Account"] = relationship(back_populates="positions")

    __table_args__ = (UniqueConstraint("account_id", "ticker", name="uq_position_account_ticker"),)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY | SELL
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[str] = mapped_column(String(8), nullable=False)  # MARKET | LIMIT
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="OPEN", index=True)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["Account"] = relationship(back_populates="orders")

    __table_args__ = (Index("ix_orders_account_status", "account_id", "status"),)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # DEPOSIT | BUY | SELL
    ticker: Mapped[str | None] = mapped_column(String(16), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    account: Mapped["Account"] = relationship(back_populates="transactions")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="watchlist_items")

    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # above | below
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped["User"] = relationship(back_populates="alerts")


class TokenBlocklist(Base):
    """Revoked JWT ids (`jti`), so `POST /auth/logout` actually invalidates a
    token instead of relying on the client to discard it."""

    __tablename__ = "token_blocklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
