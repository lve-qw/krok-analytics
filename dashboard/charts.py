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
    divisor: int = 1,
    axis_title: str | None = None,
    height: int | None = None,
) -> go.Figure:
    """A ranked horizontal bar for integrations, tools, clusters, failures.

    ``divisor`` rescales the axis: token totals plotted raw come out as
    «0.2M», which is neither Russian nor readable across a room.
    """

    if _is_empty(data, value):
        return empty(theme, height=height or 300)
    ordered = data.head(limit).sort_values(value, ascending=True)
    raw = ordered[value]
    if divisor != 1:
        ordered = ordered.assign(**{value: raw / divisor})
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
            # The hover always states the measured value, never the rescaled one.
            customdata=list(zip(ticks, raw)),
            hovertemplate=f"%{{customdata[0]}}<br>%{{customdata[1]:,.0f}} {unit}<extra></extra>",
        )
    )
    figure.update_xaxes(title_text=(axis_title or unit).capitalize(), showgrid=True)
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
    total = float(data[value].sum())
    # Plotly writes «0.0348%»: a Latin decimal point and four digits of noise.
    # The label is built here so a share below one per cent reads as «<1 %».
    captions = []
    for name, amount in zip(data[label], data[value]):
        share = amount / total * 100
        share_text = "<1 %" if 0 < share < 1 else f"{share:.1f} %".replace(".", ",")
        captions.append(f"{name}<br>{share_text}")
    figure = go.Figure(
        go.Pie(
            labels=data[label],
            values=data[value],
            hole=0.62,
            sort=False,
            marker=dict(colors=list(theme.series), line=dict(color=theme.surface, width=2)),
            text=captions,
            textinfo="text",
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


def scenario_scatter(data: pd.DataFrame, theme: Theme, height: int = 420) -> go.Figure:
    """The automation map: how often a scenario happens vs how ready it is.

    Median lines split the plane into four quadrants; the interesting one is
    upper-right — frequent scenarios that the analysis already marked as
    automatable. Colour carries the share of simple dialogues, because a
    frequent, automatable *and* simple scenario is the cheapest thing to build.
    """

    if data is None or data.empty:
        return empty(theme, height=height)

    x_median = float(data["share"].median())
    y_median = float(data["automation_share"].median())
    highlight = (data["share"] >= x_median) & (data["automation_share"] >= y_median)
    labels = data["label"].where(highlight, "")

    figure = go.Figure(
        go.Scatter(
            x=data["share"],
            y=data["automation_share"],
            mode="markers+text",
            text=labels,
            textposition="top center",
            textfont=dict(color=theme.text_secondary, size=11),
            cliponaxis=False,
            marker=dict(
                size=22,
                color=data["simple_share"],
                colorscale=[[index / (len(theme.sequential) - 1), color]
                            for index, color in enumerate(theme.sequential)],
                cmin=0,
                cmax=100,
                line=dict(color=theme.surface, width=1.5),
                colorbar=dict(
                    title=dict(text="простых, %", font=dict(color=theme.muted, size=10)),
                    tickfont=dict(color=theme.muted, size=10),
                    thickness=8,
                    len=0.7,
                    outlinewidth=0,
                ),
            ),
            customdata=data[["label", "dialogs", "automation_share", "simple_share", "avg_tokens"]],
            hovertemplate=(
                "%{customdata[0]}<br>"
                "%{customdata[1]} диалогов · %{x:.1f} % выгрузки<br>"
                "кандидатов на автоматизацию: %{customdata[2]:.0f} %<br>"
                "простых: %{customdata[3]:.0f} % · в среднем %{customdata[4]:,.0f} токенов"
                "<extra></extra>"
            ),
        )
    )
    for value, orientation in ((x_median, "v"), (y_median, "h")):
        line = dict(color=theme.guide, width=1, dash="dot")
        if orientation == "v":
            figure.add_vline(x=value, line=line)
        else:
            figure.add_hline(y=value, line=line)
    figure.add_annotation(
        x=1,
        y=1.06,
        xref="paper",
        yref="paper",
        xanchor="right",
        showarrow=False,
        text="частые и готовые к автоматизации →",
        font=dict(color=theme.muted, size=10.5),
    )
    figure.update_xaxes(title_text="Доля диалогов, %", showgrid=True, rangemode="tozero")
    figure.update_yaxes(title_text="Кандидатов на автоматизацию, %", showgrid=True, rangemode="tozero")
    return _base(figure, theme, height=height)


def grouped_bar(
    data: pd.DataFrame,
    theme: Theme,
    *,
    left: tuple[str, str],
    right: tuple[str, str],
    height: int = 280,
) -> go.Figure:
    """Two series side by side over the same categories."""

    if data is None or data.empty or (data[left[0]].sum() + data[right[0]].sum()) == 0:
        return empty(theme, height=height)
    figure = go.Figure()
    for (column, name), color in ((left, theme.series[0]), (right, theme.dim)):
        figure.add_bar(
            x=data["key"],
            y=data[column],
            name=name,
            marker=dict(color=color),
            text=data[column],
            textposition="outside",
            textfont=dict(color=theme.muted, size=11),
            cliponaxis=False,
            hovertemplate=f"%{{x}} · {name}<br>%{{y:,.0f}} диалогов<extra></extra>",
        )
    figure.update_layout(barmode="group", showlegend=True, legend=dict(
        orientation="h", yanchor="top", y=-0.16, xanchor="left", x=0,
        font=dict(color=theme.text_secondary, size=11), bgcolor="rgba(0,0,0,0)",
    ))
    figure.update_xaxes(title_text="", showgrid=False)
    figure.update_yaxes(title_text="Диалоги", showgrid=True, rangemode="tozero")
    figure = _base(figure, theme, height=height)
    # `_base` turns legends off for every other chart on the page, so this one
    # is switched back on afterwards, together with the room its row needs.
    figure.update_layout(showlegend=True, margin=dict(l=16, r=16, t=14, b=58))
    return figure


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
