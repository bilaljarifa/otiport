# -*- coding: utf-8 -*-
"""News preprocessing.

Pipeline: Raw News -> strip HTML -> clean/normalize text -> combine
headline + description/content -> ready for the sentiment model.

Handles the messy realities of NewsAPI content: missing description, HTML
entities, truncated `content` (NewsAPI cuts it at ~200 chars and appends a
"[+N chars]" marker), duplicate articles, and empty/too-short text.
"""

from __future__ import annotations

import html
import re
from typing import Any

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_TRUNCATION_SUFFIX_RE = re.compile(r"\s*\[\+\d+\s+chars?\]\s*$", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")

MIN_TEXT_LENGTH = 12  # below this, there is nothing meaningful to classify


def strip_html(text: str) -> str:
    if not text:
        return ""
    return _HTML_TAG_RE.sub(" ", text)


def clean_text(text: str | None) -> str:
    """HTML removal + entity decoding + truncation-marker removal + whitespace
    normalization. Never raises: bad input just yields an empty string."""
    if not text:
        return ""
    text = html.unescape(text)
    text = strip_html(text)
    text = _TRUNCATION_SUFFIX_RE.sub("", text)
    text = _URL_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def build_analysis_text(headline: str | None, description: str | None = None,
                         content: str | None = None) -> str:
    """Concatenate headline + best available body text for the sentiment model.

    The headline carries most of the signal for short financial news, so it
    is always included; body text is appended when present so longer context
    (once through the model's truncation) can shift the classification.
    """
    parts = [clean_text(headline)]
    body = clean_text(description) or clean_text(content)
    if body and body.lower() != parts[0].lower():
        parts.append(body)
    return " — ".join(p for p in parts if p)


def is_analyzable(text: str) -> bool:
    return len(text.strip()) >= MIN_TEXT_LENGTH


def dedupe_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicates by URL, falling back to normalized title."""
    seen: set[str] = set()
    result = []
    for article in articles:
        key = (article.get("url") or "").strip().lower() or clean_text(
            article.get("title")
        ).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result


def preprocess_article(article: dict[str, Any]) -> dict[str, Any] | None:
    """Clean one raw NewsAPI article into `{title, description, content,
    source, url, publishedAt, analysis_text}`, or `None` if it carries no
    usable text (empty title, no ticker-relevant content, etc.)."""
    title = clean_text(article.get("title"))
    description = clean_text(article.get("description"))
    content = clean_text(article.get("content"))
    analysis_text = build_analysis_text(title, description, content)

    if not title or not is_analyzable(analysis_text):
        return None

    return {
        "title": title,
        "description": description,
        "content": content,
        "source": article.get("source") or "Unknown",
        "url": article.get("url"),
        "publishedAt": article.get("publishedAt"),
        "analysis_text": analysis_text,
    }


def preprocess_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = dedupe_articles(articles)
    cleaned = (preprocess_article(a) for a in deduped)
    return [a for a in cleaned if a is not None]
