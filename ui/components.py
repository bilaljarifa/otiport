# -*- coding: utf-8 -*-
"""Reusable UI components.

Everything here is presentation-only: a component takes already-computed values
and returns/renders markup. Two flavours:

* `*_html()` helpers return a string, so they can be embedded in bigger blocks.
* The other functions render directly through `st.html` / Streamlit containers.

Custom markup is intentionally used for dense financial widgets (KPI cards,
market tables, sparklines) where Streamlit's native elements cannot express the
required layout, while native widgets are kept everywhere interaction matters.
"""

from __future__ import annotations

import hashlib
import html as _html
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

import pandas as pd
import streamlit as st

from ui import tokens
from ui.format import PLACEHOLDER, tone_of
from ui.icons import icon_html

# ---------------------------------------------------------------------------
#  Internals
# ---------------------------------------------------------------------------

_TONE_COLOR_VAR = {
    "accent": "var(--opt-accent)",
    "up": "var(--opt-up)",
    "down": "var(--opt-down)",
    "warn": "var(--opt-warn)",
    "info": "var(--opt-info)",
    "violet": "var(--opt-violet)",
    "neutral": "var(--opt-text-muted)",
}

_MARK_COLORS = tokens.CHART_CATEGORICAL


def esc(value: Any) -> str:
    """HTML-escape any value for safe interpolation into markup."""
    if value is None:
        return PLACEHOLDER
    return _html.escape(str(value), quote=True)


def tone_color(tone: str) -> str:
    """Resolve a semantic tone name to a CSS color expression."""
    return _TONE_COLOR_VAR.get(tone, _TONE_COLOR_VAR["accent"])


def _counter(prefix: str) -> str:
    """Return a stable-per-run unique suffix, used to key generated containers."""
    key = f"_opt_seq_{prefix}"
    st.session_state[key] = st.session_state.get(key, 0) + 1
    return f"{prefix}{st.session_state[key]}"


def render(markup: str) -> None:
    """Send a block of custom markup to the app."""
    st.html(markup)


# ---------------------------------------------------------------------------
#  Containers
# ---------------------------------------------------------------------------

def card(variant: str = "default", *, key: str | None = None, height: Any = "content"):
    """A premium surface container.

    Variants: `default` (padded card), `flush` (no padding, for charts and
    tables that bleed to the edge), `hero` (accent-tinted, for primary panels).
    """
    prefix = {"default": "optcard", "flush": "optflush", "hero": "opthero"}.get(variant, "optcard")
    container_key = f"{prefix}-{key}" if key else _counter(prefix)
    return st.container(key=container_key, height=height)


# ---------------------------------------------------------------------------
#  Headers
# ---------------------------------------------------------------------------

def page_header(
    title: str,
    *,
    subtitle: str | None = None,
    eyebrow: str | None = None,
    icon: str | None = None,
    aside: str | None = None,
) -> None:
    """The title block at the top of every page."""
    parts = ['<div class="opt-page"><div>']
    if eyebrow:
        eyebrow_icon = icon_html(icon, size="0.9375rem") if icon else ""
        parts.append(f'<div class="opt-page__eyebrow">{eyebrow_icon}{esc(eyebrow)}</div>')
    parts.append(f'<h1 class="opt-page__title">{esc(title)}</h1>')
    if subtitle:
        parts.append(f'<div class="opt-page__sub">{esc(subtitle)}</div>')
    parts.append("</div>")
    if aside:
        parts.append(f'<div class="opt-row opt-row--wrap">{aside}</div>')
    parts.append("</div>")
    render("".join(parts))


def section(
    title: str,
    *,
    subtitle: str | None = None,
    icon: str | None = None,
    aside: str | None = None,
) -> None:
    """A section heading used inside cards and page bodies."""
    icon_block = (
        f'<span class="opt-section__icon">{icon_html(icon, size="1.0625rem")}</span>'
        if icon else ""
    )
    sub = f'<div class="opt-section__sub">{esc(subtitle)}</div>' if subtitle else ""
    aside_block = f'<div class="opt-section__aside">{aside}</div>' if aside else ""
    render(
        '<div class="opt-section"><div class="opt-section__main">'
        f'{icon_block}<div><div class="opt-section__title">{esc(title)}</div>{sub}</div>'
        f"</div>{aside_block}</div>"
    )


def divider() -> None:
    render('<hr class="opt-hr" />')


