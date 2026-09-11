# -*- coding: utf-8 -*-
"""AI Assistant — a chat endpoint that answers using real Optiport data via
LLM tool/function calling, never by inventing figures itself.

Every tool the model can call (`backend/assistant_tools.py`) wraps an
existing data source — the account database, live pricing, the news
pipeline, the LSTM forecaster, the mean-variance optimizer. This file only
orchestrates the request/tool-call loop; it holds no financial logic of its
own.

Two interchangeable providers, chosen by `AI_PROVIDER` in `.env`
(`backend/config.py::ai_provider`):

- "groq" (default) — hosted, free tier, no local compute needed. Talks to
  Groq's OpenAI-compatible endpoint (`backend.config.groq_base_url()`), so
  it reuses the same `openai` SDK and the same tool-calling code path as
  the OpenAI provider — only the client's `base_url`/`api_key`/model
  differ. Requires `GROQ_API_KEY`.
- "openai" — hosted, paid, requires `OPENAI_API_KEY`.

When the active provider isn't available, every route here answers 503
rather than silently degrading to a canned or fabricated response — the
frontend shows a plain "AI unavailable" state instead of a chat box.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import assistant_tools as tools
from backend import config
from backend.db import get_db
from backend.deps import get_current_user
from backend.models import User
from backend.schemas import AssistantChatRequest, AssistantChatResponse, AssistantStatusOut

router = APIRouter(prefix="/assistant", tags=["assistant"], dependencies=[Depends(get_current_user)])
_logger = logging.getLogger(__name__)

_MAX_REPLY_TOKENS = 700
_MAX_TOOL_ROUNDS = 4  # hard cap so a confused model can't loop indefinitely

_SYSTEM_PROMPT = """You are Optiport's portfolio assistant, embedded in a paper-trading app.

