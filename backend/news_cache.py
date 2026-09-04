# -*- coding: utf-8 -*-
"""Tiny in-process TTL cache used by the news pipeline.

The project has no database — portfolio/order state lives in Streamlit's
`session_state` (see `services/store.py`), and there is nothing durable to
plug news storage into on the backend side either. Rather than introduce a
new persistence layer for a cache, this reuses the same "in-memory, per
process" philosophy: it avoids re-hitting NewsAPI for the same query within
a short window (default 20 minutes, within the 15-30 min range requested).

This is intentionally simple and process-local: it resets on API restart and
is not shared across workers. That is an accepted limitation, documented in
the README, not an oversight.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Callable

_DEFAULT_TTL_SECONDS = 20 * 60


class TTLCache:
    def __init__(self, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self._ttl, value)

    def get_or_set(self, key: str, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# Shared caches, one per resource kind so a clear() on one doesn't wipe another.
raw_news_cache = TTLCache(ttl_seconds=20 * 60)
analyzed_news_cache = TTLCache(ttl_seconds=20 * 60)
