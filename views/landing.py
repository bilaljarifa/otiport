# -*- coding: utf-8 -*-
"""Public landing page — the first thing an unauthenticated visitor sees.

Not a page in the `st.Page` sense (those are only registered once
authenticated — see `app.py::navigation()`). Rendered directly by
`app.py::main()` whenever `store.is_authenticated()` is false and
`store.auth_view() == "landing"`.

Visual identity is deliberately distinct from the authenticated app's dark
palette: white background, near-black text, gray borders, no gradients —
a plain institutional/trading-terminal look (see `ui.styles.inject_light_shell`
for how the app's own dark chrome gets overridden just for this screen).
Green/red are used *only* for market up/down data, never as decoration.

Purely presentational: it makes no backend call, so it renders instantly and
stays reachable even if the FastAPI backend is offline. The only interactive
elements are the Log in / Create account / Get Started / Create your account
buttons, which switch `store.auth_view()` to "login"/"register" and rerun
into `views/auth.py`. Everything else — nav "scroll to section" links, the
market card, feature cards — is static HTML rendered via `ui.components.render`.
"""

from __future__ import annotations

import streamlit as st

from services import catalog, store
from ui import components as c, styles
from ui.format import money
from ui.icons import icon_html

# Deterministic, clearly-illustrative sparkline shapes. This page must render
# before any authentication or backend call, so it never fetches a real
# quote — every price/curve here is labelled as illustrative rather than
# implying it's live.
_DEMO_CURVES: tuple[tuple[float, ...], ...] = (
    (100, 101, 100, 103, 105, 104, 107, 110, 109, 113, 116, 115, 119, 123),
    (100, 100, 102, 101, 103, 104, 103, 106, 108, 107, 110, 112, 111, 114),
    (100, 99, 101, 98, 99, 96, 97, 94, 95, 92, 93, 90, 91, 88),
    (100, 102, 101, 104, 103, 106, 105, 108, 110, 109, 112, 111, 114, 117),
)
_DEMO_CHANGES = (1.24, 0.68, -0.41, 0.92, 2.10, -0.85)


def _curve_for(ticker: str) -> tuple[float, ...]:
    return _DEMO_CURVES[hash(ticker) % len(_DEMO_CURVES)]


def _change_for(ticker: str) -> float:
    return _DEMO_CHANGES[hash(ticker) % len(_DEMO_CHANGES)]


def _go(view: str) -> None:
    store.set_auth_view(view)
    st.rerun()


# ---------------------------------------------------------------------------
#  Styles
# ---------------------------------------------------------------------------

