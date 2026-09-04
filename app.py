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
from views import auth  # noqa: E402

ASSETS = Path(__file__).parent / "ui" / "assets"


# ---------------------------------------------------------------------------
#  Shell
# ---------------------------------------------------------------------------

def build_context() -> AppContext:
    """Fetch market data once per run and mark the account to market."""
    universe = tuple(dict.fromkeys((*catalog.TICKERS, catalog.BENCHMARK)))
    quotes = market.snapshot(universe)

    store.settle(quotes)
    valuation = store.valuation(quotes)

    return AppContext(
        quotes=quotes,
        valuation=valuation,
        market=market.market_status(),
        api_online=api_client.is_online(),
    )


def navigation() -> tuple[Any, dict[str, Any]]:
    """Declare the navigation tree, grouped into sidebar sections."""
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
    # `expanded=True` keeps every section open: the sidebar is the primary
    # navigation surface and all twelve destinations must stay one click away.
    return st.navigation(sections, expanded=True), pages


def main() -> None:
    store.init()
    preferences = store.prefs()
    styles.inject(preferences["palette"], preferences["density"])

    # Sign-in gate. Deliberately credential-free: this is a demo workspace, so
    # there is nothing to authenticate against and no password is ever asked.
    if not st.session_state.get("signed_in", True):
        auth.signed_out_screen()
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
