"""Page structure: banner, KPI row, filter bar, chart grid, drill-down table."""

from __future__ import annotations

import pandas as pd
from dash import dash_table, dcc, html

from analytics_contract.dashboard import filters as filters_module
from analytics_contract.dashboard.metrics import Kpi
from analytics_contract.dashboard.theme import Theme
from analytics_contract.schema import DRILLDOWN_COLUMNS

#: Column headers for the drill-down table. `summary` is deliberately labelled
#: as a summary: the contract carries no verbatim request text.
DRILLDOWN_LABELS = {
    "request_id": "ID",
    "class_names": "Классы",
    "use_case": "Сценарий",
    "summary": "Резюме диалога",
    "confidence": "Уверенность",
    "complexity": "Сложность",
    "automation_candidate": "Автоматизируем",
    "integrations": "Интеграции",
    "tools": "Инструменты",
    "agent_failed": "Сбой",
    "failure_reason": "Причина сбоя",
    "estimated_cost": "Стоимость",
}

CHART_CARDS = [
    ("chart-volume", "Топ сценариев по объёму", "Что используют чаще всего"),
    ("chart-periodicity", "Сценарий × периодичность", "Какие сценарии подходят для автоматизации"),
    ("chart-failure", "Объём против доли сбоев", "Где агент чаще ломается; размер точки — стоимость"),
    ("chart-reliability", "Надёжность инструментов и интеграций",
     "Доля сбоев с интервалом Уилсона. Сбой отнесён ко всем инструментам диалога — это верхняя оценка вины"),
    ("chart-cost", "Парето расходов по сценариям", "Куда уходит стоимость обработки"),
    ("chart-tokens", "Разложение токенов по сложности",
     "Инструменты дают 0: в исходных логах нет сообщений с ролью tool"),
    ("chart-security", "Риски данных по сценариям", "Где чувствительные данные и prompt injection"),
]


def banner(theme: Theme) -> html.Div:
    return html.Div(
        [
            html.Span("DEMO / SYNTHETIC DATA", className="banner-tag"),
            html.Span(
                "Данные синтетические. Частоты порождены генератором и не являются "
                "наблюдаемым спросом.",
                className="banner-text",
            ),
        ],
        className="banner",
    )


def kpi_row(cards: list[Kpi]) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(card.label, className="kpi-label"),
                    html.Div(card.value, className="kpi-value"),
                    html.Div(card.detail, className="kpi-detail"),
                    html.Div(card.note, className="kpi-note") if card.note else None,
                ],
                className="kpi-card",
            )
            for card in cards
        ],
        className="kpi-row",
    )


def filter_bar(frame: pd.DataFrame) -> html.Div:
    controls = []
    for spec in filters_module.FILTERS:
        options = filters_module.options_for(frame, spec)
        if spec.kind == "bool":
            control = dcc.Dropdown(
                id={"type": "filter", "key": spec.key},
                options=options,
                value=filters_module.ANY,
                clearable=False,
                className="filter-input",
            )
        else:
            control = dcc.Dropdown(
                id={"type": "filter", "key": spec.key},
                options=options,
                multi=True,
                placeholder="Все",
                className="filter-input",
            )
        controls.append(
            html.Div([html.Label(spec.label, className="filter-label"), control],
                     className="filter-cell")
        )
    return html.Div(
        [
            html.Div(controls, className="filter-grid"),
            html.Div(
                [
                    html.Button("Сбросить фильтры", id="reset-filters", className="ghost-button"),
                    html.Button("Экспорт CSV", id="export-button", className="ghost-button"),
                    dcc.Download(id="download-csv"),
                ],
                className="filter-actions",
            ),
        ],
        className="filter-bar",
    )


def chart_grid() -> html.Div:
    cards = []
    for index, (chart_id, title, subtitle) in enumerate(CHART_CARDS):
        header = [html.H3(title, className="card-title"),
                  html.P(subtitle, className="card-subtitle")]
        if chart_id == "chart-volume":
            header.append(
                dcc.RadioItems(
                    id="volume-dimension",
                    options=[{"label": " Сценарии", "value": "use_case"},
                             {"label": " Классы", "value": "class_names"}],
                    value="use_case",
                    inline=True,
                    className="card-toggle",
                )
            )
        if chart_id == "chart-reliability":
            header.append(
                dcc.RadioItems(
                    id="reliability-dimension",
                    options=[{"label": " Инструменты", "value": "tools"},
                             {"label": " Интеграции", "value": "integrations"}],
                    value="tools",
                    inline=True,
                    className="card-toggle",
                )
            )
        cards.append(
            html.Div(
                header + [dcc.Graph(id=chart_id, config={"displayModeBar": False})],
                className="card" + (" card-wide" if index in (0, 1) else ""),
            )
        )
    return html.Div(cards, className="chart-grid")


def drilldown_table() -> html.Div:
    return html.Div(
        [
            html.H3("Записи", className="card-title"),
            html.P(
                "Колонка «Резюме диалога» — производный текст, а не исходный запрос "
                "пользователя: контракт его не содержит.",
                className="card-subtitle",
            ),
            dash_table.DataTable(
                id="drilldown",
                columns=[{"name": DRILLDOWN_LABELS[column], "id": column}
                         for column in DRILLDOWN_COLUMNS],
                page_size=15,
                sort_action="native",
                style_as_list_view=True,
                style_table={"overflowX": "auto"},
                style_cell={
                    "fontFamily": 'system-ui, -apple-system, "Segoe UI", sans-serif',
                    "fontSize": "12px",
                    "textAlign": "left",
                    "padding": "8px 10px",
                    "maxWidth": "260px",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                },
            ),
        ],
        className="card card-full",
    )


def limitations_panel(items: list[str]) -> html.Div:
    return html.Div(
        [
            html.H3("Ограничения данных", className="card-title"),
            html.Ul([html.Li(item) for item in items], className="limitations"),
        ],
        className="card card-full",
    )


def build(frame: pd.DataFrame, cards: list[Kpi], limitations: list[str], theme: Theme) -> html.Div:
    return html.Div(
        [
            dcc.Store(id="theme-store", data=theme.name),
            html.Header(
                [
                    html.Div(
                        [
                            html.H1("Prompt Radar", className="app-title"),
                            html.P("Аналитика запросов к корпоративным ИИ-агентам",
                                   className="app-subtitle"),
                        ]
                    ),
                    html.Button("Тема", id="theme-toggle", className="ghost-button"),
                ],
                className="app-header",
            ),
            banner(theme),
            html.Div(id="kpi-container", children=kpi_row(cards)),
            filter_bar(frame),
            html.Div(id="result-count", className="result-count"),
            chart_grid(),
            drilldown_table(),
            limitations_panel(limitations),
        ],
        className="viz-root",
        id="viz-root",
    )