def _styles() -> None:
    styles.inject_light_shell()
    c.render("""
    <style>
    :root {
        --optl-bg-alt: #FAFAFA; --optl-bg-soft: #F4F4F5;
        --optl-border: #E4E4E7; --optl-border-strong: #D4D4D8;
        --optl-text: #0A0A0A; --optl-muted: #52525B; --optl-faint: #71717A;
        --optl-up: #15803D; --optl-down: #B91C1C;
        --optl-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    #markets, #intelligence, #how-it-works, #portfolio { scroll-margin-top: 4.5rem; }

    .optl-eyebrow {
        display: inline-flex; align-items: center; gap: 0.5rem;
        font-size: 0.6875rem; font-weight: 700; letter-spacing: 0.14em;
        text-transform: uppercase; color: var(--optl-faint);
    }
    .optl-eyebrow::before { content: ""; width: 1.25rem; height: 1px; background: var(--optl-text); }

    /* ---- Nav ---- */
    .st-key-landing_nav {
        position: sticky; top: 0; z-index: 30; background: #fff;
        border-bottom: 1px solid var(--optl-border); padding: 0.85rem 0;
    }
    .st-key-landing_nav [data-testid^="stBaseButton"] {
        border-radius: 4px !important; font-weight: 600 !important;
        padding: 0.4rem 0.95rem !important; box-shadow: none !important;
    }
    .st-key-landing_nav [data-testid="stBaseButton-secondary"] {
        background: #fff !important; color: var(--optl-text) !important;
        border: 1px solid var(--optl-border-strong) !important;
    }
    .st-key-landing_nav [data-testid="stBaseButton-secondary"]:hover { border-color: var(--optl-text) !important; }
    .st-key-landing_nav [data-testid="stBaseButton-primary"] {
        background: var(--optl-text) !important; color: #fff !important; border: 1px solid var(--optl-text) !important;
    }
    .st-key-landing_nav [data-testid="stBaseButton-primary"]:hover { background: #262626 !important; }
    .optl-navlinks {
        display: flex; align-items: center; gap: 1.75rem; height: 2.1rem;
        font-size: 0.8125rem; font-weight: 600; color: var(--optl-muted);
    }
    .optl-navlinks a { color: inherit; text-decoration: none; }
    .optl-navlinks a:hover { color: var(--optl-text); }

    /* ---- Hero ---- */
    .optl-hero-copy h1 {
        font-size: clamp(1.85rem, 3.2vw, 2.75rem); font-weight: 800; letter-spacing: -0.02em;
        line-height: 1.15; margin: 0.75rem 0 1rem; color: var(--optl-text);
    }
    .optl-hero-copy p {
        font-size: 1.0625rem; color: var(--optl-muted); line-height: 1.65; max-width: 30rem;
        margin: 0 0 1.5rem;
    }
    .st-key-landing_hero_actions [data-testid="stBaseButton-primary"] {
        background: var(--optl-text) !important; color: #fff !important; border: 1px solid var(--optl-text) !important;
        font-weight: 700 !important; border-radius: 4px !important; padding: 0.65rem 1.1rem !important;
        box-shadow: none !important;
    }
    .st-key-landing_hero_actions [data-testid="stBaseButton-primary"]:hover { background: #262626 !important; }
    .optl-hero-explore {
        display: flex; align-items: center; justify-content: center;
        height: 100%; min-height: 2.6rem; border: 1px solid var(--optl-border-strong);
        border-radius: 4px; color: var(--optl-text); font-weight: 700; font-size: 0.9375rem;
        text-decoration: none;
    }
    .optl-hero-explore:hover { border-color: var(--optl-text); }

    /* Market card */
    .optl-mcard {
        background: #fff; border: 1px solid var(--optl-border); border-radius: 6px;
        overflow: hidden;
    }
    .optl-mcard__head {
        display: flex; align-items: baseline; justify-content: space-between;
        padding: 1rem 1.125rem; border-bottom: 1px solid var(--optl-border);
    }
    .optl-mcard__sym { font-family: var(--optl-mono); font-weight: 700; font-size: 0.9375rem; color: var(--optl-text); }
    .optl-mcard__name { font-size: 0.75rem; color: var(--optl-faint); margin-left: 0.5rem; }
    .optl-mcard__price { font-family: var(--optl-mono); font-weight: 700; font-size: 1.375rem; color: var(--optl-text); }
    .optl-mcard__delta { font-family: var(--optl-mono); font-size: 0.8125rem; font-weight: 700; margin-left: 0.5rem; }
    .optl-mcard__delta--up { color: var(--optl-up); }
    .optl-mcard__delta--down { color: var(--optl-down); }
    .optl-mcard__chart { padding: 0.5rem 1.125rem 0.25rem; }
    .optl-mcard__rows { border-top: 1px solid var(--optl-border); }
    .optl-mrow {
        display: flex; align-items: center; justify-content: space-between;
        padding: 0.625rem 1.125rem; border-bottom: 1px solid var(--optl-bg-soft);
        font-family: var(--optl-mono); font-size: 0.8125rem;
    }
    .optl-mrow:last-child { border-bottom: none; }
    .optl-mrow__left { display: flex; align-items: center; gap: 0.625rem; }
    .optl-mrow__sym { font-weight: 700; color: var(--optl-text); width: 3.2rem; }
    .optl-mrow__right { display: flex; align-items: center; gap: 0.75rem; }

    /* ---- Ticker rail ---- */
    .optl-rail {
        display: flex; flex-wrap: wrap; gap: 0.625rem; padding-top: 1.25rem;
        border-top: 1px solid var(--optl-border);
    }
    .optl-chip {
        display: flex; align-items: center; gap: 0.5rem;
        border: 1px solid var(--optl-border); border-radius: 4px; padding: 0.4rem 0.75rem;
        font-family: var(--optl-mono); font-size: 0.75rem;
    }
    .optl-chip__sym { font-weight: 700; color: var(--optl-text); }

    /* ---- Section heads ---- */
    .optl-head { margin: 0 0 2rem; }
    .optl-head h2 {
        font-size: clamp(1.375rem, 2.4vw, 1.875rem); font-weight: 800; letter-spacing: -0.015em;
        margin: 0.5rem 0 0.375rem; color: var(--optl-text);
    }
    .optl-head p { color: var(--optl-muted); font-size: 0.9375rem; margin: 0; max-width: 34rem; }

    /* ---- Feature grid ---- */
    .optl-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); }
    .optl-fcard {
        border: 1px solid var(--optl-border); padding: 1.5rem;
        margin: -1px 0 0 -1px;
    }
    .optl-fcard__icon {
        width: 2.25rem; height: 2.25rem; border: 1px solid var(--optl-text); border-radius: 4px;
        display: flex; align-items: center; justify-content: center; margin-bottom: 1rem; color: var(--optl-text);
    }
    .optl-fcard h3 { font-size: 1rem; font-weight: 700; margin: 0 0 0.375rem; color: var(--optl-text); }
    .optl-fcard p { font-size: 0.875rem; color: var(--optl-muted); margin: 0; line-height: 1.55; }

    /* ---- Steps ---- */
    .optl-steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 1.75rem; }
    .optl-step__num {
        font-family: var(--optl-mono); font-size: 0.8125rem; font-weight: 700; color: var(--optl-faint);
        border-bottom: 2px solid var(--optl-text); display: inline-block; padding-bottom: 0.5rem;
        margin-bottom: 0.75rem; width: 100%;
    }
    .optl-step h4 { font-size: 0.9375rem; font-weight: 700; margin: 0 0 0.25rem; color: var(--optl-text); }
    .optl-step p { font-size: 0.8125rem; color: var(--optl-muted); margin: 0; line-height: 1.55; }

    /* ---- Paper trading ---- */
    .optl-paper {
        border: 1px solid var(--optl-border); background: var(--optl-bg-alt);
        border-radius: 6px; padding: 2rem;
        display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1.5rem;
    }
    .optl-paper__stat { font-size: clamp(1.5rem, 3.2vw, 2.125rem); font-weight: 800; color: var(--optl-text); letter-spacing: -0.01em; }
    .optl-paper__copy { max-width: 26rem; color: var(--optl-muted); font-size: 0.875rem; margin-top: 0.5rem; line-height: 1.6; }

    /* ---- Final CTA ---- */
    .optl-cta { background: var(--optl-text); border-radius: 6px; text-align: center; padding: 3rem 1.5rem; }
    .optl-cta h2 { color: #fff; font-size: clamp(1.375rem, 2.8vw, 2rem); font-weight: 800; margin: 0 0 1.5rem; letter-spacing: -0.015em; }
    .st-key-landing_cta_action { max-width: 16rem; margin: 0 auto; }
    .st-key-landing_cta_action [data-testid="stBaseButton-primary"] {
        background: #fff !important; color: var(--optl-text) !important; border: none !important;
        font-weight: 700 !important; border-radius: 4px !important; padding: 0.65rem 1.25rem !important;
        box-shadow: none !important;
    }
    .st-key-landing_cta_action [data-testid="stBaseButton-primary"]:hover { background: #F4F4F5 !important; }

    /* ---- Footer ---- */
    .optl-footer {
        display: flex; flex-wrap: wrap; justify-content: space-between; gap: 1rem;
        border-top: 1px solid var(--optl-border); padding: 1.75rem 0 2.5rem;
        color: var(--optl-faint); font-size: 0.8125rem;
    }
    .optl-footer a { color: var(--optl-muted); text-decoration: none; margin-right: 1.25rem; }
    .optl-footer a:hover { color: var(--optl-text); }
    </style>
    """)


