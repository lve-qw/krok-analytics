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


def _padded(values, share: float, top_share: float | None = None) -> list[float]:
    """Axis range with headroom, for charts whose marks have pixel size.

    The top is padded separately because a label drawn above a mark needs more
    room than the mark itself: at the plot edge the ascenders get clipped and
    "простой" reads as "простои".
    """

    low, high = float(min(values)), float(max(values))
    span = (high - low) or high or 1.0
    return [low - span * share, high + span * (share if top_share is None else top_share)]


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


def usage_bar(
    data: pd.DataFrame,
    theme: Theme,
    dimension: str,
    metric: str,
    selected: str | None = None,
    total: float | None = None,
) -> go.Figure:
    """Interactive usage ranking by scenario, class or pseudonymous user."""

    if data.empty:
        return _empty(theme, 420)

    metric_labels = {
        "dialogues": ("Диалоги", "диалогов"),
        "tokens": ("Токены", "токенов"),
        "tool_calls": ("Вызовы инструментов", "вызовов"),
    }
    axis_title, value_label = metric_labels[metric]
    data = data.sort_values(metric)
    names = list(data["key"])
    values = list(data[metric])
    denominator = float(total or sum(values))
    shares = [value / denominator if denominator else 0.0 for value in values]

    def compact(value: float) -> str:
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f} млн".replace(".", ",")
        if value >= 1_000:
            return f"{value / 1_000:.0f} тыс."
        return f"{value:,.0f}".replace(",", " ")

    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels.axis(names, dimension),
            orientation="h",
            marker=dict(
                color=_mark_colours(names, selected, theme, theme.series[0]),
                line=dict(color=theme.surface, width=2),
            ),
            text=[compact(value) for value in values],
            textposition="outside",
            textfont=dict(color=theme.text_secondary, size=LABEL_SIZE),
            customdata=list(
                zip(
                    labels.show_all(names, dimension),
                    data["dialogues"],
                    data["tokens"],
                    data["tool_calls"],
                    shares,
                    names,
                )
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                f"<br>{axis_title}: %{{x:,.0f}}"
                "<br>Диалогов: %{customdata[1]:,.0f}"
                "<br>Токенов: %{customdata[2]:,.0f}"
                "<br>Вызовов инструментов: %{customdata[3]:,.0f}"
                f"<br>Доля по показателю: %{{customdata[4]:.1%}}"
                "<extra></extra>"
            ),
        )
    )
    figure.update_xaxes(title_text=axis_title, showgrid=True, gridcolor=theme.grid)
    figure.update_yaxes(showgrid=False, automargin=True)
    figure.update_layout(separators=", ")
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


def lorenz_curve(data: pd.DataFrame, theme: Theme, gini: float) -> go.Figure:
    """Chart A — how evenly the agent is used across employees.

    A ranked bar per user was rejected: twenty-five bars of near-equal height
    read as noise, and the question is about the shape of the distribution, not
    about which pseudonymous id is on top. The Lorenz form answers it with one
    line, carries its own reference (the diagonal is perfectly even use) and
    keeps a single scale, since both axes are shares of their own total.
    """

    if data.empty:
        return _empty(theme)
    figure = go.Figure()
    figure.add_scatter(
        x=[0, 1],
        y=[0, 1],
        mode="lines",
        name="Равномерное использование",
        line=dict(color=theme.guide, width=2, dash="dash"),
        hovertemplate="Равномерно: %{y:.0%}<extra></extra>",
    )
    figure.add_scatter(
        x=data["users"],
        y=data["dialogues"],
        mode="lines",
        name="Фактическое",
        line=dict(color=theme.series[0], width=2),
        fill="tonexty",
        fillcolor="rgba(42,120,214,0.10)",
        customdata=data["label"],
        hovertemplate=(
            "Нижние %{x:.0%} пользователей<br>дают %{y:.0%} диалогов<extra></extra>"
        ),
    )
    figure.add_annotation(
        x=0.02, y=0.97, xref="paper", yref="paper", showarrow=False, align="left",
        text=f"Джини {gini:.2f} — чем ближе к 0, тем ровнее распределено",
        font=dict(color=theme.muted, size=12),
    )
    figure.update_xaxes(title_text="Доля пользователей, от наименее активных", tickformat=".0%")
    figure.update_yaxes(title_text="Накопленная доля диалогов", tickformat=".0%",
                        showgrid=True, gridcolor=theme.grid)
    return _base(figure, theme)