Ground rules:
- You have tools to fetch the user's REAL account (cash, positions), live market quotes, \
recent news, return forecasts, and portfolio optimization. Call the relevant tool before \
answering any question that needs real numbers — never guess or invent a ticker, price, \
quantity, or figure.
- If a tool returns an error or a value is missing, say so plainly instead of guessing.
- This is a simulated ($ paper trading) account — never suggest real brokerage actions.
- The forecast and optimization tools are slow and call real historical-data fetches; only \
call them when the user is actually asking about forecasts or an optimized allocation.
- Keep answers concise.
"""

_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": "The user's real simulated account: cash and every open position marked to the latest price.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_quotes",
            "description": "Live price, previous close and day change for one or more ticker symbols.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {"type": "array", "items": {"type": "string"}, "description": "Ticker symbols, e.g. [\"SPY\", \"PSI\"]"},
                },
                "required": ["tickers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticker_news",
            "description": "Recent news headlines and aggregated sentiment for one ticker.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_return_forecast",
            "description": "22-day forward return forecast per ticker from the LSTM forecasting model. Slow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {"type": "array", "items": {"type": "string"}, "description": "Defaults to the full covered ETF universe if omitted."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_optimization",
            "description": "Mean-variance optimized allocation over real forecasted returns and historical covariance. Slow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {"type": "array", "items": {"type": "string"}},
                    "strategy": {
                        "type": "string",
                        "enum": ["max_sharpe", "min_volatility", "risk_parity", "equal_weight"],
                    },
                    "risk_free_rate": {"type": "number", "description": "Annual rate as a fraction, e.g. 0.05 for 5%."},
                },
            },
        },
    },
]


def _availability() -> tuple[bool, str | None]:
    """(available, reason) for the currently configured provider. `reason`
    is only meaningful when `available` is False."""
    provider = config.ai_provider()

    if provider == "openai":
        if config.has_openai_key():
            return True, None
        return False, "OPENAI_API_KEY is not configured on the server."

    if provider == "groq":
        if config.has_groq_key():
            return True, None
        return False, "GROQ_API_KEY is not configured on the server."

    return False, f"Unknown AI_PROVIDER '{provider}'."


def _client_and_model():
    """An `openai.OpenAI` client pointed at whichever provider is active,
    plus the model name to use. Only called after `_availability()` has
    already confirmed the provider is usable."""
    from openai import OpenAI

    provider = config.ai_provider()
    if provider == "openai":
        return OpenAI(api_key=config.openai_api_key()), config.openai_model()
    # provider == "groq"
    return OpenAI(base_url=config.groq_base_url(), api_key=config.groq_api_key()), config.groq_model()


def _dispatch(name: str, args: dict[str, Any], db: Session, user: User) -> dict[str, Any]:
    try:
        if name == "get_portfolio":
            return tools.get_portfolio(db, user)
        if name == "get_market_quotes":
            return tools.get_market_quotes(args.get("tickers", []))
        if name == "get_ticker_news":
            return tools.get_ticker_news(args["ticker"])
        if name == "get_return_forecast":
            return tools.get_return_forecast(args.get("tickers"))
        if name == "get_portfolio_optimization":
            return tools.get_portfolio_optimization(
                tickers=args.get("tickers"),
                strategy=args.get("strategy", "max_sharpe"),
                risk_free_rate=args.get("risk_free_rate", 0.05),
            )
        return {"error": f"Unknown tool '{name}'."}
    except Exception as exc:  # a tool failing must not 500 the whole chat request
        return {"error": str(exc)}


@router.get("/status", response_model=AssistantStatusOut)
def status() -> AssistantStatusOut:
    available, reason = _availability()
    return AssistantStatusOut(available=available, provider=config.ai_provider(), reason=reason)


@router.post("/chat", response_model=AssistantChatResponse)
def chat(
    req: AssistantChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> AssistantChatResponse:
    available, reason = _availability()
    if not available:
        raise HTTPException(status_code=503, detail=reason or "AI Assistant is not configured on the server.")

    try:
        from openai import (  # imported lazily so the package is only required when actually used
            APIConnectionError,
            AuthenticationError,
            RateLimitError,
        )
    except ImportError:
        raise HTTPException(
            status_code=503, detail="AI Assistant is not configured on the server.",
        ) from None

    client, model = _client_and_model()
    provider = config.ai_provider()
    key_name = "OPENAI_API_KEY" if provider == "openai" else "GROQ_API_KEY"
    provider_label = "the OpenAI API" if provider == "openai" else "the Groq API"
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        *({"role": m.role, "content": m.content} for m in req.messages),
    ]

    try:
        for _ in range(_MAX_TOOL_ROUNDS):
            completion = client.chat.completions.create(
                model=model, messages=messages, tools=_TOOLS,
                tool_choice="auto", max_tokens=_MAX_REPLY_TOKENS,
            )
            message = completion.choices[0].message

            if not message.tool_calls:
                reply = (message.content or "").strip()
                if not reply:
                    raise HTTPException(status_code=502, detail="AI Assistant returned an empty response.")
                return AssistantChatResponse(reply=reply)

            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [tc.model_dump() for tc in message.tool_calls],
            })
            for call in message.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = _dispatch(call.function.name, args, db, user)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, default=str),
                })
    except HTTPException:
        raise
    except AuthenticationError:
        # The SDK's own message for this can echo back a masked-but-
        # partially-visible fragment of the key — never put that in a
        # response or a log line. Only the class name is logged.
        _logger.error("AI Assistant: %s authentication failed (check %s).", provider_label, key_name)
        raise HTTPException(
            status_code=502,
            detail=f"AI Assistant authentication with {provider_label} failed. The server's {key_name} is likely invalid.",
        ) from None
    except RateLimitError as exc:
        # OpenAI reports "no billing credit on this account/project" through
        # the same exception class as an actual rate limit — `code` is safe
        # to read (unlike the auth error above, it never carries key
        # fragments) and lets us give an accurate, non-misleading message.
        if provider == "openai" and getattr(exc, "code", None) in ("insufficient_quota", "credit_balance_exhausted"):
            _logger.error("AI Assistant: OpenAI account has no available credit balance.")
            raise HTTPException(
                status_code=503,
                detail="The configured OpenAI account has no available credit balance. Add billing credit at platform.openai.com, then try again.",
            ) from None
        raise HTTPException(status_code=429, detail="AI Assistant rate limit reached — try again shortly.") from None
    except APIConnectionError:
        raise HTTPException(status_code=502, detail=f"AI Assistant could not reach {provider_label}.") from None
    except Exception as exc:
        # Deliberately logging only the exception's class name, never its
        # message/traceback (`logging.exception`/`str(exc)`) or including it
        # in the HTTP response — any exception raised from inside the SDK
        # call can carry request/key fragments in its message, as
        # `AuthenticationError` above demonstrably does.
        _logger.error("AI Assistant request failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="AI Assistant request failed.") from None

    raise HTTPException(status_code=502, detail="AI Assistant could not produce an answer in time.")
