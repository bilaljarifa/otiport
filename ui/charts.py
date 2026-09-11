# -*- coding: utf-8 -*-
"""Plotly chart factory.

Every figure in the application is produced here so that axes, grids, fonts,
hover labels and colour semantics are identical across pages. Charts are
rendered with `theme=None` because the figures already carry the full Optiport
template — letting Streamlit re-theme them would undo the styling.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from services import store
from ui import tokens

# ---------------------------------------------------------------------------
#  Palette helpers
# ---------------------------------------------------------------------------


class _ActivePalette:
    """Resolves the *current* palette (Settings > Appearance, default the
    light "Terminal" theme) on every lookup, instead of a palette frozen at
    import time. Charts must follow the user's actual theme choice — every
    `_P[...]` call below (there are ~50 of them) stays syntactically
    unchanged; only what it resolves to becomes dynamic."""

    def __getitem__(self, key: str) -> str:
        try:
            name = store.prefs().get("palette")
        except Exception:
            name = None
        return tokens.palette(name)[key]


_P = _ActivePalette()


def _grid() -> str:
    return rgba(_P["border"], 0.5)


def _axis() -> str:
    return rgba(_P["border"], 0.7)

CONFIG: dict[str, Any] = {
    "displayModeBar": False,
    "displaylogo": False,
    "scrollZoom": False,
    "responsive": True,
}

# Mode bar kept for charts users are likely to explore (candlesticks, frontier).
CONFIG_INTERACTIVE: dict[str, Any] = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
}


def rgba(hex_color: str, alpha: float) -> str:
    """Convert `#RRGGBB` to an `rgba()` string."""
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def tone_hex(tone: str) -> str:
    """Semantic tone -> hex colour."""
    return {
        "up": _P["up"],
        "down": _P["down"],
        "warn": _P["warn"],
        "accent": _P["accent"],
        "info": _P["info"],
        "violet": _P["violet"],
        "neutral": _P["text_muted"],
    }.get(tone, _P["accent"])


def series_color(index: int) -> str:
    return tokens.CHART_CATEGORICAL[index % len(tokens.CHART_CATEGORICAL)]


# ---------------------------------------------------------------------------
#  Base layout
# ---------------------------------------------------------------------------

def _base(fig: go.Figure, *, height: int = 280, legend: bool = False,
          margin: Mapping[str, int] | None = None, hovermode: Any = "x unified") -> go.Figure:
    """Apply the shared Optiport layout to a figure."""
    m = dict(l=8, r=8, t=8, b=8)
    if margin:
        m.update(margin)

    fig.update_layout(
        height=height,
        margin=m,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=11.5, color=_P["text_muted"]),
        hovermode=hovermode,
        hoverlabel=dict(
            bgcolor=_P["surface"],
            bordercolor=_P["border"],
            font=dict(family="Inter, sans-serif", size=12, color=_P["text_soft"]),
            align="left",
        ),
        showlegend=legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=11, color=_P["text_muted"]),
            itemsizing="constant",
        ),
        dragmode=False,
        modebar=dict(bgcolor="rgba(0,0,0,0)", color=_P["text_faint"], activecolor=_P["accent"]),
        transition=dict(duration=280, easing="cubic-in-out"),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=_axis(),
        tickcolor=_axis(),
        ticklen=4,
        tickfont=dict(size=11, color=_P["text_faint"]),
        showspikes=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=_grid(),
        gridwidth=1,
        zeroline=False,
        showline=False,
        tickfont=dict(size=11, color=_P["text_faint"]),
    )
    return fig


# ---------------------------------------------------------------------------
#  Line / area
# ---------------------------------------------------------------------------

def area(
    x: Sequence[Any],
    y: Sequence[float],
    *,
    name: str = "",
    tone: str | None = None,
    height: int = 260,
    value_prefix: str = "",
    value_suffix: str = "",
    baseline: float | None = None,
) -> go.Figure:
    """Single-series area chart with a vertical gradient fill.

    The tone defaults to the direction of the series, so a losing period is red
    and a winning one green without the caller having to decide.
    """
    values = list(y)
    if tone is None:
        tone = "up" if len(values) > 1 and values[-1] >= values[0] else "down"
    color = tone_hex(tone)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(x),
            y=values,
            name=name,
            mode="lines",
            line=dict(color=color, width=2, shape="spline", smoothing=0.4),
            fill="tozeroy",
            fillgradient=dict(
                type="vertical",
                colorscale=[[0.0, rgba(color, 0.0)], [1.0, rgba(color, 0.30)]],
            ),
            hovertemplate=f"%{{x|%d %b %Y}}<br><b>{value_prefix}%{{y:,.2f}}{value_suffix}</b><extra></extra>",
        )
    )
    if baseline is not None:
        fig.add_hline(
            y=baseline,
            line=dict(color=_P["text_faint"], width=1, dash="dot"),
            opacity=0.7,
        )
    _base(fig, height=height)
    fig.update_yaxes(tickformat=",.0f", ticksuffix=value_suffix)
    return fig


def multi_line(
    df: pd.DataFrame,
    *,
    x: str,
    series: Sequence[str],
    height: int = 340,
    value_suffix: str = "",
    highlight: str | None = None,
    baseline: float | None = None,
    legend: bool = True,
) -> go.Figure:
    """Comparison chart — one line per series, optionally highlighting one."""
    fig = go.Figure()
    for i, name in enumerate(series):
        if name not in df.columns:
            continue
        is_dim = highlight is not None and name != highlight
        color = _P["text_faint"] if is_dim else series_color(i)
        fig.add_trace(
            go.Scatter(
                x=df[x],
                y=df[name],
                name=name,
                mode="lines",
                line=dict(color=color, width=1.2 if is_dim else 2.1),
                opacity=0.45 if is_dim else 1.0,
                hovertemplate=f"<b>{name}</b> %{{y:,.2f}}{value_suffix}<extra></extra>",
            )
        )
    if baseline is not None:
        fig.add_hline(y=baseline, line=dict(color=_P["border_strong"], width=1, dash="dot"))
    _base(fig, height=height, legend=legend, margin={"t": 28 if legend else 8})
    fig.update_yaxes(ticksuffix=value_suffix)
    return fig


def band_compare(
    x: Sequence[Any],
    primary: Sequence[float],
    reference: Sequence[float],
    *,
    primary_name: str,
    reference_name: str = "Peer average",
    height: int = 260,
) -> go.Figure:
    """Instrument versus benchmark, with the spread shaded between them."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(x), y=list(reference), name=reference_name, mode="lines",
            line=dict(color=_P["text_faint"], width=1.5, dash="dot"),
            hovertemplate=f"{reference_name} %{{y:,.1f}}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(x), y=list(primary), name=primary_name, mode="lines",
            line=dict(color=_P["accent"], width=2.2),
            fill="tonexty",
            fillcolor=rgba(_P["accent"], 0.12),
            hovertemplate=f"<b>{primary_name}</b> %{{y:,.1f}}<extra></extra>",
        )
    )
    _base(fig, height=height, legend=True, margin={"t": 28})
    return fig


