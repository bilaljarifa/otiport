# -*- coding: utf-8 -*-
"""Return/risk statistics for an equity curve (a plain array of portfolio
values over time). Shared by `backend/backtester.py` (a simulated strategy's
curve) and `backend/risk.py` (the risk profile of the user's *current*
holdings, replayed over trailing historical returns) — one formula for
total/annualized return, volatility, Sharpe and max drawdown, not two.
"""

from __future__ import annotations

import numpy as np


class InsufficientHistoryError(ValueError):
    """Raised when an equity curve has too few points to compute statistics
    from — never silently returns a fabricated zero."""


def curve_stats(equity: np.ndarray, risk_free_rate: float = 0.0) -> dict:
    """Total/annualized return, annualized volatility, Sharpe ratio and max
    drawdown for a chronological equity curve. `equity` must have at least
    2 points (one return observation)."""
    if len(equity) < 2:
        raise InsufficientHistoryError(
            "Not enough data points to compute equity-curve statistics (need at least 2)."
        )

    daily_returns = np.diff(equity) / equity[:-1]
    n_days = len(equity) - 1

    total_return = equity[-1] / equity[0] - 1
    annualized_return = (equity[-1] / equity[0]) ** (252 / n_days) - 1 if n_days > 0 else 0.0
    annualized_vol = float(np.std(daily_returns, ddof=1)) * np.sqrt(252) if len(daily_returns) > 1 else 0.0
    sharpe = (annualized_return - risk_free_rate) / annualized_vol if annualized_vol > 0 else 0.0

    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max
    max_drawdown = float(drawdown.min())

    return {
        "total_return_pct": float(total_return * 100),
        "annualized_return_pct": float(annualized_return * 100),
        "annualized_volatility_pct": float(annualized_vol * 100),
        "sharpe_ratio": float(sharpe),
        "max_drawdown_pct": float(max_drawdown * 100),
        "trading_days": int(n_days),
    }


def historical_var_cvar(daily_returns: np.ndarray, confidence: float = 0.95) -> dict:
    """Non-parametric (historical) 1-day Value at Risk and Conditional
    VaR / Expected Shortfall, as a fraction of portfolio value (negative =
    a loss). Uses the empirical distribution of `daily_returns` directly —
    no assumption of normality.
    """
    if len(daily_returns) < 20:
        raise InsufficientHistoryError(
            "Not enough daily observations for a historical VaR estimate (need at least 20)."
        )
    var_pct = float(np.percentile(daily_returns, (1 - confidence) * 100))
    tail = daily_returns[daily_returns <= var_pct]
    cvar_pct = float(tail.mean()) if len(tail) > 0 else var_pct
    return {
        "confidence": confidence,
        "var_pct": var_pct * 100,
        "cvar_pct": cvar_pct * 100,
        "observations": int(len(daily_returns)),
    }
