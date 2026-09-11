# -*- coding: utf-8 -*-
"""Login / Register screen.

Not a page: rendered by `app.py` in place of the whole shell whenever
`store.is_authenticated()` is false *and* `store.auth_view()` is "login" or
"register" (the third option, "landing", renders `views/landing.py`
instead — see `app.py::main()`). Both forms call the FastAPI backend
directly (`services.api_client`); on success the token + profile are stashed
in session state (`store.begin_session`) and the app reruns into the shell.

Which of the two forms is shown is driven entirely by `store.auth_view()`,
not a `st.tabs` widget — Streamlit can't be told to open a specific tab
programmatically, and the landing page's "Log in" vs. "Create account"
buttons need to land on the matching form, not just some tabbed default.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

import streamlit as st

from services import api_client, store
from ui import components as c, styles
from ui.icons import st_icon

_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def _styles() -> None:
    styles.inject_light_shell()
    c.render("""
    <style>
    .optl-auth-header { text-align: center; padding: 0.5rem 0 1.25rem; }
    .optl-auth-header .opt-mark-row { display: flex; justify-content: center; }
    .optl-auth-header p {
        margin: 0.625rem auto 0; max-width: 22rem; color: #52525B;
        font-size: 0.875rem; line-height: 1.5;
    }
    .st-key-auth_card {
        background: #fff; border: 1px solid #E4E4E7; border-radius: 6px; padding: 2rem;
    }
    .st-key-auth_card [data-testid="stBaseButton-primaryFormSubmit"],
    .st-key-auth_card [data-testid="stBaseButton-primary"] {
        background: #0A0A0A !important; color: #fff !important; border: 1px solid #0A0A0A !important;
        border-radius: 4px !important; box-shadow: none !important;
    }
    .st-key-auth_card [data-testid="stBaseButton-primaryFormSubmit"]:hover,
    .st-key-auth_card [data-testid="stBaseButton-primary"]:hover { background: #262626 !important; }
    .st-key-auth_card [data-testid="stBaseButton-secondary"] {
        background: #fff !important; color: #0A0A0A !important;
        border: 1px solid #D4D4D8 !important; border-radius: 4px !important; box-shadow: none !important;
    }
    .st-key-auth_back [data-testid="stBaseButton-tertiary"] { color: #52525B !important; }
    .st-key-auth_back [data-testid="stBaseButton-tertiary"]:hover { color: #0A0A0A !important; }

    .optl-or {
        display: flex; align-items: center; gap: 0.75rem; margin: 1.25rem 0;
        color: #A1A1AA; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.05em;
    }
    .optl-or::before, .optl-or::after { content: ""; flex: 1; height: 1px; background: #E4E4E7; }
    .optl-google-btn {
        display: flex; align-items: center; justify-content: center; gap: 0.5rem;
        width: 100%; box-sizing: border-box; padding: 0.55rem 1rem;
        border: 1px solid #D4D4D8; border-radius: 4px; text-decoration: none;
        color: #0A0A0A; font-weight: 600; font-size: 0.875rem;
    }
    .optl-google-btn:hover { border-color: #0A0A0A; background: #FAFAFA; }
    .optl-google-btn--disabled {
        color: #A1A1AA; border-color: #E4E4E7; cursor: not-allowed;
    }
    .optl-google-btn--disabled:hover { background: none; border-color: #E4E4E7; }
    </style>
    """)


def _handle_google_callback() -> None:
    """Completes the Google sign-in round trip if the browser just came back
    from Google's consent screen with `?code=...&state=...` — clears the
    query params either way so a page refresh doesn't replay a used code."""
    params = st.query_params
    code = params.get("code")
    if not code:
        return

    state = params.get("state")
    expected_state = st.session_state.pop("_google_oauth_state", None)
    st.query_params.clear()

    if not state or state != expected_state:
        st.error("La connexion Google a échoué (état invalide) — réessayez.")
        return

    config = api_client.google_config()
    try:
        result = api_client.google_login(code, config.get("redirect_uri") or "")
    except api_client.ApiError as exc:
        st.error(exc.detail or str(exc))
        return

    store.begin_session(result["access_token"], result["user"])
    st.rerun()


def _google_button() -> None:
    config = api_client.google_config()
    c.render('<div class="optl-or"><span>OR</span></div>')

    if not config.get("enabled"):
        c.render(
            '<span class="optl-google-btn optl-google-btn--disabled" '
            'title="Non configuré côté serveur (GOOGLE_CLIENT_ID / SECRET manquants)">'
            "Continue with Google</span>"
        )
        return

    state = secrets.token_urlsafe(16)
    st.session_state["_google_oauth_state"] = state
    url = f"{_GOOGLE_AUTHORIZE_URL}?" + urlencode({
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    c.render(f'<a href="{c.esc(url)}" class="optl-google-btn">Continue with Google</a>')


def _header() -> None:
    c.render(
        '<div class="optl-auth-header"><div class="opt-mark-row">'
        f"{c.brand_wordmark_html(mark_size='2.25rem', text_size='1.375rem')}</div>"
        "<p>ETF portfolio intelligence — return forecasting, market analysis "
        "and portfolio optimization.</p></div>"
    )


def _login_form() -> None:
    with st.form("login_form", border=False):
        username = st.text_input("Nom d'utilisateur", key="login_username")
        password = st.text_input("Mot de passe", type="password", key="login_password")
        submitted = st.form_submit_button(
            "Se connecter", type="primary", width="stretch", icon=st_icon("logout"),
        )

    if not submitted:
        return
    # Trim accidental leading/trailing whitespace (copy-paste, browser
    # autofill, a stray space from the keyboard) — a space the user never
    # meant to type must not silently turn into "wrong password".
    username = username.strip()
    password = password.strip()
    if not username or not password:
        st.error("Nom d'utilisateur et mot de passe requis.")
        return

    try:
        result = api_client.login(username, password)
    except api_client.ApiError as exc:
        if exc.kind == "offline":
            c.error_state("Backend injoignable", exc.hint)
            st.code("uvicorn api:app --reload --port 8000", language="bash")
        else:
            st.error(exc.detail or str(exc))
        return

    store.begin_session(result["access_token"], result["user"])
    st.rerun()


def _register_form() -> None:
    with st.form("register_form", border=False):
        full_name = st.text_input("Nom complet", key="register_full_name")
        username = st.text_input(
            "Nom d'utilisateur", key="register_username",
            help="3 à 32 caractères : lettres, chiffres, points, tirets ou underscores.",
        )
        email = st.text_input("E-mail", key="register_email")
        password = st.text_input(
            "Mot de passe", type="password", key="register_password",
            help="8 caractères minimum.",
        )
        confirm = st.text_input("Confirmer le mot de passe", type="password", key="register_confirm")
        submitted = st.form_submit_button(
            "Créer mon compte", type="primary", width="stretch", icon=st_icon("check"),
        )

    if not submitted:
        return
    full_name = full_name.strip()
    username = username.strip()
    email = email.strip()
    password = password.strip()
    confirm = confirm.strip()
    if not all([full_name, username, email, password, confirm]):
        st.error("Tous les champs sont requis.")
        return
    if password != confirm:
        st.error("Les mots de passe ne correspondent pas.")
        return
    if len(password) < 8:
        st.error("Le mot de passe doit contenir au moins 8 caractères.")
        return

    try:
        result = api_client.register(username, email, password, full_name)
    except api_client.ApiError as exc:
        if exc.kind == "offline":
            c.error_state("Backend injoignable", exc.hint)
            st.code("uvicorn api:app --reload --port 8000", language="bash")
        else:
            st.error(exc.detail or str(exc))
        return

    store.begin_session(result["access_token"], result["user"])
    st.toast("Compte créé — bienvenue sur Optiport", icon="✅")
    st.rerun()


def auth_screen() -> None:
    view = store.auth_view()
    if view not in ("login", "register"):
        view = "login"

    _styles()
    _handle_google_callback()
    st.write("")
    columns = st.columns([1, 1.4, 1])
    with columns[1]:
        with st.container(key="auth_back"):
            if st.button("← Retour à l'accueil", key="auth_back_home", type="tertiary"):
                store.set_auth_view("landing")
                st.rerun()

        with st.container(key="auth_card"):
            _header()
            st.write("")

            if view == "login":
                _login_form()
                _google_button()
                st.write("")
                c.caption("Vous n'avez pas de compte ?")
                if st.button("Créer un compte", key="auth_switch_register", width="stretch"):
                    store.set_auth_view("register")
                    st.rerun()
            else:
                _register_form()
                _google_button()
                st.write("")
                c.caption("Vous avez déjà un compte ?")
                if st.button("Se connecter", key="auth_switch_login", width="stretch"):
                    store.set_auth_view("login")
                    st.rerun()

            c.caption(
                "Espace de démonstration : les ordres et le solde du compte "
                "sont simulés (paper trading). Vos identifiants ne sont "
                "utilisés que pour retrouver votre portefeuille simulé."
            )
