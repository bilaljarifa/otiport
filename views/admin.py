# -*- coding: utf-8 -*-
"""Administration — user management and system stats.

Only reachable from the sidebar when `store.is_admin()` (see `app.py`'s
`navigation()`), but that is a UX convenience, not the security boundary:
every call below hits an `/admin/*` endpoint that independently re-checks
the caller's role server-side (`backend/deps.py::require_admin`). A non-admin
who opens this page directly gets a 403 from the very first API call.

Deliberately scoped to *account* management — there is no view here into
another user's portfolio, orders, watchlist or alerts (see README).
"""

from __future__ import annotations

import streamlit as st

from services import api_client, store
from ui import components as c
from ui.format import money, time_ago
from ui.icons import st_icon

c.page_header(
    "Administration",
    eyebrow="Gestion des comptes",
    icon="shield",
    subtitle="Utilisateurs, rôles et statistiques système. Réservé aux "
             "administrateurs — sans accès aux portefeuilles individuels.",
)

me = store.user()


def _guard_error(exc: api_client.ApiError) -> None:
    if exc.kind == "offline":
        c.error_state("Backend injoignable", exc.hint)
        st.code("uvicorn api:app --reload --port 8000", language="bash")
    else:
        c.error_state("Erreur", exc.detail or str(exc))


def _apply_change(user_id: int, *, role: str | None = None, is_active: bool | None = None) -> None:
    try:
        api_client.admin_update_user(user_id, role=role, is_active=is_active)
    except api_client.AuthError:
        store.sign_out()
        st.rerun()
    except api_client.ApiError as exc:
        st.error(exc.detail or str(exc))
        return
    st.toast("Utilisateur mis à jour", icon="✅")
    st.rerun()


def _delete_user(user_id: int) -> None:
    try:
        api_client.admin_delete_user(user_id)
    except api_client.AuthError:
        store.sign_out()
        st.rerun()
    except api_client.ApiError as exc:
        st.error(exc.detail or str(exc))
        return
    st.toast("Utilisateur supprimé", icon="🗑️")
    st.rerun()


try:
    stats = api_client.admin_stats()
except api_client.AuthError:
    store.sign_out()
    st.rerun()
except api_client.ApiError as exc:
    _guard_error(exc)
    st.stop()

c.kpi_row([
    c.kpi_html("Utilisateurs", str(stats["total_users"]), icon="profile", tone="accent",
               hint=f"{stats['active_users']} actifs · {stats['disabled_users']} désactivés"),
    c.kpi_html("Administrateurs", str(stats["admin_users"]), icon="shield", tone="warn"),
    c.kpi_html("Comptes simulés", str(stats["total_accounts"]), icon="portfolio", tone="info"),
    c.kpi_html("Liquidités cumulées", money(stats["total_cash"]), icon="value", tone="up"),
    c.kpi_html("Ordres au total", str(stats["total_orders"]), icon="orders",
               tone="violet", hint=f"{stats['total_open_orders']} en attente"),
], min_width="13rem")

st.write("")

try:
    users = api_client.admin_list_users()
except api_client.AuthError:
    store.sign_out()
    st.rerun()
except api_client.ApiError as exc:
    _guard_error(exc)
    st.stop()

ROLE_OPTIONS = ["user", "admin"]
ROLE_LABEL = {"user": "Utilisateur", "admin": "Administrateur"}

with c.card(key="users"):
    c.section(
        "Utilisateurs", icon="profile",
        subtitle=f"{len(users)} compte(s) — rôle, statut et actions",
        aside=c.chip_html(f"Backend v{stats['backend_version']}", tone="flat", icon="api"),
    )

    header = st.columns([2.4, 1.3, 1.3, 1.6, 1.8], vertical_alignment="center")
    for col, label in zip(header, ["Utilisateur", "Rôle", "Statut", "Créé", "Actions"]):
        col.markdown(f'<span class="opt-caption">{label.upper()}</span>', unsafe_allow_html=True)

    for u in users:
        is_self = u["id"] == me.get("id")
        columns = st.columns([2.4, 1.3, 1.3, 1.6, 1.8], vertical_alignment="center")

        with columns[0]:
            c.render(
                '<div style="font-weight:600">' + c.esc(u["full_name"]) + "</div>"
                f'<div class="opt-caption">@{c.esc(u["username"])} · {c.esc(u["email"])}</div>'
            )
        with columns[1]:
            c.render(c.chip_html(
                ROLE_LABEL[u["role"]], tone="warn" if u["role"] == "admin" else "flat",
                icon="shield" if u["role"] == "admin" else "info",
            ))
        with columns[2]:
            c.render(c.chip_html(
                "Actif" if u["is_active"] else "Désactivé",
                tone="up" if u["is_active"] else "down",
                icon="check" if u["is_active"] else "close",
            ))
        with columns[3]:
            c.render(f'<span class="opt-caption">{time_ago(u["created_at"])}</span>')
        with columns[4]:
            with st.popover("Gérer", icon=st_icon("settings"), width="stretch",
                            disabled=is_self, help="Vous ne pouvez pas modifier votre propre compte"):
                new_role = st.selectbox(
                    "Rôle", ROLE_OPTIONS, index=ROLE_OPTIONS.index(u["role"]),
                    format_func=lambda r: ROLE_LABEL[r], key=f"role_{u['id']}",
                )
                if st.button("Changer le rôle", key=f"apply_role_{u['id']}", width="stretch"):
                    _apply_change(u["id"], role=new_role)

                toggle_label = "Désactiver le compte" if u["is_active"] else "Réactiver le compte"
                if st.button(toggle_label, key=f"toggle_{u['id']}", width="stretch",
                             type="secondary"):
                    _apply_change(u["id"], is_active=not u["is_active"])

                st.divider()
                confirm = st.checkbox("Confirmer la suppression", key=f"confirm_del_{u['id']}")
                if st.button("Supprimer définitivement", key=f"delete_{u['id']}",
                             width="stretch", disabled=not confirm, icon=st_icon("delete")):
                    _delete_user(u["id"])

    if not users:
        c.empty_state("Aucun utilisateur", icon="empty")
