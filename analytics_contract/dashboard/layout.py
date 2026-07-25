"""Page structure.

The page is four panels behind a tab bar, under one shared control plane:
provenance strip, filters, active-filter chips, result count. Filters sit above
the tabs because they are global — switching a tab must never quietly change
what is being counted.

All four panels are always in the DOM and are hidden with `display: none`
rather than being built by a callback. That keeps every chart id present at all
times, so a callback can write to a chart on a tab nobody is looking at, and
switching tabs costs no recompute.
"""

from __future__ import annotations

import pandas as pd
from dash import dash_table, dcc, html

from analytics_contract.dashboard import filters as filters_module, labels
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
    "automation_candidate": "Автоматизация",
    "integrations": "Интеграции",
    "tools": "Инструменты",
    "agent_failed": "Сбой",
    "failure_reason": "Причина сбоя",
    "estimated_cost": "Стоимость, у.е.",
}

#: Widths measured against the demo data and summing to about 1350px, which is
#: the card's inner width at 1440. `summary` gets the room to wrap; the table
#: scrolls sideways below that width rather than squeezing every column.
DRILLDOWN_WIDTHS = {
    "request_id": 54,
    "class_names": 132,
    "use_case": 126,
    "summary": 180,
    # A one-word header cannot wrap, so these two are sized by their caption
    # rather than by their values.
    "confidence": 100,
    "complexity": 86,
    "automation_candidate": 124,
    "integrations": 124,
    "tools": 124,
    "agent_failed": 62,
    "failure_reason": 140,
    "estimated_cost": 92,
}

TABS = (
    ("overview", "Обзор"),
    ("scenarios", "Сценарии и автоматизация"),
    ("reliability", "Надёжность, стоимость и риски"),
    ("records", "Записи"),
)

FONT_STACK = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _info(text: str) -> html.Span:
    """Hover note carrying a formula and its caveats.

    A number on a projector cannot be questioned out loud, so the answer to
    "where is that from?" travels with it.
    """

    return html.Span(
        "?",
        className="info",
        tabIndex="0",
        **{"data-tip": text, "aria-label": text},
    )


def _card_head(title: str, tip: str = "") -> html.Div:
    children = [html.H3(title, className="card-title")]
    if tip:
        children.append(_info(tip))
    return html.Div(children, className="card-head")


# --------------------------------------------------------------------------
# header and provenance
# --------------------------------------------------------------------------


def provenance_strip(counts: dict | None) -> html.Div:
    """Where the numbers came from, stated before any number is shown.

    The DEMO badge alone says "do not trust this". The chain says something
    more useful: we know exactly how many records went in, how many are on
    screen, and how many we dropped and why.
    """

    children = [
        html.Span("DEMO / SYNTHETIC DATA", className="banner-tag"),
        html.Span(
            "Данные синтетические. Частоты порождены генератором и не являются "
            "наблюдаемым спросом.",
            className="provenance-text",
        ),
    ]
    if counts:
        children.append(
            html.Div(
                [
                    html.Span("Загружено на вход:", className="provenance-arrow"),
                    html.B(f"{counts['input_rows']}"),
                    html.Span("→", className="provenance-arrow"),
                    html.Span("в отчёте:"),
                    html.B(f"{counts['exported_rows']}"),
                    html.Span("→", className="provenance-arrow"),
                    html.Span("отброшено из-за сбоя pipeline:"),
                    html.B(f"{counts['error_rows']}"),
                    _info(
                        "Строки, на которых упал наш аналитический pipeline, "
                        "исключены из отчёта и записаны в "
                        "outputs/pipeline_errors.csv.\n\n"
                        "Они не помечены agent_failed: отказ разбора — это отказ "
                        "нашего инструмента, а не отказ агента."
                    ),
                ],
                className="provenance-chain",
            )
        )
    return html.Div(children, className="provenance")


# --------------------------------------------------------------------------
# KPI
# --------------------------------------------------------------------------


