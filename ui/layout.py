# -*- coding: utf-8 -*-
"""Application shell: sidebar rail and sticky topbar.

`app.py` registers the navigation pages here (`register_pages`) so any component
can navigate with `goto("trading")` without importing the page objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from services import api_client, catalog, store
from services.context import AppContext
from ui import components as c
from ui.format import compact_money, money, signed_money, signed_percent
from ui.icons import icon_html, st_icon

# Populated by app.py: name -> StreamlitPage
PAGES: dict[str, Any] = {}


def register_pages(pages: dict[str, Any]) -> None:
    PAGES.clear()
    PAGES.update(pages)


def goto(name: str) -> None:
    """Navigate to a registered page."""
    page = PAGES.get(name)
    if page is not None:
        st.switch_page(page)


# ---------------------------------------------------------------------------
#  Topbar
# ---------------------------------------------------------------------------

def _status_chips(ctx: AppContext) -> str:
    """Market state, clock, balance and backend health as a single markup block."""
    market = ctx.market or {}
    state = market.get("state", "closed")
    dot = c.dot_html("open" if state == "open" else ("warn" if state in {"pre", "post"} else "closed"))
    market_chip = (
        f'<span class="opt-chip opt-chip--{"up" if state == "open" else "flat"}">'
        f'{dot}{c.esc(market.get("label", "Marché"))}</span>'
    )

    clock_chip = (
        f'<span class="opt-chip">{icon_html("clock", size="0.875rem")}'
        f'{c.esc(market.get("clock", "--:--"))} {c.esc(market.get("zone", "NY"))}</span>'
    )

    valuation = ctx.valuation or {}
    equity = valuation.get("equity")
    balance_chip = ""
    if equity is not None:
        day = valuation.get("day_pnl", 0.0)
        tone = "up" if day >= 0 else "down"
        balance_chip = (
            '<span class="opt-chip opt-chip--strong" title="Valeur totale du compte simulé">'
            f'{icon_html("value", size="0.875rem")}<span class="opt-num">{c.esc(money(equity))}</span>'
            f'<span class="opt-{tone}">{c.esc(signed_money(day))}</span></span>'
        )

    api_title = "Backend d'optimisation connecté" if ctx.api_online else "Backend d'optimisation hors ligne"
    api_chip = (
        f'<span class="opt-chip opt-chip--{"info" if ctx.api_online else "down"}" '
        f'title="{api_title}">'
        f'{icon_html("api", size="0.875rem")}{"API" if ctx.api_online else "API HS"}</span>'
    )

    paper_chip = (
        '<span class="opt-chip opt-chip--warn" title="Compte de démonstration : '
        'les ordres sont simulés aux prix réels du marché">'
        f'{icon_html("shield", size="0.875rem")}{store.ACCOUNT_MODE}</span>'
    )

    return (
        '<div class="opt-topbar-meta">'
        f"{market_chip}{clock_chip}{balance_chip}{api_chip}{paper_chip}</div>"
    )


def _notifications_panel() -> None:
    items = store.notifications()
    if not items:
        c.empty_state("Aucune notification", "Les exécutions d'ordres et les alertes "
                                            "déclenchées apparaîtront ici.", icon="bell")
        return

    if st.button("Tout marquer comme lu", key="notif_read", width="stretch",
                 icon=st_icon("check"), type="tertiary"):
        store.mark_all_read()
        st.rerun()

    c.feed([
        {
            "title": item["title"],
            "summary": item["body"],
            "icon": item["icon"],
            "tone": item["tone"],
            "meta": c.chip_html(item["timestamp"].strftime("%d %b · %H:%M"), tone="flat"),
        }
        for item in items[:12]
    ])


def _appearance_panel() -> None:
    from ui import styles, tokens

    prefs = store.prefs()
    c.section("Apparence", subtitle="Thème et densité de l'interface", icon="theme")

    palette = st.radio(
        "Palette",
        list(tokens.PALETTES),
        index=list(tokens.PALETTES).index(prefs["palette"]),
        format_func=lambda name: tokens.PALETTE_LABELS[name],
        key="topbar_palette",
        horizontal=True,
    )
    density = st.select_slider(
        "Densité",
        options=list(styles.DENSITY_LABELS),
        value=prefs["density"],
        format_func=lambda name: styles.DENSITY_LABELS[name],
        key="topbar_density",
    )
    if palette != prefs["palette"] or density != prefs["density"]:
        store.set_pref("palette", palette)
        store.set_pref("density", density)
        st.rerun()

    c.caption(
        "L'application est conçue en mode sombre, comme les terminaux de marché : "
        "les deux palettes ajustent la température des surfaces sans dégrader les "
        "contrastes de lecture."
    )


def _profile_panel(ctx: AppContext) -> None:
    profile = store.user()
    valuation = ctx.valuation or {}
    c.render(
        '<div class="opt-row" style="gap:0.75rem;margin-bottom:0.5rem">'
        f'{c.avatar_html(profile["initials"], large=True)}'
        f'<div><div style="font-weight:700;font-size:var(--opt-fs-md)">{c.esc(profile["name"])}</div>'
        f'<div class="opt-caption">{c.esc(profile["role"])} · {c.esc(profile["desk"])}</div>'
        f'<div style="margin-top:0.375rem">{c.chip_html(profile["plan"], tone="info", icon="verified")}</div>'
        "</div></div>"
    )
    c.kv_list([
        ("Valeur du compte", money(valuation.get("equity", 0))),
        ("Liquidités", money(valuation.get("cash", 0))),
        ("Performance totale", signed_percent(valuation.get("total_return_pct", 0))),
    ])
    st.divider()
    if st.button("Profil", key="topbar_profile", width="stretch", icon=st_icon("profile")):
        goto("profile")
    if st.button("Paramètres", key="topbar_settings", width="stretch", icon=st_icon("settings")):
        goto("settings")
    if st.button("Se déconnecter", key="topbar_logout", width="stretch",
                 icon=st_icon("logout"), type="secondary"):
        goto("logout")


def topbar(ctx: AppContext) -> None:
    """Sticky command bar: brand, global search, market state, and account actions."""
    with st.container(key="topbar"):
        cols = st.columns([1.7, 2.7, 3.8, 1.05, 1.0, 1.15], vertical_alignment="center")

        with cols[0]:
            c.render(c.brand_wordmark_html(mark_size="1.5rem", text_size="0.9375rem"))

        with cols[1]:
            choice = st.selectbox(
                "Recherche globale",
                options=list(catalog.TICKERS),
                index=None,
                format_func=catalog.label,
                placeholder="Rechercher un ETF, un secteur…",
                label_visibility="collapsed",
                key="global_search",
            )
            if choice:
                store.select_ticker(choice)
                st.session_state["global_search"] = None
                goto("markets")

        with cols[2]:
            _live_meta(ctx)

        with cols[3]:
            unread = store.unread_count()
            with st.popover(str(unread), icon=st_icon("bell"), width="stretch",
                            type="secondary" if unread else "tertiary",
                            help="Notifications"):
                c.section("Notifications", icon="bell")
                _notifications_panel()

        with cols[4]:
            with st.popover("Thème", icon=st_icon("theme"), width="stretch",
                            type="tertiary", help="Apparence"):
                _appearance_panel()

        with cols[5]:
            initials = store.user()["initials"]
            with st.popover(initials, icon=st_icon("profile"), width="stretch",
                            type="tertiary", help="Compte"):
                _profile_panel(ctx)


@st.fragment(run_every="30s")
def _live_meta(ctx: AppContext) -> None:
    """Market clock and balance, refreshed on its own without a full rerun."""
    from services import market

    live = dict(ctx.market or {})
    live.update(market.market_status())
    refreshed = AppContext(
        quotes=ctx.quotes, valuation=ctx.valuation, market=live,
        api_online=ctx.api_online,
    )
    c.render(_status_chips(refreshed))


# ---------------------------------------------------------------------------
#  Sidebar
# ---------------------------------------------------------------------------

def sidebar(ctx: AppContext) -> None:
    """Account summary, quick actions and user card below the navigation."""
    valuation = ctx.valuation or {}

    with st.sidebar:
        equity = valuation.get("equity", 0.0)
        day_pnl = valuation.get("day_pnl", 0.0)
        day_pct = valuation.get("day_pnl_pct", 0.0)
        invested = valuation.get("invested_pct", 0.0)

        c.render(
            '<div class="opt-user" style="flex-direction:column;align-items:stretch;gap:0.5rem">'
            '<div class="opt-row opt-row--between">'
            f'<span class="opt-caption">VALEUR DU COMPTE</span>'
            f'{c.chip_html(store.ACCOUNT_MODE, tone="warn")}</div>'
            f'<div style="font-size:var(--opt-fs-xl);font-weight:700;letter-spacing:-0.02em" '
            f'class="opt-num">{c.esc(money(equity))}</div>'
            f'<div class="opt-row">{c.delta_html(day_pct)}'
            f'<span class="opt-caption">{c.esc(signed_money(day_pnl))} aujourd\'hui</span></div>'
            f'<div style="margin-top:0.125rem">{c.bar_html(invested)}</div>'
            f'<div class="opt-row opt-row--between">'
            f'<span class="opt-caption">Investi {invested:.0f}%</span>'
            f'<span class="opt-caption">Cash {c.esc(compact_money(valuation.get("cash", 0)))}</span>'
            "</div></div>"
        )

        st.write("")
        if st.button("Optimiser le portefeuille", key="side_optimize", width="stretch",
                     type="primary", icon=st_icon("forecast")):
            goto("trading")
        if st.button("Passer un ordre", key="side_order", width="stretch",
                     icon=st_icon("buy")):
            goto("trading")

        st.write("")
        profile = store.user()
        c.render(
            '<div class="opt-user">'
            f'{c.avatar_html(profile["initials"])}'
            f'<div style="min-width:0"><div class="opt-user__name">{c.esc(profile["name"])}</div>'
            f'<div class="opt-user__role">{c.esc(profile["role"])}</div></div></div>'
        )
        c.render(
            '<div class="opt-caption" style="margin-top:0.5rem;text-align:center">'
            f"Optiport · v2.1 · {datetime.now():%Y}</div>"
        )


# ---------------------------------------------------------------------------
#  Shared page furniture
# ---------------------------------------------------------------------------

def api_offline_notice(ctx: AppContext, *, feature: str) -> None:
    """Consistent explanation when the optimizer backend is unreachable."""
    c.error_state(
        "Backend d'optimisation hors ligne",
        f"{feature} nécessite l'API FastAPI. Lancez-la depuis le dossier Optiport :\n"
        "uvicorn api:app --reload --port 8000",
    )
    st.code("uvicorn api:app --reload --port 8000", language="bash")
    if st.button("Réessayer la connexion", icon=st_icon("refresh"), key=f"retry_{feature}"):
        api_client.health.clear()
        st.rerun()


def data_unavailable_notice(what: str = "Les données de marché") -> None:
    c.error_state(
        "Données de marché indisponibles",
        f"{what} n'ont pas pu être récupérées auprès de Yahoo Finance. "
        "Vérifiez la connexion réseau puis actualisez.",
    )
    if st.button("Actualiser les données", icon=st_icon("refresh"), key=f"reload_{hash(what)}"):
        st.cache_data.clear()
        st.rerun()