def caption(text: str) -> None:
    render(f'<div class="opt-caption">{esc(text)}</div>')


def spacer(height: str = "0.5rem") -> None:
    render(f'<div style="height:{height}"></div>')


# ---------------------------------------------------------------------------
#  Atoms
# ---------------------------------------------------------------------------

def chip_html(
    label: str,
    *,
    tone: str = "flat",
    icon: str | None = None,
    mono: bool = False,
    title: str | None = None,
) -> str:
    """A small status/metadata pill."""
    classes = f"opt-chip opt-chip--{tone}"
    if mono:
        classes += " opt-chip__mono"
    icon_block = icon_html(icon, size="0.875rem") if icon else ""
    tip = f' title="{esc(title)}"' if title else ""
    return f'<span class="{classes}"{tip}>{icon_block}{esc(label)}</span>'


def delta_html(value: Any, *, suffix: str = "%", decimals: int = 2, show_arrow: bool = True) -> str:
    """A signed, tone-coloured variation badge."""
    tone = tone_of(value)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return f'<span class="opt-delta opt-delta--flat">{PLACEHOLDER}</span>'
    arrow = {"up": "arrow_up", "down": "arrow_down", "flat": "remove"}[tone]
    icon_block = icon_html(arrow, size="0.8125rem") if show_arrow else ""
    text = f"{float(value):+,.{decimals}f}{suffix}" if suffix == "%" else f"{float(value):+,.{decimals}f}{suffix}"
    return f'<span class="opt-delta opt-delta--{tone}">{icon_block}{esc(text)}</span>'


def dot_html(state: str = "open") -> str:
    """Live/closed status indicator."""
    modifier = {"open": "", "closed": " opt-dot--closed", "warn": " opt-dot--warn",
                "down": " opt-dot--down"}.get(state, "")
    return f'<span class="opt-dot{modifier}"></span>'


def avatar_html(initials: str, *, large: bool = False) -> str:
    size = " opt-avatar--lg" if large else ""
    return f'<span class="opt-avatar{size}">{esc(initials[:2].upper())}</span>'


def brand_mark_html(*, size: str = "2.25rem", color: str = "#0A0A0A") -> str:
    """Optiport's geometric mark: three ascending bars inside a square frame
    — the same symbol as `ui/assets/logo-mark.svg` (used on the dark
    sidebar via `st.logo`), redrawn with plain `<span>`s instead of `<svg>`
    so it can appear inside `st.html()`-rendered markup, which strips SVG
    entirely (DOMPurify's HTML profile). `color` lets the same mark work on
    both the dark sidebar's white-on-transparent SVG and this light,
    recolourable HTML version — same shape, adapted per surface, not two
    unrelated logos.
    """
    bar = lambda h: f'<span style="width:18%;height:{h}%;background:{color}"></span>'
    return (
        f'<span style="display:inline-flex;align-items:flex-end;justify-content:center;'
        f"gap:2px;width:{size};height:{size};border:1.5px solid {color};border-radius:4px;"
        f'padding:3px;box-sizing:border-box;flex-shrink:0">'
        f'{bar(35)}{bar(60)}{bar(90)}</span>'
    )


def brand_wordmark_html(*, mark_size: str = "2rem", color: str = "#0A0A0A",
                        text_size: str = "1.25rem") -> str:
    """Mark + "OPTIPORT" wordmark for light backgrounds (landing page,
    login/register). The dark sidebar keeps its own SVG lockup via
    `st.logo` — same mark (see `brand_mark_html`), dark-surface variant."""
    return (
        '<span style="display:inline-flex;align-items:center;gap:0.625rem">'
        f"{brand_mark_html(size=mark_size, color=color)}"
        f'<span style="font-weight:800;font-size:{text_size};letter-spacing:0.03em;'
        f'color:{color}">OPTIPORT</span></span>'
    )


def mark_color(symbol: str) -> str:
    """Deterministic accent colour for a ticker, stable across sessions."""
    digest = hashlib.md5(symbol.encode("utf-8")).hexdigest()  # noqa: S324 - display only
    return _MARK_COLORS[int(digest[:8], 16) % len(_MARK_COLORS)]


