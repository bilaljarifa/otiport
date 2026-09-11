# -*- coding: utf-8 -*-
"""Tiny in-process TTL cache, shared by every backend module that needs one
(news pipeline, market/pricing data). Intentionally simple and process-local:
resets on API restart, not shared across workers — same accepted tradeoff
already documented for the news cache.

Only ever used for public, non-user-specific data (market prices, news).
Nothing user-owned is ever cached through this — see `backend/crud.py` and
`backend/routers/portfolio.py`, which always compute a user's own portfolio
fresh from the database on every request.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Callable


class TTLCache:
    def __init__(self, ttl_seconds: float) -> None:
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
