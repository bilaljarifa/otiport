# -*- coding: utf-8 -*-
"""Profile — workspace identity and activity summary."""

from __future__ import annotations

import streamlit as st

from services import api_client, catalog, store
from services.context import get as get_context
from ui import components as c, layout, styles, tokens
from ui.format import money, percent, signed_money, signed_percent, time_ago
from ui.icons import st_icon

ctx = get_context()
profile = store.user()
valuation = ctx.valuation

c.page_header(
    "Profil",
    eyebrow="Espace de travail",
    icon="profile",
    subtitle="Identité de l'utilisateur, préférences actives et activité sur le "
             "compte de démonstration.",
)

header = st.columns([1.6, 1])

with header[0]:
    with c.card("hero", key="identity"):
        c.render(
            '<div class="opt-row" style="gap:1rem;align-items:center">'
            f'{c.avatar_html(profile["initials"], large=True)}'
            '<div style="min-width:0">'
            f'<div style="font-size:var(--opt-fs-xl);font-weight:750;letter-spacing:-0.02em">'
            f'{c.esc(profile["name"])}</div>'
            f'<div class="opt-caption" style="font-size:var(--opt-fs-sm)">'
            f'{c.esc(profile["role"])} · {c.esc(profile["desk"])}</div>'
            '<div class="opt-row opt-row--wrap" style="margin-top:0.5rem">'
            + c.chip_html(profile["plan"], tone="info", icon="verified")
            + c.chip_html(f"Membre depuis {profile['member_since']}", tone="flat",
                          icon="clock")
            + c.chip_html(store.ACCOUNT_MODE, tone="warn", icon="shield")
            + "</div></div></div>"
        )

        st.write("")
        edit = st.columns(2)
        with edit[0]:
            name = st.text_input("Nom affiché", value=profile["name"],
                                 key="profile_name")
        with edit[1]:
            role = st.text_input("Fonction", value=profile["role"], key="profile_role")
        desk = st.text_input("Périmètre / desk", value=profile["desk"],
                             key="profile_desk")

        if st.button("Mettre à jour le profil", type="primary", width="stretch",
                     icon=st_icon("check"), key="profile_save"):
            try:
                store.update_profile(name=name, job_title=role, desk=desk)
            except api_client.ApiError as exc:
                st.error(exc.detail or str(exc))
            else:
                st.toast("Profil mis à jour", icon="✅")
                st.rerun()

        c.caption(
            "Le nom, la fonction et le desk sont enregistrés sur votre compte. "
            "Le nom d'utilisateur, l'e-mail et le mot de passe ne se modifient "
            "pas depuis cette page."
        )

with header[1]:
    with c.card(key="accountsummary"):
        c.section("Compte", subtitle="Valorisation courante", icon="value")
        c.kv_list([
            ("Valeur totale", money(valuation.get("equity", 0))),
            ("Liquidités", money(valuation.get("cash", 0))),
            ("Positions", str(valuation.get("positions_count", 0))),
            ("P&L latent", signed_money(valuation.get("pnl", 0))),
            ("Performance totale", signed_percent(valuation.get("total_return_pct", 0))),
        ])
        st.write("")
        if st.button("Ouvrir le portefeuille", width="stretch",
                     icon=st_icon("portfolio"), key="profile_to_portfolio"):
            layout.goto("portfolio")

st.write("")

c.kpi_row([
    c.kpi_html("Valeur du compte", money(valuation.get("equity", 0)),
               delta=valuation.get("day_pnl_pct"), icon="value", tone="accent"),
    c.kpi_html("Ordres passés", str(len(store.orders())), icon="orders", tone="info",
               hint=f"{len([o for o in store.orders() if o['status'] == 'FILLED'])} exécutés"),
    c.kpi_html("Transactions", str(len(store.transactions())), icon="transactions",
               tone="violet", hint="mouvements enregistrés"),
    c.kpi_html("Instruments suivis", str(len(store.watchlist())), icon="watchlist",
               tone="warn", hint=f"sur {len(catalog.TICKERS)} disponibles"),
    c.kpi_html("Alertes", str(len(store.alerts())), icon="alerts", tone="down",
               hint=f"{len([a for a in store.alerts() if a['status'] == 'ACTIVE'])} actives"),
], min_width="14rem")

st.write("")

body = st.columns([1.4, 1])

with body[0]:
    with c.card(key="activity"):
        c.section("Activité récente", subtitle="Derniers événements de la session",
                  icon="transactions")
        events = store.notifications()[:10]
        if not events:
            c.empty_state("Aucune activité",
                          "Les exécutions et alertes déclenchées apparaîtront ici.",
                          icon="empty")
        else:
            c.feed([
                {
                    "title": event["title"],
                    "summary": event["body"],
                    "icon": event["icon"],
                    "tone": event["tone"],
                    "meta": c.chip_html(time_ago(event["timestamp"]), tone="flat",
                                        icon="clock"),
                }
                for event in events
            ])

with body[1]:
    with c.card(key="prefsummary"):
        c.section("Préférences actives", icon="settings")
        prefs = store.prefs()
        c.kv_list([
            ("Palette", tokens.PALETTE_LABELS[prefs["palette"]]),
            ("Densité", styles.DENSITY_LABELS[prefs["density"]]),
            ("Période par défaut", prefs["chart_period"]),
            ("Taux sans risque", percent(prefs["risk_free_rate"] * 100, 2)),
            ("Montant par défaut", money(prefs["default_amount"])),
            ("Backend", prefs["api_url"]),
        ])
        st.write("")
        if st.button("Modifier les paramètres", width="stretch",
                     icon=st_icon("settings"), key="profile_to_settings"):
            layout.goto("settings")

    with c.card(key="security"):
        c.section("Sécurité et données", icon="lock")
        c.kv_list([
            ("Compte", c.chip_html(profile["username"], tone="info", icon="profile")),
            ("Rôle", c.chip_html(
                "Administrateur" if store.is_admin() else "Utilisateur",
                tone="warn" if store.is_admin() else "flat",
                icon="shield" if store.is_admin() else "info")),
            ("Mot de passe", c.chip_html("Haché (bcrypt), jamais stocké en clair",
                                         tone="up", icon="check")),
            ("Ordres réels", c.chip_html("Jamais transmis", tone="up", icon="shield")),
        ])
        c.caption(
            "Optiport ne stocke aucun moyen de paiement et n'est connecté à "
            "aucun courtier. Votre portefeuille simulé est propre à votre "
            "compte et n'est visible par aucun autre utilisateur."
        )
        st.write("")
        if st.button("Se déconnecter", width="stretch", type="secondary",
                     icon=st_icon("logout"), key="profile_logout"):
            layout.goto("logout")