def spread(
    x: Sequence[Any],
    values: Sequence[float],
    *,
    height: int = 220,
    name: str = "Écart",
) -> go.Figure:
    """Signed spread chart: green above zero, red below."""
    series = list(values)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(x), y=[v if v is not None and v >= 0 else 0 for v in series],
            mode="lines", line=dict(width=0), fill="tozeroy",
            fillcolor=rgba(_P["up"], 0.22), hoverinfo="skip", showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(x), y=[v if v is not None and v < 0 else 0 for v in series],
            mode="lines", line=dict(width=0), fill="tozeroy",
            fillcolor=rgba(_P["down"], 0.22), hoverinfo="skip", showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(x), y=series, name=name, mode="lines",
            line=dict(color=_P["accent_hi"], width=1.8),
            hovertemplate=f"{name} <b>%{{y:+,.2f}}</b><extra></extra>",
        )
    )
    fig.add_hline(y=0, line=dict(color=_P["border_strong"], width=1))
    _base(fig, height=height)
    return fig


# ---------------------------------------------------------------------------
#  Candlestick + volume
# ---------------------------------------------------------------------------

def candlestick(
    df: pd.DataFrame,
    *,
    height: int = 420,
    show_volume: bool = True,
    ma_windows: Sequence[int] = (20, 50),
) -> go.Figure:
    """OHLC candles with moving averages and an optional volume panel.

    `df` needs `Open`, `High`, `Low`, `Close` and (for the volume panel)
    `Volume`, indexed by date.
    """
    if show_volume and "Volume" in df.columns:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.76, 0.24], vertical_spacing=0.035,
        )
    else:
        fig = make_subplots(rows=1, cols=1)
        show_volume = False

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name="Prix",
            increasing=dict(line=dict(color=_P["up"], width=1), fillcolor=_P["up"]),
            decreasing=dict(line=dict(color=_P["down"], width=1), fillcolor=_P["down"]),
            whiskerwidth=0.4,
            hoverlabel=dict(bgcolor=_P["surface"]),
        ),
        row=1, col=1,
    )

    for i, window in enumerate(ma_windows):
        if len(df) > window:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["Close"].rolling(window).mean(),
                    name=f"MM{window}",
                    mode="lines",
                    line=dict(color=[_P["accent_hi"], _P["warn"]][i % 2], width=1.4),
                    hovertemplate=f"MM{window} %{{y:,.2f}}<extra></extra>",
                ),
                row=1, col=1,
            )

    if show_volume:
        colors = [
            rgba(_P["up"], 0.5) if c >= o else rgba(_P["down"], 0.5)
            for o, c in zip(df["Open"], df["Close"])
        ]
        fig.add_trace(
            go.Bar(
                x=df.index, y=df["Volume"], name="Volume",
                marker=dict(color=colors, line=dict(width=0)),
                hovertemplate="Volume %{y:,.0f}<extra></extra>",
            ),
            row=2, col=1,
        )

    _base(fig, height=height, legend=True, margin={"t": 28}, hovermode="x unified")
    fig.update_layout(xaxis_rangeslider_visible=False, bargap=0.25)
    fig.update_yaxes(side="right", tickformat=",.2f", row=1, col=1)
    if show_volume:
        fig.update_yaxes(showgrid=False, showticklabels=False, row=2, col=1)
    return fig


