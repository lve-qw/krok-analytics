"""Plotly figures for the dashboard.

Colour carries one meaning per chart and nothing else: a single accent for
measured volume, the copper accent for a highlighted extreme, and the muted
``dim`` token for everything outside the current selection. Selection is a
state, so it de-emphasises the rest instead of recolouring the chosen mark.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import Theme

FONT = '"Avenir Next", "Segoe UI Variable", system-ui, sans-serif'


def _base(figure: go.Figure, theme: Theme, *, height: int = 300) -> go.Figure:
    figure.update_layout(
        height=height,
        margin=dict(l=16, r=16, t=14, b=28),
        paper_bgcolor=theme.surface,
        plot_bgcolor=theme.surface,
        font=dict(color=theme.text_primary, family=FONT, size=12),
        showlegend=False,
        bargap=0.28,
        hoverlabel=dict(
            bgcolor=theme.surface,
            font_color=theme.text_primary,
            bordercolor=theme.guide,
        ),
    )
    figure.update_xaxes(
        showline=False,
        zeroline=False,
        gridcolor=theme.grid,
        tickfont=dict(color=theme.muted),
        title_font=dict(color=theme.muted, size=11),
    )
    figure.update_yaxes(
        showline=False,
        zeroline=False,
        gridcolor=theme.grid,
        tickfont=dict(color=theme.muted),
        title_font=dict(color=theme.muted, size=11),
    )
    return figure


def empty(theme: Theme, height: int = 300, text: str = "Нет данных для выбранного фильтра") -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=text,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(color=theme.muted),
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return _base(figure, theme, height=height)


def _is_empty(data: pd.DataFrame, column: str) -> bool:
    return data is None or data.empty or column not in data or data[column].sum() == 0


def usage_bar(
    data: pd.DataFrame,
    theme: Theme,
    metric: str,
    selected: str | None = None,
) -> go.Figure:
    """Top users by dialogues or by consumed tokens."""

    if _is_empty(data, metric):
        return empty(theme, height=340)
    ordered = data.sort_values(metric, ascending=True)
    colors = [
        theme.series[0] if selected is None or key == selected else theme.dim
        for key in ordered["key"]
    ]
    suffix = " диалогов" if metric == "dialogues" else " токенов"
    figure = go.Figure(
        go.Bar(
            x=ordered[metric],
            y=ordered["key"],
            orientation="h",
            marker=dict(color=colors),
            customdata=ordered[["key"]],
            hovertemplate=f"%{{y}}<br>%{{x:,.0f}}{suffix}<extra></extra>",
        )
    )
    figure.update_xaxes(title_text="Диалоги" if metric == "dialogues" else "Токены", showgrid=True)
    figure.update_yaxes(title_text="")
    return _base(figure, theme, height=max(340, 26 * len(ordered) + 90))


def hourly_profile(data: pd.DataFrame, theme: Theme, metric: str) -> go.Figure:
    """Load by UTC hour: a profile of the available period, not a trend."""

    if _is_empty(data, metric):
        return empty(theme, height=340)
    values = data[metric]
    peak = float(values.max())
    figure = go.Figure(
        go.Bar(
            x=[f"{hour:02d}" for hour in data["hour"]],
            y=values,
            marker=dict(
                color=[theme.series[1] if value == peak and peak else theme.dim for value in values]
            ),
            hovertemplate="%{x}:00 UTC<br>%{y:,.0f}<extra></extra>",
        )
    )
    figure.update_xaxes(title_text="Час UTC", dtick=2, showgrid=False)
    figure.update_yaxes(title_text="Диалоги" if metric == "dialogues" else "Токены", showgrid=True)
    return _base(figure, theme, height=340)


def category_bar(
    data: pd.DataFrame,
    theme: Theme,
    *,
    value: str = "dialogs",
    title: str = "Диалоги",
    color: str | None = None,
    height: int = 260,
) -> go.Figure:
    """A short vertical distribution: complexity, periodicity, language."""

    if _is_empty(data, value):
        return empty(theme, height=height)
    total = float(data[value].sum())
    figure = go.Figure(
        go.Bar(
            x=data["key"],
            y=data[value],
            marker=dict(color=color or theme.series[0]),
            text=[f"{v / total * 100:.0f}%" for v in data[value]],
            textposition="outside",
            textfont=dict(color=theme.muted, size=11),
            cliponaxis=False,
            hovertemplate="%{x}<br>%{y:,.0f} диалогов<extra></extra>",
        )
    )
    figure.update_xaxes(title_text="", showgrid=False)
    figure.update_yaxes(title_text=title, showgrid=True, rangemode="tozero")
    return _base(figure, theme, height=height)


def ranked_bar(
    data: pd.DataFrame,
    theme: Theme,
    *,
    label: str = "key",
    value: str = "dialogs",
    limit: int = 12,
    color: str | None = None,
    unit: str = "диалогов",
    height: int | None = None,
) -> go.Figure:
    """A ranked horizontal bar for integrations, tools, clusters, failures."""

    if _is_empty(data, value):
        return empty(theme, height=height or 300)
    ordered = data.head(limit).sort_values(value, ascending=True)
    # A failure_reason can be a whole sentence. Left whole it eats the plotting
    # area; the hover keeps the full text.
    ticks = ordered[label].astype(str)
    shortened = ticks.map(lambda text: text if len(text) <= 34 else text[:33] + "…")
    if shortened.duplicated().any():
        # Two bars sharing a category label would be drawn on the same row.
        collisions = shortened.duplicated(keep=False)
        shortened = shortened.where(
            ~collisions, shortened + " " + shortened.groupby(shortened).cumcount().add(1).astype(str)
        )
    figure = go.Figure(
        go.Bar(
            x=ordered[value],
            y=shortened,
            orientation="h",
            marker=dict(color=color or theme.series[2]),
            customdata=ordered[[label]],
            hovertemplate=f"%{{customdata[0]}}<br>%{{x:,.0f}} {unit}<extra></extra>",
        )
    )
    figure.update_xaxes(title_text=unit.capitalize(), showgrid=True)
    figure.update_yaxes(title_text="", automargin=True)
    return _base(figure, theme, height=height or max(260, 24 * len(ordered) + 80))


def donut(
    data: pd.DataFrame,
    theme: Theme,
    *,
    label: str = "key",
    value: str = "tokens",
    unit: str = "токенов",
    height: int = 260,
) -> go.Figure:
    """A share of a whole where the parts are named directly on the ring."""

    if _is_empty(data, value):
        return empty(theme, height=height)
    figure = go.Figure(
        go.Pie(
            labels=data[label],
            values=data[value],
            hole=0.62,
            sort=False,
            marker=dict(colors=list(theme.series), line=dict(color=theme.surface, width=2)),
            textinfo="label+percent",
            textposition="outside",
            insidetextorientation="horizontal",
            hovertemplate=f"%{{label}}<br>%{{value:,.0f}} {unit} (%{{percent}})<extra></extra>",
        )
    )
    figure.update_traces(textfont=dict(color=theme.text_secondary, size=11))
    return _base(figure, theme, height=height)


def stacked_pair(
    theme: Theme,
    *,
    left_label: str,
    left_value: float,
    right_label: str,
    right_value: float,
    unit: str = "сообщений",
    height: int = 150,
) -> go.Figure:
    """One bar split in two parts — useful vs useless, work vs non-work."""

    if left_value + right_value <= 0:
        return empty(theme, height=height)
    figure = go.Figure()
    for name, amount, color in (
        (left_label, left_value, theme.series[2]),
        (right_label, right_value, theme.dim),
    ):
        figure.add_bar(
            x=[amount],
            y=[""],
            name=name,
            orientation="h",
            marker=dict(color=color),
            text=[f"{name}: {amount:,.0f}".replace(",", " ")],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color=theme.surface if color != theme.dim else theme.text_primary, size=12),
            hovertemplate=f"{name}<br>%{{x:,.0f}} {unit}<extra></extra>",
        )
    figure.update_layout(barmode="stack", bargap=0.4)
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return _base(figure, theme, height=height)


def confidence_histogram(values: pd.Series, theme: Theme, threshold: float, height: int = 260) -> go.Figure:
    """Distribution of classifier confidence with the low-confidence cut."""

    if values is None or len(values) == 0:
        return empty(theme, height=height)
    figure = go.Figure(
        go.Histogram(
            x=values,
            xbins=dict(start=0, end=1.0001, size=0.1),
            marker=dict(color=theme.series[0]),
            hovertemplate="confidence %{x}<br>%{y} диалогов<extra></extra>",
        )
    )
    figure.add_vline(
        x=threshold,
        line=dict(color=theme.guide, width=1, dash="dash"),
        annotation_text=f"порог {threshold}".replace(".", ","),
        annotation_position="top left",
        annotation_font=dict(color=theme.muted, size=11),
    )
    figure.update_xaxes(title_text="confidence", showgrid=False, range=[0, 1.02])
    figure.update_yaxes(title_text="Диалоги", showgrid=True)
    return _base(figure, theme, height=height)
