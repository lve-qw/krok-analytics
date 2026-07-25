"""Plotly figures for the seven selected charts.

Conventions applied throughout, per the project's visualization rules:

- one y-axis per figure; no dual-scale charts;
- categorical hues assigned by fixed slot, never cycled by rank;
- thin marks, recessive grid, hover on every mark;
- axis captions are shortened for the canvas and repeated in full in the hover,
  so a truncated label is never the only copy of a name;
- selection is drawn by de-emphasising the rest, so a mark's hue keeps meaning
  its identity rather than its state.

Type sizes are set for a projector rather than for a desk: the smallest text in
any figure is 12px, and axis ticks and value labels are 13px.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from analytics_contract.dashboard import labels
from analytics_contract.dashboard.theme import Theme

EMPTY_NOTE = "Недостаточно данных при текущих фильтрах"

TICK_SIZE = 13
LABEL_SIZE = 13


def _base(figure: go.Figure, theme: Theme, *, height: int = 340) -> go.Figure:
    figure.update_layout(
        height=height,
        paper_bgcolor=theme.surface,
        plot_bgcolor=theme.surface,
        font=dict(
            family='system-ui, -apple-system, "Segoe UI", sans-serif',
            color=theme.text_secondary,
            size=LABEL_SIZE,
        ),
        margin=dict(l=8, r=16, t=8, b=8),
        hoverlabel=dict(
            bgcolor=theme.surface,
            bordercolor=theme.border,
            font_color=theme.text_primary,
            font_size=13,
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            bgcolor="rgba(0,0,0,0)", font=dict(size=13),
        ),
    )
    figure.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=theme.axis,
        tickfont=dict(color=theme.muted, size=TICK_SIZE),
        title_font=dict(color=theme.muted, size=13),
    )
    figure.update_yaxes(
        gridcolor=theme.grid,
        zeroline=False,
        linecolor=theme.axis,
        tickfont=dict(color=theme.muted, size=TICK_SIZE),
        title_font=dict(color=theme.muted, size=13),
    )
    return figure


def _empty(theme: Theme, height: int = 340) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=EMPTY_NOTE, showarrow=False, font=dict(color=theme.muted, size=13)
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return _base(figure, theme, height=height)


def _mark_colours(values, selected, theme: Theme, hue: str) -> list[str]:
    """One colour per mark, dimming everything outside the selection."""

    if not selected:
        return [hue] * len(values)
    return [hue if value == selected else theme.dim for value in values]


def volume_bar(
    data: pd.DataFrame,
    theme: Theme,
    selected: str | None = None,
    total: int | None = None,
) -> go.Figure:
    """Chart 1 — top scenarios (or classes) by volume."""

    if data.empty:
        return _empty(theme, 420)
    data = data.sort_values("count")
    names = list(data["use_case"])
    denominator = total if total else int(data["count"].sum())
    shares = [count / denominator if denominator else 0.0 for count in data["count"]]
    figure = go.Figure(
        go.Bar(
            x=data["count"],
            y=labels.axis(names, "use_case"),
            orientation="h",
            marker=dict(
                color=_mark_colours(names, selected, theme, theme.series[0]),
                line=dict(color=theme.surface, width=2),
            ),
            text=data["count"],
            textposition="outside",
            textfont=dict(color=theme.text_secondary, size=LABEL_SIZE),
            # Last element is the stored value: a click has to come back as
            # the raw key, never as the shortened caption drawn on the axis.
            customdata=list(zip(labels.show_all(names, "use_case"), shares, names)),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>Диалогов: %{x}"
                "<br>Доля: %{customdata[1]:.1%}<extra></extra>"
            ),
        )
    )
    figure.update_xaxes(showgrid=True, gridcolor=theme.grid)
    figure.update_yaxes(showgrid=False, automargin=True)
    return _base(figure, theme, height=420)


def periodicity_heatmap(matrix: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart 2 — scenario x declared periodicity."""

    if matrix.empty:
        return _empty(theme, 420)
    names = [labels.use_case(value) for value in matrix.index]
    figure = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=[labels.show(column, "periodicity") for column in matrix.columns],
            y=labels.axis(matrix.index, "use_case"),
            colorscale=[[index / (len(theme.sequential) - 1), colour]
                        for index, colour in enumerate(theme.sequential)],
            xgap=2,
            ygap=2,
            customdata=[[name] * len(matrix.columns) for name in names],
            hovertemplate="<b>%{customdata}</b><br>%{x}: %{z} диалогов<extra></extra>",
            colorbar=dict(
                outlinewidth=0,
                tickfont=dict(color=theme.muted, size=12),
                title=dict(text="диалогов", font=dict(color=theme.muted, size=12)),
                thickness=12,
            ),
        )
    )
    figure.update_xaxes(tickangle=0, automargin=True)
    figure.update_yaxes(showgrid=False, automargin=True)
    return _base(figure, theme, height=420)


