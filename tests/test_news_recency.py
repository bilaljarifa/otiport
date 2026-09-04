# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

from backend.news_recency import recency_weight


def test_just_published_has_weight_close_to_one():
    now = datetime.now(timezone.utc)
    weight = recency_weight(now.isoformat(), now=now)
    assert weight == 1.0


def test_weight_at_half_life_is_one_half():
    now = datetime.now(timezone.utc)
    published = now - timedelta(hours=6)
    weight = recency_weight(published.isoformat(), now=now, half_life_hours=6.0)
    assert abs(weight - 0.5) < 1e-9


def test_weight_decreases_monotonically_with_age():
    now = datetime.now(timezone.utc)
    fresh = recency_weight((now - timedelta(hours=1)).isoformat(), now=now)
    old = recency_weight((now - timedelta(hours=48)).isoformat(), now=now)
    assert fresh > old
    assert old < 0.01


def test_missing_or_unparseable_timestamp_gets_minimum_weight():
    assert recency_weight(None) == 0.0
    assert recency_weight("not-a-date") == 0.0


def test_future_timestamp_does_not_exceed_max_weight():
    now = datetime.now(timezone.utc)
    weight = recency_weight((now + timedelta(hours=5)).isoformat(), now=now)
    assert weight == 1.0
