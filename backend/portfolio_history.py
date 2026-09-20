# -*- coding: utf-8 -*-
"""Reconstructs the caller's own account equity over time from its real
transaction ledger — the Dashboard's performance chart needs a historical
curve, but the app has never persisted a daily equity snapshot per user.
Rather than fabricate one, this replays the account's actual DEPOSIT/BUY/SELL
transactions (`backend/models.py::Transaction`, already signed so cash
running total is a simple cumulative sum — see `backend/crud.py::_fill`)
against real historical closing prices for whatever tickers were ever held
(`backend/forecaster.py::fetch_etf_data`, the same source used everywhere
else). Every point on the resulting curve is a real reconstructed state of
the real account — never a smoothed or simulated line.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backend import pricing
from backend.forecaster import fetch_etf_data


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_account_equity_curve(transactions: list[dict], current_positions: dict[str, float]) -> dict:
    """`transactions`: chronological list of {type, ticker, quantity, amount,
    created_at} dicts (already the caller's own — the router scopes this,
    never a client-supplied account). `current_positions`: {ticker: quantity}
    from the live `Position` table, used only to sanity-check the replay
    ends where the real account actually is (a transaction-replay bug should
    never silently misreport current holdings).
    """
    if not transactions:
        return {"dates": [], "equity": [], "note": "No transaction history yet."}

    transactions = sorted(transactions, key=lambda t: t["created_at"])
    first_date = transactions[0]["created_at"].date()
    tickers_ever_held = sorted({t["ticker"] for t in transactions if t["ticker"]})

    if not tickers_ever_held:
        # Cash-only history (e.g. just the initial deposit) — a flat line,
        # not fabricated, just genuinely flat.
        cash = sum(t["amount"] for t in transactions)
        today = _utcnow().date()
        dates = pd.bdate_range(first_date, today)
        if len(dates) == 0:
            # `first_date..today` can contain zero business days — e.g. a
            # brand-new account whose only transaction (today's deposit)
            # falls on a Saturday/Sunday. The deposit is still real and must
            # still produce a point rather than an empty curve; fall back to
            # the actual calendar date(s) (never invented ones — `first_date`
            # is always <= `today`, so this is always non-empty) instead of
            # silently reporting no history.
            dates = pd.date_range(first_date, today)
        return {
            "dates": [d.strftime("%Y-%m-%d") for d in dates],
            "equity": [round(cash, 2)] * len(dates),
            "note": None,
        }

    try:
        close_prices = fetch_etf_data(tickers_ever_held, first_date.strftime("%Y-%m-%d"))
    except ValueError:
        return {"dates": [], "equity": [], "note": "Historical price data unavailable for this account's holdings."}

    # `fetch_etf_data` can return a day or two before `first_date` depending
    # on how yfinance aligns the start date to the trading calendar — the
    # account didn't exist yet on those days, so including them would draw a
    # misleading near-zero point before the first real deposit.
    calendar = close_prices.index[close_prices.index.date >= first_date]
    equity_curve = []
    dates_out = []

    # Cumulative cash/position deltas per transaction date, applied in order
    # as the calendar walk reaches each date — O(n_days + n_transactions),
    # not O(n_days * n_transactions).
    tx_idx = 0
    n_tx = len(transactions)
    cash = 0.0
    positions = {t: 0.0 for t in tickers_ever_held}

    for day in calendar:
        day_date = day.date() if hasattr(day, "date") else day
        while tx_idx < n_tx and transactions[tx_idx]["created_at"].date() <= day_date:
            tx = transactions[tx_idx]
            cash += tx["amount"]
            if tx["ticker"] and tx["quantity"]:
                sign = 1.0 if tx["type"] == "BUY" else (-1.0 if tx["type"] == "SELL" else 0.0)
                positions[tx["ticker"]] = positions.get(tx["ticker"], 0.0) + sign * tx["quantity"]
            tx_idx += 1

        market_value = 0.0
        for ticker, qty in positions.items():
            if qty == 0 or ticker not in close_prices.columns:
                continue
            price = close_prices.loc[day, ticker]
            if pd.notna(price):
                market_value += qty * float(price)

        equity_curve.append(round(cash + market_value, 2))
        dates_out.append(day_date.strftime("%Y-%m-%d"))

    # Apply any remaining same-day transactions past the last priced day
    # (e.g. a trade placed today, after which the market hasn't closed yet).
    while tx_idx < n_tx:
        tx = transactions[tx_idx]
        cash += tx["amount"]
        if tx["ticker"] and tx["quantity"]:
            sign = 1.0 if tx["type"] == "BUY" else (-1.0 if tx["type"] == "SELL" else 0.0)
            positions[tx["ticker"]] = positions.get(tx["ticker"], 0.0) + sign * tx["quantity"]
        tx_idx += 1

    # Append "right now" using live prices (the same source Dashboard/Portfolio
    # already use) so the chart's last point matches the on-screen current
    # value instead of stopping at the last market close.
    today_str = _utcnow().strftime("%Y-%m-%d")
    if dates_out and dates_out[-1] != today_str:
        live_prices = pricing.get_last_prices([t for t, q in positions.items() if q != 0])
        market_value_now = sum(
            qty * live_prices[ticker] for ticker, qty in positions.items()
            if qty != 0 and ticker in live_prices
        )
        # Fall back to the last known close for any ticker missing a live
        # price rather than silently under-valuing the position.
        for ticker, qty in positions.items():
            if qty != 0 and ticker not in live_prices and ticker in close_prices.columns:
                last_close = close_prices[ticker].ffill().iloc[-1]
                if pd.notna(last_close):
                    market_value_now += qty * float(last_close)
        equity_curve.append(round(cash + market_value_now, 2))
        dates_out.append(today_str)

    return {"dates": dates_out, "equity": equity_curve, "note": None}