def instrument_html(ticker: str, name: str | None = None, *, mark: bool = True) -> str:
    """Ticker + company/sector identity cell."""
    color = mark_color(ticker)
    mark_block = (
        f'<span class="opt-idcell__mark" style="background:linear-gradient(135deg,{color},'
        f'color-mix(in srgb,{color} 55%,#000))">{esc(ticker[:3])}</span>'
        if mark else ""
    )
    name_block = f'<div class="opt-idcell__name">{esc(name)}</div>' if name else ""
    return (
        f'<div class="opt-idcell">{mark_block}<div class="opt-idcell__body">'
        f'<div class="opt-idcell__ticker">{esc(ticker)}</div>{name_block}</div></div>'
    )


def signal_html(signal: str) -> str:
    """Recommendation badge coloured by the shared signal scale."""
    tone = tokens.SIGNAL_TONE.get(signal, "flat")
    icon = {
        "Strong Buy": "arrow_up", "Buy": "arrow_up", "Hold": "remove",
        "Light": "info", "Reduce": "arrow_down", "Avoid": "arrow_down",
    }.get(signal)
    return chip_html(signal, tone=tone, icon=icon)


def bar_html(pct: float, *, color: str | None = None, large: bool = False,
             max_pct: float = 100.0) -> str:
    """Horizontal allocation/progress bar, animated on mount."""
    width = 0.0 if max_pct <= 0 else max(0.0, min(100.0, (float(pct) / max_pct) * 100.0))
    size = " opt-bar--lg" if large else ""
    style = f"--opt-bar-w:{width:.2f}%"
    if color:
        style += f";--opt-bar-color:{color}"
    return (
        f'<div class="opt-bar{size}" role="progressbar" aria-valuenow="{width:.0f}" '
        f'aria-valuemin="0" aria-valuemax="100">'
        f'<span class="opt-bar__fill" style="{style}"></span></div>'
    )


def diverging_bar_html(value: float, *, scale: float = 20.0) -> str:
    """Signed bar growing left (negative) or right (positive) from the centre."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return f'<span class="opt-faint">{PLACEHOLDER}</span>'
    width = min(abs(float(value)) / scale, 1.0) * 50.0
    if value >= 0:
        pos, color = f"left:50%;width:{width:.1f}%", "var(--opt-up)"
    else:
        pos, color = f"right:50%;width:{width:.1f}%", "var(--opt-down)"
    return (
        '<div class="opt-dbar"><span class="opt-dbar__mid"></span>'
        f'<span class="opt-dbar__fill" style="{pos};background:{color}"></span></div>'
    )


def sparkline_html(
    values: Sequence[float],
    *,
    width: int | None = 120,
    height: int = 32,
    tone: str | None = None,
    area: bool = True,
    marker: bool = True,
) -> str:
    """Miniature trend chart, drawn with clip-path polygons.

    SVG cannot be used here: `st.html` sanitises markup with DOMPurify's HTML
    profile, which drops SVG entirely. Two stacked polygons give the same
    result — a gradient area plus a constant-thickness line — and because the
    geometry is expressed in percentages the chart is fully responsive.

    `tone` defaults to the direction of the series, matching how variations are
    coloured everywhere else in the app.
    """
    series = [
        float(v) for v in values
        if v is not None and not (isinstance(v, float) and math.isnan(v))
    ]
    if len(series) < 2:
        return f'<span class="opt-faint">{PLACEHOLDER}</span>'

    if tone is None:
        tone = "up" if series[-1] >= series[0] else "down"
    color = tone_color(tone)

    low, high = min(series), max(series)
    span = (high - low) or 1.0
    inset = 8.0                                    # vertical padding, in percent
    usable = 100.0 - inset * 2
    count = len(series) - 1

    # y is measured from the top, so a high value sits near 0%.
    points = [
        (i / count * 100.0, inset + usable - ((value - low) / span) * usable)
        for i, value in enumerate(series)
    ]

    thickness = max(4.0, 2.2 / max(height, 1) * 100)   # line width, in percent
    forward = ", ".join(f"{x:.2f}% {y:.2f}%" for x, y in points)
    backward = ", ".join(
        f"{x:.2f}% {min(y + thickness, 100.0):.2f}%" for x, y in reversed(points)
    )

    layers = []
    if area:
        layers.append(
            f'<span class="opt-spark__area" style="clip-path:polygon(0% 100%, '
            f'{forward}, 100% 100%);background:linear-gradient(180deg,'
            f'color-mix(in srgb,{color} 30%,transparent),'
            f'color-mix(in srgb,{color} 2%,transparent))"></span>'
        )
    layers.append(
        f'<span class="opt-spark__line" style="clip-path:polygon({forward}, '
        f'{backward});background:{color}"></span>'
    )
    if marker:
        last_x, last_y = points[-1]
        layers.append(
            f'<span class="opt-spark__dot" style="left:{last_x:.2f}%;'
            f'top:{last_y:.2f}%;background:{color}"></span>'
        )

    size = f"width:{width}px;" if width else "width:100%;"
    change = (series[-1] / series[0] - 1) * 100 if series[0] else 0.0
    return (
        f'<span class="opt-spark" style="{size}height:{height}px" role="img" '
        f'aria-label="Tendance récente, {change:+.1f}%">{"".join(layers)}</span>'
    )


def gauge_html(value: float, *, low: float = 0.0, high: float = 100.0,
               label: str | None = None, invert: bool = False) -> str:
    """Linear gauge with a cursor — used for risk and diversification scores."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return f'<span class="opt-faint">{PLACEHOLDER}</span>'
    span = (high - low) or 1.0
    pct = max(0.0, min(100.0, ((float(value) - low) / span) * 100.0))
    cursor = 100.0 - pct if invert else pct
    label_block = f'<span class="opt-gauge__val">{esc(label)}</span>' if label else ""
    return (
        '<div class="opt-gauge"><span class="opt-gauge__track">'
        f'<span class="opt-gauge__cursor" style="left:{cursor:.1f}%"></span></span>'
        f"{label_block}</div>"
    )


