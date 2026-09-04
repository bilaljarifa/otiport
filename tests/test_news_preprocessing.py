# -*- coding: utf-8 -*-
from backend.news_preprocessing import (
    build_analysis_text,
    clean_text,
    dedupe_articles,
    is_analyzable,
    preprocess_article,
    preprocess_articles,
)


def test_clean_text_strips_html_and_entities():
    assert clean_text("<b>Apple</b> beats &amp; raises guidance") == "Apple beats & raises guidance"


def test_clean_text_removes_truncation_marker():
    assert clean_text("Apple reported strong sales... [+1234 chars]") == "Apple reported strong sales..."


def test_clean_text_handles_none_and_empty():
    assert clean_text(None) == ""
    assert clean_text("") == ""
    assert clean_text("   ") == ""


def test_build_analysis_text_combines_headline_and_body_without_duplication():
    text = build_analysis_text("Apple beats earnings", "Apple beats earnings")
    assert text == "Apple beats earnings"

    text = build_analysis_text("Apple beats earnings", "Shares rose 5% after the report.")
    assert "Apple beats earnings" in text
    assert "Shares rose 5%" in text


def test_is_analyzable_rejects_too_short_text():
    assert not is_analyzable("Apple")
    assert is_analyzable("Apple beats quarterly earnings estimates")


def test_preprocess_article_drops_empty_title():
    assert preprocess_article({"title": "", "description": "something"}) is None


def test_preprocess_article_drops_too_short_text():
    assert preprocess_article({"title": "Hi", "description": ""}) is None


def test_preprocess_article_keeps_usable_article():
    article = {
        "title": "Apple reports record quarterly earnings",
        "description": "<p>Shares jumped after the report.</p>",
        "content": "Full article body... [+500 chars]",
        "source": "Reuters",
        "url": "https://example.com/a",
        "publishedAt": "2026-08-30T10:00:00Z",
    }
    result = preprocess_article(article)
    assert result is not None
    assert result["title"] == "Apple reports record quarterly earnings"
    assert "jumped" in result["analysis_text"]
    assert "[+500 chars]" not in result["analysis_text"]


def test_dedupe_articles_by_url():
    articles = [
        {"title": "A", "url": "https://x.com/1"},
        {"title": "A duplicate", "url": "https://x.com/1"},
        {"title": "B", "url": "https://x.com/2"},
    ]
    result = dedupe_articles(articles)
    assert len(result) == 2


def test_dedupe_articles_falls_back_to_title_when_no_url():
    articles = [
        {"title": "Same headline", "url": None},
        {"title": "Same headline", "url": ""},
    ]
    assert len(dedupe_articles(articles)) == 1


def test_preprocess_articles_end_to_end_skips_unusable_entries():
    articles = [
        {"title": "Apple reports record quarterly earnings", "description": "Great quarter", "url": "https://x/1"},
        {"title": "", "description": "no title"},
        {"title": "Hi", "description": ""},
    ]
    result = preprocess_articles(articles)
    assert len(result) == 1
    assert result[0]["title"].startswith("Apple")
