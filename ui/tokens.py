# -*- coding: utf-8 -*-
"""Design tokens — the single source of truth for the Optiport design system.

Everything visual derives from this module: the injected CSS variables
(`ui.styles`), the Plotly chart template (`ui.charts`) and the inline styles of
custom components (`ui.components`). `.streamlit/config.toml` mirrors the
default palette so native Streamlit widgets match without CSS overrides.

Changing a value here propagates through the whole application.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
#  Color palettes
# ---------------------------------------------------------------------------
# Two production-grade dark palettes. "midnight" is the reference navy palette;
# "graphite" is a neutral variant for users who prefer lower color temperature.
# Both share the same semantic keys so any component works with either.

MIDNIGHT: Final[dict[str, str]] = {
    # Surfaces, from deepest to most elevated
    "bg_root": "#070C15",
    "bg": "#0B1220",
    "bg_alt": "#111827",
    "surface": "#1E293B",
    "surface_hi": "#243449",
    "surface_low": "#16213A",
    "sidebar": "#080E1A",
    "sidebar_hi": "#141F35",
    # Borders
    "border": "#334155",
    "border_soft": "rgba(51, 65, 85, 0.55)",
    "border_strong": "#41526B",
    # Text
    "text": "#FFFFFF",
    "text_soft": "#E2E8F0",
    "text_muted": "#94A3B8",
    # Lightened from the classic slate-500 so captions clear WCAG AA (4.5:1)
    # against the #0B1220 background — measured at 4.6:1.
    "text_faint": "#7C8AA3",
    # Brand / accent
    "accent": "#3B82F6",
    "accent_hi": "#60A5FA",
    "accent_lo": "#2563EB",
    "accent_soft": "rgba(59, 130, 246, 0.12)",
    "accent_glow": "rgba(59, 130, 246, 0.35)",
    # Semantic
    "up": "#22C55E",
    "up_soft": "rgba(34, 197, 94, 0.12)",
    "up_text": "#4ADE80",
    "down": "#EF4444",
    "down_soft": "rgba(239, 68, 68, 0.12)",
    "down_text": "#F87171",
    "warn": "#F59E0B",
    "warn_soft": "rgba(245, 158, 11, 0.12)",
    "warn_text": "#FBBF24",
    "info": "#06B6D4",
    "info_soft": "rgba(6, 182, 212, 0.12)",
    "violet": "#8B5CF6",
    "violet_soft": "rgba(139, 92, 246, 0.12)",
    "neutral_soft": "rgba(148, 163, 184, 0.12)",
    # Ambient background dressing — dark palettes only, see TERMINAL below.
    "ambient": (
        "radial-gradient(1100px 620px at 12% -8%, rgba(59, 130, 246, 0.10), transparent 60%), "
        "radial-gradient(900px 560px at 92% 4%, rgba(139, 92, 246, 0.07), transparent 62%), "
        "radial-gradient(1200px 800px at 50% 110%, rgba(6, 182, 212, 0.05), transparent 65%)"
    ),
    "hero_glow": "radial-gradient(120% 140% at 0% 0%, rgba(59, 130, 246, 0.16), transparent 55%)",
}

GRAPHITE: Final[dict[str, str]] = {
    **MIDNIGHT,
    "bg_root": "#0A0A0C",
    "bg": "#101114",
    "bg_alt": "#16181C",
    "surface": "#1E2126",
    "surface_hi": "#282C33",
    "surface_low": "#191C21",
    "sidebar": "#0C0D10",
    "sidebar_hi": "#181B20",
    "border": "#31363F",
    "border_soft": "rgba(49, 54, 63, 0.6)",
    "border_strong": "#414855",
    "text_soft": "#E4E6EB",
    "text_muted": "#9BA3AF",
    "text_faint": "#868E9C",
}

# The primary Optiport experience: a flat, professional light "terminal"
# theme — white/near-black/gray, no gradients, no purple/blue accent. The
# sidebar stays a dark nav rail (a deliberate, common institutional pattern:
# dark chrome around a light workspace, not a fully white app) — everything
# else is white/near-white. Green/red are reserved for market up/down only;
# "accent" here is near-black, not a hue, so buttons/links/focus rings read
# as ink, not brand-color decoration.
TERMINAL: Final[dict[str, str]] = {
    "bg_root": "#FFFFFF",
    "bg": "#FFFFFF",
    "bg_alt": "#FAFAFA",
    "surface": "#FFFFFF",
    "surface_hi": "#F4F4F5",
    "surface_low": "#FAFAFA",
    "sidebar": "#0A0A0A",
    "sidebar_hi": "#171717",
    "border": "#E4E4E7",
    "border_soft": "rgba(228, 228, 231, 0.8)",
    "border_strong": "#D4D4D8",
    "text": "#0A0A0A",
    "text_soft": "#18181B",
    "text_muted": "#52525B",
    "text_faint": "#71717A",
    "accent": "#0A0A0A",
    "accent_hi": "#262626",
    "accent_lo": "#000000",
    "accent_soft": "rgba(10, 10, 10, 0.05)",
    "accent_glow": "rgba(10, 10, 10, 0.14)",
    "up": "#16A34A",
    "up_soft": "rgba(22, 163, 74, 0.10)",
    "up_text": "#15803D",
    "down": "#DC2626",
    "down_soft": "rgba(220, 38, 38, 0.10)",
    "down_text": "#B91C1C",
    "warn": "#D97706",
    "warn_soft": "rgba(217, 119, 6, 0.10)",
    "warn_text": "#B45309",
    "info": "#0369A1",
    "info_soft": "rgba(3, 105, 161, 0.10)",
    "violet": "#6D28D9",
    "violet_soft": "rgba(109, 40, 217, 0.08)",
    "neutral_soft": "rgba(113, 113, 122, 0.08)",
    "ambient": "none",
    "hero_glow": "none",
}

PALETTES: Final[dict[str, dict[str, str]]] = {
    "terminal": TERMINAL,
    "midnight": MIDNIGHT,
    "graphite": GRAPHITE,
}

DEFAULT_PALETTE: Final[str] = "terminal"

PALETTE_LABELS: Final[dict[str, str]] = {
    "terminal": "Terminal (light)",
    "midnight": "Midnight (dark)",
    "graphite": "Graphite (dark)",
}


def palette(name: str | None = None) -> dict[str, str]:
    """Return a palette by name, falling back to the default."""
    return PALETTES.get(name or DEFAULT_PALETTE, MIDNIGHT)


# ---------------------------------------------------------------------------
#  Spacing — 4px base scale
# ---------------------------------------------------------------------------
SPACING: Final[dict[str, str]] = {
    "0": "0",
    "1": "0.25rem",   # 4
    "2": "0.5rem",    # 8
    "3": "0.75rem",   # 12
    "4": "1rem",      # 16
    "5": "1.25rem",   # 20
    "6": "1.5rem",    # 24
    "7": "2rem",      # 32
    "8": "2.5rem",    # 40
    "9": "3rem",      # 48
    "10": "4rem",     # 64
}

# ---------------------------------------------------------------------------
#  Radius — crisp, institutional corners (not the rounded "consumer app"
#  look). Pill stays sharp-cornerless only for chips/badges, where a full
#  stadium shape is the standard, expected convention, not decoration.
# ---------------------------------------------------------------------------
RADIUS: Final[dict[str, str]] = {
    "xs": "0.1875rem",
    "sm": "0.25rem",
    "md": "0.375rem",
    "lg": "0.5rem",
    "xl": "0.625rem",
    "2xl": "0.75rem",
    "pill": "999px",
}

# ---------------------------------------------------------------------------
#  Elevation
# ---------------------------------------------------------------------------
SHADOW: Final[dict[str, str]] = {
    "xs": "0 1px 2px rgba(2, 6, 23, 0.4)",
    "sm": "0 2px 6px -1px rgba(2, 6, 23, 0.45)",
    "md": "0 6px 20px -6px rgba(2, 6, 23, 0.65)",
    "lg": "0 16px 40px -12px rgba(2, 6, 23, 0.8)",
    "xl": "0 28px 64px -20px rgba(2, 6, 23, 0.9)",
    "inset": "inset 0 1px 0 rgba(255, 255, 255, 0.04)",
    "focus": "0 0 0 3px rgba(59, 130, 246, 0.35)",
}

# ---------------------------------------------------------------------------
#  Typography
# ---------------------------------------------------------------------------
FONT_SANS: Final[str] = (
    "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "'Helvetica Neue', Arial, sans-serif"
)
FONT_MONO: Final[str] = (
    "'JetBrains Mono', ui-monospace, SFMono-Regular, 'SF Mono', Consolas, "
    "'Liberation Mono', monospace"
)

FONT_SIZE: Final[dict[str, str]] = {
    "2xs": "0.6875rem",  # 11
    "xs": "0.75rem",     # 12
    "sm": "0.8125rem",   # 13
    "base": "0.875rem",  # 14
    "md": "0.9375rem",   # 15
    "lg": "1.0625rem",   # 17
    "xl": "1.25rem",     # 20
    "2xl": "1.5rem",     # 24
    "3xl": "1.875rem",   # 30
    "4xl": "2.375rem",   # 38
}

FONT_WEIGHT: Final[dict[str, int]] = {
    "regular": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
    "black": 800,
}

# ---------------------------------------------------------------------------
#  Motion
# ---------------------------------------------------------------------------
MOTION: Final[dict[str, str]] = {
    "fast": "120ms cubic-bezier(0.4, 0, 0.2, 1)",
    "base": "200ms cubic-bezier(0.4, 0, 0.2, 1)",
    "slow": "320ms cubic-bezier(0.16, 1, 0.3, 1)",
    "spring": "480ms cubic-bezier(0.34, 1.36, 0.64, 1)",
}

# ---------------------------------------------------------------------------
#  Layout
# ---------------------------------------------------------------------------
LAYOUT: Final[dict[str, str]] = {
    "sidebar_width": "16.5rem",
    "topbar_height": "3.5rem",
    "content_max": "1680px",
    "gutter": "1.25rem",
}

# ---------------------------------------------------------------------------
#  Chart palettes — mirrored in .streamlit/config.toml
# ---------------------------------------------------------------------------
CHART_CATEGORICAL: Final[tuple[str, ...]] = (
    "#3B82F6", "#22C55E", "#F59E0B", "#8B5CF6", "#06B6D4", "#EC4899",
    "#14B8A6", "#F97316", "#6366F1", "#84CC16", "#A855F7", "#0EA5E9",
)

CHART_SEQUENTIAL: Final[tuple[str, ...]] = (
    "#0B1F3A", "#12325C", "#1A467F", "#215BA2", "#2970C5", "#3B82F6",
    "#5B9BF8", "#8CBAFB", "#BDD7FD", "#E3EDFE",
)

# ---------------------------------------------------------------------------
#  Domain color mappings — keep signals and regions visually stable app-wide
# ---------------------------------------------------------------------------
SIGNAL_TONE: Final[dict[str, str]] = {
    "Strong Buy": "up",
    "Buy": "up",
    "Hold": "warn",
    "Light": "info",
    "Reduce": "down",
    "Avoid": "down",
}

REGION_COLOR: Final[dict[str, str]] = {
    "North America": "#3B82F6",
    "Developed Markets": "#8B5CF6",
    "Emerging Markets": "#F59E0B",
    "Other": "#64748B",
}

# Risk profile → optimizer strategy. Mirrors the mapping the original app used,
# kept here so both the UI labels and the API payload share one definition.
RISK_PROFILES: Final[dict[str, dict[str, str]]] = {
    "Conservative": {
        "strategy": "min_volatility",
        "icon": "shield",
        "caption": "Minimise la volatilité du portefeuille",
    },
    "Balanced": {
        "strategy": "risk_parity",
        "icon": "balance",
        "caption": "Contribution au risque égale entre actifs",
    },
    "Growth": {
        "strategy": "max_sharpe",
        "icon": "rocket_launch",
        "caption": "Maximise le rendement ajusté du risque",
    },
    "Equal Weight": {
        "strategy": "equal_weight",
        "icon": "grid_view",
        "caption": "Allocation uniforme, sans optimisation",
    },
}