def heatmap_button_css(tiles: Sequence[dict[str, Any]], *, scale: float = 0.5) -> str:
    """CSS that recolours a grid of `st.button` widgets into heatmap tiles.

    Pair each tile with `st.button(..., key=tile["key"])` using that exact
    key — Streamlit exposes it as a `st-key-<key>` class on the button's
    wrapper, which is what these rules target. This keeps the heatmap a real,
    clickable widget (selecting an instrument to inspect) instead of inert
    HTML, while still reading as a Finviz-style green/red grid.

    Each tile: `{"key", "value" (signed float, e.g. -1..1), "selected"
    (optional bool, adds a highlight ring)}`.
    """
    rules = []
    for t in tiles:
        value = float(t.get("value") or 0.0)
        magnitude = min(abs(value) / scale, 1.0) if scale else 0.0
        color = "var(--opt-up)" if value >= 0 else "var(--opt-down)"
        fill_mix = 12 + magnitude * 55
        border_mix = min(fill_mix + 20, 75)
        ring = "box-shadow:0 0 0 2px var(--opt-accent) !important;" if t.get("selected") else ""
        rules.append(
            f'.st-key-{t["key"]} button {{'
            f'background:color-mix(in srgb,{color} {fill_mix:.0f}%,var(--opt-surface-low)) !important;'
            f'border-color:color-mix(in srgb,{color} {border_mix:.0f}%,var(--opt-border-soft)) !important;'
            f"{ring}}}"
        )
    return f"<style>{''.join(rules)}</style>"


def legend_html(items: Iterable[tuple[str, str]]) -> str:
    """Colour legend: iterable of `(label, color)`."""
    body = "".join(
        f'<span class="opt-legend__item">'
        f'<span class="opt-legend__swatch" style="background:{color}"></span>{esc(label)}</span>'
        for label, color in items
    )
    return f'<div class="opt-legend">{body}</div>'


# ---------------------------------------------------------------------------
#  Composite blocks
# ---------------------------------------------------------------------------

def kpi_html(
    label: str,
    value: str,
    *,
    delta: Any = None,
    delta_suffix: str = "%",
    hint: str | None = None,
    icon: str | None = None,
    tone: str = "accent",
    spark: Sequence[float] | None = None,
    footer: str | None = None,
    small: bool = False,
) -> str:
    """A single KPI card. Compose several with `kpi_row`."""
    badge = (
        f'<span class="opt-kpi__badge">{icon_html(icon, size="1.0625rem")}</span>'
        if icon else ""
    )
    foot_parts: list[str] = []
    if delta is not None:
        foot_parts.append(delta_html(delta, suffix=delta_suffix))
    if footer:
        foot_parts.append(footer)
    if hint:
        foot_parts.append(f'<span class="opt-kpi__hint">{esc(hint)}</span>')
    foot = f'<div class="opt-kpi__foot">{"".join(foot_parts)}</div>' if foot_parts else ""
    spark_block = (
        f'<div class="opt-kpi__spark">{sparkline_html(spark, height=34, tone=None)}</div>'
        if spark is not None else ""
    )
    value_cls = "opt-kpi__value opt-kpi__value--sm" if small else "opt-kpi__value"
    return (
        f'<div class="opt-kpi" style="--opt-kpi-accent:{tone_color(tone)}">'
        f'<div class="opt-kpi__head"><span class="opt-kpi__label">{esc(label)}</span>{badge}</div>'
        f'<div class="{value_cls}">{esc(value)}</div>'
        f"{foot}{spark_block}</div>"
    )


