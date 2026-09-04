# -*- coding: utf-8 -*-
"""Markets — the market board and per-instrument detail."""

from __future__ import annotations

import numpy as np
import streamlit as st

from services import catalog, market, store
from services.context import get as get_context
from ui import charts, components as c, layout
from ui.format import compact_number, percent, ratio, signed_percent
from ui.icons import st_icon
from views import _shared as shared

ctx = get_context()

c.page_header(
    "Marchés",
    eyebrow="Univers ETF thématiques",
    icon="markets",
    subtitle="Cotations, momentum et signaux techniques sur les douze ETF "
             "couverts par le moteur de prévision.",
    aside=c.chip_html(ctx.market.get("label", "Marché"), tone="flat", icon="live")
    + c.chip_html(f"{ctx.market.get('clock', '--:--')} NY", tone="flat", icon="clock"),
)

if not ctx.has_quotes:
    layout.data_unavailable_notice()
    st.stop()

universe = ctx.quotes[ctx.quotes["ticker"] != catalog.BENCHMARK].copy()

shared.strip_block(ctx.quotes)
st.write("")

# ---------------------------------------------------------------------------
#  Market breadth
# ---------------------------------------------------------------------------

advancers = int((universe["change_pct"] > 0).sum())
decliners = int((universe["change_pct"] < 0).sum())
best = universe.loc[universe["change_pct"].idxmax()] if advancers or decliners else None
worst = universe.loc[universe["change_pct"].idxmin()] if advancers or decliners else None
buy_signals = int(universe["signal"].isin(["Strong Buy", "Buy"]).sum())

c.kpi_row([
    c.kpi_html(
        "Largeur du marché", f"{advancers} / {len(universe)}",
        icon="performance", tone="up" if advancers >= decliners else "down",
        footer=c.chip_html(f"{advancers} hausses", tone="up")
        + c.chip_html(f"{decliners} baisses", tone="down"),
        hint="ETF en hausse sur la séance",
    ),
    c.kpi_html(
        "Meilleure performance", best["ticker"] if best is not None else "—",
        delta=best["change_pct"] if best is not None else None,
        icon="profit", tone="up",
        hint=catalog.sector_of(best["ticker"]) if best is not None else None,
    ),
    c.kpi_html(
        "Moins bonne performance", worst["ticker"] if worst is not None else "—",
        delta=worst["change_pct"] if worst is not None else None,
        icon="loss", tone="down",
        hint=catalog.sector_of(worst["ticker"]) if worst is not None else None,
    ),
    c.kpi_html(
        "Signaux acheteurs", f"{buy_signals} / {len(universe)}",
        icon="bolt", tone="info",
        hint="Signal technique composite Buy ou Strong Buy",
    ),
    c.kpi_html(
        "Volatilité moyenne", percent(universe["volatility"].mean(), 1),
        icon="volatility", tone="warn",
        hint="Annualisée, 12 derniers mois",
    ),
], min_width="15rem")

st.write("")

# ---------------------------------------------------------------------------
#  Board
# ---------------------------------------------------------------------------

with c.card(key="board"):
    c.section(
        "Tableau de marché",
        subtitle="Recherche, filtres, tri et pagination sur l'ensemble de l'univers",
        icon="table",
        aside=c.chip_html("Signal technique — non prédictif", tone="warn", icon="info"),
    )
    show_aum = st.toggle(
        "Afficher les actifs sous gestion estimés",
        value=False, key="markets_aum",
        help="Parts en circulation × dernier cours (Yahoo ne publie pas la "
             "capitalisation des ETF). Nécessite une requête par instrument.",
    )
    if show_aum:
        with st.spinner("Récupération des encours…"):
            shared.market_table(universe, key="markets_board", with_aum=True,
                                page_size=12)
    else:
        shared.market_table(universe, key="markets_board", page_size=12)

    c.caption(
        f"Signal technique composite — {market.SIGNAL_RULES} "
        "Il ne s'agit ni d'un conseil en investissement ni de la sortie du modèle LSTM."
    )

st.write("")

# ---------------------------------------------------------------------------
#  Detail
# ---------------------------------------------------------------------------

detail_columns = st.columns([2.1, 1])

with detail_columns[0]:
    with c.card(key="detail"):
        tickers = list(universe["ticker"])
        current = store.selected_ticker()
        selected = st.selectbox(
            "Instrument",
            tickers,
            index=tickers.index(current) if current in tickers else 0,
            format_func=catalog.label,
            key="markets_instrument",
        )
        if selected != current:
            store.select_ticker(selected)

        shared.instrument_panel(selected, ctx, key_prefix="markets")

with detail_columns[1]:
    row = ctx.quote(store.selected_ticker())

    with c.card(key="perfbreak"):
        c.section("Performance", subtitle="Rendements glissants", icon="performance")
        if row is None:
            c.empty_state("Indisponible", icon="empty")
        else:
            horizons = [
                ("5 séances", row["return_5d"]),
                ("1 mois", row["return_1m"]),
                ("3 mois", row["return_3m"]),
                ("6 mois", row["return_6m"]),
                ("YTD", row["ytd"]),
                ("1 an", row["return_1y"]),
            ]
            valid = [(label, value) for label, value in horizons
                     if value is not None and not np.isnan(value)]
            if valid:
                st.plotly_chart(
                    charts.signed_bar([v[0] for v in valid], [v[1] for v in valid],
                                      height=230),
                    width="stretch", theme=None, config=charts.CONFIG,
                )
            c.kv_list([(label, signed_percent(value)) for label, value in horizons])

    with c.card(key="tech"):
        c.section("Profil technique", icon="analytics")
        if row is None:
            c.empty_state("Indisponible", icon="empty")
        else:
            position = row["position_52w"]
            c.render(
                '<div class="opt-stack">'
                '<div class="opt-row opt-row--between">'
                '<span class="opt-caption">POSITION DANS LE RANGE 52 SEMAINES</span>'
                f'<span class="opt-num" style="font-weight:600">{percent(position, 0)}</span>'
                "</div>"
                + c.bar_html(position if position and not np.isnan(position) else 0)
                + '<div class="opt-row opt-row--between">'
                f'<span class="opt-caption">{c.esc(ratio(row["low_52w"]))}</span>'
                f'<span class="opt-caption">{c.esc(ratio(row["high_52w"]))}</span>'
                "</div></div>"
            )
            st.write("")
            c.kv_list([
                ("Signal composite", c.signal_html(str(row["signal"]))),
                ("Score technique", ratio(row["score"], 1)),
                ("RSI 14", ratio(row["rsi"], 1)),
                ("Volatilité annualisée", percent(row["volatility"], 1)),
                ("Drawdown 52 semaines", percent(row["max_drawdown"], 1)),
                ("Volume moyen 3M", compact_number(row["avg_volume"])),
            ])
            c.caption(f"Composition du score : {market.SIGNAL_RULES}")

    with c.card(key="quicklinks"):
        c.section("Actions", icon="bolt")
        if st.button("Voir les actualités", width="stretch",
                     icon=st_icon("news"), key="markets_to_news"):
            layout.goto("news")
