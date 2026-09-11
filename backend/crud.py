# -*- coding: utf-8 -*-
"""Database operations, including the trading engine.

This is `services/store.py`'s current logic (fills, limit settlement,
rebalance bookkeeping, watchlist, alerts) ported to SQLAlchemy and scoped to
a single account/user per call — every query here is already filtered by
the caller's own `account_id`/`user_id`, so an `Order`/`Alert`/etc. that
belongs to someone else simply cannot be found, let alone mutated. Fill
prices come from `backend.pricing` (server-fetched), never from the caller.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from backend import pricing
from backend.google_oauth import GoogleProfile
from backend.models import Account, Alert, Order, Position, Transaction, User, WatchlistItem
from backend.security import hash_password, verify_password

_USERNAME_CHARS = re.compile(r"[^a-zA-Z0-9_.-]")


class EmailAlreadyRegistered(Exception):
    """A Google sign-in matched an existing local-password account whose
    email Google has not verified — refuse to silently link it rather than
    risk attaching someone else's OAuth identity to an account they don't
    control."""

_DUST = 1.0  # ignore rebalance deltas smaller than this notional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
#  Users
# ---------------------------------------------------------------------------

def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(
    db: Session, *, username: str, email: str, password: str, full_name: str,
    role: str = "user",
) -> User:
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.flush()  # assign user.id

    account = Account(user_id=user.id)
    db.add(account)
    db.flush()

    db.add(Transaction(
        account_id=account.id, type="DEPOSIT", amount=account.initial_cash,
        note="Dotation initiale du compte simulé",
    ))
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def get_user_by_google_sub(db: Session, google_sub: str) -> User | None:
    return db.query(User).filter(User.google_sub == google_sub).first()


def _unique_username_from_email(db: Session, email: str) -> str:
    base = _USERNAME_CHARS.sub("", email.split("@")[0])[:28] or "user"
    if len(base) < 3:
        base = (base + "user")[:28]
    candidate = base
    suffix = 2
    while get_user_by_username(db, candidate) is not None:
        candidate = f"{base}{suffix}"[:32]
        suffix += 1
    return candidate


def get_or_create_google_user(db: Session, profile: GoogleProfile) -> User:
    """Find the user for a verified Google identity, linking or creating an
    account as needed. New accounts get a random, never-shared password
    hash (see `User.google_sub`'s docstring) and the same $250,000
    simulated account every registration gets (`create_user`)."""
    existing = get_user_by_google_sub(db, profile.sub)
    if existing is not None:
        return existing

    by_email = get_user_by_email(db, profile.email)
    if by_email is not None:
        if not profile.email_verified:
            raise EmailAlreadyRegistered(
                "This email is already registered. Log in with your password instead."
            )
        by_email.google_sub = profile.sub
        db.commit()
        db.refresh(by_email)
        return by_email

    username = _unique_username_from_email(db, profile.email)
    user = create_user(
        db, username=username, email=profile.email,
        password=secrets.token_urlsafe(32), full_name=profile.full_name,
    )
    user.google_sub = profile.sub
    db.commit()
    db.refresh(user)
    return user


def update_profile(
    db: Session, user: User, *, full_name: str | None = None,
    job_title: str | None = None, desk: str | None = None,
) -> User:
    if full_name is not None:
        user.full_name = full_name
    if job_title is not None:
        user.job_title = job_title
    if desk is not None:
        user.desk = desk
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
#  Admin
# ---------------------------------------------------------------------------

def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at).all()


def update_user_role(
    db: Session, target: User, *, role: str | None = None, is_active: bool | None = None,
) -> User:
    if role is not None:
        target.role = role
    if is_active is not None:
        target.is_active = is_active
    db.commit()
    db.refresh(target)
    return target


def delete_user(db: Session, target: User) -> None:
    db.delete(target)
    db.commit()


def system_stats(db: Session) -> dict:
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active.is_(True)).count()
    admin_users = db.query(User).filter(User.role == "admin").count()
    total_accounts = db.query(Account).count()
    total_cash = sum((a.cash for a in db.query(Account).all()), 0.0)
    total_orders = db.query(Order).count()
    total_open_orders = db.query(Order).filter(Order.status == "OPEN").count()
    return {
        "total_users": total_users,
        "active_users": active_users,
        "disabled_users": total_users - active_users,
        "admin_users": admin_users,
        "total_accounts": total_accounts,
        "total_cash": total_cash,
        "total_orders": total_orders,
        "total_open_orders": total_open_orders,
    }


# ---------------------------------------------------------------------------
#  Positions / orders / transactions
# ---------------------------------------------------------------------------

def list_positions(db: Session, account_id: int) -> list[Position]:
    return db.query(Position).filter(Position.account_id == account_id).all()


def list_orders(db: Session, account_id: int) -> list[Order]:
    return (
        db.query(Order).filter(Order.account_id == account_id)
        .order_by(Order.created_at.desc()).all()
    )


def list_transactions(db: Session, account_id: int) -> list[Transaction]:
    return (
        db.query(Transaction).filter(Transaction.account_id == account_id)
        .order_by(Transaction.created_at.desc()).all()
    )


def _get_position(db: Session, account_id: int, ticker: str) -> Position | None:
    return (
        db.query(Position)
        .filter(Position.account_id == account_id, Position.ticker == ticker)
        .first()
    )


def _fill(db: Session, order: Order, price: float) -> None:
    """Apply a fill to cash, positions and the transaction ledger."""
    account = db.get(Account, order.account_id)
    notional = order.quantity * price

    if order.side == "BUY":
        account.cash -= notional
        position = _get_position(db, account.id, order.ticker)
        if position is None:
            position = Position(account_id=account.id, ticker=order.ticker, quantity=0.0, avg_price=0.0)
            db.add(position)
        total_quantity = position.quantity + order.quantity
        position.avg_price = (
            (position.avg_price * position.quantity + notional) / total_quantity
            if total_quantity else 0.0
        )
        position.quantity = total_quantity
    else:
        account.cash += notional
        position = _get_position(db, account.id, order.ticker)
        if position is not None:
            position.quantity -= order.quantity
            if position.quantity <= 1e-9:
                db.delete(position)

    order.status = "FILLED"
    order.fill_price = price
    order.filled_at = _utcnow()

    db.add(Transaction(
        account_id=account.id, type=order.side, ticker=order.ticker,
        quantity=order.quantity, price=price,
        amount=-notional if order.side == "BUY" else notional,
        note=f"{order.type.title()} · ordre #{order.id}",
    ))


def place_order(
    db: Session, account: Account, *, ticker: str, side: str, quantity: float,
    order_type: str = "MARKET", limit_price: float | None = None,
) -> Order:
    order = Order(
        account_id=account.id, ticker=ticker, side=side, quantity=float(quantity),
        type=order_type, limit_price=float(limit_price) if limit_price else None,
        status="OPEN",
    )

    if quantity <= 0:
        order.status, order.reject_reason = "REJECTED", "Quantité invalide"
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    if side == "SELL":
        held = _get_position(db, account.id, ticker)
        held_qty = held.quantity if held else 0.0
        if quantity > held_qty + 1e-9:
            order.status = "REJECTED"
            order.reject_reason = f"Position insuffisante ({held_qty:,.4f} détenus)"
            db.add(order)
            db.commit()
            db.refresh(order)
            return order

    if order_type == "MARKET":
        price = pricing.get_last_price(ticker)
        if not price:
            order.status, order.reject_reason = "REJECTED", "Prix de marché indisponible"
            db.add(order)
            db.commit()
            db.refresh(order)
            return order

        if side == "BUY" and quantity * price > account.cash + 1e-6:
            order.status = "REJECTED"
            order.reject_reason = f"Liquidités insuffisantes ({account.cash:,.2f} disponibles)"
            db.add(order)
            db.commit()
            db.refresh(order)
            return order

        db.add(order)
        db.flush()  # assign order.id before _fill records the transaction note
        _fill(db, order, price)
        db.commit()
        db.refresh(order)
        return order

    # LIMIT
    if not limit_price:
        order.status, order.reject_reason = "REJECTED", "Prix limite manquant"
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, account_id: int, order_id: int) -> Order | None:
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.account_id == account_id, Order.status == "OPEN")
        .first()
    )
    if order is None:
        return None
    order.status = "CANCELLED"
    db.commit()
    db.refresh(order)
    return order


def reset_account(db: Session, user: User) -> None:
    """Reset cash/positions/orders/transactions/alerts. Watchlist is kept,
    mirroring the original `services.store.reset_account` behaviour."""
    account = user.account
    account.cash = account.initial_cash

    db.query(Position).filter(Position.account_id == account.id).delete()
    db.query(Order).filter(Order.account_id == account.id).delete()
    db.query(Transaction).filter(Transaction.account_id == account.id).delete()
    db.query(Alert).filter(Alert.user_id == user.id).delete()

    db.add(Transaction(
        account_id=account.id, type="DEPOSIT", amount=account.initial_cash,
        note="Dotation initiale du compte simulé",
    ))
    db.commit()


# ---------------------------------------------------------------------------
#  Watchlist
# ---------------------------------------------------------------------------

def list_watchlist(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id)
        .order_by(WatchlistItem.created_at).all()
    )
    return [row.ticker for row in rows]


def add_watch(db: Session, user_id: int, ticker: str) -> None:
    exists = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user_id, WatchlistItem.ticker == ticker)
        .first()
    )
    if exists is None:
        db.add(WatchlistItem(user_id=user_id, ticker=ticker))
        db.commit()


def remove_watch(db: Session, user_id: int, ticker: str) -> None:
    db.query(WatchlistItem).filter(
        WatchlistItem.user_id == user_id, WatchlistItem.ticker == ticker,
    ).delete()
    db.commit()


# ---------------------------------------------------------------------------
#  Alerts
# ---------------------------------------------------------------------------

def list_alerts(db: Session, user_id: int) -> list[Alert]:
    return (
        db.query(Alert).filter(Alert.user_id == user_id)
        .order_by(Alert.created_at.desc()).all()
    )


def add_alert(
    db: Session, user_id: int, *, ticker: str, direction: str, threshold: float, note: str = "",
) -> Alert:
    alert = Alert(
        user_id=user_id, ticker=ticker, direction=direction,
        threshold=float(threshold), note=note, status="ACTIVE",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def remove_alert(db: Session, user_id: int, alert_id: int) -> bool:
    deleted = (
        db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user_id).delete()
    )
    db.commit()
    return bool(deleted)


def reset_alert(db: Session, user_id: int, alert_id: int) -> Alert | None:
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user_id).first()
    if alert is None:
        return None
    alert.status = "ACTIVE"
    alert.triggered_at = None
    alert.triggered_price = None
    db.commit()
    db.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
#  Settlement — limit orders + alerts against live prices
# ---------------------------------------------------------------------------

def settle(db: Session, user: User) -> None:
    """Match open limit orders and active alerts against fresh prices.

    Mirrors `services.store.settle`, but prices are fetched here (backend
    is authoritative) rather than passed in by the caller.
    """
    account = user.account
    open_orders = (
        db.query(Order).filter(Order.account_id == account.id, Order.status == "OPEN").all()
    )
    active_alerts = (
        db.query(Alert).filter(Alert.user_id == user.id, Alert.status == "ACTIVE").all()
    )

    tickers: set[str] = {o.ticker for o in open_orders} | {a.ticker for a in active_alerts}
    if not tickers:
        return

    prices = pricing.get_last_prices(tickers)
    if not prices:
        return

    for order in open_orders:
        price = prices.get(order.ticker)
        limit = order.limit_price
        if price is None or limit is None:
            continue
        if order.side == "BUY" and price <= limit:
            if order.quantity * price <= account.cash + 1e-6:
                _fill(db, order, min(limit, price))
            else:
                order.status, order.reject_reason = "REJECTED", "Liquidités insuffisantes"
        elif order.side == "SELL" and price >= limit:
            held = _get_position(db, account.id, order.ticker)
            held_qty = held.quantity if held else 0.0
            if order.quantity <= held_qty + 1e-9:
                _fill(db, order, max(limit, price))
            else:
                order.status, order.reject_reason = "REJECTED", "Position insuffisante"

    for alert in active_alerts:
        price = prices.get(alert.ticker)
        if price is None:
            continue
        crossed = price >= alert.threshold if alert.direction == "above" else price <= alert.threshold
        if crossed:
            alert.status = "TRIGGERED"
            alert.triggered_at = _utcnow()
            alert.triggered_price = price

    db.commit()