def kpi_row(cards: Sequence[str], *, columns: int | None = None, min_width: str = "13rem") -> None:
    """Render KPI cards in a responsive CSS grid (never breaks on mobile)."""
    template = (
        f"repeat({columns}, minmax(0, 1fr))" if columns
        else f"repeat(auto-fit, minmax({min_width}, 1fr))"
    )
    render(
        f'<div style="display:grid;grid-template-columns:{template};gap:0.75rem">'
        f'{"".join(cards)}</div>'
    )


def tiles(items: Sequence[tuple[str, str]] | Sequence[tuple[str, str, str]]) -> None:
    """Compact stat grid: `(label, value)` or `(label, value, sub)`."""
    blocks = []
    for item in items:
        label, value = item[0], item[1]
        sub = item[2] if len(item) > 2 else None
        sub_block = f'<div class="opt-tile__s">{sub}</div>' if sub else ""
        blocks.append(
            f'<div class="opt-tile"><div class="opt-tile__k">{esc(label)}</div>'
            f'<div class="opt-tile__v">{esc(value)}</div>{sub_block}</div>'
        )
    render(f'<div class="opt-tiles">{"".join(blocks)}</div>')


def kv_list(items: Sequence[tuple[str, str]], *, icons: dict[str, str] | None = None) -> None:
    """Definition list for metric breakdowns. Values may contain markup."""
    icons = icons or {}
    rows = []
    for key, value in items:
        icon_block = icon_html(icons[key], size="0.9375rem") if key in icons else ""
        rows.append(
            f'<div class="opt-kv__row"><span class="opt-kv__k">{icon_block}{esc(key)}</span>'
            f'<span class="opt-kv__v">{value}</span></div>'
        )
    render(f'<div class="opt-kv">{"".join(rows)}</div>')


def market_strip(items: Sequence[dict[str, Any]]) -> None:
    """Horizontal quote strip: dicts with `ticker`, `price`, `change`."""
    blocks = []
    for item in items:
        change = item.get("change")
        tone = tone_of(change)
        arrow = {"up": "▲", "down": "▼", "flat": "•"}[tone]
        change_text = PLACEHOLDER if change is None else f"{arrow} {abs(float(change)):.2f}%"
        color = {"up": "var(--opt-up-text)", "down": "var(--opt-down-text)",
                 "flat": "var(--opt-text-muted)"}[tone]
        blocks.append(
            '<div class="opt-strip__item"><div class="opt-strip__top">'
            f'<span class="opt-strip__tkr">{esc(item["ticker"])}</span>'
            f'<span class="opt-strip__ch" style="color:{color}">{esc(change_text)}</span></div>'
            f'<div class="opt-strip__px">{esc(item.get("price", PLACEHOLDER))}</div></div>'
        )
    render(f'<div class="opt-strip">{"".join(blocks)}</div>')


def feed(items: Sequence[dict[str, Any]]) -> None:
    """Activity/news feed.

    Each item: `title`, optional `meta` (markup), `summary`, `url`, `icon`,
    `tone`.
    """
    blocks = []
    for item in items:
        tone = item.get("tone", "info")
        color = tone_color(tone)
        icon = icon_html(item.get("icon", "info"), size="1rem", color=color)
        mark = (
            f'<span class="opt-feed__mark" style="background:color-mix(in srgb,{color} 14%,transparent);'
            f'border:1px solid color-mix(in srgb,{color} 26%,transparent)">{icon}</span>'
        )
        title = esc(item["title"])
        if item.get("url"):
            title_block = (
                f'<a class="opt-feed__title" href="{esc(item["url"])}" target="_blank" '
                f'rel="noopener noreferrer">{title}</a>'
            )
        else:
            title_block = f'<span class="opt-feed__title">{title}</span>'
        meta = f'<div class="opt-feed__meta">{item["meta"]}</div>' if item.get("meta") else ""
        summary = f'<div class="opt-feed__sum">{esc(item["summary"])}</div>' if item.get("summary") else ""
        blocks.append(
            f'<div class="opt-feed__item">{mark}<div class="opt-feed__body">'
            f"{title_block}{summary}{meta}</div></div>"
        )
    render(f'<div class="opt-feed">{"".join(blocks)}</div>')


