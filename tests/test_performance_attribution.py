# -*- coding: utf-8 -*-
"""Tests for `backend/performance_attribution.py` — pure-function tests,
no database/network involved (mirrors `test_performance_metrics.py`'s own
style for calculation-only modules)."""

from __future__ import annotations

from backend import performance_attribution as pa


def _tx(type_, ticker, amount):
    return {"type": type_, "ticker": ticker, "amount": amount}


def test_no_trades_is_reported_as_insufficient_history():
    result = pa.compute_attribution([_tx("DEPOSIT", None, 250_000.0)], {})
    assert result["status"] == "insufficient_history"
    assert result["holdings"] == []
    assert result["total_return"] is None


def test_single_open_position_with_positive_contribution():
    transactions = [
        _tx("DEPOSIT", None, 250_000.0),
        _tx("BUY", "PSI", -10_000.0),
    ]
    result = pa.compute_attribution(transactions, {"PSI": 11_500.0})
    assert result["status"] == "ok"
    assert result["total_return"] == 1_500.0  # -10,000 (cost) + 11,500 (current value)
    assert len(result["holdings"]) == 1
    psi = result["holdings"][0]
    assert psi["ticker"] == "PSI"
    assert psi["contribution"] == 1_500.0
    assert psi["is_open_position"] is True
    assert psi["contribution_pct"] == 100.0
    assert result["largest_contributor"]["ticker"] == "PSI"
    assert result["largest_detractor"] is None


def test_single_open_position_with_negative_contribution():
    transactions = [
        _tx("DEPOSIT", None, 250_000.0),
        _tx("BUY", "PSI", -10_000.0),
    ]
    result = pa.compute_attribution(transactions, {"PSI": 8_000.0})
    assert result["total_return"] == -2_000.0
    assert result["largest_contributor"] is None
    assert result["largest_detractor"]["ticker"] == "PSI"


def test_multiple_positions_positive_and_negative_contributors():
    transactions = [
        _tx("DEPOSIT", None, 250_000.0),
        _tx("BUY", "PSI", -10_000.0),
        _tx("BUY", "IYW", -5_000.0),
        _tx("BUY", "RING", -3_000.0),
    ]
    current_values = {"PSI": 12_000.0, "IYW": 4_000.0, "RING": 3_600.0}
    result = pa.compute_attribution(transactions, current_values)

    # PSI: +2000, IYW: -1000, RING: +600 -> total +1600
    assert result["total_return"] == 1_600.0
    by_ticker = {h["ticker"]: h for h in result["holdings"]}
    assert by_ticker["PSI"]["contribution"] == 2_000.0
    assert by_ticker["IYW"]["contribution"] == -1_000.0
    assert by_ticker["RING"]["contribution"] == 600.0
    assert result["largest_contributor"]["ticker"] == "PSI"
    assert result["largest_detractor"]["ticker"] == "IYW"

    # Reconciliation: contributions sum to exactly the total return.
    assert round(sum(h["contribution"] for h in result["holdings"]), 2) == result["total_return"]


def test_closed_position_still_contributes_its_realized_pnl():
    """A fully-sold position (0 current market value) must still show its
    real realized gain/loss — attribution isn't only about open positions."""
    transactions = [
        _tx("DEPOSIT", None, 100_000.0),
        _tx("BUY", "PSI", -5_000.0),
        _tx("SELL", "PSI", 6_200.0),
    ]
    result = pa.compute_attribution(transactions, {})  # no longer held
    psi = next(h for h in result["holdings"] if h["ticker"] == "PSI")
    assert psi["contribution"] == 1_200.0
    assert psi["is_open_position"] is False
    assert psi["market_value"] == 0.0


def test_partial_sell_reflects_remaining_position_plus_realized_gain():
    transactions = [
        _tx("DEPOSIT", None, 100_000.0),
        _tx("BUY", "PSI", -10_000.0),   # bought 100 @ 100
        _tx("SELL", "PSI", 6_600.0),    # sold 60 @ 110 -> realized +600 on those 60
    ]
    # Remaining 40 shares now worth 110 each = 4,400
    result = pa.compute_attribution(transactions, {"PSI": 4_400.0})
    psi = result["holdings"][0]
    # net cash flow = -10,000 + 6,600 = -3,400; + market value 4,400 = 1,000
    assert psi["contribution"] == 1_000.0
    assert psi["is_open_position"] is True


def test_contribution_pct_omitted_when_total_return_is_near_zero():
    transactions = [
        _tx("DEPOSIT", None, 250_000.0),
        _tx("BUY", "PSI", -10_000.0),
    ]
    result = pa.compute_attribution(transactions, {"PSI": 10_000.50})
    assert abs(result["total_return"]) < pa._MIN_TOTAL_RETURN_FOR_PCT
    assert result["holdings"][0]["contribution_pct"] is None


def test_region_contributions_group_by_real_etf_metadata():
    transactions = [
        _tx("DEPOSIT", None, 200_000.0),
        _tx("BUY", "PSI", -10_000.0),   # North America
        _tx("BUY", "RING", -10_000.0),  # Developed Markets
    ]
    result = pa.compute_attribution(transactions, {"PSI": 11_000.0, "RING": 9_500.0})
    regions = {r["region"] for r in result["region_contributions"]}
    assert "North America" in regions
    assert "Developed Markets" in regions
    total_region_contribution = round(sum(r["contribution"] for r in result["region_contributions"]), 2)
    assert total_region_contribution == result["total_return"]


def test_reconciliation_holds_across_many_positions_and_trades():
    """The core mathematical-honesty guarantee: summed holding
    contributions must equal total portfolio return exactly, for an
    arbitrary real-shaped transaction history."""
    transactions = [
        _tx("DEPOSIT", None, 500_000.0),
        _tx("BUY", "PSI", -20_000.0),
        _tx("BUY", "IYW", -15_000.0),
        _tx("SELL", "PSI", 5_000.0),
        _tx("BUY", "RING", -8_000.0),
        _tx("SELL", "RING", 8_500.0),
        _tx("BUY", "GUNR", -12_000.0),
    ]
    current_values = {"PSI": 17_000.0, "IYW": 16_200.0, "GUNR": 11_400.0}
    result = pa.compute_attribution(transactions, current_values)
    assert round(sum(h["contribution"] for h in result["holdings"]), 2) == result["total_return"]
