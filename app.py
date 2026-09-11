# -*- coding: utf-8 -*-
"""Optiport — ETF portfolio intelligence platform.

Entry point: `streamlit run app.py`

Responsibilities of this module only:
  1. page configuration and global style injection
  2. resolving the shared per-run context (market data + account valuation)
  3. declaring the navigation tree and rendering the shell (sidebar + topbar)

Page bodies live in `views/`, presentation primitives in `ui/`, and data access
in `services/`. The portfolio optimisation and forecasting logic is untouched:
it stays in `api.py` / `backend/` and is reached over HTTP.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Optiport · ETF Portfolio Intelligence",
    page_icon=":material/candlestick_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "about": (
            "**Optiport** — allocation d'ETF pilotée par prévisions LSTM et "
            "théorie moderne du portefeuille.\n\n"
            "Les ordres et le solde du compte sont simulés (paper trading) ; "
            "les cours, historiques et actualités proviennent de Yahoo Finance."
        ),
    },
)

from pathlib import Path  # noqa: E402  (must follow set_page_config)
from typing import Any  # noqa: E402

from services import api_client, catalog, market, store  # noqa: E402
from services.context import AppContext, publish  # noqa: E402
from ui import layout, styles  # noqa: E402
from ui.icons import st_icon  # noqa: E402
from views import auth, landing  # noqa: E402

ASSETS = Path(__file__).parent / "ui" / "assets"


# ---------------------------------------------------------------------------
#  Shell
# ---------------------------------------------------------------------------

def build_context() -> AppContext:
    """Fetch market data once per run and mark the account to market.

    Also settles the backend account (fills crossed limit orders, triggers
    price alerts) and syncs the resulting positions/orders/transactions/
    watchlist/alerts snapshot into session state. `refresh_portfolio()` is
    throttled (a few seconds) rather than unconditional: Streamlit reruns
    this on *every* widget interaction anywhere in the app, not just page
    navigation, and neither the account nor market prices meaningfully
    change between two clicks a second apart. A mutation (placing an order,
    toggling a watchlist entry, ...) always refreshes immediately regardless
    of this — see `services/store.py`.
    """
    universe = tuple(dict.fromkeys((*catalog.TICKERS, catalog.BENCHMARK)))
    quotes = market.snapshot(universe)

    store.refresh_portfolio()
    valuation = store.valuation(quotes)

    return AppContext(
        quotes=quotes,
        valuation=valuation,
        market=market.market_status(),
        api_online=api_client.is_online(),
    )


def navigation() -> tuple[Any, dict[str, Any]]:
    """Declare the navigation tree, grouped into sidebar sections.

    The "Administration" section/page is only *added* to the tree for admins
    — a convenience so non-admins never see it. It is not the security
    boundary: every `/admin/*` backend call independently re-checks the
    caller's role (`backend/deps.py::require_admin`), so a non-admin cannot
    reach admin data even by guessing the page's URL path.
    """
    pages = {
        "dashboard": st.Page("views/dashboard.py", title="Dashboard",
                             icon=st_icon("dashboard"), url_path="dashboard", default=True),
        "markets": st.Page("views/markets.py", title="Markets",
                           icon=st_icon("markets"), url_path="markets"),
        "portfolio": st.Page("views/portfolio.py", title="Portfolio",
                             icon=st_icon("portfolio"), url_path="portfolio"),
        "watchlist": st.Page("views/watchlist.py", title="Watchlist",
                             icon=st_icon("watchlist"), url_path="watchlist"),
        "trading": st.Page("views/trading.py", title="Trading",
                           icon=st_icon("trading"), url_path="trading"),
        "orders": st.Page("views/orders.py", title="Orders",
                          icon=st_icon("orders"), url_path="orders"),
        "transactions": st.Page("views/transactions.py", title="Transactions",
                                icon=st_icon("transactions"), url_path="transactions"),
        "news": st.Page("views/news.py", title="News",
                        icon=st_icon("news"), url_path="news"),
        "news_analysis": st.Page("views/news_analysis.py", title="News Analysis",
                                 icon=st_icon("sentiment"), url_path="news-analysis"),
        "alerts": st.Page("views/alerts.py", title="Alerts",
                          icon=st_icon("alerts"), url_path="alerts"),
        "settings": st.Page("views/settings.py", title="Settings",
                            icon=st_icon("settings"), url_path="settings"),
        "profile": st.Page("views/profile.py", title="Profile",
                           icon=st_icon("profile"), url_path="profile"),
        "logout": st.Page("views/logout.py", title="Logout",
                          icon=st_icon("logout"), url_path="logout"),
    }

    sections = {
        "Pilotage": [pages["dashboard"], pages["markets"], pages["portfolio"],
                     pages["watchlist"]],
        "Exécution": [pages["trading"], pages["orders"], pages["transactions"]],
        "Intelligence": [pages["news"], pages["news_analysis"], pages["alerts"]],
        "Compte": [pages["settings"], pages["profile"], pages["logout"]],
    }

    if store.is_admin():
        pages["admin"] = st.Page("views/admin.py", title="Administration",
                                 icon=st_icon("shield"), url_path="admin")
        sections["Administration"] = [pages["admin"]]

    # `expanded=True` keeps every section open: the sidebar is the primary
    # navigation surface and every destination must stay one click away.
    return st.navigation(sections, expanded=True), pages


def main() -> None:
    store.init()
    preferences = store.prefs()
    styles.inject(preferences["palette"], preferences["density"])

    # Auth gate: no token in session state -> show the public landing page
    # (or, once the visitor has clicked through, the login/register form)
    # instead of the app shell. `navigation()`/`nav.run()` below — the only
    # place any protected page gets registered or executed — is never
    # reached in this branch, so manually navigating to a page URL (e.g.
    # `?page=dashboard`) while signed out still lands here, not on a
    # protected page: Streamlit has nothing registered for that path in this
    # run. This is a UX convenience, not the actual security boundary —
    # every backend endpoint independently rejects an absent/invalid/
    # expired/revoked token regardless (see backend/deps.py).
    if not store.is_authenticated():
        if store.auth_view() == "landing":
            landing.landing_page()
        else:
            auth.auth_screen()
        return

    st.logo(
        str(ASSETS / "logo.svg"),
        size="large",
        icon_image=str(ASSETS / "logo-mark.svg"),
        link=None,
    )

    context = build_context()
    publish(context)

    nav, pages = navigation()
    layout.register_pages(pages)
    layout.sidebar(context)
    layout.topbar(context)

    nav.run()


main()
