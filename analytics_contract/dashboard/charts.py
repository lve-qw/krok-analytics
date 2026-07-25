"""Plotly figures for the seven selected charts.

Conventions applied throughout, per the project's visualization rules:

- one y-axis per figure; no dual-scale charts;
- categorical hues assigned by fixed slot, never cycled by rank;
- thin marks, recessive grid, hover on every mark;
- direct labels wherever a mark's colour sits below 3:1 on the light surface.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from analytics_contract.dashboard.theme import Theme

EMPTY_NOTE = "Недостаточно данных при текущих фильтрах"


def _base(figure: go.Figure, theme: Theme, *, height: int = 340) -> go.Figure:
    figure.update_layout(
        height=height,
        paper_bgcolor=theme.surface,
        plot_bgcolor=theme.surface,
        font=dict(
            family='system-ui, -apple-system, "Segoe UI", sans-serif',
            color=theme.text_secondary,
            size=12,
        ),
        margin=dict(l=8, r=16, t=8, b=8),
        hoverlabel=dict(
            bgcolor=theme.surface, bordercolor=theme.border, font_color=theme.text_primary
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
    )
    figure.update_xaxes(
        showgrid=False, zeroline=False, linecolor=theme.axis, tickfont_color=theme.muted
    )
    figure.update_yaxes(
        gridcolor=theme.grid, zeroline=False, linecolor=theme.axis, tickfont_color=theme.muted
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


def volume_bar(data: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart 1 — top scenarios (or classes) by volume."""

    if data.empty:
        return _empty(theme, 420)
    data = data.sort_values("count")
    figure = go.Figure(
        go.Bar(
            x=data["count"],
            y=data["use_case"],
            orientation="h",
            marker=dict(color=theme.series[0], line=dict(color=theme.surface, width=2)),
            text=data["count"],
            textposition="outside",
            textfont=dict(color=theme.text_secondary),
            hovertemplate="%{y}<br>Диалогов: %{x}<extra></extra>",
        )
    )
    figure.update_xaxes(showgrid=True, gridcolor=theme.grid)
    figure.update_yaxes(showgrid=False, automargin=True)
    return _base(figure, theme, height=420)


def periodicity_heatmap(matrix: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart 2 — scenario x declared periodicity."""

    if matrix.empty:
        return _empty(theme, 420)
    labels = {"none": "разовые", "daily": "ежедневно", "weekly": "еженедельно", "monthly": "ежемесячно"}
    figure = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=[labels.get(column, column) for column in matrix.columns],
            y=list(matrix.index),
            colorscale=[[index / (len(theme.sequential) - 1), colour]
                        for index, colour in enumerate(theme.sequential)],
            xgap=2,
            ygap=2,
            hovertemplate="%{y}<br>%{x}: %{z} диалогов<extra></extra>",
            colorbar=dict(outlinewidth=0, tickfont=dict(color=theme.muted)),
        )
    )
    figure.update_yaxes(showgrid=False, automargin=True)
    return _base(figure, theme, height=420)


def failure_scatter(data: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart 3 — volume against failure rate, bubble size is cost."""

    if data.empty:
        return _empty(theme)
    sizes = data["cost"] / data["cost"].max() * 42 + 10 if data["cost"].max() > 0 else 14
    figure = go.Figure(
        go.Scatter(
            x=data["volume"],
            y=data["failure_rate"],
            mode="markers+text",
            marker=dict(
                size=sizes,
                color=theme.series[0],
                opacity=0.75,
                line=dict(color=theme.surface, width=2),
            ),
            text=data["use_case"],
            textposition="top center",
            textfont=dict(color=theme.text_secondary, size=10),
            customdata=data[["cost"]],
            hovertemplate=(
                "%{text}<br>Диалогов: %{x}<br>Доля сбоев: %{y:.1%}"
                "<br>Стоимость: %{customdata[0]:.4f}<extra></extra>"
            ),
        )
    )
    figure.update_xaxes(title_text="Объём, диалогов", showgrid=True, gridcolor=theme.grid)
    figure.update_yaxes(title_text="Доля сбоев", tickformat=".0%")
    return _base(figure, theme)


def reliability_bar(data: pd.DataFrame, theme: Theme, label_column: str) -> go.Figure:
    """Chart 4 — failure rate per tool or integration with Wilson intervals."""

    if data.empty:
        return _empty(theme)
    data = data.sort_values("failure_rate")
    figure = go.Figure(
        go.Bar(
            x=data["failure_rate"],
            y=data[label_column],
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
            customdata=data[["volume", "failures"]],
            hovertemplate=(
                "%{y}<br>Доля сбоев: %{x:.1%}"
                "<br>Сбоев: %{customdata[1]} из %{customdata[0]}<extra></extra>"
            ),
        )
    )
    figure.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=theme.grid)
    figure.update_yaxes(showgrid=False, automargin=True)
    return _base(figure, theme)


