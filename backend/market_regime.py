# -*- coding: utf-8 -*-
"""Market regime classification — a transparent, non-ML statistical read on
whether the broad market has recently been trending and how volatile it's
been, computed from the same real Yahoo Finance daily closes every other
forecasting/risk module already uses (`backend.forecaster.fetch_etf_data`).

Methodology (deliberately simple and disclosed, not a predictive model):
- Trend: the ticker's trailing `TREND_WINDOW_DAYS`-day cumulative return.
  Above `TREND_THRESHOLD` -> "POSITIVE_TREND", below -threshold ->
  "NEGATIVE_TREND", otherwise "NEUTRAL".
- Volatility: trailing `VOL_WINDOW_DAYS`-day annualized realized volatility
  (rolling std of daily returns * sqrt(252)), compared to its own expanding
  median over the lookback window. Above `VOL_HIGH_MULTIPLIER` times that
  median -> "HIGH_VOLATILITY", otherwise "NORMAL_VOLATILITY".

This never predicts a future regime — it labels *already-observed* price
history using fixed, disclosed thresholds. No parameter here is fit to the
data; the thresholds are round, pre-chosen numbers.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backend.forecaster import fetch_etf_data

TREND_WINDOW_DAYS = 63  # ~1 trading quarter
VOL_WINDOW_DAYS = 21  # ~1 trading month
TREND_THRESHOLD = 0.02  # +/-2% over the trend window
VOL_HIGH_MULTIPLIER = 1.3  # rolling vol > 1.3x its own expanding median

# Real trading days of history fetched for the timeline/median baseline —
# long enough for the expanding volatility median to be meaningful, short
# enough to stay fast.
_LOOKBACK_CALENDAR_DAYS = 400
_MIN_OBSERVATIONS = TREND_WINDOW_DAYS + VOL_WINDOW_DAYS + 20


class MarketRegimeError(ValueError):
    """Raised on insufficient/unavailable price history — never a
    fabricated regime."""


def classify_market_regime(ticker: str = "SPY", timeline_days: int = 180) -> dict:
    ticker = ticker.strip().upper()
    start = (pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=_LOOKBACK_CALENDAR_DAYS)).strftime("%Y-%m-%d")

    try:
        prices = fetch_etf_data([ticker], start)[ticker]
    except (ValueError, KeyError) as exc:
        raise MarketRegimeError(f"Price history unavailable for {ticker}: {exc}")

    prices = prices.dropna()
    if len(prices) < _MIN_OBSERVATIONS:
        raise MarketRegimeError(
            f"Not enough price history for {ticker} to classify a regime "
            f"(need at least {_MIN_OBSERVATIONS} trading days, have {len(prices)})."
        )

    returns = prices.pct_change().dropna()
    cum_return = prices.pct_change(TREND_WINDOW_DAYS)
    rolling_vol = returns.rolling(VOL_WINDOW_DAYS).std() * np.sqrt(252)
    vol_expanding_median = rolling_vol.expanding(min_periods=VOL_WINDOW_DAYS).median()

    valid = cum_return.dropna().index.intersection(rolling_vol.dropna().index).intersection(
        vol_expanding_median.dropna().index
    )
    if len(valid) == 0:
        raise MarketRegimeError(f"Not enough overlapping trend/volatility history for {ticker}.")

    def _trend_label(value: float) -> str:
        if value > TREND_THRESHOLD:
            return "POSITIVE_TREND"
        if value < -TREND_THRESHOLD:
            return "NEGATIVE_TREND"
        return "NEUTRAL"

    def _vol_label(vol: float, median: float) -> str:
        if median > 0 and vol > median * VOL_HIGH_MULTIPLIER:
            return "HIGH_VOLATILITY"
        return "NORMAL_VOLATILITY"

    timeline_dates = valid[-timeline_days:]
    timeline = [
        {
            "date": str(pd.Timestamp(d).date()),
            "trend": _trend_label(float(cum_return.loc[d])),
            "volatility_regime": _vol_label(float(rolling_vol.loc[d]), float(vol_expanding_median.loc[d])),
            "cumulative_return_pct": round(float(cum_return.loc[d]) * 100, 2),
            "annualized_volatility_pct": round(float(rolling_vol.loc[d]) * 100, 2),
        }
        for d in timeline_dates
    ]

    latest_date = valid[-1]
    current_trend = _trend_label(float(cum_return.loc[latest_date]))
    current_vol = _vol_label(float(rolling_vol.loc[latest_date]), float(vol_expanding_median.loc[latest_date]))

    # Max drawdown over the same fetched window — real, not a separate model.
    running_max = prices.cummax()
    drawdown = (prices - running_max) / running_max
    max_drawdown_pct = round(float(drawdown.min()) * 100, 2)

    return {
        "ticker": ticker,
        "as_of": str(pd.Timestamp(latest_date).date()),
        "current_regime": {
            "trend": current_trend,
            "volatility_regime": current_vol,
            "cumulative_return_pct": round(float(cum_return.loc[latest_date]) * 100, 2),
            "annualized_volatility_pct": round(float(rolling_vol.loc[latest_date]) * 100, 2),
        },
        "max_drawdown_pct": max_drawdown_pct,
        "observations": int(len(prices)),
        "timeline": timeline,
        "methodology": {
            "trend_window_days": TREND_WINDOW_DAYS,
            "trend_threshold_pct": TREND_THRESHOLD * 100,
            "volatility_window_days": VOL_WINDOW_DAYS,
            "volatility_high_multiplier": VOL_HIGH_MULTIPLIER,
        },
    }