def volume_bars(df: pd.DataFrame, *, height: int = 160) -> go.Figure:
    """Standalone volume histogram, coloured by the day's direction."""
    colors = [
        rgba(_P["up"], 0.65) if c >= o else rgba(_P["down"], 0.65)
        for o, c in zip(df.get("Open", df["Close"]), df["Close"])
    ]
    fig = go.Figure(
        go.Bar(
            x=df.index, y=df["Volume"],
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate="%{x|%d %b}<br>Volume <b>%{y:,.0f}</b><extra></extra>",
        )
    )
    _base(fig, height=height)
    fig.update_layout(bargap=0.2)
    fig.update_yaxes(showticklabels=False, showgrid=False)
    return fig


# ---------------------------------------------------------------------------
#  Composition
# ---------------------------------------------------------------------------

def donut(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    height: int = 280,
    center_title: str = "",
    center_value: str = "",
    colors: Sequence[str] | None = None,
    hole: float = 0.7,
) -> go.Figure:
    """Allocation donut with a value in the middle."""
    palette = list(colors) if colors else [series_color(i) for i in range(len(labels))]
    fig = go.Figure(
        go.Pie(
            labels=list(labels),
            values=list(values),
            hole=hole,
            sort=False,
            direction="clockwise",
            marker=dict(colors=palette, line=dict(color=_P["surface"], width=2)),
            textinfo="none",
            hovertemplate="<b>%{label}</b><br>%{value:.2f}%<br>%{percent}<extra></extra>",
        )
    )
    _base(fig, height=height, hovermode=False, margin={"l": 4, "r": 4, "t": 4, "b": 4})
    annotations = []
    if center_value:
        annotations.append(dict(
            text=center_value, x=0.5, y=0.54, showarrow=False,
            font=dict(size=22, color=_P["text"], family="Inter, sans-serif", weight="bold"),
        ))
    if center_title:
        annotations.append(dict(
            text=center_title.upper(), x=0.5, y=0.40, showarrow=False,
            font=dict(size=10, color=_P["text_faint"], family="Inter, sans-serif"),
        ))
    fig.update_layout(annotations=annotations)
    return fig


