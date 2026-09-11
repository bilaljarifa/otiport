# -*- coding: utf-8 -*-
"""Logout — session summary and sign-out confirmation."""

from __future__ import annotations

import streamlit as st

from services import store
from services.context import get as get_context
from ui import components as c, layout
from ui.format import money, signed_money, signed_percent
from ui.icons import st_icon

ctx = get_context()
valuation = ctx.valuation

c.page_header(
    "Déconnexion",
    eyebrow="Fin de session",
    icon="logout",
    subtitle="Récapitulatif de la session avant de quitter l'espace de travail.",
)

columns = st.columns([1.4, 1])

with columns[0]:
    with c.card(key="sessionsummary"):
        c.section("Récapitulatif de session", icon="dashboard",
                  subtitle="État du compte simulé au moment de la déconnexion")
        c.kv_list([
            ("Valeur du compte", money(valuation.get("equity", 0))),
            ("Liquidités", money(valuation.get("cash", 0))),
            ("Positions ouvertes", str(valuation.get("positions_count", 0))),
            ("P&L latent", signed_money(valuation.get("pnl", 0))),
            ("Performance totale", signed_percent(valuation.get("total_return_pct", 0))),
            ("Ordres passés", str(len(store.orders()))),
            ("Alertes configurées", str(len(store.alerts()))),
        ])

    with c.card(key="signoutaction"):
        c.section("Quitter la plateforme", icon="logout")
        st.info(
            "Votre portefeuille simulé (positions, ordres, transactions, "
            "alertes) est conservé sur le serveur : reconnectez-vous avec "
            "votre compte pour le retrouver tel quel.",
            icon=st_icon("info"),
        )
        actions = st.columns(2)
        if actions[0].button("Se déconnecter", type="primary", width="stretch",
                             icon=st_icon("logout"), key="logout_confirm"):
            store.sign_out()
            st.rerun()
        if actions[1].button("Rester connecté", width="stretch",
                             icon=st_icon("dashboard"), key="logout_cancel"):
            layout.goto("dashboard")

with columns[1]:
    with c.card(key="logoutnote"):
        c.section("Avant de partir", icon="info")
        c.kv_list([
            ("Compte", c.chip_html(store.ACCOUNT_MODE, tone="warn", icon="shield")),
            ("Ordres réels", c.chip_html("Aucun", tone="up", icon="check")),
            ("Mot de passe", c.chip_html("Jamais stocké en clair", tone="up",
                                         icon="check")),
        ])
        c.caption(
            "Aucun ordre n'a été transmis à un courtier : l'ensemble des "
            "exécutions de cette session est simulé, aux cours réels du marché."
        )
