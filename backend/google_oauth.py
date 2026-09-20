# -*- coding: utf-8 -*-
"""Google OAuth 2.0 — authorization-code exchange and ID token verification.

The authorization-code exchange happens *here*, server-side, specifically so
`GOOGLE_CLIENT_SECRET` never reaches the browser — the frontend only ever
sees the *code* Google redirected back with, and hands it to
`POST /auth/google`, which does the rest.

The ID token's signature, issuer, audience and expiration are verified
against Google's published public keys via `google-auth`
(`google.oauth2.id_token.verify_oauth2_token`) rather than a bare unverified
decode — accepting an unverified JWT here would let anyone forge a login as
any email address. Concretely, `verify_oauth2_token`:
  - verifies the RS256 signature against Google's current public keys,
  - rejects an issuer other than "accounts.google.com" / "https://accounts.google.com",
  - rejects a token whose `aud` claim doesn't match the `audience` we pass
    (our own `GOOGLE_CLIENT_ID` — never trust a client-supplied audience),
  - rejects an expired token (`exp` claim).
We additionally require `sub` and `email` to be present before trusting the
identity at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from backend.config import google_client_id, google_client_secret, google_redirect_uri

_TOKEN_URL = "https://oauth2.googleapis.com/token"
logger = logging.getLogger(__name__)


class GoogleOAuthError(Exception):
    """Anything that goes wrong talking to Google or validating its response.
    Always mapped to a generic-enough HTTP error by the router — never
    exposes Google's raw error body to the client."""


@dataclass
class GoogleProfile:
    sub: str
    email: str
    email_verified: bool
    full_name: str


def exchange_code_for_profile(code: str, redirect_uri: str | None = None) -> GoogleProfile:
    """Exchanges an authorization code for a verified Google identity.

    `redirect_uri` must exactly match the one used to build the authorize
    URL the user was sent to (OAuth requirement) — defaults to the
    configured `GOOGLE_REDIRECT_URI` when the caller doesn't override it.
    """
    client_id = google_client_id()
    client_secret = google_client_secret()
    if not client_id or not client_secret:
        raise GoogleOAuthError("Google OAuth is not configured on this server.")

    try:
        response = requests.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri or google_redirect_uri(),
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        raise GoogleOAuthError("Could not reach Google's token endpoint.") from exc

    if response.status_code >= 400:
        raise GoogleOAuthError("Google rejected the authorization code.")

    payload = response.json()
    raw_id_token = payload.get("id_token")
    if not raw_id_token:
        raise GoogleOAuthError("Google's response did not include an ID token.")

    try:
        claims = google_id_token.verify_oauth2_token(
            raw_id_token, google_requests.Request(), audience=client_id,
            # google-auth's own default here is 0 — zero tolerance for any
            # timing difference between this server's clock and Google's
            # when checking `iat`/`exp`. Even a sub-second real-world skew
            # (network latency between the code exchange and this check,
            # minor clock drift) then rejects an otherwise entirely valid,
            # correctly-signed token. 10s is the tolerance Google's own
            # client libraries use elsewhere for exactly this reason — it
            # does not weaken signature, audience or issuer verification,
            # only how strictly the time window is enforced.
            clock_skew_in_seconds=10,
        )
    except ValueError as exc:  # invalid signature, expired, wrong audience...
        # google-auth's own ValueError message names exactly which check
        # failed (audience mismatch, expiry, signature...) and never
        # includes the client secret or a usable credential — safe to log,
        # and the only way to diagnose a real rejection instead of guessing.
        logger.warning("Google ID token verification failed: %s", exc)
        raise GoogleOAuthError("Google ID token failed verification.") from exc

    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise GoogleOAuthError("Google ID token is missing required claims.")

    return GoogleProfile(
        sub=sub,
        email=email.lower(),
        email_verified=bool(claims.get("email_verified", False)),
        full_name=claims.get("name") or email.split("@")[0],
    )