# ---------------------------------------------------------------------------
#  Sections
# ---------------------------------------------------------------------------

def _nav() -> None:
    with st.container(key="landing_nav"):
        cols = st.columns([2.4, 3.4, 0.9, 1.1], vertical_alignment="center")
        with cols[0]:
            c.render(c.brand_wordmark_html(mark_size="1.9rem", text_size="1.0625rem"))
        with cols[1]:
            c.render(
                '<div class="optl-navlinks">'
                '<a href="#markets">Markets</a>'
                '<a href="#intelligence">Intelligence</a>'
                '<a href="#portfolio">Portfolio</a>'
                '<a href="#how-it-works">How it works</a>'
                "</div>"
            )
        with cols[2]:
            if st.button("Log in", key="nav_login", width="stretch"):
                _go("login")
        with cols[3]:
            if st.button("Create account", key="nav_register", type="primary", width="stretch"):
                _go("register")


def _market_card() -> None:
    rows = "".join(
        '<div class="optl-mrow"><div class="optl-mrow__left">'
        f'<span class="optl-mrow__sym">{c.esc(t)}</span>'
        f'{c.sparkline_html(_curve_for(t), width=64, height=20, area=False)}'
        '</div><div class="optl-mrow__right">'
        f'<span class="optl-mcard__delta optl-mcard__delta--{"up" if _change_for(t) >= 0 else "down"}">'
        f'{_change_for(t):+.2f}%</span></div></div>'
        for t in catalog.DEFAULT_SELECTION[:4]
    )
    c.render(
        '<div class="optl-mcard"><div class="optl-mcard__head"><div>'
        f'<span class="optl-mcard__sym">{c.esc(catalog.BENCHMARK)}</span>'
        f'<span class="optl-mcard__name">{c.esc(catalog.BENCHMARK_LABEL)}</span></div>'
        '<div><span class="optl-mcard__price">642.31</span>'
        '<span class="optl-mcard__delta optl-mcard__delta--up">+1.24%</span></div></div>'
        f'<div class="optl-mcard__chart">{c.sparkline_html(_curve_for("SPY"), width=None, height=64, tone="up")}</div>'
        f'<div class="optl-mcard__rows">{rows}</div></div>'
    )


