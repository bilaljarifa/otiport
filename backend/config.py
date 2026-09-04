# -*- coding: utf-8 -*-
"""Environment configuration for the FastAPI backend.

Secrets (currently: `NEWS_API_KEY`) are read from `.env` (via `python-dotenv`)
or the process environment and never leave this module as a bare string
outside of the one function that hands it to the NewsAPI HTTP client. Nothing
here logs, prints, or returns the key — `api.py` must never place it in a
response body.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is in requirements.txt
    load_dotenv = None

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

if load_dotenv is not None:
    load_dotenv(_ENV_PATH)


def news_api_key() -> str | None:
    """The NewsAPI key, or `None` when unset.

    Never log or serialize the return value.
    """
    return os.environ.get("NEWS_API_KEY") or None


def has_news_api_key() -> bool:
    return bool(news_api_key())