def kpi_row(cards: list[Kpi]) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(card.label, className="kpi-label"),
                            _info(card.tooltip) if card.tooltip else None,
                        ],
                        className="kpi-head",
                    ),
                    html.Div(
                        [
                            html.Span(card.value),
                            html.Span(card.unit, className="kpi-unit") if card.unit else None,
                        ],
                        className="kpi-value",
                    ),
                    html.Div(card.detail, className="kpi-detail"),
                ],
                className="kpi-card",
            )
            for card in cards
        ],
        className="kpi-row",
    )


# --------------------------------------------------------------------------
# filters
# --------------------------------------------------------------------------


def _control(frame: pd.DataFrame, spec) -> html.Div:
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
    return html.Div(
        [html.Label(spec.label, className="filter-label"), control],
        className="filter-cell",
    )


def filter_bar(frame: pd.DataFrame) -> html.Div:
    return html.Div(
        [
            html.Div(
                [_control(frame, spec) for spec in filters_module.PRIMARY],
                className="filter-grid",
            ),
            html.Details(
                [
                    html.Summary(
                        f"Дополнительные фильтры ({len(filters_module.SECONDARY)})"
                    ),
                    html.Div(
                        [_control(frame, spec) for spec in filters_module.SECONDARY],
                        className="filter-grid",
                    ),
                ],
                className="filter-more",
            ),
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


# --------------------------------------------------------------------------
# panels
# --------------------------------------------------------------------------


def _graph(chart_id: str) -> dcc.Graph:
    return dcc.Graph(id=chart_id, config={"displayModeBar": False})


def _chart_card(chart_id, title, subtitle, tip="", extra=None, wide=False) -> html.Div:
    body = [_card_head(title, tip), html.P(subtitle, className="card-subtitle")]
    if extra is not None:
        body.append(extra)
    body.append(_graph(chart_id))
    return html.Div(body, className="card" + (" card-full" if wide else ""))


def overview_panel() -> html.Div:
    return html.Div(
        [
            html.Div(id="kpi-container"),
            html.Div(
                [
                    _chart_card(
                        "chart-volume",
                        "Топ сценариев по объёму",
                        "Что запрашивают чаще всего. Клик по столбцу выбирает сценарий "
                        "и фильтрует вкладку «Записи».",
                        tip="Частота use_case среди отфильтрованных диалогов.\n\n"
                            "В режиме «Классы» считается по class_names — разметка "
                            "многозначная, поэтому доли в сумме дают больше 100%.",
                        extra=dcc.RadioItems(
                            id="volume-dimension",
                            options=[
                                {"label": " Сценарии", "value": "use_case"},
                                {"label": " Классы", "value": "class_names"},
                            ],
                            value="use_case",
                            inline=True,
                            className="card-toggle",
                        ),
                        wide=True,
                    )
                ],
                className="chart-grid",
            ),
        ],
        id="panel-overview",
    )


def scenarios_panel() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    _chart_card(
                        "chart-periodicity",
                        "Сценарий × заявленная периодичность",
                        "Повторяющиеся сценарии — первые кандидаты на автоматизацию.",
                        tip="Число диалогов в каждой паре «сценарий × periodicity».\n\n"
                            "Периодичность извлечена LLM из текста запроса, а не "
                            "измерена по журналу: это заявление пользователя.",
                        wide=True,
                    ),
                    _chart_card(
                        "chart-tokens",
                        "Разложение токенов по сложности",
                        "Во что обходится диалог в зависимости от сложности запроса.",
                        tip="Среднее число токенов на диалог по ролям, в разрезе "
                            "complexity.\n\n"
                            "Столбец «Инструменты» всегда нулевой: в исходных логах нет "
                            "сообщений с ролью tool. Это отсутствие данных, а не "
                            "бесплатные вызовы инструментов.",
                        wide=True,
                    ),
                ],
                className="chart-grid",
            )
        ],
        id="panel-scenarios",
    )