def hourly_profile(data: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart B — dialogues by hour of day.

    Drawn as a load profile and titled as one. The export covers a single date,
    so a date axis would be one point; the hour axis is the only time structure
    the data actually contains, and it is the one that sizes capacity.
    """

    if data.empty:
        return _empty(theme)
    active = data[data["count"] > 0]
    peak = int(active["count"].max()) if not active.empty else 0
    figure = go.Figure(
        go.Bar(
            x=[f"{hour:02d}" for hour in data["hour"]],
            y=data["count"],
            marker=dict(
                # The peak hour is the one the reader acts on, so it keeps the
                # series hue and the rest recede. This is emphasis, not a
                # second category: no legend entry is created for it.
                color=[theme.series[0] if value == peak and peak else theme.dim
                       for value in data["count"]],
                line=dict(color=theme.surface, width=2),
            ),
            hovertemplate="<b>%{x}:00 UTC</b><br>Диалогов: %{y}<extra></extra>",
        )
    )
    figure.update_xaxes(title_text="Час суток, UTC")
    figure.update_yaxes(title_text="Диалогов")
    return _base(figure, theme)


def automation_bubbles(data: pd.DataFrame, theme: Theme) -> go.Figure:
    """Chart C — where automation should start.

    Volume on one axis, median requested steps on the other, bubble area for
    the dialogue count and the automation share written on each bubble. A
    heatmap was rejected here: with four live cells the colour channel would
    carry the whole message and small cells would look like large ones, whereas
    area makes the size of each pocket of work legible directly.
    """

    if data.empty:
        return _empty(theme)
    company = {True: "с корпданными", False: "без корпданных"}
    figure = go.Figure()
    for flag, colour in ((True, theme.series[0]), (False, theme.series[1])):
        subset = data[data["uses_company_data"] == flag]
        if subset.empty:
            continue
        figure.add_scatter(
            x=subset["volume"],
            y=subset["automation"],
            mode="markers+text",
            name=company[flag],
            text=labels.show_all(subset["complexity"], "complexity"),
            textposition="top center",
            textfont=dict(color=theme.text_secondary, size=LABEL_SIZE),
            marker=dict(
                color=colour,
                size=subset["volume"],
                sizemode="area",
                sizeref=max(data["volume"]) / 55**2,
                sizemin=10,
                line=dict(color=theme.surface, width=2),
            ),
            customdata=list(zip(
                labels.show_all(subset["complexity"], "complexity"),
                [company[flag]] * len(subset),
                subset["steps"],
            )),
            hovertemplate=(
                "<b>%{customdata[0]}, %{customdata[1]}</b><br>Диалогов: %{x}"
                "<br>Кандидатов на автоматизацию: %{y:.0%}"
                "<br>Шагов в запросе, медиана: %{customdata[2]:.0f}<extra></extra>"
            ),
        )
    figure.update_xaxes(
        title_text="Диалогов в группе",
        showgrid=True,
        gridcolor=theme.grid,
        # Bubbles are sized in pixels, so a range ending at the largest value
        # clips the widest circle and the label above it. The padding is a
        # share of the span rather than a constant, so it holds under filtering.
        range=_padded(data["volume"], 0.30),
    )
    figure.update_yaxes(
        title_text="Доля кандидатов на автоматизацию",
        tickformat=".0%",
        range=_padded(data["automation"], 0.45, top_share=0.70),
    )
    return _base(figure, theme)


def economics_curve(
    data: pd.DataFrame,
    theme: Theme,
    threshold: float,
    tco_rub: float,
    assumed_minutes: float | None = None,
    assumed_fte: float | None = None,
) -> go.Figure:
    """Chart D — benefit against cost, over the assumption nobody can measure.

    A single ROI number was rejected. Value of time saved is the product of a
    measured volume and an assumed minutes-per-request, and quoting one figure
    buries the assumption inside it. Putting the assumption on the x-axis makes
    the shape of the argument visible: cost is flat, benefit is a ray from the
    origin, and the only question left for the room is which point on that ray
    they believe. The crossing is the break-even card's own number.
    """

    if data.empty:
        return _empty(theme, 380)
    figure = go.Figure()
    figure.add_scatter(
        x=data["minutes"],
        y=data["cost"],
        mode="lines",
        name="Затраты, A",
        line=dict(color=theme.series[1], width=2),
        hovertemplate="Затраты: %{y:,.0f} ₽/мес<extra></extra>",
    )
    figure.add_scatter(
        x=data["minutes"],
        y=data["benefit"],
        mode="lines",
        name="Выгода, B",
        line=dict(color=theme.series[0], width=2),
        hovertemplate=(
            "При %{x:.1f} мин на запрос<br>выгода: %{y:,.0f} ₽/мес<extra></extra>"
        ),
    )
    figure.add_vline(x=threshold, line=dict(color=theme.guide, width=2, dash="dash"))
    figure.add_annotation(
        x=threshold,
        y=1.0,
        yref="paper",
        yanchor="top",
        xanchor="left",
        showarrow=False,
        align="left",
        text=f"  безубыточность: {threshold:.1f} мин/запрос<br>"
             f"  правее — B больше A",
        font=dict(color=theme.text_secondary, size=LABEL_SIZE),
    )
    if assumed_minutes is not None:
        nearest = data.iloc[(data["minutes"] - assumed_minutes).abs().argsort()[:1]]
        if not nearest.empty:
            benefit = float(nearest["benefit"].iloc[0])
            figure.add_scatter(
                x=[assumed_minutes],
                y=[benefit],
                mode="markers",
                name="Выбранное допущение",
                marker=dict(
                    color=theme.series[0],
                    size=11,
                    line=dict(color=theme.surface, width=2),
                ),
                hovertemplate=(
                    f"<b>{assumed_minutes:g} мин на запрос</b><br>"
                    f"Высвобождено: {assumed_fte or 0:.2f} FTE/мес"
                    "<br>Оценка выгоды: %{y:,.0f} ₽/мес<extra></extra>"
                ),
            )
    figure.update_xaxes(title_text="Допущение: минут экономии на один запрос")
    figure.update_yaxes(
        title_text="₽ в месяц", showgrid=True, gridcolor=theme.grid, tickformat=",.0f"
    )
    figure.update_layout(separators=", ")
    return _base(figure, theme, height=380)
