# -*- coding: utf-8 -*-
"""GET /news/{ticker}/analytics — the News Impact Analytics endpoint.
Exercises the real pipeline (NewsAPI call + LSTM-adjacent price fetch mocked
only at their external boundaries) end to end through the API, checking the
response is well-typed and degrades to explicit insufficient-data states
rather than fabricating numbers when the sample is thin."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.news_cache import news_analytics_cache


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_news_analytics_cache():
    news_analytics_cache.clear()
    yield
    news_analytics_cache.clear()


def _raw_article(title, published_at, url, description="A market-moving headline about the company."):
    return {
        "title": title,
        "description": description,
        "content": description,
        "source": "Reuters",
        "url": url,
        "publishedAt": published_at,
        "urlToImage": None,
    }


def test_requires_auth(client):
    response = client.get("/news/SPY/analytics")
    assert response.status_code == 401


@patch("backend.pricing.get_ohlc", return_value=[])
@patch("api.fetch_news_for_ticker", return_value=[])
def test_no_news_degrades_to_explicit_empty_and_insufficient_states(
    mock_fetch, mock_ohlc, client, register_user,
):
    user = register_user(username="alice")
    response = client.get("/news/SPY/analytics", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    body = response.json()

    assert body["ticker"] == "SPY"
    assert body["overview"]["status"] == "empty"
    assert body["overview"]["articles_analyzed"] == 0
    assert body["sentiment_distribution"]["status"] == "empty"
    assert body["sentiment_trend"]["status"] == "insufficient_data"
    assert body["volume_analysis"]["status"] == "insufficient_data"
    assert body["market_impact"]["status"] == "empty"
    assert body["top_news"]["status"] == "empty"
    assert body["news_vs_price"]["status"] == "insufficient_data"
    assert body["impact_history"]["status"] == "insufficient_data"


@patch("backend.pricing.get_ohlc", return_value=[])
@patch("api.fetch_news_for_ticker")
def test_real_articles_produce_a_populated_overview_and_top_news(
    mock_fetch, mock_ohlc, client, register_user,
):
    mock_fetch.return_value = [
        _raw_article(
            "Company beats earnings and raises guidance sharply",
            "2026-09-18T10:00:00Z",
            "https://example.com/article-1",
        ),
        _raw_article(
            "Company announces minor office renovation",
            "2026-09-18T09:00:00Z",
            "https://example.com/article-2",
        ),
    ]
    user = register_user(username="bob")
    response = client.get("/news/IYW/analytics", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    body = response.json()

    assert body["overview"]["status"] == "ok"
    assert body["overview"]["articles_analyzed"] == 2
    assert body["top_news"]["status"] == "ok"
    assert len(body["top_news"]["items"]) == 2
    # Ranked by the existing impact score — the earnings/guidance headline
    # (high materiality keywords) must outrank the low-materiality one.
    assert "earnings" in body["top_news"]["items"][0]["title"].lower()


@patch("backend.pricing.get_ohlc", return_value=[])
@patch("api.fetch_news_for_ticker", return_value=[])
def test_response_never_returns_nan_or_null_in_place_of_a_real_status(
    mock_fetch, mock_ohlc, client, register_user,
):
    user = register_user(username="carol")
    response = client.get("/news/QQQ/analytics", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    body = response.json()
    for section in (
        "overview", "sentiment_distribution", "sentiment_trend", "volume_analysis",
        "market_impact", "top_news", "news_vs_price", "impact_history",
    ):
        assert body[section]["status"] in ("ok", "empty", "insufficient_data")