def failure_scatter(
    data: pd.DataFrame, theme: Theme, selected: str | None = None
) -> go.Figure:
    """Chart 3 — volume against failure rate, bubble size is cost.

    Median guides split the plane so the reader can place a point without being
    told how: past both medians a scenario is both frequent and unreliable.
    Only the points in that corner are labelled on the canvas — labelling all of
    them is what turned this chart into overlapping text.
    """

    if data.empty:
        return _empty(theme, 380)
    peak = float(data["cost"].max())
    sizes = data["cost"] / peak * 40 + 12 if peak > 0 else [16] * len(data)
    names = list(data["use_case"])
    shown = labels.show_all(names, "use_case")

    median_volume = float(data["volume"].median())
    median_rate = float(data["failure_rate"].median())
    hot = (data["volume"] >= median_volume) & (data["failure_rate"] >= median_rate)
    captions = [
        labels.truncate(name, 22) if flag else ""
        for name, flag in zip(shown, hot)
    ]

    figure = go.Figure(
        go.Scatter(
            x=data["volume"],
            y=data["failure_rate"],
            mode="markers+text",
            marker=dict(
                size=sizes,
                color=_mark_colours(names, selected, theme, theme.series[0]),
                opacity=0.8,
                line=dict(color=theme.surface, width=2),
            ),
            text=captions,
            textposition="top center",
            textfont=dict(color=theme.text_secondary, size=12),
            customdata=list(zip(shown, data["cost"], data["failures"], names)),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>Диалогов: %{x}"
                "<br>Доля сбоев: %{y:.1%} (%{customdata[2]} шт.)"
                "<br>Стоимость: %{customdata[1]:.4f} у.е.<extra></extra>"
            ),
        )
    )
    figure.add_vline(x=median_volume, line=dict(color=theme.guide, width=1, dash="dot"))
    figure.add_hline(y=median_rate, line=dict(color=theme.guide, width=1, dash="dot"))
    figure.add_annotation(
        x=1, y=1.04, xref="paper", yref="paper",
        text="выше и правее медиан — чаще и с большей долей сбоев",
        showarrow=False, xanchor="right",
        font=dict(color=theme.muted, size=12),
    )
    # Bubbles are sized in pixels, so the data range has to be padded by hand
    # or the marks at 0% and at the smallest volume are cut by the axis.
    volume_pad = max(float(data["volume"].max()) * 0.12, 1.0)
    rate_pad = max(float(data["failure_rate"].max()) * 0.18, 0.04)
    figure.update_xaxes(
        title_text="Объём, диалогов",
        showgrid=True,
        gridcolor=theme.grid,
        range=[float(data["volume"].min()) - volume_pad, float(data["volume"].max()) + volume_pad],
    )
    figure.update_yaxes(
        title_text="Доля диалогов со сбоем",
        tickformat=".0%",
        range=[-rate_pad, float(data["failure_rate"].max()) + rate_pad],
    )
    return _base(figure, theme, height=380)


def reliability_bar(data: pd.DataFrame, theme: Theme, label_column: str) -> go.Figure:
    """Chart 4 — share of dialogues that failed while a tool was in use.

    Not a measure of the tool's fault: the contract has no per-call events, so
    a failure is attributed to every tool present in the dialogue. The chart
    title says share-on-use for that reason, and the Wilson bars keep small
    groups from reading as findings.
    """

    if data.empty:
        return _empty(theme)
    data = data.sort_values("failure_rate")
    names = list(data[label_column])
    figure = go.Figure(
        go.Bar(
            x=data["failure_rate"],
            y=labels.axis(names, label_column),
            orientation="h",
            marker=dict(color=theme.series[1], line=dict(color=theme.surface, width=2)),
            error_x=dict(
                type="data",
                symmetric=False,
                array=data["high"] - data["failure_rate"],
                arrayminus=data["failure_rate"] - data["low"],
                color=theme.muted,
                thickness=1.5,
                width=4,
            ),
            customdata=list(zip(
                labels.show_all(names, label_column), data["volume"], data["failures"]
            )),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>Доля диалогов со сбоем: %{x:.1%}"
                "<br>Сбоев: %{customdata[2]} из %{customdata[1]}"
                "<br>Усы — 95% интервал Уилсона<extra></extra>"
            ),
        )
    )
    figure.update_xaxes(
        tickformat=".0%", showgrid=True, gridcolor=theme.grid,
        title_text="Доля диалогов со сбоем при использовании",
    )
    figure.update_yaxes(showgrid=False, automargin=True)
    return _base(figure, theme)