def cost_pareto(data: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart 5 — cost share per scenario plus cumulative share.

    Both series are percentages of the same total, so they share one axis.
    """

    if data.empty:
        return _empty(theme)
    figure = go.Figure()
    figure.add_bar(
        x=data["use_case"],
        y=data["share"],
        name="Доля расходов",
        marker=dict(color=theme.series[0], line=dict(color=theme.surface, width=2)),
        customdata=data[["cost"]],
        hovertemplate="%{x}<br>Доля: %{y:.1%}<br>Стоимость: %{customdata[0]:.4f}<extra></extra>",
    )
    figure.add_scatter(
        x=data["use_case"],
        y=data["cumulative"],
        name="Накопленная доля",
        mode="lines+markers",
        line=dict(color=theme.series[1], width=2),
        marker=dict(size=8, line=dict(color=theme.surface, width=2)),
        hovertemplate="%{x}<br>Накоплено: %{y:.1%}<extra></extra>",
    )
    figure.update_yaxes(tickformat=".0%", title_text="Доля общей стоимости")
    figure.update_xaxes(automargin=True)
    return _base(figure, theme, height=380)


def token_split_bar(data: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart 6 — mean tokens by role and complexity."""

    if data.empty:
        return _empty(theme)
    series = [
        ("user_tokens", "Пользователь", theme.series[0]),
        ("assistant_tokens", "Ответ агента", theme.series[1]),
        ("tool_tokens", "Инструменты", theme.series[2]),
    ]
    figure = go.Figure()
    for column, name, colour in series:
        figure.add_bar(
            x=data["complexity"],
            y=data[column],
            name=name,
            marker=dict(color=colour, line=dict(color=theme.surface, width=2)),
            text=[f"{value:.0f}" for value in data[column]],
            textposition="inside",
            insidetextfont=dict(color=theme.surface),
            hovertemplate=f"{name}<br>%{{x}}: %{{y:.0f}} токенов<extra></extra>",
        )
    figure.update_layout(barmode="stack")
    figure.update_yaxes(title_text="Токенов в среднем")
    return _base(figure, theme)


def security_heatmap(matrix: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart 7 — data-risk indicators per scenario."""

    if matrix.empty:
        return _empty(theme, 380)
    labels = {
        "sensitive": "чувствительные данные",
        "company": "корпоративные данные",
        "injection": "prompt injection",
    }
    figure = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=[labels[column] for column in matrix.columns],
            y=list(matrix.index),
            colorscale=[[index / (len(theme.sequential) - 1), colour]
                        for index, colour in enumerate(theme.sequential)],
            zmin=0,
            zmax=1,
            xgap=2,
            ygap=2,
            hovertemplate="%{y}<br>%{x}: %{z:.0%}<extra></extra>",
            colorbar=dict(tickformat=".0%", outlinewidth=0, tickfont=dict(color=theme.muted)),
        )
    )
    figure.update_yaxes(showgrid=False, automargin=True)
    return _base(figure, theme, height=380)
