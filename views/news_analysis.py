# -*- coding: utf-8 -*-
"""News Analysis — sentiment, market impact and news-context forecasting.

Everything on this page is computed by the FastAPI backend
(`/news/analyze`, `/news/{ticker}`, `/news/{ticker}/summary`,
`/forecast/context`): this module only composes the request, renders the
response and never talks to NewsAPI or the sentiment model directly. The
existing "News" page (raw Yahoo Finance headlines, no scoring) is untouched;
this is a separate, deliberately more analytical view.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services import api_client, catalog, market, store
from services.context import get as get_context
from ui import charts
from ui import components as c
from ui.format import time_ago
from ui.icons import st_icon

ctx = get_context()

SENTIMENT_TONE = {"POSITIVE": "up", "NEGATIVE": "down", "NEUTRAL": "neutral"}
SENTIMENT_CHIP_TONE = {"POSITIVE": "up", "NEGATIVE": "down", "NEUTRAL": "flat"}
IMPACT_LEVEL_TONE = {"LOW": "flat", "MEDIUM": "warn", "HIGH": "accent"}
DISCLAIMER = (
    "Le sentiment et l'impact de marché sont des estimations probabilistes. "
    "Ils ne garantissent en rien les mouvements futurs du marché."
)

c.page_header(
    "News Analysis",
    eyebrow="Intelligence",
    icon="sentiment",
    subtitle="Sentiment financier et impact de marché estimés à partir des "
             "actualités, mis en regard des prévisions du modèle LSTM.",
    aside=c.chip_html("NewsAPI · Sentiment · Forecast", tone="violet",
                      icon="api", mono=True),
)

st.warning(DISCLAIMER, icon=st_icon("info"))

default_pool = list(dict.fromkeys([*store.watchlist(), *store.positions()])) \
    or list(catalog.DEFAULT_SELECTION)
default_ticker = default_pool[0] if default_pool[0] in catalog.TICKERS else catalog.TICKERS[0]

ticker = st.selectbox(
    "Ticker", options=list(catalog.TICKERS),
    index=list(catalog.TICKERS).index(default_ticker),
    format_func=catalog.label, key="na_ticker",
)

if st.session_state.get("na_last_ticker") != ticker:
    # Switching tickers invalidates any manual-analysis result and forces a
    # fresh "Analyze Today's News" / forecast run instead of showing stale data.
    st.session_state["na_last_ticker"] = ticker
    st.session_state.pop("na_manual_result", None)
    st.session_state["na_news_nonce"] = 0
    st.session_state["na_forecast_nonce"] = 0

tabs = st.tabs([
    "Analyse manuelle", "Actualités du jour", "Prévision contextualisée",
    "Impact sur le marché",
])

# ===========================================================================
#  Manual analysis
# ===========================================================================

with tabs[0]:
    with c.card(key="na_manual"):
        c.section(
            "Analyser une actualité", icon="edit",
            subtitle="Saisissez un titre (et éventuellement le contenu) pour "
                     "obtenir un sentiment et un impact de marché estimés.",
            aside=c.chip_html("POST /news/analyze", tone="flat", mono=True, icon="api"),
        )
        headline = st.text_input(
            "Headline", key="na_headline",
            placeholder="Apple reports record quarterly earnings",
        )
        content = st.text_area(
            "News Content", key="na_content", height=140,
            placeholder="Texte complet ou résumé de l'article (optionnel)…",
        )

        if st.button("Analyze News", type="primary", icon=st_icon("sentiment"),
                     key="na_analyze_btn"):
            if not headline.strip():
                st.warning("Saisissez au moins un titre.", icon=st_icon("warning"))
            elif not ctx.api_online:
                from ui import layout
                layout.api_offline_notice(ctx, feature="L'analyse de sentiment")
            else:
                with st.spinner("Analyse du sentiment et de l'impact de marché…"):
                    try:
                        st.session_state["na_manual_result"] = api_client.analyze_news(
                            ticker, headline, content=content,
                        )
                    except api_client.ApiError as error:
                        c.error_state(error.title, f"{error.message}\n\n{error.hint}")
                        st.session_state.pop("na_manual_result", None)

        result = st.session_state.get("na_manual_result")
        if result:
            st.write("")
            sentiment, impact = result["sentiment"], result["marketImpact"]
            c.kpi_row([
                c.kpi_html("Sentiment", sentiment["label"].title(), icon="sentiment",
                           tone=SENTIMENT_TONE.get(sentiment["label"], "neutral"),
                           hint=f"Confiance {sentiment['score'] * 100:.0f}%"),
                c.kpi_html("Market Impact", impact["direction"].title(), icon="impact",
                           tone=SENTIMENT_TONE.get(impact["direction"], "neutral"),
                           hint=f"Confiance {impact['confidence'] * 100:.0f}%"),
                c.kpi_html("Impact Level", impact["level"].title(), icon="risk",
                           tone={"LOW": "neutral", "MEDIUM": "warn", "HIGH": "accent"}
                           .get(impact["level"], "neutral")),
            ], min_width="13rem")

with tabs[1]:
    with c.card(key="na_today_header"):
        c.section(
            "Analyser les actualités du jour", icon="news",
            subtitle=f"Récupère et note les dépêches récentes pour {ticker} via NewsAPI.",
            aside=c.chip_html("GET /news/{ticker}", tone="flat", mono=True, icon="api"),
        )
        if st.button("Analyze Today's News", type="primary", icon=st_icon("news"),
                     key="na_news_run"):
            st.session_state["na_news_nonce"] = st.session_state.get("na_news_nonce", 0) + 1

    if not st.session_state.get("na_news_nonce"):
        c.empty_state(
            "Actualités non analysées",
            "Lancez l'analyse pour interroger NewsAPI et noter chaque dépêche "
            "(sentiment, impact, récence).", icon="news", variant="info",
        )
    elif not ctx.api_online:
        from ui import layout
        layout.api_offline_notice(ctx, feature="L'analyse des actualités")
    else:
        with st.spinner("Récupération et analyse des actualités…"):
            try:
                news_data = api_client.ticker_news(ticker)
                summary = api_client.ticker_news_summary(ticker)
            except api_client.ApiError as error:
                c.error_state(error.title, f"{error.message}\n\n{error.hint}")
                news_data, summary = None, None

        if summary and summary["news_count"] == 0:
            c.empty_state(
                "Aucune actualité récente",
                f"NewsAPI n'a renvoyé aucune dépêche exploitable pour {ticker} "
                "sur la fenêtre récente.", icon="news", variant="info",
            )
        elif news_data and summary:
            impact_label = {
                "STRONGLY_POSITIVE": "Fortement positif", "MODERATELY_POSITIVE": "Modérément positif",
                "NEUTRAL": "Neutre", "MODERATELY_NEGATIVE": "Modérément négatif",
                "STRONGLY_NEGATIVE": "Fortement négatif",
            }.get(summary["overall_market_impact"], summary["overall_market_impact"])

            with c.card(key="na_summary"):
                c.section("Sentiment du marché aujourd'hui", icon="analytics")
                c.kpi_row([
                    c.kpi_html("Dépêches", str(summary["news_count"]), icon="news",
                               tone="accent",
                               hint=f'{summary["positive_news_count"]} positives · '
                                    f'{summary["negative_news_count"]} négatives · '
                                    f'{summary["neutral_news_count"]} neutres'),
                    c.kpi_html("Sentiment global", summary["overall_sentiment"].title(),
                               icon="sentiment",
                               tone=SENTIMENT_TONE.get(summary["overall_sentiment"], "neutral")),
                    c.kpi_html("Impact de marché", impact_label, icon="impact",
                               tone=SENTIMENT_TONE.get(summary["overall_sentiment"], "neutral")),
                    c.kpi_html("Confiance", f'{summary["overall_confidence"] * 100:.0f}%',
                               icon="verified", tone="violet",
                               hint=f'Moyenne par dépêche {summary["average_confidence"] * 100:.0f}%'),
                ], min_width="13rem")

            st.write("")
            with c.card(key="na_feed"):
                c.section("Actualités du jour", subtitle="Les plus récentes en premier",
                          icon="news")
                c.feed([
                    {
                        "title": item["title"],
                        "summary": item["description"][:220] if item["description"] else "",
                        "url": item["url"],
                        "icon": "news",
                        "tone": SENTIMENT_TONE.get(item["sentiment"]["label"], "neutral"),
                        "meta": (
                            c.chip_html(item["source"], tone="flat", icon="database")
                            + (c.chip_html(time_ago(item["publishedAt"]), tone="flat", icon="clock")
                               if item["publishedAt"] else "")
                            + c.chip_html(
                                f'{item["sentiment"]["label"].title()} '
                                f'{item["sentiment"]["score"] * 100:.0f}%',
                                tone=SENTIMENT_CHIP_TONE.get(item["sentiment"]["label"], "flat"),
                                icon="sentiment",
                            )
                            + c.chip_html(
                                f'Impact {item["marketImpact"]["level"].title()}',
                                tone=IMPACT_LEVEL_TONE.get(item["marketImpact"]["level"], "flat"),
                                icon="impact",
                            )
                        ),
                    }
                    for item in news_data["items"][:30]
                ])
                c.caption(
                    "Les titres renvoient vers l'article original. Le sentiment et "
                    "l'impact sont calculés automatiquement et peuvent se tromper."
                )

# ===========================================================================
#  Forecast comparison
# ===========================================================================

with tabs[2]:
    with c.card(key="na_forecast_header"):
        c.section(
            "Base Forecast vs. News-Context Forecast", icon="forecast",
            subtitle="Le forecast LSTM existant, comparé à une version ajustée "
                     "par le sentiment et l'impact des actualités récentes.",
            aside=c.chip_html("POST /forecast/context", tone="flat", mono=True, icon="api"),
        )
        if st.button("Comparer les prévisions", type="primary", icon=st_icon("forecast"),
                     key="na_forecast_run"):
            st.session_state["na_forecast_nonce"] = st.session_state.get(
                "na_forecast_nonce", 0) + 1

    if not st.session_state.get("na_forecast_nonce"):
        c.empty_state(
            "Comparaison non générée",
            "L'inférence charge le modèle LSTM et analyse les actualités : "
            "lancez-la explicitement.", icon="model", variant="info",
        )
    elif not ctx.api_online:
        from ui import layout
        layout.api_offline_notice(ctx, feature="La prévision contextualisée")
    else:
        current_price = ctx.price(ticker)
        with st.spinner("Inférence LSTM + analyse des actualités…"):
            try:
                comparison = api_client.forecast_context(ticker, current_price=current_price)
            except api_client.ApiError as error:
                c.error_state(error.title, f"{error.message}\n\n{error.hint}")
                comparison = None

        if comparison:
            base = comparison["base_forecast"]
            news_ctx = comparison["news_context_forecast"]
            price = comparison["current_price"]

            if not base["model_loaded"]:
                st.warning(
                    "Le modèle LSTM entraîné n'a pas été trouvé : le backend "
                    "utilise le dernier rendement observé à la place d'une "
                    "prévision du modèle.", icon=st_icon("warning"),
                )

            direction_label = {
                "POTENTIAL_POSITIVE_IMPACT": "↑ Impact potentiel positif",
                "POTENTIAL_NEGATIVE_IMPACT": "↓ Impact potentiel négatif",
                "NEUTRAL": "→ Impact neutre",
            }.get(comparison["potential_direction"], comparison["potential_direction"])
            direction_tone = {
                "POTENTIAL_POSITIVE_IMPACT": "up",
                "POTENTIAL_NEGATIVE_IMPACT": "down",
            }.get(comparison["potential_direction"], "neutral")

            with c.card(key="na_forecast_kpis"):
                c.kpi_row([
                    c.kpi_html("Cours actuel",
                               f"{price:,.2f} $" if price is not None else "—",
                               icon="value", tone="info"),
                    c.kpi_html("Base Forecast",
                               f'{base["forecast_price"]:,.2f} $' if base["forecast_price"] is not None else "—",
                               icon="model", tone="violet",
                               delta=base["used_return_22d"] * 100, delta_suffix="%",
                               hint="Rendement 22j du modèle LSTM"),
                    c.kpi_html("News-Context Forecast",
                               f'{news_ctx["forecast_price"]:,.2f} $' if news_ctx["forecast_price"] is not None else "—",
                               icon="sentiment", tone="accent",
                               delta=news_ctx["predicted_return_22d"] * 100, delta_suffix="%",
                               hint=f'Ajustement news {news_ctx["adjustment_22d"] * 100:+.2f} pt'),
                    c.kpi_html("Direction potentielle", direction_label, icon="target",
                               tone=direction_tone, small=True),
                ], min_width="14rem")

            features = comparison["news_features"]
            st.write("")
            cols = st.columns([1.6, 1])
            with cols[0]:
                with c.card(key="na_forecast_chart"):
                    c.section("Historique + prévisions", icon="markets")
                    prices_df = market.closes([ticker], period="6mo")
                    if not prices_df.empty and ticker in prices_df.columns:
                        series = prices_df[ticker].dropna()
                        news_markers = []
                        if features["news_count"] > 0:
                            try:
                                items = api_client.ticker_news(ticker)["items"]
                                for item in items[:12]:
                                    if not item["publishedAt"]:
                                        continue
                                    ts = pd.Timestamp(item["publishedAt"])
                                    if ts.tzinfo is not None:
                                        ts = ts.tz_convert(None)
                                    idx = series.index.get_indexer([ts], method="nearest")[0]
                                    news_markers.append({
                                        "date": series.index[idx],
                                        "price": float(series.iloc[idx]),
                                        "sentiment": item["sentiment"]["label"],
                                        "title": item["title"][:80],
                                    })
                            except Exception:
                                news_markers = []

                        import pandas as pd
                        last_date = series.index[-1]
                        forecast_date = last_date + pd.Timedelta(days=22)
                        st.plotly_chart(
                            charts.forecast_with_news(
                                series.index, series.tolist(),
                                base_forecast=((forecast_date, base["forecast_price"])
                                               if base["forecast_price"] is not None else None),
                                news_context_forecast=((forecast_date, news_ctx["forecast_price"])
                                                        if news_ctx["forecast_price"] is not None else None),
                                news_markers=news_markers,
                                height=340,
                            ),
                            width="stretch", theme=None, config=charts.CONFIG,
                        )
                    else:
                        c.empty_state("Historique indisponible", icon="empty")
            with cols[1]:
                with c.card(key="na_features"):
                    c.section("News features", icon="insights",
                              subtitle="Entrées transmises à la couche de contexte")
                    c.kv_list([
                        ("Sentiment pondéré", f'{features["weighted_sentiment"]:+.3f}'),
                        ("Confiance moyenne", f'{features["sentiment_confidence"] * 100:.0f}%'),
                        ("Score d'impact", f'{features["impact_score"] * 100:.0f}%'),
                        ("Confiance impact", f'{features["impact_confidence"] * 100:.0f}%'),
                        ("Poids de récence moyen", f'{features["recency_weight"] * 100:.0f}%'),
                        ("Dépêches", str(features["news_count"])),
                    ])
                    c.caption(
                        f"Ajustement borné à ±{news_ctx['max_adjustment_22d'] * 100:.1f} pt "
                        "sur le rendement à 22 séances — voir backend/forecast_context.py."
                    )

            st.info(comparison["disclaimer"], icon=st_icon("info"))

# ===========================================================================
#  Market-wide impact
# ===========================================================================

IMPACT_LABEL_FR = {
    "STRONGLY_POSITIVE": "Fortement positif", "MODERATELY_POSITIVE": "Modérément positif",
    "NEUTRAL": "Neutre", "MODERATELY_NEGATIVE": "Modérément négatif",
    "STRONGLY_NEGATIVE": "Fortement négatif",
}

with tabs[3]:
    with c.card(key="na_market_header"):
        c.section(
            "Impact des actualités sur le marché", icon="impact",
            subtitle="Agrège le sentiment et l'impact des actualités récentes sur "
                     "plusieurs instruments pour donner une lecture de marché "
                     "d'ensemble, au-delà d'un seul ticker.",
            aside=c.chip_html("POST /news/market-impact", tone="flat", mono=True, icon="api"),
        )
        market_universe = st.multiselect(
            "Instruments à analyser", options=list(catalog.TICKERS),
            default=[t for t in default_pool if t in catalog.TICKERS] or list(catalog.DEFAULT_SELECTION),
            format_func=catalog.label, key="na_market_universe",
        )
        if st.button("Analyser l'impact sur le marché", type="primary", icon=st_icon("impact"),
                     key="na_market_run", disabled=not market_universe):
            st.session_state["na_market_nonce"] = st.session_state.get("na_market_nonce", 0) + 1
            st.session_state["na_market_tickers"] = tuple(market_universe)
            st.session_state.pop("na_heat_selected", None)

    if not st.session_state.get("na_market_nonce"):
        c.empty_state(
            "Impact de marché non calculé",
            "Sélectionnez un ou plusieurs instruments puis lancez l'analyse : "
            "chaque ticker est interrogé via NewsAPI et les résultats sont "
            "agrégés en une lecture de marché unique.", icon="impact", variant="info",
        )
    elif not ctx.api_online:
        from ui import layout
        layout.api_offline_notice(ctx, feature="L'impact de marché")
    else:
        market_tickers = st.session_state.get("na_market_tickers", tuple(market_universe))
        with st.spinner(f"Analyse des actualités sur {len(market_tickers)} instrument(s)…"):
            try:
                market_data = api_client.market_news_impact(market_tickers)
            except api_client.ApiError as error:
                c.error_state(error.title, f"{error.message}\n\n{error.hint}")
                market_data = None

        if market_data:
            overall = market_data["overall"]
            rows = market_data["tickers"]
            failed = market_data["failed_tickers"]

            if overall["news_count"] == 0:
                c.empty_state(
                    "Aucune actualité exploitable",
                    "NewsAPI n'a renvoyé aucune dépêche exploitable pour cette "
                    "sélection d'instruments.", icon="news", variant="info",
                )
            else:
                impact_label = IMPACT_LABEL_FR.get(
                    overall["overall_market_impact"], overall["overall_market_impact"])

                with c.card(key="na_market_summary"):
                    c.section("Lecture de marché agrégée", icon="analytics",
                              subtitle=f'{len(rows)} instrument(s) analysé(s)'
                                       + (f' · {len(failed)} en échec' if failed else ''))
                    c.kpi_row([
                        c.kpi_html("Actualités totales", str(overall["news_count"]),
                                   icon="news", tone="accent",
                                   hint=f'{overall["positive_news_count"]} positives · '
                                        f'{overall["negative_news_count"]} négatives · '
                                        f'{overall["neutral_news_count"]} neutres'),
                        c.kpi_html("Sentiment de marché", overall["overall_sentiment"].title(),
                                   icon="sentiment",
                                   tone=SENTIMENT_TONE.get(overall["overall_sentiment"], "neutral")),
                        c.kpi_html("Impact de marché", impact_label, icon="impact",
                                   tone=SENTIMENT_TONE.get(overall["overall_sentiment"], "neutral"),
                                   small=True),
                        c.kpi_html("Confiance", f'{overall["overall_confidence"] * 100:.0f}%',
                                   icon="verified", tone="violet"),
                    ], min_width="13rem")

                if failed:
                    c.caption(
                        "Récupération impossible (clé manquante, quota NewsAPI ou "
                        f"service indisponible) pour : {', '.join(failed)}."
                    )

                st.write("")
                ranked_desc = sorted(rows, key=lambda r: -r["weighted_sentiment"])
                universe_tickers = {r["ticker"] for r in ranked_desc}
                if st.session_state.get("na_heat_selected") not in universe_tickers:
                    st.session_state.pop("na_heat_selected", None)

                with c.card(key="na_market_heatmap"):
                    c.section(
                        "Heatmap du sentiment de marché", icon="analytics",
                        subtitle="Vert = actualités favorables, rouge = défavorables · "
                                 "cliquez un instrument pour voir les actualités qui l'impactent",
                    )
                    if ranked_desc:
                        tile_css = []
                        for row_start in range(0, len(ranked_desc), 6):
                            row_cols = st.columns(6)
                            for col, r in zip(row_cols, ranked_desc[row_start:row_start + 6]):
                                ticker = r["ticker"]
                                key = f"na_heat_{ticker}"
                                count_label = (
                                    f'{r["news_count"]} actu'
                                    + ("s" if r["news_count"] != 1 else "")
                                )
                                with col:
                                    if st.button(
                                        f'{ticker}\n{r["weighted_sentiment"] * 100:+.1f}%',
                                        key=key, width="stretch",
                                        help=f'{catalog.sector_of(ticker)} · {count_label}',
                                    ):
                                        st.session_state["na_heat_selected"] = ticker
                                tile_css.append({
                                    "key": key, "value": r["weighted_sentiment"], "ticker": ticker,
                                })
                        active = st.session_state.get("na_heat_selected")
                        for t in tile_css:
                            t["selected"] = t["ticker"] == active
                        c.render(c.heatmap_button_css(tile_css))
                    else:
                        c.empty_state("Aucune donnée", icon="empty")

                selected = st.session_state.get("na_heat_selected")
                st.write("")
                with c.card(key="na_market_selected_news"):
                    if not selected:
                        c.section("Actualités qui impactent un instrument", icon="news")
                        c.empty_state(
                            "Aucun instrument sélectionné",
                            "Cliquez sur une tuile de la heatmap ci-dessus pour afficher les "
                            "actualités exactes qui influencent son sentiment.",
                            icon="news", variant="info",
                        )
                    else:
                        c.section(
                            f"Actualités qui impactent {catalog.label(selected)}", icon="news",
                            subtitle="Les dépêches à l'origine du sentiment pondéré de cet instrument, "
                                     "les plus récentes en premier.",
                            aside=c.chip_html("GET /news/{ticker}", tone="flat", mono=True, icon="api"),
                        )
                        try:
                            selected_news = api_client.ticker_news(selected)
                        except api_client.ApiError as error:
                            c.error_state(error.title, f"{error.message}\n\n{error.hint}")
                            selected_news = None

                        if selected_news and selected_news["items"]:
                            c.feed([
                                {
                                    "title": item["title"],
                                    "summary": item["description"][:220] if item["description"] else "",
                                    "url": item["url"],
                                    "icon": "news",
                                    "tone": SENTIMENT_TONE.get(item["sentiment"]["label"], "neutral"),
                                    "meta": (
                                        c.chip_html(item["source"], tone="flat", icon="database")
                                        + (c.chip_html(time_ago(item["publishedAt"]), tone="flat", icon="clock")
                                           if item["publishedAt"] else "")
                                        + c.chip_html(
                                            f'{item["sentiment"]["label"].title()} '
                                            f'{item["sentiment"]["score"] * 100:.0f}%',
                                            tone=SENTIMENT_CHIP_TONE.get(item["sentiment"]["label"], "flat"),
                                            icon="sentiment",
                                        )
                                        + c.chip_html(
                                            f'Impact {item["marketImpact"]["level"].title()}',
                                            tone=IMPACT_LEVEL_TONE.get(item["marketImpact"]["level"], "flat"),
                                            icon="impact",
                                        )
                                    ),
                                }
                                for item in selected_news["items"][:20]
                            ])
                        elif selected_news:
                            c.empty_state(
                                "Aucune actualité récente",
                                f"NewsAPI n'a renvoyé aucune dépêche exploitable pour {selected}.",
                                icon="news", variant="info",
                            )

                st.write("")
                with c.card(key="na_market_ranking"):
                    c.section(
                        "Classement détaillé", icon="table",
                        subtitle="Du plus favorable au plus défavorable",
                    )
                    entries = []
                    for r in ranked_desc:
                        count_chip = c.chip_html(
                            f'{r["news_count"]} actu' + ('s' if r["news_count"] > 1 else ''),
                            tone="flat", mono=True,
                        )
                        entries.append(
                            '<div class="opt-kv__row">'
                            '<span class="opt-kv__k">'
                            f'{c.instrument_html(r["ticker"], catalog.sector_of(r["ticker"]))}'
                            "</span>"
                            '<span class="opt-kv__v">'
                            f'{c.delta_html(r["weighted_sentiment"] * 100)}{count_chip}'
                            "</span>"
                            "</div>"
                        )
                    if entries:
                        c.render(f'<div class="opt-kv">{"".join(entries)}</div>')
                    else:
                        c.empty_state("Aucune donnée", icon="empty")

                st.info(DISCLAIMER, icon=st_icon("info"))
