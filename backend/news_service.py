# -*- coding: utf-8 -*-
"""NewsAPI client.

Architecture: `Frontend (Streamlit) -> Backend (FastAPI, this module's callers)
-> NewsService -> NewsAPI`. The Streamlit side never imports this module or
sees `NEWS_API_KEY`; it only calls the FastAPI endpoints declared in `api.py`.

Only `requests` is used (already a dependency) — no NewsAPI SDK needed for
the `/v2/everything` endpoint this module relies on.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from backend.config import news_api_key
from backend.news_cache import raw_news_cache

logger = logging.getLogger(__name__)

NEWS_API_URL = "https://newsapi.org/v2/everything"
REQUEST_TIMEOUT = 10


class NewsServiceError(Exception):
    """Raised for any NewsAPI failure. `kind` lets callers map to a clean
    user-facing message without leaking request/response internals."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind  # "no_api_key" | "invalid_key" | "rate_limit" | "timeout" | "unavailable" | "empty"
        self.message = message


def _company_queries(ticker: str, company_name: str | None) -> list[str]:
    """Query variants tried in order, e.g. for AAPL: "AAPL", "Apple", ...

    Broadest-to-narrowest so the first query with real results wins without
    the caller having to know which phrasing NewsAPI will match.
    """
    queries = [ticker]
    if company_name:
        queries.append(company_name)
        queries.append(f"{company_name} stock")
        queries.append(f"{company_name} earnings")
    return queries


def _normalize_article(raw: dict[str, Any]) -> dict[str, Any]:
    source = raw.get("source") or {}
    return {
        "title": (raw.get("title") or "").strip(),
        "description": (raw.get("description") or "").strip(),
        "content": (raw.get("content") or "").strip(),
        "source": source.get("name") or "Unknown",
        "url": raw.get("url"),
        "publishedAt": raw.get("publishedAt"),
        "urlToImage": raw.get("urlToImage"),
    }


def _call_news_api(*, query: str, language: str, page_size: int,
                    from_date: str | None) -> list[dict[str, Any]]:
    api_key = news_api_key()
    if not api_key:
        raise NewsServiceError("no_api_key", "NEWS_API_KEY is not configured on the server.")

    params: dict[str, Any] = {
        "q": query,
        "language": language,
        "pageSize": page_size,
        "sortBy": "publishedAt",
        "apiKey": api_key,
    }
    if from_date:
        params["from"] = from_date

    try:
        response = requests.get(NEWS_API_URL, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout as exc:
        raise NewsServiceError("timeout", "NewsAPI did not respond in time.") from exc
    except requests.exceptions.RequestException as exc:
        raise NewsServiceError("unavailable", "NewsAPI is unreachable.") from exc

    if response.status_code == 401:
        raise NewsServiceError("invalid_key", "NewsAPI rejected the configured API key.")
    if response.status_code == 429:
        raise NewsServiceError("rate_limit", "NewsAPI rate limit exceeded.")
    if response.status_code >= 400:
        # Never surface response.text verbatim: it can echo back the request
        # (including, in principle, the query) and we want a bounded message.
        raise NewsServiceError("unavailable", f"NewsAPI returned HTTP {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise NewsServiceError("unavailable", "NewsAPI returned a non-JSON response.") from exc

    articles = payload.get("articles") or []
    return [_normalize_article(a) for a in articles]


def fetch_news_for_ticker(
    ticker: str,
    *,
    company_name: str | None = None,
    language: str = "en",
    page_size: int = 20,
    lookback_days: int = 2,
) -> list[dict[str, Any]]:
    """Recent news for a ticker, trying broad-to-narrow query variants.

    Results are de-duplicated by URL/title and cached for ~20 minutes per
    (ticker, company_name, language, page_size) to avoid refetching the same
    window on every page interaction.
    """
    cache_key = f"{ticker}|{company_name}|{language}|{page_size}|{lookback_days}"

    def _fetch() -> list[dict[str, Any]]:
        from_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        seen: dict[str, dict[str, Any]] = {}
        last_error: NewsServiceError | None = None

        for query in _company_queries(ticker, company_name):
            try:
                articles = _call_news_api(
                    query=query, language=language, page_size=page_size, from_date=from_date,
                )
            except NewsServiceError as exc:
                last_error = exc
                continue

            for article in articles:
                key = article["url"] or article["title"]
                if key and key not in seen:
                    seen[key] = article

            if seen:
                break  # a broad query already returned results; no need to narrow further

        if not seen and last_error is not None:
            raise last_error

        return list(seen.values())

    return raw_news_cache.get_or_set(cache_key, _fetch)
