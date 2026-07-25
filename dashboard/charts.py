"""Plotly figures for the dashboard.

Two rules hold every chart together.

**Chrome is removed until only the data is left.** No plot frames, no legends
where a direct label will do, no axis where the value is written on the mark.
What remains is a hairline grid and mono tick labels, which is what makes the
figures look like part of the page instead of a library's default output.

**One amber mark per chart.** Amber is the answer: the biggest spender, the
peak hour, the actionable quadrant, the candidates. Everything else is steel or
dim. A chart where two things are bright is a chart with no point.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import Theme

BODY = '"Golos Text", system-ui, sans-serif'
MONO = '"JetBrains Mono", "SFMono-Regular", Menlo, monospace'


def _base(figure: go.Figure, theme: Theme, *, height: int = 300) -> go.Figure:
    figure.update_layout(
        height=height,
        margin=dict(l=8, r=14, t=10, b=26),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme.text_secondary, family=BODY, size=12),
        showlegend=False,
        bargap=0.42,
        hoverlabel=dict(
            bgcolor=theme.raised,
            font_color=theme.text_primary,
            font_family=BODY,
            bordercolor=theme.guide,
        ),
    )
    axis = dict(
        showline=False,
        zeroline=False,
        gridcolor=theme.grid,
        tickfont=dict(color=theme.muted, family=MONO, size=10),
        title_font=dict(color=theme.muted, family=MONO, size=9),
    )
    figure.update_xaxes(**axis)
    figure.update_yaxes(**axis)
    return figure


def empty(theme: Theme, height: int = 300, text: str = "нет данных для выбранного фильтра") -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=text.upper(),
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(color=theme.muted, family=MONO, size=10),
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return _base(figure, theme, height=height)


def _is_empty(data: pd.DataFrame, column: str) -> bool:
    return data is None or data.empty or column not in data or data[column].sum() == 0


def _short(labels: pd.Series, limit: int = 32) -> pd.Series:
    """Trim long categories and keep them unique.

    A failure_reason can be a whole sentence; left whole it eats the plotting
    area, and two bars sharing a trimmed label would be drawn on the same row.
    """

    trimmed = labels.astype(str).map(lambda text: text if len(text) <= limit else text[: limit - 1] + "…")
    if trimmed.duplicated().any():
        collisions = trimmed.duplicated(keep=False)
        trimmed = trimmed.where(
            ~collisions, trimmed + " " + trimmed.groupby(trimmed).cumcount().add(1).astype(str)
        )
    return trimmed


def usage_bar(
    data: pd.DataFrame,
    theme: Theme,
    metric: str,
    selected: str | None = None,
) -> go.Figure:
    """Top users by dialogues or by consumed tokens."""

    if _is_empty(data, metric):
        return empty(theme, height=330)
    ordered = data.sort_values(metric, ascending=True)
    peak = ordered[metric].max()
    colors = []
    for key, value in zip(ordered["key"], ordered[metric]):
        if selected is not None:
            colors.append(theme.signal if key == selected else theme.dim)
        else:
            colors.append(theme.signal if value == peak else theme.series[0])
    unit = "диалогов" if metric == "dialogues" else "токенов"
    figure = go.Figure(
        go.Bar(
            x=ordered[metric],
            y=ordered["key"],
            orientation="h",
            marker=dict(color=colors),
            text=ordered[metric].map(lambda value: f"{value:,.0f}".replace(",", " ")),
            textposition="outside",
            textfont=dict(color=theme.muted, family=MONO, size=10),
            cliponaxis=False,
            customdata=ordered[["key"]],
            hovertemplate=f"%{{y}}<br>%{{x:,.0f}} {unit}<extra></extra>",
        )
    )
    figure.update_xaxes(visible=False, range=[0, float(peak) * 1.16])
    figure.update_yaxes(title_text="", tickfont=dict(color=theme.text_secondary, family=MONO, size=10))
    return _base(figure, theme, height=max(320, 25 * len(ordered) + 60))


def hourly_profile(data: pd.DataFrame, theme: Theme, metric: str) -> go.Figure:
    """Load by UTC hour: a profile of the available period, not a trend."""

    if _is_empty(data, metric):
        return empty(theme, height=330)
    values = data[metric]
    peak = float(values.max())
    figure = go.Figure(
        go.Bar(
            x=[f"{hour:02d}" for hour in data["hour"]],
            y=values,
            marker=dict(color=[theme.signal if value == peak else theme.dim for value in values]),
            hovertemplate="%{x}:00 UTC<br>%{y:,.0f}<extra></extra>",
        )
    )
    figure.update_xaxes(title_text="ЧАС UTC", dtick=3, showgrid=False)
    figure.update_yaxes(title_text="", showgrid=True, rangemode="tozero")
    return _base(figure, theme, height=330)


def ranked_bar(
    data: pd.DataFrame,
    theme: Theme,
    *,
    label: str = "key",
    value: str = "dialogs",
    limit: int = 12,
    color: str | None = None,
    highlight: str | None = None,
    unit: str = "диалогов",
    divisor: int = 1,
    axis_title: str | None = None,
    height: int | None = None,
) -> go.Figure:
    """A ranked horizontal bar with the value written at the end of each bar.

    The axis is dropped entirely: with the number on the mark, a scale would
    only repeat it. ``divisor`` rescales the printed value — token totals shown
    raw read as «0.2M», which is neither Russian nor legible across a room.
    """

    del axis_title  # the axis is gone; the unit lives in the hover
    if _is_empty(data, value):
        return empty(theme, height=height or 280)
    ordered = data.head(limit).sort_values(value, ascending=True)
    raw = ordered[value]
    scaled = raw / divisor
    top = float(scaled.max())
    accent = color or theme.series[0]
    # The leader is the answer, so it takes the signal — unless the caller
    # already owns the meaning of the colour, as failures own alarm red.
    lead = highlight or theme.signal
    colors = [lead if value_ == top else accent for value_ in scaled]
    suffix = " тыс." if divisor == 1000 else ""
    figure = go.Figure(
        go.Bar(
            x=scaled,
            y=_short(ordered[label]),
            orientation="h",
            marker=dict(color=colors),
            text=[f"{value_:,.0f}{suffix}".replace(",", " ") for value_ in scaled],
            textposition="outside",
            textfont=dict(color=theme.muted, family=MONO, size=10),
            cliponaxis=False,
            # The hover always states the measured value, never the rescaled one.
            customdata=list(zip(ordered[label].astype(str), raw)),
            hovertemplate=f"%{{customdata[0]}}<br>%{{customdata[1]:,.0f}} {unit}<extra></extra>",
        )
    )
    figure.update_xaxes(visible=False, range=[0, top * 1.2])
    figure.update_yaxes(
        title_text="",
        automargin=True,
        tickfont=dict(color=theme.text_secondary, family=MONO, size=10),
    )
    return _base(figure, theme, height=height or max(240, 24 * len(ordered) + 54))


def stacked_pair(
    theme: Theme,
    *,
    left_label: str,
    left_value: float,
    right_label: str,
    right_value: float,
    unit: str = "сообщений",
    height: int = 130,
) -> go.Figure:
    """One bar split in two parts — useful against useless."""

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
            text=[f"{name} {amount:,.0f}".replace(",", " ")],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color=theme.page if color != theme.dim else theme.text_primary,
                          family=MONO, size=11),
            hovertemplate=f"{name}<br>%{{x:,.0f}} {unit}<extra></extra>",
        )
    figure.update_layout(barmode="stack", bargap=0.5)
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return _base(figure, theme, height=height)


def scenario_scatter(data: pd.DataFrame, theme: Theme, height: int = 400) -> go.Figure:
    """The automation map: how often a scenario happens against how ready it is.

    Median lines cut the plane into quadrants. Only the upper-right one is
    amber — frequent scenarios the analysis already marked as automatable —
    because that quadrant is the whole point of the chart.
    """

    if data is None or data.empty:
        return empty(theme, height=height)

    x_median = float(data["share"].median())
    y_median = float(data["automation_share"].median())
    actionable = (data["share"] >= x_median) & (data["automation_share"] >= y_median)

    figure = go.Figure()
    for value, orientation in ((x_median, "v"), (y_median, "h")):
        line = dict(color=theme.guide, width=1, dash="dot")
        if orientation == "v":
            figure.add_vline(x=value, line=line)
        else:
            figure.add_hline(y=value, line=line)

    for mask, color, size in ((~actionable, theme.series[0], 13), (actionable, theme.signal, 19)):
        subset = data[mask]
        if subset.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=subset["share"],
                y=subset["automation_share"],
                mode="markers+text" if color == theme.signal else "markers",
                text=subset["label"],
                textposition="middle right",
                textfont=dict(color=theme.text_primary, family=MONO, size=10.5),
                cliponaxis=False,
                marker=dict(color=color, size=size, line=dict(color=theme.surface, width=2)),
                customdata=subset[["label", "dialogs", "automation_share", "simple_share", "avg_tokens"]],
                hovertemplate=(
                    "%{customdata[0]}<br>"
                    "%{customdata[1]} диалогов · %{x:.1f} % выгрузки<br>"
                    "кандидатов на автоматизацию: %{customdata[2]:.0f} %<br>"
                    "простых: %{customdata[3]:.0f} % · в среднем %{customdata[4]:,.0f} токенов"
                    "<extra></extra>"
                ),
            )
        )
    figure.add_annotation(
        x=1, y=1.07, xref="paper", yref="paper", xanchor="right", showarrow=False,
        text="ЧАСТЫЕ И ГОТОВЫЕ К АВТОМАТИЗАЦИИ →",
        font=dict(color=theme.signal, family=MONO, size=9.5),
    )
    # Labels sit to the right of their marks, so the axis keeps room for the
    # longest of them instead of letting it run off the panel.
    figure.update_xaxes(
        title_text="ДОЛЯ ДИАЛОГОВ, %",
        showgrid=True,
        range=[0, float(data["share"].max()) * 1.55],
    )
    figure.update_yaxes(title_text="КАНДИДАТОВ, %", showgrid=True, rangemode="tozero")
    return _base(figure, theme, height=height)


def grouped_bar(
    data: pd.DataFrame,
    theme: Theme,
    *,
    left: tuple[str, str],
    right: tuple[str, str],
    height: int = 300,
) -> go.Figure:
    """Two series over the same categories, named on the marks themselves."""

    if data is None or data.empty or (data[left[0]].sum() + data[right[0]].sum()) == 0:
        return empty(theme, height=height)
    figure = go.Figure()
    for (column, name), color in ((left, theme.signal), (right, theme.dim)):
        figure.add_bar(
            x=data["key"],
            y=data[column],
            name=name,
            marker=dict(color=color),
            text=data[column],
            textposition="outside",
            textfont=dict(color=theme.muted, family=MONO, size=10),
            cliponaxis=False,
            hovertemplate=f"%{{x}} · {name}<br>%{{y:,.0f}} диалогов<extra></extra>",
        )
    figure.update_xaxes(title_text="", showgrid=False,
                        tickfont=dict(color=theme.text_secondary, family=MONO, size=10))
    figure.update_yaxes(visible=False, rangemode="tozero")
    figure = _base(figure, theme, height=height)
    # `_base` turns legends off for every other chart, so this one is switched
    # back on: two series over the same categories cannot be read without it.
    figure.update_layout(
        barmode="group",
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="top", y=-0.08, xanchor="left", x=0,
            font=dict(color=theme.muted, family=MONO, size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=8, r=14, t=18, b=44),
    )
    return figure


def breakeven_chart(economics: dict, theme: Theme, height: int = 340) -> go.Figure:
    """Затраты против выгоды, где по оси лежит то, чего в данных нет.

    Затраты — горизонтальная линия: они от экономии минут не зависят. Выгода —
    луч из нуля. Их пересечение и есть порог. Так вопрос «откуда вы взяли
    15 минут» превращается в «верите ли вы, что диалог экономит больше N» —
    и это вопрос к залу, а не к докладчику.
    """

    value_per_minute = economics["value_per_minute"]
    if value_per_minute <= 0:
        return empty(theme, height=height, text="нет запросов для расчёта")

    breakeven = economics["breakeven_minutes"]
    chosen = economics["minutes_saved"]
    limit = max(breakeven * 2, chosen * 1.35, 5)
    minutes = [limit * step / 40 for step in range(41)]
    benefit = [value_per_minute * minute for minute in minutes]
    tco = economics["tco_month"]

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=minutes, y=[tco] * len(minutes), mode="lines", name="Затраты",
            line=dict(color=theme.text_secondary, width=1.5, dash="dash"),
            hovertemplate="затраты %{y:,.0f} ₽/мес<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=minutes, y=benefit, mode="lines", name="Выгода",
            line=dict(color=theme.series[0], width=2.5),
            hovertemplate="при %{x:.1f} мин — выгода %{y:,.0f} ₽/мес<extra></extra>",
        )
    )
    figure.add_vline(
        x=breakeven,
        line=dict(color=theme.signal, width=1, dash="dot"),
        annotation_text=f"ПОРОГ {breakeven:.1f} МИН".replace(".", ","),
        annotation_position="top left",
        annotation_font=dict(color=theme.signal, family=MONO, size=10),
    )
    figure.add_trace(
        go.Scatter(
            x=[chosen], y=[economics["benefit_month"]], mode="markers",
            marker=dict(color=theme.signal, size=13, line=dict(color=theme.surface, width=2)),
            hovertemplate=(
                f"выбрано {chosen:.1f} мин".replace(".", ",")
                + "<br>выгода %{y:,.0f} ₽/мес<extra></extra>"
            ),
        )
    )
    # Both lines are named on the plot: a legend for two lines is one legend
    # too many, and on a projector a colour key is read last or not at all.
    figure.add_annotation(
        x=limit, y=tco, xanchor="right", yanchor="bottom", showarrow=False,
        text="ЗАТРАТЫ", font=dict(color=theme.muted, family=MONO, size=10),
    )
    figure.add_annotation(
        x=limit, y=value_per_minute * limit, xanchor="right", yanchor="top", showarrow=False,
        text="ВЫГОДА", font=dict(color=theme.series[0], family=MONO, size=10),
    )
    figure.update_xaxes(title_text="МИНУТ ЭКОНОМИИ НА ЗАПРОС", showgrid=True, rangemode="tozero")
    figure.update_yaxes(title_text="₽ В МЕСЯЦ", showgrid=True, rangemode="tozero", tickformat=",.0f")
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
        line=dict(color=theme.signal, width=1, dash="dot"),
        annotation_text=f"ПОРОГ {threshold}".replace(".", ","),
        annotation_position="top left",
        annotation_font=dict(color=theme.signal, family=MONO, size=9.5),
    )
    figure.update_xaxes(title_text="CONFIDENCE", showgrid=False, range=[0, 1.02])
    figure.update_yaxes(title_text="", showgrid=True)
    return _base(figure, theme, height=height)
