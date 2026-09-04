# -*- coding: utf-8 -*-
"""News recency weighting.

Method: exponential decay by age, `weight = 0.5 ** (age_hours / half_life)`.
With the default 6-hour half-life:
  * a news item published now             -> weight ~= 1.00
  * published 6 hours ago                 -> weight ~= 0.50
  * published 24 hours ago (1 day)        -> weight ~= 0.06
  * published 72 hours ago (3 days)       -> weight ~= 0.001

This is deliberately steep: intraday financial news loses relevance fast
because price action typically already reacted to it within hours. The
half-life is a module constant (not hardcoded inline) so it can be tuned in
one place if the aggregation weighting needs adjusting later.
"""

from __future__ import annotations

from datetime import datetime, timezone

HALF_LIFE_HOURS = 6.0

# Below this, a headline is old enough that it should not meaningfully move
# an "overall" sentiment/impact figure, but it is not excluded outright —
# the weight alone (very close to 0) already does that job.
_MIN_WEIGHT = 0.0


def _parse_timestamp(published_at: str | datetime | None) -> datetime | None:
    if published_at is None:
        return None
    if isinstance(published_at, datetime):
        dt = published_at
    else:
        try:
            dt = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def recency_weight(published_at: str | datetime | None, *,
                    now: datetime | None = None,
                    half_life_hours: float = HALF_LIFE_HOURS) -> float:
    """Weight in (0, 1] for a news item published at `published_at`.

    Unparseable or missing timestamps get the minimum weight rather than
    raising or defaulting to "now" — an article we can't date should not be
    treated as fresh.
    """
    dt = _parse_timestamp(published_at)
    if dt is None:
        return _MIN_WEIGHT

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    age_hours = max((reference - dt).total_seconds() / 3600.0, 0.0)
    return 0.5 ** (age_hours / half_life_hours)