def reliability_panel() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    _chart_card(
                        "chart-failure",
                        "Объём против доли сбоев",
                        "Размер точки — суммарная стоимость сценария.",
                        tip="По оси X — число диалогов сценария, по оси Y — доля "
                            "диалогов с agent_failed.\n\n"
                            "Показаны только сценарии от 5 диалогов: доля по двум "
                            "строкам равна 0% или 100% и ничего не значит.",
                    ),
                    _chart_card(
                        "chart-reliability",
                        "Доля диалогов со сбоем при использовании",
                        "Совместная встречаемость, а не установленная причина сбоя.",
                        tip="Доля диалогов с agent_failed среди тех, где инструмент "
                            "или интеграция использовались. Усы — 95% интервал "
                            "Уилсона.\n\n"
                            "В контракте нет событий отдельных вызовов, поэтому сбой "
                            "отнесён ко всем инструментам диалога. Это верхняя оценка "
                            "совместной встречаемости, а не вина инструмента.",
                        extra=dcc.RadioItems(
                            id="reliability-dimension",
                            options=[
                                {"label": " Инструменты", "value": "tools"},
                                {"label": " Интеграции", "value": "integrations"},
                            ],
                            value="tools",
                            inline=True,
                            className="card-toggle",
                        ),
                    ),
                    _chart_card(
                        "chart-cost",
                        "Парето расходов по сценариям",
                        "Столбцы — доля сценария, линия — накопленная доля. Пересечение "
                        "линии с отметкой 80% даёт набор сценариев, который стоит "
                        "оптимизировать первым.",
                        tip="estimated_cost сценария ÷ общая стоимость; линия — "
                            "кумулятивная сумма долей.\n\n"
                            "Обе величины — доли одного и того же итога, поэтому у "
                            "диаграммы одна ось. Второй оси Y здесь нет намеренно.",
                        wide=True,
                    ),
                    _chart_card(
                        "chart-security",
                        "Индикаторы риска данных по сценариям",
                        "Где встречаются чувствительные данные, корпоративные источники "
                        "и признаки prompt injection.",
                        tip="Доля диалогов сценария с каждым признаком.\n\n"
                            "Фиксируется обнаружение признака, а не успешность атаки и "
                            "не факт утечки за периметр.",
                        wide=True,
                    ),
                ],
                className="chart-grid",
            )
        ],
        id="panel-reliability",
    )


def records_panel(limitations: list[str]) -> html.Div:
    return html.Div(
        [
            html.Div([drilldown_table(), limitations_panel(limitations)], className="chart-grid")
        ],
        id="panel-records",
    )


# --------------------------------------------------------------------------
# table
# --------------------------------------------------------------------------


