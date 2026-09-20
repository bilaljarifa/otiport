# -*- coding: utf-8 -*-
"""Account equity-curve reconstruction tests. Market data is mocked at
`backend.portfolio_history`'s own import boundary — these test the
transaction-replay logic itself, not real Yahoo Finance data."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend import portfolio_history as ph


def _tx(type_, ticker, quantity, amount, day):
    return {
        "type": type_, "ticker": ticker, "quantity": quantity, "amount": amount,
        "created_at": datetime(2024, 1, day, tzinfo=timezone.utc),
    }


def test_no_transactions_returns_empty_curve():
    result = ph.compute_account_equity_curve([], {})
    assert result == {"dates": [], "equity": [], "note": "No transaction history yet."}


def test_cash_only_history_is_a_flat_line():
    txs = [_tx("DEPOSIT", None, None, 250_000.0, 1)]
    result = ph.compute_account_equity_curve(txs, {})
    assert result["note"] is None
    assert len(result["equity"]) > 0
    assert all(e == 250_000.0 for e in result["equity"])


def test_buy_transaction_is_reflected_in_the_curve():
    dates = pd.bdate_range("2024-01-01", periods=10, name="Date")
    frame = pd.DataFrame({"PSI": np.linspace(100.0, 110.0, 10)}, index=dates)

    txs = [
        _tx("DEPOSIT", None, None, 250_000.0, 1),
        _tx("BUY", "PSI", 100.0, -10_000.0, 2),
    ]
    with patch("backend.portfolio_history.fetch_etf_data", return_value=frame), \
         patch("backend.portfolio_history.pricing.get_last_prices", return_value={"PSI": 110.0}):
        result = ph.compute_account_equity_curve(txs, {"PSI": 100.0})

    assert result["note"] is None
    # Before the buy: flat at 250,000 (cash only). After: cash - 10,000 + 100*price.
    first_equity = result["equity"][0]
    assert first_equity == pytest.approx(250_000.0)
    last_equity = result["equity"][-1]
    assert last_equity == pytest.approx(240_000.0 + 100 * 110.0)


def test_sell_transaction_reduces_position():
    dates = pd.bdate_range("2024-01-01", periods=5, name="Date")
    frame = pd.DataFrame({"PSI": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=dates)

    txs = [
        _tx("DEPOSIT", None, None, 100_000.0, 1),
        _tx("BUY", "PSI", 50.0, -5_000.0, 1),
        _tx("SELL", "PSI", 20.0, 2_020.0, 3),
    ]
    with patch("backend.portfolio_history.fetch_etf_data", return_value=frame), \
         patch("backend.portfolio_history.pricing.get_last_prices", return_value={"PSI": 104.0}):
        result = ph.compute_account_equity_curve(txs, {"PSI": 30.0})

    final_cash = 100_000.0 - 5_000.0 + 2_020.0
    assert result["equity"][-1] == pytest.approx(final_cash + 30 * 104.0)


def test_curve_never_includes_a_day_before_the_first_transaction():
    """Regression test: `fetch_etf_data` can return a day or two before the
    requested start date depending on trading-calendar alignment — those
    days must be dropped, not shown as a misleading near-zero point before
    the account's first real deposit."""
    dates = pd.bdate_range("2023-12-30", periods=5, name="Date")  # starts 2 days early
    frame = pd.DataFrame({"PSI": [100.0, 100.0, 101.0, 102.0, 103.0]}, index=dates)

    txs = [_tx("DEPOSIT", None, None, 250_000.0, 1)]  # 2024-01-01
    txs.append(_tx("BUY", "PSI", 100.0, -10_000.0, 1))
    with patch("backend.portfolio_history.fetch_etf_data", return_value=frame), \
         patch("backend.portfolio_history.pricing.get_last_prices", return_value={"PSI": 103.0}):
        result = ph.compute_account_equity_curve(txs, {"PSI": 100.0})

    assert all(d >= "2024-01-01" for d in result["dates"])
    assert all(e > 200_000.0 for e in result["equity"])


def test_cash_only_history_on_a_weekend_still_returns_a_flat_line():
    """Regression test: `pd.bdate_range(first_date, today)` returns zero
    business days when a brand-new account's only transaction (today's
    deposit) falls on a Saturday/Sunday — the account must still get a
    valid flat equity curve, not an empty one."""
    saturday = datetime(2024, 1, 6, tzinfo=timezone.utc)  # a real Saturday
    assert saturday.weekday() == 5

    txs = [{
        "type": "DEPOSIT", "ticker": None, "quantity": None, "amount": 250_000.0,
        "created_at": saturday,
    }]
    with patch("backend.portfolio_history._utcnow", return_value=saturday):
        result = ph.compute_account_equity_curve(txs, {})

    assert result["note"] is None
    assert len(result["dates"]) > 0
    assert len(result["equity"]) > 0
    assert result["dates"] == ["2024-01-06"]
    assert all(e == 250_000.0 for e in result["equity"])


def test_cash_only_history_on_a_sunday_still_returns_a_flat_line():
    sunday = datetime(2024, 1, 7, tzinfo=timezone.utc)
    assert sunday.weekday() == 6

    txs = [{
        "type": "DEPOSIT", "ticker": None, "quantity": None, "amount": 100_000.0,
        "created_at": sunday,
    }]
    with patch("backend.portfolio_history._utcnow", return_value=sunday):
        result = ph.compute_account_equity_curve(txs, {})

    assert result["note"] is None
    assert result["dates"] == ["2024-01-07"]
    assert all(e == 100_000.0 for e in result["equity"])


def test_cash_only_history_spanning_a_weekend_still_uses_business_days():
    """When the span *does* contain a business day, behavior is unchanged —
    the weekend fallback must not kick in and start including weekend days
    that were never part of the original range."""
    friday = datetime(2024, 1, 5, tzinfo=timezone.utc)
    monday = datetime(2024, 1, 8, tzinfo=timezone.utc)
    assert friday.weekday() == 4 and monday.weekday() == 0

    txs = [{
        "type": "DEPOSIT", "ticker": None, "quantity": None, "amount": 250_000.0,
        "created_at": friday,
    }]
    with patch("backend.portfolio_history._utcnow", return_value=monday):
        result = ph.compute_account_equity_curve(txs, {})

    assert result["dates"] == ["2024-01-05", "2024-01-08"]  # Fri, Mon — no Sat/Sun
    assert all(e == 250_000.0 for e in result["equity"])


def test_market_data_failure_is_reported_not_fabricated():
    txs = [_tx("BUY", "PSI", 10.0, -1000.0, 1)]
    with patch("backend.portfolio_history.fetch_etf_data", side_effect=ValueError("no data")):
        result = ph.compute_account_equity_curve(txs, {"PSI": 10.0})
    assert result["dates"] == []
    assert result["equity"] == []
    assert result["note"] is not None
