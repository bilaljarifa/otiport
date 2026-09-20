# -*- coding: utf-8 -*-
"""Risk analysis for the user's *current* holdings.

Methodology (documented here so it's also easy to surface verbatim in the
UI): every metric below describes the risk profile of the portfolio's
*current* composition — its weights are held fixed and combined with
trailing 1-year historical daily returns for the tickers actually held
(`backend/forecaster.py::fetch_etf_data`/`compute_covariance_matrix`, the
same data source the optimizer and forecaster use). This is standard
ex-ante/"as-held" portfolio risk analysis, not a replay of the account's
actual trade-by-trade history (that would require a persisted daily equity
snapshot, which this app does not keep) — VaR/Sharpe/volatility here answer
"what would this exact allocation's risk have looked like over the last
year," not "what did this account actually experience," and the API/UI say
so explicitly.

Only the risky (non-cash) sleeve is analyzed: cash carries no price risk,
so folding it into the weights would understate volatility/risk without
adding real information. Cash's share of the account is reported separately
as context.

Reuses, never duplicates: `compute_covariance_matrix` (forecaster.py),
`portfolio_volatility`/`compute_risk_contributions` (optimizer.py),
`curve_stats`/`historical_var_cvar` (performance_metrics.py) — this module
only wires them together and adds the pieces those don't already cover
(beta, correlation matrix, concentration, exposure by region).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from backend.etf_metadata import ETF_METADATA
from backend.forecaster import compute_covariance_matrix, ensure_positive_semidefinite, fetch_etf_data
from backend.optimizer import compute_risk_contributions, portfolio_volatility
from backend.performance_metrics import InsufficientHistoryError, curve_stats, historical_var_cvar

LOOKBACK_DAYS = 365
_MIN_TICKERS_FOR_CORRELATION = 2


class RiskAnalysisError(ValueError):
    """Invalid input or insufficient market history — never a fabricated result."""


def compute_portfolio_risk(
    tickers: list[str],
    dollar_values: list[float],
    cash: float,
    benchmark_ticker: Optional[str] = "SPY",
    risk_free_rate: float = 0.0,
) -> dict:
    """`tickers`/`dollar_values` are the current risky-sleeve holdings
    (same order, current market value each) — the caller (the API route)
    computes these from the user's real positions and live quotes, never
    from a client-supplied guess.
    """
    if len(tickers) != len(dollar_values):
        raise RiskAnalysisError("tickers and dollar_values must be the same length.")

    invested_value = float(sum(dollar_values))
    equity = invested_value + cash
    cash_pct = (cash / equity * 100.0) if equity > 0 else 0.0

    if not tickers or invested_value <= 0:
        return {
            "status": "empty",
            "detail": "No open positions to analyze — place a trade to see risk metrics.",
            "invested_value": invested_value,
            "cash": cash,
            "cash_pct": cash_pct,
        }

    weights = np.array(dollar_values) / invested_value

    start_date = (datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    fetch_universe = sorted(set(tickers) | ({benchmark_ticker} if benchmark_ticker else set()))
    try:
        close_prices = fetch_etf_data(fetch_universe, start_date)
    except ValueError as exc:
        raise RiskAnalysisError(f"Market data unavailable: {exc}")

    cov, returns = compute_covariance_matrix(tickers, close_prices=close_prices[tickers])
    cov = ensure_positive_semidefinite(cov)

    daily_portfolio_returns = returns[tickers].values @ weights
    curve = invested_value * np.concatenate([[1.0], np.cumprod(1 + daily_portfolio_returns)])

    try:
        stats = curve_stats(curve, risk_free_rate)
    except InsufficientHistoryError as exc:
        raise RiskAnalysisError(str(exc))

    var_cvar = None
    try:
        var_cvar = historical_var_cvar(daily_portfolio_returns)
        var_cvar["var_dollar"] = round(var_cvar["var_pct"] / 100 * invested_value, 2)
        var_cvar["cvar_dollar"] = round(var_cvar["cvar_pct"] / 100 * invested_value, 2)
    except InsufficientHistoryError:
        pass  # reported as null — never fabricated from too few observations

    beta = None
    if benchmark_ticker and benchmark_ticker in close_prices.columns:
        bench_returns = close_prices[benchmark_ticker].pct_change().dropna()
        common_idx = returns.index.intersection(bench_returns.index)
        if len(common_idx) >= 20:
            port_aligned = pd.Series(daily_portfolio_returns, index=returns.index).loc[common_idx]
            bench_aligned = bench_returns.loc[common_idx]
            bench_var = float(np.var(bench_aligned, ddof=1))
            if bench_var > 0:
                beta = float(np.cov(port_aligned, bench_aligned, ddof=1)[0, 1] / bench_var)

    herfindahl = float(np.sum(weights ** 2))
    risk_contrib = compute_risk_contributions(weights, cov)
    port_vol = portfolio_volatility(weights, cov)
    risk_contrib_pct = (risk_contrib / port_vol * 100.0) if port_vol > 0 else np.zeros_like(weights)

    positions = []
    for i, ticker in enumerate(tickers):
        positions.append({
            "ticker": ticker,
            "weight_pct": round(float(weights[i]) * 100, 2),
            "market_value": round(float(dollar_values[i]), 2),
            "risk_contribution_pct": round(float(risk_contrib_pct[i]), 2),
        })
    positions.sort(key=lambda p: p["risk_contribution_pct"], reverse=True)

    exposure_by_region: dict[str, float] = {}
    for i, ticker in enumerate(tickers):
        region = ETF_METADATA.get(ticker, {}).get("region", "Other")
        exposure_by_region[region] = exposure_by_region.get(region, 0.0) + float(weights[i]) * 100

    correlation_matrix = None
    if len(tickers) >= _MIN_TICKERS_FOR_CORRELATION:
        corr = returns[tickers].corr()
        correlation_matrix = {
            "tickers": tickers,
            "values": [[round(float(v), 3) for v in row] for row in corr.values],
        }

    return {
        "status": "ok",
        "invested_value": round(invested_value, 2),
        "cash": round(cash, 2),
        "cash_pct": round(cash_pct, 2),
        "lookback_days": LOOKBACK_DAYS,
        "volatility_pct": stats["annualized_volatility_pct"],
        "annualized_return_pct": stats["annualized_return_pct"],
        "sharpe_ratio": stats["sharpe_ratio"],
        "max_drawdown_pct": stats["max_drawdown_pct"],
        "var": var_cvar,
        "beta": round(beta, 2) if beta is not None else None,
        "benchmark_ticker": benchmark_ticker,
        "concentration_hhi": round(herfindahl, 4),
        "diversification_score": round(1 - herfindahl, 4),
        "positions": positions,
        "exposure_by_region": [
            {"region": r, "weight_pct": round(pct, 2)}
            for r, pct in sorted(exposure_by_region.items(), key=lambda x: -x[1])
        ],
        "correlation_matrix": correlation_matrix,
        "methodology_notes": [
            "Weights are the portfolio's current holdings, held fixed and combined with the "
            f"trailing {LOOKBACK_DAYS} calendar days of historical daily returns — this describes "
            "the risk of the current allocation as if held over the last year, not a replay of "
            "this account's actual trade history.",
            "Only invested capital (not cash) is included in volatility/VaR/beta/correlation — "
            "cash carries no price risk.",
            "Value at Risk (VaR) and Conditional VaR (Expected Shortfall) are historical "
            "(non-parametric): the empirical 5th percentile of daily portfolio returns, and the "
            "average of returns at or beyond it — no assumption that returns are normally distributed.",
            "Beta is measured against the selected benchmark's daily returns over the same window.",
            "Risk contribution allocates total portfolio volatility across positions by each "
            "position's marginal contribution to variance (Euler decomposition) — it sums to 100%.",
            "Past volatility and returns are not a guarantee of future risk or performance.",
        ],
    }
