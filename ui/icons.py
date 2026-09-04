# -*- coding: utf-8 -*-
"""Icon system built on Material Symbols Rounded.

Streamlit ships the Material Symbols Rounded font with its static bundle, so
icons render offline and stay pixel-consistent with the icons Streamlit itself
draws (`:material/...:` syntax in widget labels, page icons, alerts).

Two ways to emit an icon:
  * `st_icon("dashboard")`      -> `":material/dashboard:"` for Streamlit args
  * `icon_html("dashboard")`    -> `<span>` for custom HTML components
"""

from __future__ import annotations

from typing import Final

# Semantic name -> Material Symbols glyph name. Views reference semantic names
# so the icon set can be swapped without touching page code.
ICONS: Final[dict[str, str]] = {
    # Navigation
    "dashboard": "space_dashboard",
    "markets": "candlestick_chart",
    "portfolio": "account_balance_wallet",
    "watchlist": "bookmark_star",
    "trading": "swap_horiz",
    "orders": "receipt_long",
    "transactions": "sync_alt",
    "news": "newspaper",
    "analytics": "insights",
    "alerts": "notifications_active",
    "settings": "settings",
    "profile": "account_circle",
    "logout": "logout",
    # Metrics & finance
    "value": "savings",
    "profit": "trending_up",
    "loss": "trending_down",
    "cash": "payments",
    "assets": "inventory_2",
    "return": "percent",
    "performance": "show_chart",
    "risk": "gpp_maybe",
    "diversification": "donut_small",
    "allocation": "pie_chart",
    "sharpe": "speed",
    "volatility": "waves",
    "benchmark": "flag",
    "forecast": "auto_awesome",
    "sentiment": "psychology",
    "impact": "bolt",
    "target": "target",
    "drawdown": "south_east",
    # UI
    "search": "search",
    "bell": "notifications",
    "clock": "schedule",
    "theme": "contrast",
    "expand": "unfold_more",
    "filter": "filter_list",
    "sort": "swap_vert",
    "refresh": "refresh",
    "download": "download",
    "add": "add",
    "remove": "remove",
    "close": "close",
    "check": "check_circle",
    "warning": "warning",
    "error": "error",
    "info": "info",
    "empty": "inbox",
    "chevron_right": "chevron_right",
    "chevron_left": "chevron_left",
    "arrow_up": "arrow_upward",
    "arrow_down": "arrow_downward",
    "open": "open_in_new",
    "bolt": "bolt",
    "shield": "shield",
    "verified": "verified",
    "live": "sensors",
    "help": "help",
    "star": "star",
    "star_outline": "star_border",
    "delete": "delete",
    "edit": "edit",
    "buy": "add_shopping_cart",
    "sell": "sell",
    "rebalance": "balance",
    "table": "table_rows",
    "grid": "grid_view",
    "menu": "menu",
    "lock": "lock",
    "globe": "public",
    "sector": "category",
    "database": "database",
    "api": "cable",
    "model": "network_intelligence",
}


def glyph(name: str) -> str:
    """Resolve a semantic icon name to its Material Symbols glyph name."""
    return ICONS.get(name, name)


def st_icon(name: str) -> str:
    """Return the `:material/...:` token Streamlit understands in labels."""
    return f":material/{glyph(name)}:"


def icon_html(name: str, size: str = "1.125rem", color: str = "currentColor",
              classes: str = "") -> str:
    """Return an inline `<span>` icon for use inside custom HTML markup."""
    extra = f" {classes}" if classes else ""
    return (
        f'<span class="opt-icon{extra}" aria-hidden="true" '
        f'style="font-size:{size};color:{color}">{glyph(name)}</span>'
    )
