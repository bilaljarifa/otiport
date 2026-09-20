# -*- coding: utf-8 -*-
"""Performance attribution — "which holdings contributed to my portfolio
performance?" Built entirely from the account's own real transaction
ledger and current mark-to-market prices, the same data
`backend/portfolio_history.py` and `backend/crud.py` already use. This is
deliberately *not* a second portfolio-accounting system: it reads the same
`Transaction` rows and `Position` quantities everything else in the app
reads, and adds no new state of its own.

Methodology (a cash-flow + mark-to-market reconciliation, chosen because
it is exact given the data the app already persists — no point-in-time
historical position valuation is available outside the existing daily
equity-curve reconstruction, so a time-weighted or Brinson-style
attribution is not attempted; see the docstring on `compute_attribution`
for why this method reconciles exactly with total portfolio return):

    contribution(ticker) = net_cash_flow(ticker) + current_market_value(ticker)

where `net_cash_flow` is the signed sum of every BUY/SELL transaction's
`amount` for that ticker (BUY is already stored as a negative amount,
SELL as positive — see `backend/crud.py::_fill`) and `current_market_value`
is 0 for a fully-closed position. Summed over every ticker ever traded,
this equals `current_equity - initial_cash` (total portfolio return)
exactly, because cash itself is just the running sum of every
transaction's amount (deposits + every ticker's net cash flow) plus
today's market value of whatever is still held.

Never fabricates a result: an account with no BUY/SELL transactions ever
has no meaningful "contribution by holding" to report (contribution is
technically defined but degenerate — every value is zero) and gets an
explicit `insufficient_history` status instead.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.etf_metadata import ETF_METADATA

# Below this, a computed contribution-% would be dividing by a
# near-zero total return — mathematically defined but not meaningfully
# interpretable (a $1 contribution against a $2 total return is "50%" in a
# way that says nothing useful). Contribution-% is reported as unavailable
# under this bar; the real dollar contribution is still always shown.
_MIN_TOTAL_RETURN_FOR_PCT = 1.0


def compute_attribution(
    transactions: list[dict[str, Any]],
    current_market_values: dict[str, float],
) -> dict[str, Any]:
    """`transactions`: the account's real ledger, each a dict with at least
    `type` ("DEPOSIT"/"BUY"/"SELL"), `ticker` (or `None` for a deposit),
    and `amount` (already signed). `current_market_values`: {ticker: dollar
    value of the quantity currently held}, 0.0 (or omitted) for a ticker no
    longer held at all — the same real, backend-fetched prices every other
    valuation in the app uses (never client-supplied).
    """
    traded_tickers = sorted({t["ticker"] for t in transactions if t.get("ticker") and t["type"] in ("BUY", "SELL")})

    if not traded_tickers:
        return {
            "status": "insufficient_history",
            "detail": "No buy/sell transactions yet — performance attribution requires at least one trade.",
            "total_return": None,
            "holdings": [],
            "region_contributions": [],
            "largest_contributor": None,
            "largest_detractor": None,
            "methodology": None,
        }

    holdings: list[dict[str, Any]] = []
    total_return = 0.0
    for ticker in traded_tickers:
        net_cash_flow = sum(
            t["amount"] for t in transactions if t.get("ticker") == ticker and t["type"] in ("BUY", "SELL")
        )
        market_value = current_market_values.get(ticker, 0.0) or 0.0
        contribution = round(net_cash_flow + market_value, 2)
        total_return += contribution
        holdings.append({
            "ticker": ticker,
            "contribution": contribution,
            "market_value": round(market_value, 2) if market_value else 0.0,
            "is_open_position": market_value > 1e-9,
        })

    total_return = round(total_return, 2)
    show_pct = abs(total_return) >= _MIN_TOTAL_RETURN_FOR_PCT
    for h in holdings:
        h["contribution_pct"] = round(h["contribution"] / total_return * 100, 1) if show_pct else None

    holdings.sort(key=lambda h: h["contribution"], reverse=True)
    largest_contributor = holdings[0] if holdings[0]["contribution"] > 0 else None
    largest_detractor = holdings[-1] if holdings[-1]["contribution"] < 0 else None

    region_totals: dict[str, float] = {}
    for h in holdings:
        region = ETF_METADATA.get(h["ticker"], {}).get("region", "Other")
        region_totals[region] = region_totals.get(region, 0.0) + h["contribution"]
    region_contributions = [
        {"region": region, "contribution": round(value, 2)}
        for region, value in sorted(region_totals.items(), key=lambda kv: -kv[1])
    ]

    return {
        "status": "ok",
        "detail": None,
        "total_return": total_return,
        "holdings": holdings,
        "region_contributions": region_contributions,
        "largest_contributor": largest_contributor,
        "largest_detractor": largest_detractor,
        "methodology": {
            "method": "cash_flow_plus_mark_to_market",
            "description": (
                "Contribution per ticker = net cash flow from its own buy/sell transactions "
                "+ current market value of whatever quantity is still held. Summed across every "
                "ticker ever traded, this reconciles exactly with total portfolio return."
            ),
            "period": "Since account inception (all-time) — point-in-time position valuation for "
                      "a shorter window is not supported by the existing portfolio accounting model.",
            "contribution_pct_minimum_total_return": _MIN_TOTAL_RETURN_FOR_PCT,
        },
    }