def hbar(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    height: int = 220,
    colors: Sequence[str] | None = None,
    suffix: str = "%",
    max_value: float | None = None,
) -> go.Figure:
    """Horizontal ranking bars (regions, sectors, contributions)."""
    palette = list(colors) if colors else [series_color(i) for i in range(len(labels))]
    fig = go.Figure(
        go.Bar(
            x=list(values),
            y=list(labels),
            orientation="h",
            marker=dict(color=palette, line=dict(width=0), cornerradius=4),
            text=[f"{v:,.1f}{suffix}" for v in values],
            textposition="outside",
            textfont=dict(size=11, color=_P["text_soft"]),
            hovertemplate=f"<b>%{{y}}</b> %{{x:,.2f}}{suffix}<extra></extra>",
            cliponaxis=False,
        )
    )
    _base(fig, height=height, hovermode="y unified", margin={"l": 4, "r": 40})
    fig.update_xaxes(
        showgrid=True, gridcolor=_grid(), showline=False, ticksuffix=suffix,
        range=[0, (max_value or max(values, default=1)) * 1.18],
    )
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11.5, color=_P["text_muted"]))
    return fig


def grouped_bar(
    categories: Sequence[str],
    groups: Mapping[str, Sequence[float]],
    *,
    height: int = 260,
    suffix: str = "%",
    colors: Mapping[str, str] | None = None,
) -> go.Figure:
    """Side-by-side comparison, e.g. YTD versus forecast per instrument."""
    fig = go.Figure()
    for i, (name, values) in enumerate(groups.items()):
        color = (colors or {}).get(name, series_color(i))
        fig.add_trace(
            go.Bar(
                x=list(categories), y=list(values), name=name,
                marker=dict(color=color, line=dict(width=0), cornerradius=3),
                hovertemplate=f"<b>%{{x}}</b><br>{name} %{{y:,.2f}}{suffix}<extra></extra>",
            )
        )
    _base(fig, height=height, legend=True, margin={"t": 28})
    fig.update_layout(barmode="group", bargap=0.32, bargroupgap=0.12)
    fig.add_hline(y=0, line=dict(color=_P["border_strong"], width=1))
    fig.update_yaxes(ticksuffix=suffix)
    return fig


def signed_bar(
    categories: Sequence[str],
    values: Sequence[float],
    *,
    height: int = 240,
    suffix: str = "%",
    horizontal: bool = False,
) -> go.Figure:
    """Bars coloured by sign — contribution and attribution charts."""
    colors = [_P["up"] if v >= 0 else _P["down"] for v in values]
    if horizontal:
        trace = go.Bar(
            x=list(values), y=list(categories), orientation="h",
            marker=dict(color=colors, line=dict(width=0), cornerradius=3),
            hovertemplate=f"<b>%{{y}}</b> %{{x:+,.2f}}{suffix}<extra></extra>",
        )
    else:
        trace = go.Bar(
            x=list(categories), y=list(values),
            marker=dict(color=colors, line=dict(width=0), cornerradius=3),
            hovertemplate=f"<b>%{{x}}</b> %{{y:+,.2f}}{suffix}<extra></extra>",
        )
    fig = go.Figure(trace)
    _base(fig, height=height, hovermode="closest")
    fig.update_layout(bargap=0.35)
    if horizontal:
        fig.add_vline(x=0, line=dict(color=_P["border_strong"], width=1))
        fig.update_xaxes(showgrid=True, gridcolor=_grid(), ticksuffix=suffix)
        fig.update_yaxes(showgrid=False)
    else:
        fig.add_hline(y=0, line=dict(color=_P["border_strong"], width=1))
        fig.update_yaxes(ticksuffix=suffix)
    return fig


# ---------------------------------------------------------------------------
#  Risk analytics
# ---------------------------------------------------------------------------