# ---------------------------------------------------------------------------
#  Feedback states
# ---------------------------------------------------------------------------

def empty_state(
    title: str,
    text: str | None = None,
    *,
    icon: str = "empty",
    variant: str = "default",
) -> None:
    """Empty / error / success / info placeholder."""
    body = f'<div class="opt-state__text">{esc(text)}</div>' if text else ""
    render(
        f'<div class="opt-state opt-state--{variant}">'
        f'<span class="opt-state__icon">{icon_html(icon, size="1.5rem")}</span>'
        f'<div class="opt-state__title">{esc(title)}</div>{body}</div>'
    )


def error_state(title: str, text: str | None = None) -> None:
    empty_state(title, text, icon="error", variant="error")


def success_state(title: str, text: str | None = None) -> None:
    empty_state(title, text, icon="check", variant="success")


def skeleton(kind: str = "text", count: int = 3) -> None:
    """Shimmering placeholders shown while data loads."""
    if kind == "kpi":
        render(
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));gap:0.75rem">'
            + "".join(
                '<div class="opt-skel opt-skel--card"></div>' for _ in range(count)
            )
            + "</div>"
        )
        return
    if kind == "chart":
        render('<div class="opt-skel opt-skel--chart"></div>')
        return
    if kind == "table":
        render(
            '<div class="opt-skel opt-skel--title"></div>'
            + "".join('<div class="opt-skel opt-skel--row"></div>' for _ in range(count))
        )
        return
    render("".join('<div class="opt-skel opt-skel--text"></div>' for _ in range(count)))


# ---------------------------------------------------------------------------
#  Data table
# ---------------------------------------------------------------------------

@dataclass
class Column:
    """Column definition for `data_table`.

    `render` receives `(value, row)` and returns HTML, so a column can hold a
    sparkline, a badge or a bar as easily as a formatted number.
    """

    key: str
    label: str
    align: str = "right"
    render: Callable[[Any, pd.Series], str] | None = None
    css: Callable[[Any], str] | None = None
    sortable: bool = True
    help: str | None = None


@dataclass
class Filter:
    """Categorical filter rendered above the table."""

    key: str
    label: str
    options: Sequence[str] = field(default_factory=list)


