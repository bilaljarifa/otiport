# -*- coding: utf-8 -*-
"""In-process TTL cache instances used by the news pipeline.

The project has no database for news — portfolio/order state lives in a real
database (see `backend/models.py`), but news is deliberately kept out of it
(see README) and cached in-memory instead, the same "in-memory, per process"
philosophy `backend/market_cache.py` uses for market/pricing data. Avoids
re-hitting NewsAPI for the same query within a short window (default 20
minutes, within the 15-30 min range requested).

This is intentionally simple and process-local: it resets on API restart and
is not shared across workers. That is an accepted limitation, documented in
the README, not an oversight.
"""

from __future__ import annotations

from backend.ttl_cache import TTLCache

_DEFAULT_TTL_SECONDS = 20 * 60

# Shared caches, one per resource kind so a clear() on one doesn't wipe another.
raw_news_cache = TTLCache(ttl_seconds=_DEFAULT_TTL_SECONDS)
analyzed_news_cache = TTLCache(ttl_seconds=_DEFAULT_TTL_SECONDS)