def correlation_heatmap(matrix: pd.DataFrame, *, height: int = 380) -> go.Figure:
    """Correlation matrix with a diverging red→neutral→green scale."""
    fig = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=list(matrix.columns),
            y=list(matrix.index),
            zmin=-1, zmax=1,
            colorscale=[
                [0.0, _P["down"]], [0.25, rgba(_P["down"], 0.45)],
                [0.5, _P["surface_hi"]],
                [0.75, rgba(_P["up"], 0.45)], [1.0, _P["up"]],
            ],
            text=matrix.round(2).values,
            texttemplate="%{text:.2f}",
            textfont=dict(size=10, color=_P["text_soft"]),
            hovertemplate="<b>%{y} / %{x}</b><br>ρ = %{z:.3f}<extra></extra>",
            xgap=2, ygap=2,
            colorbar=dict(
                thickness=8, len=0.7, outlinewidth=0,
                tickfont=dict(size=10, color=_P["text_faint"]),
                tickvals=[-1, 0, 1],
            ),
        )
    )
    _base(fig, height=height, hovermode="closest", margin={"l": 4, "r": 4, "t": 4, "b": 4})
    fig.update_xaxes(showline=False, side="bottom", tickfont=dict(size=11, color=_P["text_muted"]))
    fig.update_yaxes(showgrid=False, autorange="reversed",
                     tickfont=dict(size=11, color=_P["text_muted"]))
    return fig