def _hero() -> None:
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        c.render(
            '<div class="optl-hero-copy"><span class="optl-eyebrow">Optiport</span>'
            "<h1>AI-Powered Portfolio Intelligence</h1>"
            "<p>Build smarter portfolios. Analyze markets. Test your strategy — "
            "combining real market data, ETF return forecasting, news analysis "
            "and portfolio optimization in one platform.</p></div>"
        )
        with st.container(key="landing_hero_actions"):
            cols = st.columns(2)
            with cols[0]:
                if st.button("Get Started", key="hero_get_started", type="primary", width="stretch"):
                    _go("register")
            with cols[1]:
                c.render('<a href="#markets" class="optl-hero-explore">Explore Markets</a>')
    with right:
        _market_card()

    chips = "".join(
        f'<div class="optl-chip"><span class="optl-chip__sym">{c.esc(t)}</span>'
        f'{c.sparkline_html(_curve_for(t), width=40, height=16, area=False)}</div>'
        for t in catalog.TICKERS[:8]
    )
    c.render(f'<div id="markets" class="optl-rail">{chips}</div>')
    c.caption(
        "Illustrative data — real-time quotes, history and technical signals "
        "are available once you're signed in."
    )


def _section_head(eyebrow: str, title: str, subtitle: str) -> None:
    c.render(
        f'<div class="optl-head"><span class="optl-eyebrow">{c.esc(eyebrow)}</span>'
        f"<h2>{c.esc(title)}</h2><p>{c.esc(subtitle)}</p></div>"
    )


