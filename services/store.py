# -*- coding: utf-8 -*-
"""Session-scoped application state.

Holds UI-only preferences and caches the authenticated user's **paper
trading** account (orders, positions, cash, transaction ledger, watchlist,
alerts) — all of which is now owned by the FastAPI backend + database, keyed
to the signed-in user. Nothing here is a real brokerage account: the account
is explicitly simulated and every screen that shows it says so. Fills happen
server-side against live market prices — this module never invents or
trusts a client-side price.

Every public function below keeps the exact name/signature the rest of the
app already calls (`positions()`, `orders()`, `place_order(...)`,
`toggle_watch(...)`, etc.) — only the implementation changed: instead of
mutating `st.session_state` directly, mutations go through `services.api_client`
and the result is cached in `st.session_state` for the rest of the run, the
same pattern `services.context` already uses for market quotes.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Iterable, Literal, Sequence

import pandas as pd
import streamlit as st

from services import api_client, catalog

# How long a synced portfolio snapshot stays "fresh" before `sync_portfolio()`
# re-fetches it. Streamlit reruns the whole script on *any* widget
# interaction anywhere in the app, not just page navigation — without this,
# `build_context()` (called at the top of every run) was re-fetching the
# entire portfolio, and re-settling open orders/alerts against a fresh
# yfinance call, on every single click, slider drag or text input change.
# A mutation (place_order, cancel_order, toggle_watch, ...) always bypasses
# this and fetches fresh immediately — this TTL only throttles the *passive*
# resync that happens regardless of what the user actually did.
_SYNC_TTL_SECONDS = 5.0

ACCOUNT_MODE = "Paper"
INITIAL_CASH = 250_000.0

Side = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]
OrderStatus = Literal["OPEN", "FILLED", "CANCELLED", "REJECTED"]

DEFAULT_PREFS: dict[str, Any] = {
    "palette": "terminal",
    "density": "comfortable",
    "api_url": "http://localhost:8000",
    "risk_free_rate": 0.05,
    "currency": "USD",
    "default_amount": 100_000,
    "chart_period": "6M",
    "show_signals": True,
}

_EMPTY_USER: dict[str, Any] = {
    "id": None, "username": "", "email": "", "name": "", "initials": "??",
    "role": "", "desk": "", "plan": "", "member_since": "",
    "auth_role": "user", "is_admin": False, "is_active": True,
}

# The three things an unauthenticated visitor can see. Defaults to the public
# landing page — never straight to a login/register form — see `app.py`.
_AUTH_VIEWS = {"landing", "login", "register"}
DEFAULT_AUTH_VIEW = "landing"


# ---------------------------------------------------------------------------
#  Bootstrap
# ---------------------------------------------------------------------------

def init() -> None:
    """Create default state. Safe to call on every run."""
    state = st.session_state
    state.setdefault("prefs", dict(DEFAULT_PREFS))
    state.setdefault("auth_token", None)
    state.setdefault("auth_view", DEFAULT_AUTH_VIEW)
    state.setdefault("user", dict(_EMPTY_USER))
    state.setdefault("watchlist", [])
    state.setdefault("universe", list(catalog.DEFAULT_SELECTION))
    state.setdefault("positions", {})
    state.setdefault("cash", 0.0)
    state.setdefault("orders", [])
    state.setdefault("transactions", [])
    state.setdefault("alerts", [])
    state.setdefault("notifications", [])
    state.setdefault("optimization", None)
    state.setdefault("selected_ticker", catalog.DEFAULT_SELECTION[0])


def _new_notification_id() -> str:
    import uuid
    return uuid.uuid4().hex[:10]


# ---------------------------------------------------------------------------
#  Auth session
# ---------------------------------------------------------------------------

def is_authenticated() -> bool:
    return bool(st.session_state.get("auth_token"))


def auth_view() -> str:
    """Which of the three unauthenticated screens to show: the public
    landing page, or the login/register form (see `views/landing.py`,
    `views/auth.py`). Meaningless once `is_authenticated()` is true."""
    return st.session_state.get("auth_view", DEFAULT_AUTH_VIEW)


def set_auth_view(view: str) -> None:
    st.session_state["auth_view"] = view if view in _AUTH_VIEWS else DEFAULT_AUTH_VIEW


def _initials(full_name: str) -> str:
    parts = [p for p in full_name.split() if p]
    return ("".join(p[0] for p in parts[:2]).upper()) or "OP"


def _apply_user(api_user: dict[str, Any]) -> None:
    """Map the backend's `UserOut` shape onto the dict shape the UI already
    expects from `store.user()` — plus the auth-specific fields (`auth_role`,
    `is_admin`) new call sites (Profile, Admin) read.

    Deliberately distinct from `job_title`: `profile["role"]` has always
    meant a *displayed job title* ("Portfolio Manager"), never the
    authorization role — those two concepts share an unfortunate name in the
    original UI copy, so they're kept on separate keys here.
    """
    role = api_user.get("role", "user")
    created_at = str(api_user.get("created_at", ""))
    st.session_state["user"] = {
        "id": api_user["id"],
        "username": api_user["username"],
        "email": api_user["email"],
        "name": api_user["full_name"],
        "initials": _initials(api_user["full_name"]),
        "role": api_user.get("job_title") or ("Administrateur" if role == "admin" else "Investisseur"),
        "desk": api_user.get("desk") or "",
        "plan": "Administrateur" if role == "admin" else "Standard",
        "member_since": created_at[:4] if created_at else "—",
        "auth_role": role,
        "is_admin": role == "admin",
        "is_active": api_user.get("is_active", True),
    }


def begin_session(token: str, api_user: dict[str, Any]) -> None:
    """Called after a successful register/login."""
    st.session_state["auth_token"] = token
    _apply_user(api_user)


def sign_out() -> None:
    """Revokes the token server-side (best effort) and clears every
    per-account cache. Preferences and the trading `universe` default are
    kept — they're workspace settings, not account data. Returns the visitor
    to the public landing page, not straight to a login form."""
    if st.session_state.get("auth_token"):
        api_client.logout()
    st.session_state["auth_token"] = None
    st.session_state["auth_view"] = DEFAULT_AUTH_VIEW
    st.session_state["user"] = dict(_EMPTY_USER)
    st.session_state["positions"] = {}
    st.session_state["cash"] = 0.0
    st.session_state["orders"] = []
    st.session_state["transactions"] = []
    st.session_state["watchlist"] = []
    st.session_state["alerts"] = []
    st.session_state["notifications"] = []
    st.session_state["optimization"] = None


def _force_signout() -> None:
    """A token was rejected mid-run (expired/revoked/disabled). Clear the
    session and rerun straight into the public landing page."""
    st.session_state["auth_token"] = None
    st.session_state["auth_view"] = DEFAULT_AUTH_VIEW
    st.session_state["user"] = dict(_EMPTY_USER)
    st.rerun()


def user() -> dict[str, Any]:
    return st.session_state.get("user", _EMPTY_USER)


def is_admin() -> bool:
    return bool(user().get("is_admin"))


def update_profile(*, name: str, job_title: str, desk: str) -> None:
    """Persists Profile-page edits via the backend. Raises `api_client.ApiError`
    on failure — the caller (the Profile page) already renders that state."""
    try:
        updated = api_client.update_profile(full_name=name, job_title=job_title, desk=desk)
    except api_client.AuthError:
        _force_signout()
        return
    _apply_user(updated)


# ---------------------------------------------------------------------------
#  Preferences & identity
# ---------------------------------------------------------------------------

def prefs() -> dict[str, Any]:
    return st.session_state["prefs"]


def set_pref(key: str, value: Any) -> None:
    st.session_state["prefs"][key] = value


# ---------------------------------------------------------------------------
#  Portfolio sync — one backend round-trip per Streamlit run
# ---------------------------------------------------------------------------

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _order_from_api(o: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": o["id"], "timestamp": _parse_dt(o["created_at"]), "ticker": o["ticker"],
        "side": o["side"], "quantity": o["quantity"], "type": o["type"],
        "limit_price": o["limit_price"], "status": o["status"],
        "fill_price": o["fill_price"], "filled_at": _parse_dt(o["filled_at"]),
        "reject_reason": o["reject_reason"],
    }


def _transaction_from_api(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": t["id"], "timestamp": _parse_dt(t["created_at"]), "type": t["type"],
        "ticker": t["ticker"], "quantity": t["quantity"], "price": t["price"],
        "amount": t["amount"], "note": t["note"],
    }


def _alert_from_api(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": a["id"], "ticker": a["ticker"], "direction": a["direction"],
        "threshold": a["threshold"], "note": a["note"], "status": a["status"],
        "created_at": _parse_dt(a["created_at"]), "triggered_at": _parse_dt(a["triggered_at"]),
        "triggered_price": a["triggered_price"],
    }


def _notify_fill(order: dict[str, Any]) -> None:
    notify(
        f"Ordre exécuté · {order['side']} {order['quantity']:,.2f} {order['ticker']}",
        f"{order['quantity']:,.2f} @ {order['fill_price']:,.2f} $ — "
        f"{order['quantity'] * order['fill_price']:,.2f} $",
        tone="up" if order["side"] == "BUY" else "warn", icon="check",
    )


def _notify_alert_triggered(alert: dict[str, Any]) -> None:
    arrow = "au-dessus de" if alert["direction"] == "above" else "sous"
    notify(
        f"Alerte {alert['ticker']} déclenchée",
        f"Cours {alert['triggered_price']:,.2f} $ {arrow} {alert['threshold']:,.2f} $",
        tone="warn", icon="alerts",
    )


def _sync_is_fresh() -> bool:
    last = st.session_state.get("_portfolio_synced_at")
    return last is not None and (time.monotonic() - last) < _SYNC_TTL_SECONDS


def sync_portfolio(*, force: bool = False) -> None:
    """Fetch the signed-in user's account snapshot from the backend in a
    single request (`GET /portfolio/summary`). Called once per run (from
    `app.py`, right after `api_client.settle()`), mirroring how
    `services.context` fetches quotes once per run — except this additionally
    skips the round trip entirely when the last sync is still fresh
    (`_SYNC_TTL_SECONDS`), since a plain Streamlit rerun (any widget
    interaction, not just navigating) would otherwise repeat it needlessly.

    `force=True` (used after a mutation — placing an order, cancelling one,
    resetting the account) always fetches, ignoring the TTL: the whole point
    of a mutation is that the previous snapshot is now known-stale.

    Diffs the previous cache against the fresh one to fire the same
    notifications the old client-side `settle()` used to raise locally, now
    that fills/triggers can also happen purely server-side.
    """
    if not force and _sync_is_fresh():
        return

    previous_orders = {o["id"]: o["status"] for o in orders()}
    previous_alerts = {a["id"]: a["status"] for a in alerts()}

    try:
        summary = api_client.get_portfolio_summary()
    except api_client.AuthError:
        _force_signout()
        return
    except api_client.ApiError:
        return  # backend offline — keep whatever was last cached

    st.session_state["cash"] = summary["account"]["cash"]
    st.session_state["positions"] = {
        p["ticker"]: {"quantity": p["quantity"], "avg_price": p["avg_price"]}
        for p in summary["positions"]
    }
    new_orders = [_order_from_api(o) for o in summary["orders"]]
    new_alerts = [_alert_from_api(a) for a in summary["alerts"]]
    st.session_state["orders"] = new_orders
    st.session_state["transactions"] = [_transaction_from_api(t) for t in summary["transactions"]]
    st.session_state["watchlist"] = list(summary["watchlist"])
    st.session_state["alerts"] = new_alerts
    st.session_state["_portfolio_synced_at"] = time.monotonic()

    for order in new_orders:
        if previous_orders.get(order["id"]) == "OPEN" and order["status"] == "FILLED":
            _notify_fill(order)
    for alert in new_alerts:
        if previous_alerts.get(alert["id"]) == "ACTIVE" and alert["status"] == "TRIGGERED":
            _notify_alert_triggered(alert)


# ---------------------------------------------------------------------------
#  Watchlist & universe
# ---------------------------------------------------------------------------

def watchlist() -> list[str]:
    return st.session_state["watchlist"]


def is_watched(ticker: str) -> bool:
    return ticker in st.session_state["watchlist"]


def toggle_watch(ticker: str) -> bool:
    """Add/remove from the watchlist. Returns the new membership state."""
    try:
        if is_watched(ticker):
            st.session_state["watchlist"] = api_client.remove_watch(ticker)
            return False
        st.session_state["watchlist"] = api_client.add_watch(ticker)
        return True
    except api_client.AuthError:
        _force_signout()
        return is_watched(ticker)


def set_watchlist(tickers: Sequence[str]) -> None:
    """Applies a full desired membership (the Watchlist page's multiselect
    "Appliquer" action) as the minimal set of add/remove calls."""
    target = list(dict.fromkeys(tickers))
    current = set(watchlist())
    try:
        for ticker in target:
            if ticker not in current:
                api_client.add_watch(ticker)
        for ticker in current - set(target):
            api_client.remove_watch(ticker)
    except api_client.AuthError:
        _force_signout()
        return
    st.session_state["watchlist"] = api_client.get_watchlist()


def universe() -> list[str]:
    """Tickers currently selected for optimisation."""
    return st.session_state["universe"]


def set_universe(tickers: Sequence[str]) -> None:
    st.session_state["universe"] = list(tickers)


def selected_ticker() -> str:
    return st.session_state["selected_ticker"]


def select_ticker(ticker: str) -> None:
    st.session_state["selected_ticker"] = ticker


# ---------------------------------------------------------------------------
#  Account
# ---------------------------------------------------------------------------

def cash() -> float:
    return float(st.session_state["cash"])


def positions() -> dict[str, dict[str, float]]:
    """`ticker -> {quantity, avg_price}` for non-zero holdings."""
    return st.session_state["positions"]


def orders() -> list[dict[str, Any]]:
    return st.session_state["orders"]


def open_orders() -> list[dict[str, Any]]:
    return [o for o in st.session_state["orders"] if o["status"] == "OPEN"]


def transactions() -> list[dict[str, Any]]:
    return st.session_state["transactions"]


def place_order(
    ticker: str,
    side: Side,
    quantity: float,
    *,
    order_type: OrderType = "MARKET",
    limit_price: float | None = None,
    market_price: float | None = None,
) -> dict[str, Any]:
    """Submit a paper order. `market_price` is accepted only for call-site
    compatibility (the manual order ticket's on-screen estimate) — it is
    never sent to the backend, which fetches its own authoritative fill
    price. Returns the order, whose `status`/`reject_reason` describe the
    outcome, same shape as before."""
    try:
        raw = api_client.place_order(
            ticker, side, quantity, order_type=order_type, limit_price=limit_price,
        )
    except api_client.AuthError:
        _force_signout()
        raise  # unreachable — _force_signout()'s st.rerun() never returns
    except api_client.ApiError as exc:
        return {
            "id": None, "timestamp": datetime.now(), "ticker": ticker, "side": side,
            "quantity": float(quantity), "type": order_type,
            "limit_price": float(limit_price) if limit_price else None,
            "status": "REJECTED", "fill_price": None, "filled_at": None,
            "reject_reason": str(exc),
        }

    order = _order_from_api(raw)
    if order["status"] == "FILLED":
        _notify_fill(order)
    _refresh_trading_state()
    return order


def cancel_order(order_id: str) -> bool:
    if order_id is None:
        return False
    try:
        api_client.cancel_order(order_id)
    except api_client.AuthError:
        _force_signout()
        return False
    except api_client.ApiError:
        return False
    _refresh_trading_state()
    return True


def _refresh_trading_state() -> None:
    """Re-pull the account snapshot after a mutation (place/cancel order,
    reset). Just a forced `sync_portfolio()` — one request via
    `GET /portfolio/summary` instead of separately re-fetching
    account/positions/orders/transactions, and it correctly stamps the sync
    TTL so the very next rerun doesn't immediately re-fetch the data this
    call just got fresh."""
    sync_portfolio(force=True)


# ---------------------------------------------------------------------------
#  Valuation (pure — unchanged from the original client-side implementation)
# ---------------------------------------------------------------------------

def valuation(quotes: pd.DataFrame | None) -> dict[str, Any]:
    """Mark the account to market.

    `quotes` is a `services.market.snapshot()` frame. Returns totals plus a
    per-holding breakdown; missing prices are skipped rather than guessed.
    """
    prices: dict[str, float] = {}
    previous: dict[str, float] = {}
    if quotes is not None and not quotes.empty:
        indexed = quotes.set_index("ticker")
        prices = indexed["price"].to_dict()
        previous = indexed["previous_close"].to_dict()

    holdings: list[dict[str, Any]] = []
    market_value = cost_basis = day_pnl = 0.0

    for ticker, position in positions().items():
        quantity = position["quantity"]
        price = prices.get(ticker)
        avg_price = position["avg_price"]
        cost = quantity * avg_price
        cost_basis += cost

        if price is None:
            holdings.append({
                "ticker": ticker, "quantity": quantity, "avg_price": avg_price,
                "price": None, "market_value": None, "cost": cost,
                "pnl": None, "pnl_pct": None, "day_pnl": None, "weight": None,
            })
            continue

        value = quantity * price
        market_value += value
        prev = previous.get(ticker, price)
        position_day_pnl = quantity * (price - prev)
        day_pnl += position_day_pnl
        holdings.append({
            "ticker": ticker,
            "quantity": quantity,
            "avg_price": avg_price,
            "price": price,
            "market_value": value,
            "cost": cost,
            "pnl": value - cost,
            "pnl_pct": ((value / cost - 1) * 100) if cost else None,
            "day_pnl": position_day_pnl,
            "weight": None,
        })

    equity = market_value + cash()
    for holding in holdings:
        if holding["market_value"] is not None and market_value:
            holding["weight"] = holding["market_value"] / market_value * 100

    pnl = market_value - cost_basis
    invested_yesterday = market_value - day_pnl
    return {
        "equity": equity,
        "cash": cash(),
        "market_value": market_value,
        "cost_basis": cost_basis,
        "pnl": pnl,
        "pnl_pct": (pnl / cost_basis * 100) if cost_basis else 0.0,
        "day_pnl": day_pnl,
        "day_pnl_pct": (day_pnl / invested_yesterday * 100) if invested_yesterday else 0.0,
        "total_return": equity - INITIAL_CASH,
        "total_return_pct": (equity / INITIAL_CASH - 1) * 100,
        "holdings": sorted(
            holdings, key=lambda h: h["market_value"] or 0.0, reverse=True
        ),
        "positions_count": len(holdings),
        "invested_pct": (market_value / equity * 100) if equity else 0.0,
    }


def rebalance_orders(
    allocations: Iterable[dict[str, Any]],
    budget: float,
    quotes: pd.DataFrame | None,
) -> list[dict[str, Any]]:
    """Turn optimiser target weights into a concrete order plan.

    Compares the target notional per ticker with the current holding and emits
    the BUY/SELL deltas. Returns proposals (not submitted orders) so the user
    reviews the plan before it is sent — this stays entirely client-side, it
    only reads already-public quotes and never moves money.
    """
    if quotes is None or quotes.empty:
        return []

    prices = quotes.set_index("ticker")["price"].to_dict()
    book = positions()
    plan: list[dict[str, Any]] = []

    for allocation in allocations:
        ticker = allocation["ticker"]
        weight = float(allocation.get("weight_percent", 0.0))
        price = prices.get(ticker)
        if not price:
            continue

        target_value = budget * weight / 100.0
        current_quantity = book.get(ticker, {}).get("quantity", 0.0)
        delta_quantity = target_value / price - current_quantity
        if abs(delta_quantity * price) < 1.0:      # ignore dust
            continue

        plan.append({
            "ticker": ticker,
            "side": "BUY" if delta_quantity > 0 else "SELL",
            "quantity": abs(round(delta_quantity, 4)),
            "price": price,
            "notional": abs(delta_quantity) * price,
            "target_weight": weight,
        })

    # Sell first so proceeds fund the buys.
    plan.sort(key=lambda item: (item["side"] != "SELL", -item["notional"]))
    return plan


# ---------------------------------------------------------------------------
#  Alerts
# ---------------------------------------------------------------------------

def alerts() -> list[dict[str, Any]]:
    return st.session_state["alerts"]


def add_alert(ticker: str, direction: Literal["above", "below"], threshold: float,
              note: str = "") -> dict[str, Any] | None:
    try:
        raw = api_client.add_alert(ticker, direction, threshold, note)
    except api_client.AuthError:
        _force_signout()
        return None
    except api_client.ApiError:
        return None
    alert = _alert_from_api(raw)
    st.session_state["alerts"] = [alert] + alerts()
    return alert


def remove_alert(alert_id: str) -> None:
    try:
        api_client.remove_alert(alert_id)
    except api_client.AuthError:
        _force_signout()
        return
    except api_client.ApiError:
        return
    st.session_state["alerts"] = [a for a in alerts() if a["id"] != alert_id]


def reset_alert(alert_id: str) -> None:
    try:
        raw = api_client.reset_alert_api(alert_id)
    except api_client.AuthError:
        _force_signout()
        return
    except api_client.ApiError:
        return
    updated = _alert_from_api(raw)
    st.session_state["alerts"] = [
        updated if a["id"] == alert_id else a for a in alerts()
    ]


# ---------------------------------------------------------------------------
#  Notifications (client-side only — not required to persist across sessions)
# ---------------------------------------------------------------------------

def notifications() -> list[dict[str, Any]]:
    return st.session_state["notifications"]


def unread_count() -> int:
    return sum(1 for n in notifications() if not n["read"])


def notify(title: str, body: str = "", *, tone: str = "info", icon: str = "info") -> None:
    st.session_state["notifications"].insert(0, {
        "id": _new_notification_id(),
        "timestamp": datetime.now(),
        "title": title,
        "body": body,
        "tone": tone,
        "icon": icon,
        "read": False,
    })
    del st.session_state["notifications"][40:]


def mark_all_read() -> None:
    for item in notifications():
        item["read"] = True


# ---------------------------------------------------------------------------
#  Settlement — server-side; kept as a thin call so app.py has one entry point
# ---------------------------------------------------------------------------

def settle() -> None:
    """Match open limit orders / active alerts against fresh backend-fetched
    prices. Called from `refresh_portfolio()` below — not throttled itself,
    since its only caller already gates on the same TTL."""
    try:
        api_client.settle()
    except api_client.AuthError:
        _force_signout()
    except api_client.ApiError:
        pass


def refresh_portfolio(*, force: bool = False) -> None:
    """Settle, then sync — the pair `app.py::build_context()` runs once per
    Streamlit run. Gated by the same `_SYNC_TTL_SECONDS` window as
    `sync_portfolio()`: a plain rerun triggered by an unrelated widget
    elsewhere in the app (Streamlit reruns the *entire* script on any
    interaction, not just navigation) skips both the settle and the sync
    round trips entirely when the last refresh is still fresh, instead of
    re-fetching live prices and the whole portfolio snapshot every time.
    """
    if not force and _sync_is_fresh():
        return
    settle()
    sync_portfolio(force=True)


# ---------------------------------------------------------------------------
#  Optimisation result (client-side only — a cached run of the optimiser)
# ---------------------------------------------------------------------------

def set_optimization(result: dict[str, Any], meta: dict[str, Any]) -> None:
    st.session_state["optimization"] = {
        "result": result,
        "meta": {**meta, "ran_at": datetime.now()},
    }


def optimization() -> dict[str, Any] | None:
    return st.session_state.get("optimization")


def clear_optimization() -> None:
    st.session_state["optimization"] = None


# ---------------------------------------------------------------------------
#  Maintenance
# ---------------------------------------------------------------------------

def reset_account() -> None:
    """Reset the simulated account, keeping preferences and watchlist."""
    try:
        api_client.reset_account()
    except api_client.AuthError:
        _force_signout()
        return
    except api_client.ApiError:
        return
    _refresh_trading_state()
    st.session_state["alerts"] = []
    notify("Compte simulé réinitialisé", f"Liquidités remises à {INITIAL_CASH:,.0f} $",
           tone="info", icon="refresh")
