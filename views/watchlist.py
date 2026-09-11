# -*- coding: utf-8 -*-
"""Watchlist — curated instruments with quick actions."""

from __future__ import annotations

import streamlit as st

from services import catalog, store
from services.context import get as get_context
from ui import components as c, layout
from ui.format import compact_number, percent, price, ratio, signed_percent
from ui.icons import st_icon
from views import _shared as shared

ctx = get_context()
watched = store.watchlist()

c.page_header(
    "Liste de suivi",
    eyebrow="Instruments surveillés",
    icon="watchlist",
    subtitle="Sélection personnelle d'ETF avec cotations, signaux techniques "
             "et accès direct à l'exécution.",
    aside=c.chip_html(f"{len(watched)} instruments", tone="info", icon="watchlist"),
)

if not ctx.has_quotes:
    layout.data_unavailable_notice()
    st.stop()

# ---------------------------------------------------------------------------
#  Management
# ---------------------------------------------------------------------------

with c.card(key="manage"):
    c.section("Composition", subtitle="Ajoutez ou retirez des instruments de la liste",
              icon="edit")
    columns = st.columns([3, 1], vertical_alignment="bottom")
    selection = columns[0].multiselect(
        "Instruments suivis",
        options=list(catalog.TICKERS),
        default=watched,
        format_func=catalog.label,
        key="watchlist_select",
        label_visibility="collapsed",
        placeholder="Choisir des ETF à suivre…",
    )
    if columns[1].button("Appliquer", type="primary", width="stretch",
                         icon=st_icon("check"), key="watchlist_apply"):
        store.set_watchlist(selection)
        st.toast("Liste de suivi mise à jour", icon="✅")
        st.rerun()

if not watched:
    c.empty_state(
        "Liste de suivi vide",
        "Sélectionnez des ETF ci-dessus pour les surveiller, ou explorez "
        "l'univers complet depuis la page Marchés.",
        icon="watchlist", variant="info",
    )
    if st.button("Explorer les marchés", type="primary", icon=st_icon("markets"),
                 key="watchlist_to_markets"):
        layout.goto("markets")
    st.stop()

rows = ctx.rows(watched)

# ---------------------------------------------------------------------------
#  Summary
# ---------------------------------------------------------------------------

advancers = int((rows["change_pct"] > 0).sum())
buys = int(rows["signal"].isin(["Strong Buy", "Buy"]).sum())

c.kpi_row([
    c.kpi_html("Instruments suivis", str(len(rows)), icon="watchlist", tone="accent",
               hint="dans la liste personnelle"),
    c.kpi_html("En hausse aujourd'hui", f"{advancers} / {len(rows)}",
               icon="profit", tone="up" if advancers * 2 >= len(rows) else "down"),
    c.kpi_html("Variation moyenne", signed_percent(rows["change_pct"].mean()),
               icon="performance",
               tone="up" if rows["change_pct"].mean() >= 0 else "down"),
    c.kpi_html("Signaux acheteurs", f"{buys} / {len(rows)}", icon="bolt", tone="info"),
    c.kpi_html("Performance YTD moyenne", signed_percent(rows["ytd"].mean()),
               icon="return", tone="up" if rows["ytd"].mean() >= 0 else "down"),
], min_width="14rem")

st.write("")

view_mode = st.segmented_control(
    "Affichage", ["Cartes", "Tableau"], default="Cartes",
    key="watchlist_view", label_visibility="collapsed",
)

st.write("")

# ---------------------------------------------------------------------------
#  Cards view — per-instrument actions
# ---------------------------------------------------------------------------

if view_mode == "Tableau":
    with c.card(key="wltable"):
        c.section("Cotations", subtitle="Tri, recherche et filtres", icon="table")
        shared.market_table(rows, key="wl_table", page_size=12)
else:
    per_row = 3
    items = list(rows.iterrows())
    for start in range(0, len(items), per_row):
        columns = st.columns(per_row)
        for column, (_, row) in zip(columns, items[start:start + per_row]):
            ticker = row["ticker"]
            with column:
                with c.card(key=f"wl-{ticker}"):
                    c.render(
                        '<div class="opt-row opt-row--between" style="margin-bottom:0.5rem">'
                        f'{c.instrument_html(ticker, catalog.sector_of(ticker))}'
                        f'{c.signal_html(str(row["signal"]))}</div>'
                        '<div class="opt-row opt-row--between" style="align-items:flex-end">'
                        f'<span class="opt-kpi__value opt-kpi__value--sm">{price(row["price"])}</span>'
                        f'{c.delta_html(row["change_pct"])}</div>'
                        + c.sparkline_html(row["spark"], width=260, height=54)
                    )
                    c.kv_list([
                        ("YTD", signed_percent(row["ytd"], 1)),
                        ("Volatilité", percent(row["volatility"], 1)),
                        ("RSI 14", ratio(row["rsi"], 1)),
                        ("Volume", compact_number(row["volume"])),
                    ])
                    actions = st.columns(2)
                    if actions[0].button("Trader", key=f"wl_trade_{ticker}",
                                         width="stretch", icon=st_icon("trading"),
                                         type="primary"):
                        store.select_ticker(ticker)
                        layout.goto("trading")
                    if actions[1].button("Retirer", key=f"wl_drop_{ticker}",
                                         width="stretch", icon=st_icon("remove")):
                        store.toggle_watch(ticker)
                        st.rerun()

st.write("")

# ---------------------------------------------------------------------------
#  Focus
# ---------------------------------------------------------------------------

with c.card(key="wlfocus"):
    tickers = list(rows["ticker"])
    current = store.selected_ticker()
    focus = st.selectbox(
        "Analyse détaillée",
        tickers,
        index=tickers.index(current) if current in tickers else 0,
        format_func=catalog.label,
        key="watchlist_focus",
    )
    shared.instrument_panel(focus, ctx, key_prefix="watchlist")
