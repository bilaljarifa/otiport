# -*- coding: utf-8 -*-
"""In-process TTL caches for market/pricing data fetched from Yahoo Finance.

Public, non-user-specific data only — never used for portfolio/account data,
which is always computed fresh per request from the database (see
`backend/crud.py`). Sharing these across every caller (including different
users) is intentional and safe: two users asking about the same ETF get the
same market price, which is exactly what should happen.

Three separate caches, sized to what they hold:
- `price_history_cache` — the long (since-2010) daily-close history used by
  forecasting/optimization (`backend/forecaster.py`). Expensive to fetch,
  changes at most once a trading day, so a 60s TTL only ever saves *redundant*
  re-fetches within the same short burst of activity (a slider tweak, two
  users requesting the same universe back to back) — it does not make the
  data meaningfully stale.
- `last_price_cache` — the "last known price" used for order fills and
  settlement (`backend/pricing.py`). Short TTL (15s) since this feeds
  trading decisions: long enough to absorb the settle-on-every-request
  pattern and concurrent requests, short enough that it stays "the last
  known price" in spirit, not a stale one.
- `chart_data_cache` — the YTD / 1y / 6mo series `api.py` derives for
  charting (`get_historical_prices`, `get_normalized_prices`,
  `calculate_ytd_returns`). Same 60s reasoning as price history.
"""

from __future__ import annotations

from backend.ttl_cache import TTLCache

price_history_cache = TTLCache(ttl_seconds=60)
last_price_cache = TTLCache(ttl_seconds=15)
chart_data_cache = TTLCache(ttl_seconds=60)
# `GET /market/quotes` — the REST endpoint any frontend (React included) uses
# for "current price + day change" instead of talking to yfinance directly.
# Short-lived like last_price_cache (this feeds on-screen "live-ish" quotes,
# not trading fills — that's last_price_cache specifically), separate cache
# so the two don't evict each other under different call volumes.
quote_cache = TTLCache(ttl_seconds=20)
# `GET /market/ohlc` — full OHLCV bars for a single ticker (the Markets page
# candlestick chart). Keyed by "TICKER:period" since the series itself
# depends on both. Same 60s reasoning as chart_data_cache — this is
# historical/daily data, not a trading-fill price.
ohlc_cache = TTLCache(ttl_seconds=60)


def cache_key(*parts: object) -> str:
    """Deterministic string key from ticker lists/tuples and scalars."""
    normalized = []
    for part in parts:
        if isinstance(part, (list, tuple, set, frozenset)):
            normalized.append(",".join(sorted(str(p) for p in part)))
        else:
            normalized.append(str(part))
    return "|".join(normalized)