def table_html(df: pd.DataFrame, columns: Sequence[Column], *,
               sort_key: str | None = None, sort_desc: bool = True) -> str:
    """Render a DataFrame as the premium market table.

    `sort_key` / `sort_desc` are used only to expose the current ordering to
    assistive technology via `aria-sort`; the sorting itself happens upstream.
    """
    head = []
    for col in columns:
        align_cls = {"left": " opt-th--left", "center": " opt-th--center"}.get(col.align, "")
        tip = f' title="{esc(col.help)}"' if col.help else ""
        sorted_attr = ""
        if sort_key and col.key == sort_key:
            sorted_attr = f' aria-sort="{"descending" if sort_desc else "ascending"}"'
        head.append(
            f'<th class="opt-th{align_cls}"{tip}{sorted_attr} scope="col">'
            f"{esc(col.label)}</th>"
        )

    body = []
    for _, row in df.iterrows():
        cells = []
        for col in columns:
            value = row.get(col.key)
            content = col.render(value, row) if col.render else esc(value)
            align_cls = {"left": " opt-td--left", "center": " opt-td--center"}.get(col.align, "")
            extra = f" {col.css(value)}" if col.css else ""
            cells.append(f'<td class="opt-td{align_cls}{extra}">{content}</td>')
        body.append(f"<tr>{''.join(cells)}</tr>")

    return (
        '<div class="opt-tablewrap"><table class="opt-table">'
        f"<thead><tr>{''.join(head)}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def data_table(
    df: pd.DataFrame,
    columns: Sequence[Column],
    *,
    key: str,
    search_keys: Sequence[str] = (),
    filters: Sequence[Filter] = (),
    page_size: int = 10,
    page_size_options: Sequence[int] = (10, 25, 50),
    default_sort: str | None = None,
    default_desc: bool = True,
    search_placeholder: str = "Rechercher un ticker ou un nom…",
    empty_title: str = "Aucun résultat",
    empty_text: str | None = "Ajustez votre recherche ou vos filtres.",
    toolbar: bool = True,
) -> pd.DataFrame:
    """Searchable, filterable, sortable and paginated table.

    Returns the visible slice so callers can reuse it (exports, selection…).
    """
    working = df.copy()
    active_sort: str | None = None       # reported to screen readers via aria-sort
    active_desc = True

    if toolbar:
        widths = [2.4] + [1.2] * len(filters) + [1.4, 0.85, 0.8]
        bar = st.columns(widths, vertical_alignment="bottom")
        query = bar[0].text_input(
            "Recherche",
            key=f"{key}__q",
            placeholder=search_placeholder,
            label_visibility="collapsed",
            icon=":material/search:",
        )
        active_filters: dict[str, str] = {}
        for i, flt in enumerate(filters):
            options = ["Tous"] + [str(o) for o in flt.options]
            choice = bar[1 + i].selectbox(
                flt.label, options, key=f"{key}__f{i}", label_visibility="collapsed"
            )
            active_filters[flt.key] = choice

        sortable = [c for c in columns if c.sortable]
        labels = {c.label: c.key for c in sortable}
        sort_key = None
        if labels:
            label_list = list(labels)
            default_label = next(
                (c.label for c in sortable if c.key == default_sort), label_list[0]
            )
            sort_label = bar[-3].selectbox(
                "Trier par",
                label_list,
                index=label_list.index(default_label),
                key=f"{key}__s",
                label_visibility="collapsed",
            )
            sort_key = labels[sort_label]

        direction = bar[-2].selectbox(
            "Sens",
            ["Desc", "Asc"],
            index=0 if default_desc else 1,
            key=f"{key}__dir",
            label_visibility="collapsed",
        )
        size = bar[-1].selectbox(
            "Lignes",
            list(page_size_options),
            index=(list(page_size_options).index(page_size)
                   if page_size in page_size_options else 0),
            key=f"{key}__n",
            label_visibility="collapsed",
        )

        if query and search_keys:
            needle = query.strip().lower()
            mask = pd.Series(False, index=working.index)
            for column in search_keys:
                if column in working.columns:
                    mask |= working[column].astype(str).str.lower().str.contains(needle, na=False)
            working = working[mask]

        for column, choice in active_filters.items():
            if choice != "Tous" and column in working.columns:
                working = working[working[column].astype(str) == choice]

        if sort_key and sort_key in working.columns:
            working = working.sort_values(
                sort_key,
                ascending=(direction == "Asc"),
                kind="mergesort",
                na_position="last",
            )
            active_sort, active_desc = sort_key, direction != "Asc"
    else:
        size = page_size
        if default_sort and default_sort in working.columns:
            working = working.sort_values(default_sort, ascending=not default_desc, na_position="last")
            active_sort, active_desc = default_sort, default_desc

    total = len(working)
    if total == 0:
        empty_state(empty_title, empty_text, icon="search")
        return working

    pages = max(1, math.ceil(total / size))
    page_key = f"{key}__p"
    page = min(st.session_state.get(page_key, 1), pages)
    start = (page - 1) * size
    visible = working.iloc[start:start + size]

    render(table_html(visible, columns, sort_key=active_sort, sort_desc=active_desc))

    if pages > 1:
        nav = st.columns([1, 1, 6], vertical_alignment="center")
        if nav[0].button("Précédent", key=f"{key}__prev", disabled=page <= 1,
                         width="stretch", icon=":material/chevron_left:"):
            st.session_state[page_key] = page - 1
            st.rerun()
        if nav[1].button("Suivant", key=f"{key}__next", disabled=page >= pages,
                         width="stretch", icon=":material/chevron_right:"):
            st.session_state[page_key] = page + 1
            st.rerun()
        with nav[2]:
            render(
                '<div class="opt-caption" style="text-align:right">'
                f"Page {page} / {pages} · {total} lignes</div>"
            )
    else:
        render(f'<div class="opt-caption" style="text-align:right">{total} lignes</div>')

    return visible