def drilldown_table() -> html.Div:
    return html.Div(
        [
            _card_head(
                "Записи",
                "Строки, оставшиеся после фильтров и выбранного на диаграмме "
                "сценария.\n\nСортировка — по клику на заголовок колонки.",
            ),
            html.P(
                "Колонка «Резюме диалога» — производный текст, а не исходный запрос "
                "пользователя: контракт его не содержит.",
                className="card-subtitle",
            ),
            dash_table.DataTable(
                id="drilldown",
                columns=[
                    {"name": DRILLDOWN_LABELS[column], "id": column}
                    for column in DRILLDOWN_COLUMNS
                ],
                page_size=12,
                page_action="native",
                sort_action="native",
                style_as_list_view=True,
                # The header stays put while the body scrolls, so a jury never
                # sees a column of values with no idea what they are.
                fixed_rows={"headers": True},
                style_table={"overflowX": "auto", "height": "560px", "overflowY": "auto"},
                # Colours come from the theme's custom properties, which
                # inherit down from #viz-root. That is why the table follows
                # the theme toggle without a callback of its own.
                style_header={
                    "backgroundColor": "var(--surface-2)",
                    "color": "var(--text-primary)",
                    "fontWeight": "600",
                    "fontSize": "12.5px",
                    "textAlign": "left",
                    "padding": "9px 10px",
                    "border": "none",
                    "borderBottom": "1px solid var(--border-strong)",
                    "whiteSpace": "normal",
                    "height": "auto",
                },
                style_data={
                    "backgroundColor": "var(--surface-1)",
                    "color": "var(--text-primary)",
                    "border": "none",
                    "borderBottom": "1px solid var(--border)",
                },
                style_cell={
                    "fontFamily": FONT_STACK,
                    "fontSize": "13px",
                    "textAlign": "left",
                    "padding": "9px 10px",
                    "whiteSpace": "normal",
                    "height": "auto",
                    "lineHeight": "1.42",
                    "verticalAlign": "top",
                },
                style_cell_conditional=[
                    {
                        "if": {"column_id": column},
                        "width": f"{width}px",
                        "minWidth": f"{width}px",
                        "maxWidth": f"{width}px",
                    }
                    for column, width in DRILLDOWN_WIDTHS.items()
                ]
                + [
                    {
                        "if": {"column_id": column},
                        "textAlign": "right",
                        "fontVariantNumeric": "tabular-nums",
                    }
                    for column in ("confidence", "estimated_cost")
                ],
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "var(--surface-2)"},
                    {
                        "if": {"filter_query": '{agent_failed} = "да"', "column_id": "agent_failed"},
                        "color": "var(--warning)",
                        "fontWeight": "600",
                    },
                ],
            ),
        ],
        className="card card-full records",
    )


def limitations_panel(items: list[str]) -> html.Div:
    return html.Div(
        [
            _card_head("Ограничения данных"),
            html.P(
                "Что эти цифры не показывают. Список формирует валидатор контракта, "
                "а не автор дашборда.",
                className="card-subtitle",
            ),
            html.Ul(
                [html.Li(labels.limitation(item)) for item in items],
                className="limitations",
            ),
        ],
        className="card card-full",
    )


# --------------------------------------------------------------------------
# page
# --------------------------------------------------------------------------


def build(
    frame: pd.DataFrame,
    cards: list[Kpi],
    limitations: list[str],
    theme: Theme,
    counts: dict | None = None,
) -> html.Div:
    return html.Div(
        [
            dcc.Store(id="theme-store", data=theme.name),
            # Selection is a soft filter: it narrows the Records tab and
            # highlights the matching mark, but leaves the charts showing the
            # whole filtered set so the part stays visible in its context.
            dcc.Store(id="selection-store", data=None),
            html.Header(
                [
                    html.Div(
                        [
                            html.H1("Prompt Radar", className="app-title"),
                            html.P(
                                "Аналитика запросов к корпоративным ИИ-агентам",
                                className="app-subtitle",
                            ),
                        ]
                    ),
                    html.Div(
                        [html.Button("Сменить тему", id="theme-toggle", className="ghost-button")],
                        className="header-actions",
                    ),
                ],
                className="app-header",
            ),
            provenance_strip(counts),
            filter_bar(frame),
            # Both live in the initial layout so their callbacks resolve
            # without switching on suppress_callback_exceptions, which would
            # also hide real wiring mistakes.
            html.Div(
                [
                    html.Button(
                        id="clear-selection",
                        className="chip-selection",
                        title="Снять выбор",
                        style={"display": "none"},
                    ),
                    html.Div(id="filter-chips", className="chip-list"),
                ],
                className="chip-row",
            ),
            html.Div(id="result-count", className="result-count"),
            dcc.Tabs(
                id="tabs",
                value="overview",
                children=[
                    dcc.Tab(
                        label=label,
                        value=value,
                        className="tab",
                        selected_className="tab--selected",
                    )
                    for value, label in TABS
                ],
                parent_className="tabs-bar",
                className="tabs-inner",
            ),
            html.Div(
                [
                    overview_panel(),
                    scenarios_panel(),
                    reliability_panel(),
                    records_panel(limitations),
                ],
                className="tab-content",
            ),
        ],
        className=f"viz-root theme-{theme.name}",
        id="viz-root",
    )
