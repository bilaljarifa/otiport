# -*- coding: utf-8 -*-
"""The generic TTL cache shared by `backend/news_cache.py` and
`backend/market_cache.py`."""

from __future__ import annotations

import time

from backend.ttl_cache import TTLCache


def test_returns_none_for_unknown_key():
    cache = TTLCache(ttl_seconds=10)
    assert cache.get("missing") is None


def test_set_then_get_round_trips():
    cache = TTLCache(ttl_seconds=10)
    cache.set("k", {"value": 1})
    assert cache.get("k") == {"value": 1}


def test_entry_expires_after_ttl():
    cache = TTLCache(ttl_seconds=0.05)
    cache.set("k", "v")
    assert cache.get("k") == "v"
    time.sleep(0.08)
    assert cache.get("k") is None


def test_get_or_set_only_calls_factory_once_per_ttl_window():
    cache = TTLCache(ttl_seconds=10)
    calls = []

    def factory():
        calls.append(1)
        return "computed"

    assert cache.get_or_set("k", factory) == "computed"
    assert cache.get_or_set("k", factory) == "computed"
    assert len(calls) == 1


def test_clear_removes_every_entry():
    cache = TTLCache(ttl_seconds=10)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