def _features() -> None:
    st.write("")
    c.render('<div id="intelligence"></div>')
    _section_head(
        "Platform", "Everything you need to invest with data",
        "Four capabilities, one coherent workflow — from raw market data to a "
        "simulated position.",
    )
    cards = [
        ("forecast", "AI Forecasting", "Machine-learning based ETF return forecasting."),
        ("portfolio", "Portfolio Optimization", "Build portfolios based on risk and expected return."),
        ("sentiment", "Market Intelligence", "Analyze market data and financial news."),
        ("trading", "Paper Trading", "Practice investment strategies with virtual capital."),
    ]
    grid = "".join(
        '<div class="optl-fcard">'
        f'<div class="optl-fcard__icon">{icon_html(icon, size="1.125rem")}</div>'
        f"<h3>{c.esc(title)}</h3><p>{c.esc(body)}</p></div>"
        for icon, title, body in cards
    )
    c.render(f'<div class="optl-grid">{grid}</div>')


def _how_it_works() -> None:
    st.write("")
    c.render('<div id="how-it-works"></div>')
    _section_head(
        "Workflow", "How it works",
        "From market data to a simulated position in four steps.",
    )
    steps = [
        ("01", "Explore the market", "Browse real ETF quotes, history and technical signals."),
        ("02", "Analyze with AI", "Get LSTM-based return forecasts and news-driven sentiment."),
        ("03", "Optimize your portfolio", "Generate risk-aware allocations with mean-variance optimization."),
        ("04", "Simulate your strategy", "Place paper orders and track performance over time."),
    ]
    grid = "".join(
        f'<div class="optl-step"><span class="optl-step__num">{n}</span>'
        f"<h4>{c.esc(title)}</h4><p>{c.esc(body)}</p></div>"
        for n, title, body in steps
    )
    c.render(f'<div class="optl-steps">{grid}</div>')


def _paper_trading() -> None:
    st.write("")
    c.render(
        '<div id="portfolio" class="optl-paper"><div>'
        f'<div class="optl-paper__stat">{c.esc(money(store.INITIAL_CASH))} in virtual capital</div>'
        '<div class="optl-paper__copy">Test investment strategies without risking real money. '
        "Every Optiport account starts with a simulated cash balance, filled at real "
        "market prices — no real orders are ever transmitted.</div></div>"
        f'<div style="color:var(--optl-text)">{icon_html("shield", size="2.5rem")}</div></div>'
    )


def _final_cta() -> None:
    st.write("")
    c.render('<div class="optl-cta"><h2>Ready to build your portfolio?</h2></div>')
    with st.container(key="landing_cta_action"):
        if st.button("Create your account", key="cta_register", type="primary", width="stretch"):
            _go("register")


def _footer() -> None:
    c.render(
        '<div class="optl-footer">'
        '<div><strong style="color:var(--optl-text)">OPTIPORT</strong>'
        " · ETF portfolio intelligence, simulated trading, © 2026</div>"
        '<div><a href="#markets">Markets</a>'
        '<a href="#intelligence">Intelligence</a>'
        '<a href="#portfolio">Portfolio</a>'
        '<a href="#how-it-works">How it works</a></div>'
        "</div>"
    )


def landing_page() -> None:
    _styles()
    _nav()
    st.write("")
    st.write("")
    _hero()
    _features()
    _how_it_works()
    _paper_trading()
    _final_cta()
    _footer()
