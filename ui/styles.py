# -*- coding: utf-8 -*-
"""Global style injection.

Two layers are sent to the browser on every run:

1. A small `<style>` block holding the CSS custom properties derived from
   `ui.tokens` — this is what makes palette and density switchable at runtime.
2. `ui/assets/app.css`, the static stylesheet. Streamlit wraps a `.css` path in
   `<style>` tags automatically and routes style-only content to the event
   container, so it costs no vertical space in the layout.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ui import tokens

CSS_PATH = Path(__file__).parent / "assets" / "app.css"

# Card padding per density mode — the only geometry that changes between modes.
_DENSITY: dict[str, dict[str, str]] = {
    "compact": {"card_pad": "0.75rem", "gutter": "0.875rem"},
    "comfortable": {"card_pad": "1.0625rem", "gutter": "1.25rem"},
    "spacious": {"card_pad": "1.375rem", "gutter": "1.75rem"},
}

DENSITY_LABELS: dict[str, str] = {
    "compact": "Compact",
    "comfortable": "Comfortable",
    "spacious": "Spacious",
}


def _variables_css(palette_name: str, density: str) -> str:
    """Render the `:root` custom-property block from the design tokens."""
    p = tokens.palette(palette_name)
    d = _DENSITY.get(density, _DENSITY["comfortable"])

    declarations: list[str] = [
        # Surfaces
        f"--opt-bg-root: {p['bg_root']}",
        f"--opt-bg: {p['bg']}",
        f"--opt-bg-alt: {p['bg_alt']}",
        f"--opt-surface: {p['surface']}",
        f"--opt-surface-hi: {p['surface_hi']}",
        f"--opt-surface-low: {p['surface_low']}",
        f"--opt-sidebar: {p['sidebar']}",
        f"--opt-sidebar-hi: {p['sidebar_hi']}",
        # Borders
        f"--opt-border: {p['border']}",
        f"--opt-border-soft: {p['border_soft']}",
        f"--opt-border-strong: {p['border_strong']}",
        # Text
        f"--opt-text: {p['text']}",
        f"--opt-text-soft: {p['text_soft']}",
        f"--opt-text-muted: {p['text_muted']}",
        f"--opt-text-faint: {p['text_faint']}",
        # Accent
        f"--opt-accent: {p['accent']}",
        f"--opt-accent-hi: {p['accent_hi']}",
        f"--opt-accent-lo: {p['accent_lo']}",
        f"--opt-accent-soft: {p['accent_soft']}",
        f"--opt-accent-glow: {p['accent_glow']}",
        # Semantic
        f"--opt-up: {p['up']}",
        f"--opt-up-soft: {p['up_soft']}",
        f"--opt-up-text: {p['up_text']}",
        f"--opt-down: {p['down']}",
        f"--opt-down-soft: {p['down_soft']}",
        f"--opt-down-text: {p['down_text']}",
        f"--opt-warn: {p['warn']}",
        f"--opt-warn-soft: {p['warn_soft']}",
        f"--opt-warn-text: {p['warn_text']}",
        f"--opt-info: {p['info']}",
        f"--opt-violet: {p['violet']}",
        f"--opt-violet-soft: {p['violet_soft']}",
        f"--opt-neutral-soft: {p['neutral_soft']}",
        # Ambient background dressing (dark palettes only — "none" for the
        # light "Terminal" default, see ui/tokens.py)
        f"--opt-ambient: {p['ambient']}",
        f"--opt-hero-glow: {p['hero_glow']}",
        # Typography
        f"--opt-font-sans: {tokens.FONT_SANS}",
        f"--opt-font-mono: {tokens.FONT_MONO}",
        # Layout
        f"--opt-card-pad: {d['card_pad']}",
        f"--opt-gutter: {d['gutter']}",
        f"--opt-content-max: {tokens.LAYOUT['content_max']}",
        f"--opt-sidebar-w: {tokens.LAYOUT['sidebar_width']}",
    ]

    declarations += [f"--opt-fs-{k}: {v}" for k, v in tokens.FONT_SIZE.items()]
    declarations += [f"--opt-r-{k}: {v}" for k, v in tokens.RADIUS.items()]
    declarations += [f"--opt-shadow-{k}: {v}" for k, v in tokens.SHADOW.items()]
    declarations += [f"--opt-t-{k}: {v}" for k, v in tokens.MOTION.items()]
    declarations += [f"--opt-sp-{k}: {v}" for k, v in tokens.SPACING.items()]

    body = ";\n  ".join(declarations)
    return f":root {{\n  {body};\n}}"


def inject(palette_name: str | None = None, density: str = "comfortable") -> None:
    """Inject the design tokens and the application stylesheet."""
    st.html(f"<style>{_variables_css(palette_name or tokens.DEFAULT_PALETTE, density)}</style>")
    st.html(CSS_PATH)


def inject_light_shell() -> None:
    """Flip the app chrome to a plain white/black shell for the two
    unauthenticated screens (landing page, login/register) — the
    authenticated app (`app.css`, dark palette) is left completely
    untouched; this only overrides what those two screens need, and only
    while they're the thing being rendered (`inject()` above still runs
    first on every request, so signing in and getting the real shell back
    needs no special handling).

    Necessary because Streamlit's native widget chrome (background,
    buttons, inputs, labels) is driven by `.streamlit/config.toml`'s theme,
    which is global — it can't be conditionally swapped per screen, so the
    override has to happen here, in CSS, scoped to this call site instead.
    """
    st.html("""
    <style>
    [data-testid="stAppViewContainer"] { background: #FFFFFF !important; background-image: none !important; }
    [data-testid="stMain"], [data-testid="stMainBlockContainer"] { background: transparent !important; }
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    [data-testid="stHeader"] { background: transparent !important; }

    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
    [data-testid="stCaptionContainer"], .stCaption,
    label, [data-testid="stWidgetLabel"] p,
    h1, h2, h3, h4, h5, h6 {
        color: #0A0A0A !important;
    }

    [data-testid="stForm"] { background: transparent !important; border: none !important; }

    [data-baseweb="input"], [data-baseweb="base-input"] {
        background: #FFFFFF !important; border: 1px solid #D4D4D8 !important;
    }
    [data-baseweb="input"] input { color: #0A0A0A !important; }
    [data-baseweb="input"]:focus-within { border-color: #0A0A0A !important; }
    </style>
    """)