def efficient_frontier(
    volatilities: Sequence[float],
    returns: Sequence[float],
    sharpes: Sequence[float],
    *,
    height: int = 400,
    markers: Sequence[dict[str, Any]] = (),
) -> go.Figure:
    """The efficient frontier, coloured by Sharpe ratio, with named portfolios."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[v * 100 for v in volatilities],
            y=[r * 100 for r in returns],
            mode="lines+markers",
            name="Frontière efficiente",
            line=dict(color=_P["accent"], width=2.2, shape="spline", smoothing=0.6),
            marker=dict(
                size=7,
                color=list(sharpes),
                colorscale=[[0, _P["down"]], [0.5, _P["warn"]], [1, _P["up"]]],
                showscale=True,
                line=dict(width=0.5, color=_P["bg"]),
                colorbar=dict(
                    title=dict(text="Sharpe", font=dict(size=10, color=_P["text_faint"])),
                    thickness=8, len=0.65, outlinewidth=0,
                    tickfont=dict(size=10, color=_P["text_faint"]),
                ),
            ),
            hovertemplate="Volatilité <b>%{x:.2f}%</b><br>Rendement <b>%{y:.2f}%</b>"
                          "<br>Sharpe %{marker.color:.2f}<extra></extra>",
        )
    )
    for marker in markers:
        fig.add_trace(
            go.Scatter(
                x=[marker["volatility"] * 100],
                y=[marker["return"] * 100],
                mode="markers+text",
                name=marker["label"],
                marker=dict(
                    size=15, symbol=marker.get("symbol", "star"),
                    color=marker.get("color", _P["warn"]),
                    line=dict(width=1.5, color=_P["bg"]),
                ),
                text=[marker["label"]],
                textposition=marker.get("position", "top center"),
                textfont=dict(size=11, color=_P["text_soft"]),
                hovertemplate=f"<b>{marker['label']}</b><br>Vol %{{x:.2f}}%"
                              "<br>Rendement %{y:.2f}%<extra></extra>",
            )
        )
    _base(fig, height=height, legend=True, hovermode="closest", margin={"t": 30, "l": 48, "b": 44})
    fig.update_xaxes(title=dict(text="Volatilité annualisée (%)",
                                font=dict(size=11, color=_P["text_faint"])),
                     showgrid=True, gridcolor=_grid())
    fig.update_yaxes(title=dict(text="Rendement attendu (%)",
                                font=dict(size=11, color=_P["text_faint"])))
    return fig


def drawdown(x: Sequence[Any], values: Sequence[float], *, height: int = 220) -> go.Figure:
    """Underwater (drawdown) chart."""
    fig = go.Figure(
        go.Scatter(
            x=list(x), y=list(values), mode="lines",
            line=dict(color=_P["down"], width=1.6),
            fill="tozeroy", fillcolor=rgba(_P["down"], 0.18),
            hovertemplate="%{x|%d %b %Y}<br>Drawdown <b>%{y:.2f}%</b><extra></extra>",
        )
    )
    _base(fig, height=height)
    fig.update_yaxes(ticksuffix="%")
    return fig


def scatter_risk_return(
    points: pd.DataFrame,
    *,
    x: str = "volatility",
    y: str = "expected_return",
    label: str = "ticker",
    size: str | None = "weight",
    height: int = 340,
) -> go.Figure:
    """Risk/return bubble map of the individual holdings."""
    sizes = points[size] if size and size in points.columns else None
    fig = go.Figure(
        go.Scatter(
            x=points[x] * 100,
            y=points[y] * 100,
            mode="markers+text",
            text=points[label],
            textposition="top center",
            textfont=dict(size=10.5, color=_P["text_muted"]),
            marker=dict(
                size=(sizes * 1.6 + 9) if sizes is not None else 13,
                color=[series_color(i) for i in range(len(points))],
                line=dict(width=1, color=_P["bg"]),
                opacity=0.9,
            ),
            hovertemplate="<b>%{text}</b><br>Volatilité %{x:.2f}%"
                          "<br>Rendement attendu %{y:.2f}%<extra></extra>",
        )
    )
    _base(fig, height=height, hovermode="closest", margin={"t": 16, "l": 48, "b": 44})
    fig.update_xaxes(title=dict(text="Volatilité (%)", font=dict(size=11, color=_P["text_faint"])),
                     showgrid=True, gridcolor=_grid())
    fig.update_yaxes(title=dict(text="Rendement attendu (%)",
                                font=dict(size=11, color=_P["text_faint"])))
    return fig


# ---------------------------------------------------------------------------
#  Forecast + news context
# ---------------------------------------------------------------------------

def forecast_with_news(
    dates: Sequence[Any],
    prices: Sequence[float],
    *,
    base_forecast: tuple[Any, float] | None = None,
    news_context_forecast: tuple[Any, float] | None = None,
    news_markers: Sequence[Mapping[str, Any]] | None = None,
    height: int = 320,
) -> go.Figure:
    """Historical price with the base and news-context forecast points, plus
    dated news markers (📰) coloured by sentiment.

    `news_markers`: sequence of `{"date", "price", "sentiment"}` — `sentiment`
    one of `POSITIVE`/`NEGATIVE`/`NEUTRAL`, `price` the historical close on
    (or nearest to) that date, used only to place the marker on the line.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(dates), y=list(prices), name="Historique", mode="lines",
            line=dict(color=series_color(0), width=2),
            hovertemplate="%{x|%d %b %Y}<br>%{y:,.2f} $<extra></extra>",
        )
    )

    last_x = dates[-1] if len(dates) else None
    last_y = prices[-1] if len(prices) else None

    if base_forecast and last_x is not None:
        bx, by = base_forecast
        fig.add_trace(
            go.Scatter(
                x=[last_x, bx], y=[last_y, by], name="Base Forecast",
                mode="lines+markers", line=dict(color=_P["violet"], width=2, dash="dash"),
                marker=dict(size=[0, 9], symbol="circle"),
                hovertemplate="Base Forecast<br>%{y:,.2f} $<extra></extra>",
            )
        )

    if news_context_forecast and last_x is not None:
        nx, ny = news_context_forecast
        fig.add_trace(
            go.Scatter(
                x=[last_x, nx], y=[last_y, ny], name="News-Context Forecast",
                mode="lines+markers", line=dict(color=_P["accent"], width=2, dash="dot"),
                marker=dict(size=[0, 10], symbol="star"),
                hovertemplate="News-Context Forecast<br>%{y:,.2f} $<extra></extra>",
            )
        )

    if news_markers:
        colors = {"POSITIVE": _P["up"], "NEGATIVE": _P["down"]}
        fig.add_trace(
            go.Scatter(
                x=[m["date"] for m in news_markers],
                y=[m["price"] for m in news_markers],
                name="Actualités",
                mode="markers",
                marker=dict(
                    size=11, symbol="diamond",
                    color=[colors.get(m["sentiment"], _P["text_muted"]) for m in news_markers],
                    line=dict(width=1.5, color=_P["bg"]),
                ),
                hovertext=[f"📰 {m.get('title', m['sentiment'].title())}" for m in news_markers],
                hovertemplate="%{hovertext}<extra></extra>",
            )
        )

    return _base(fig, height=height, legend=True, hovermode="closest")
