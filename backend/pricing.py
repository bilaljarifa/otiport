# -*- coding: utf-8 -*-
"""Backend-authoritative last-price lookups for order fills and settlement.

The trust boundary this module exists for: a client can no longer supply the
price a MARKET order fills at — the backend fetches it independently via
`yfinance`, the same way `api.py`'s `get_historical_prices` already does for
charting. A client-supplied price is accepted only as a documented,
non-authoritative fallback when the live fetch itself fails.

Prices are cached per-ticker for a short TTL (`backend/market_cache.py`) —
long enough to absorb the settle-on-every-request pattern and concurrent
requests for overlapping tickers, short enough to stay "the last known
price" in spirit. Caching is per-ticker (not per requested set) so two calls
with different, overlapping ticker sets each get cache hits on the overlap
instead of only matching on an identical set.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd
import yfinance as yf

from backend.market_cache import last_price_cache, ohlc_cache, quote_cache


def _fetch_last_prices(tickers: list[str]) -> dict[str, float]:
    """Uncached batch fetch for exactly the given tickers."""
    try:
        data = yf.download(tickers, period="5d", progress=False)
    except Exception:
        return {}

    if data is None or data.empty:
        return {}

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
    else:
        close = data[["Close"]]
        close.columns = tickers

    prices: dict[str, float] = {}
    for ticker in tickers:
        if ticker not in close.columns:
            continue
        series = close[ticker].ffill().dropna()
        if not series.empty:
            prices[ticker] = float(series.iloc[-1])
    return prices


def get_last_prices(tickers: Iterable[str]) -> dict[str, float]:
    """Latest known close for each ticker. Missing/failed tickers are omitted."""
    tickers = sorted({t.upper() for t in tickers})
    if not tickers:
        return {}

    prices: dict[str, float] = {}
    uncached: list[str] = []
    for ticker in tickers:
        cached = last_price_cache.get(ticker)
        if cached is None:
            uncached.append(ticker)
        else:
            prices[ticker] = cached

    if uncached:
        fetched = _fetch_last_prices(uncached)
        for ticker, price in fetched.items():
            last_price_cache.set(ticker, price)
        prices.update(fetched)

    return prices


def get_last_price(ticker: str) -> float | None:
    return get_last_prices([ticker]).get(ticker.upper())


def _fetch_quotes(tickers: list[str]) -> dict[str, dict]:
    """Uncached batch fetch of price + previous close + day change."""
    try:
        data = yf.download(tickers, period="5d", progress=False)
    except Exception:
        return {}

    if data is None or data.empty:
        return {}

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
    else:
        close = data[["Close"]]
        close.columns = tickers

    quotes: dict[str, dict] = {}
    for ticker in tickers:
        if ticker not in close.columns:
            continue
        series = close[ticker].ffill().dropna()
        if series.empty:
            continue
        price = float(series.iloc[-1])
        previous_close = float(series.iloc[-2]) if len(series) >= 2 else price
        change_abs = price - previous_close
        change_pct = (change_abs / previous_close * 100.0) if previous_close else 0.0
        quotes[ticker] = {
            "price": price,
            "previous_close": previous_close,
            "change_abs": change_abs,
            "change_pct": change_pct,
        }
    return quotes


def get_quotes(tickers: Iterable[str]) -> dict[str, dict]:
    """Price + previous close + day change per ticker — the data behind
    `GET /market/quotes`. Same per-ticker cache-then-fetch-the-gap pattern
    as `get_last_prices`, in its own cache (`quote_cache`) since it stores a
    richer shape and serves a different caller (on-screen quotes, not order
    fills)."""
    tickers = sorted({t.upper() for t in tickers})
    if not tickers:
        return {}

    quotes: dict[str, dict] = {}
    uncached: list[str] = []
    for ticker in tickers:
        cached = quote_cache.get(ticker)
        if cached is None:
            uncached.append(ticker)
        else:
            quotes[ticker] = cached

    if uncached:
        fetched = _fetch_quotes(uncached)
        for ticker, quote in fetched.items():
            quote_cache.set(ticker, quote)
        quotes.update(fetched)

    return quotes


_OHLC_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y"}


def _fetch_ohlc(ticker: str, period: str) -> list[dict]:
    """Uncached single-ticker OHLCV fetch — real Yahoo Finance bars, no
    synthetic candles. Empty list on any failure (network, unknown ticker,
    rate limit) rather than raising, matching this module's existing
    fail-soft pattern."""
    try:
        data = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    except Exception:
        return []

    if data is None or data.empty:
        return []

    if isinstance(data.columns, pd.MultiIndex):
        data = data.droplevel(1, axis=1)

    bars: list[dict] = []
    for ts, row in data.iterrows():
        if pd.isna(row.get("Open")) or pd.isna(row.get("Close")):
            continue
        bars.append({
            "time": ts.strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]) if not pd.isna(row.get("Volume")) else 0.0,
        })
    return bars


def get_ohlc(ticker: str, period: str = "6mo") -> list[dict]:
    """Real OHLCV bars for one ticker — the data behind `GET /market/ohlc`
    (Markets page candlestick chart). `period` must be one of
    `_OHLC_PERIODS`; the caller (the API route) validates that before
    calling here."""
    ticker = ticker.upper()
    key = f"{ticker}:{period}"
    cached = ohlc_cache.get(key)
    if cached is not None:
        return cached

    bars = _fetch_ohlc(ticker, period)
    ohlc_cache.set(key, bars)
    return bars