def cost_pareto(
    data: pd.DataFrame, theme: Theme, selected: str | None = None
) -> go.Figure:
    """Chart 5 — cost share per scenario plus cumulative share.

    Both series are percentages of the same total, so they share one axis. The
    80% guide is what makes it a Pareto chart rather than two series on a grid:
    where the line crosses it, that is the set of scenarios worth optimising.
    """

    if data.empty:
        return _empty(theme, 400)
    names = list(data["use_case"])
    shown = labels.show_all(names, "use_case")
    figure = go.Figure()
    figure.add_bar(
        x=labels.axis(names, "use_case", 16),
        y=data["share"],
        name="Доля расходов сценария",
        marker=dict(
            color=_mark_colours(names, selected, theme, theme.series[0]),
            line=dict(color=theme.surface, width=2),
        ),
        customdata=list(zip(shown, data["cost"], names)),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>Доля расходов: %{y:.1%}"
            "<br>Стоимость: %{customdata[1]:.4f} у.е.<extra></extra>"
        ),
    )
    figure.add_scatter(
        x=labels.axis(names, "use_case", 16),
        y=data["cumulative"],
        name="Накопленная доля",
        mode="lines+markers",
        line=dict(color=theme.series[1], width=2),
        marker=dict(size=8, line=dict(color=theme.surface, width=2)),
        customdata=list(zip(shown, names)),
        hovertemplate="<b>%{customdata[0]}</b><br>Накоплено: %{y:.1%}<extra></extra>",
    )
    figure.add_hline(
        y=0.8,
        line=dict(color=theme.guide, width=1, dash="dot"),
        annotation_text="80% расходов",
        annotation_position="top left",
        annotation_font=dict(color=theme.muted, size=12),
    )
    figure.update_yaxes(tickformat=".0%", title_text="Доля общей стоимости", range=[0, 1.05])
    figure.update_xaxes(automargin=True, tickangle=-35)
    return _base(figure, theme, height=400)


def token_split_bar(data: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart 6 — mean tokens by role and complexity."""

    if data.empty:
        return _empty(theme)
    series = [
        ("user_tokens", "Пользователь", theme.series[0]),
        ("assistant_tokens", "Ответ агента", theme.series[1]),
        ("tool_tokens", "Инструменты", theme.series[2]),
    ]
    complexity = labels.show_all(data["complexity"], "complexity")
    figure = go.Figure()
    for column, name, colour in series:
        figure.add_bar(
            x=complexity,
            y=data[column],
            name=name,
            marker=dict(color=colour, line=dict(color=theme.surface, width=2)),
            text=[f"{value:.0f}" if value else "" for value in data[column]],
            textposition="inside",
            insidetextfont=dict(color=theme.surface, size=LABEL_SIZE),
            hovertemplate=f"<b>{name}</b><br>%{{x}}: %{{y:.0f}} токенов<extra></extra>",
        )
    # Three categories across a full-width card would otherwise be drawn as
    # slabs; the gap keeps the bars reading as marks rather than as panels.
    figure.update_layout(barmode="stack", legend_traceorder="normal", bargap=0.55)
    figure.update_yaxes(title_text="Токенов в среднем на диалог")
    figure.update_xaxes(title_text="Сложность запроса")
    return _base(figure, theme)


def security_heatmap(matrix: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart 7 — data-risk indicators per scenario."""

    if matrix.empty:
        return _empty(theme, 400)
    names = [labels.use_case(value) for value in matrix.index]
    figure = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=[labels.RISK_COLUMN[column] for column in matrix.columns],
            y=labels.axis(matrix.index, "use_case"),
            colorscale=[[index / (len(theme.sequential) - 1), colour]
                        for index, colour in enumerate(theme.sequential)],
            zmin=0,
            zmax=1,
            xgap=2,
            ygap=2,
            customdata=[[name] * len(matrix.columns) for name in names],
            hovertemplate="<b>%{customdata}</b><br>%{x}: %{z:.0%} диалогов<extra></extra>",
            colorbar=dict(
                tickformat=".0%",
                outlinewidth=0,
                tickfont=dict(color=theme.muted, size=12),
                title=dict(text="доля", font=dict(color=theme.muted, size=12)),
                thickness=12,
            ),
        )
    )
    figure.update_xaxes(tickangle=0, automargin=True)
    figure.update_yaxes(showgrid=False, automargin=True)
    return _base(figure, theme, height=400)
