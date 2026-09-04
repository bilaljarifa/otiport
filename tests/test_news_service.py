# -*- coding: utf-8 -*-
"""NewsAPI client tests — all HTTP calls are mocked, no real network access
and no real API key required."""

from unittest.mock import MagicMock, patch

import pytest

from backend.news_cache import raw_news_cache
from backend.news_service import NewsServiceError, fetch_news_for_ticker


@pytest.fixture(autouse=True)
def _clear_cache():
    raw_news_cache.clear()
    yield
    raw_news_cache.clear()


def _response(status_code=200, json_body=None, raise_json_error=False):
    resp = MagicMock()
    resp.status_code = status_code
    if raise_json_error:
        resp.json.side_effect = ValueError("bad json")
    else:
        resp.json.return_value = json_body or {}
    return resp


@patch("backend.news_service.news_api_key", return_value="fake-key")
@patch("backend.news_service.requests.get")
def test_valid_api_response_is_normalized(mock_get, _mock_key):
    mock_get.return_value = _response(200, {
        "articles": [{
            "title": "Apple beats earnings",
            "description": "Shares rose.",
            "content": "Full text...",
            "source": {"name": "Reuters"},
            "url": "https://example.com/a",
            "publishedAt": "2026-08-30T10:00:00Z",
        }],
    })
    articles = fetch_news_for_ticker("AAPL_VALID", company_name="Apple")
    assert len(articles) == 1
    assert articles[0]["title"] == "Apple beats earnings"
    assert articles[0]["source"] == "Reuters"


@patch("backend.news_service.news_api_key", return_value="fake-key")
@patch("backend.news_service.requests.get")
def test_empty_response_returns_empty_list_without_raising(mock_get, _mock_key):
    mock_get.return_value = _response(200, {"articles": []})
    assert fetch_news_for_ticker("AAPL_EMPTY") == []


@patch("backend.news_service.news_api_key", return_value=None)
def test_missing_api_key_raises_no_api_key_error(_mock_key):
    with pytest.raises(NewsServiceError) as exc:
        fetch_news_for_ticker("AAPL_NOKEY")
    assert exc.value.kind == "no_api_key"


@patch("backend.news_service.news_api_key", return_value="bad-key")
@patch("backend.news_service.requests.get")
def test_invalid_api_key_raises_invalid_key_error(mock_get, _mock_key):
    mock_get.return_value = _response(401)
    with pytest.raises(NewsServiceError) as exc:
        fetch_news_for_ticker("AAPL_BADKEY")
    assert exc.value.kind == "invalid_key"


@patch("backend.news_service.news_api_key", return_value="fake-key")
@patch("backend.news_service.requests.get")
def test_rate_limit_raises_rate_limit_error(mock_get, _mock_key):
    mock_get.return_value = _response(429)
    with pytest.raises(NewsServiceError) as exc:
        fetch_news_for_ticker("AAPL_RATELIMIT")
    assert exc.value.kind == "rate_limit"


@patch("backend.news_service.news_api_key", return_value="fake-key")
@patch("backend.news_service.requests.get")
def test_api_error_status_raises_unavailable(mock_get, _mock_key):
    mock_get.return_value = _response(500)
    with pytest.raises(NewsServiceError) as exc:
        fetch_news_for_ticker("AAPL_500")
    assert exc.value.kind == "unavailable"
