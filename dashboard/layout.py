"""Page composition: five questions, each answered by its charts.

The page is ordered by what a reader wants to know — where the money goes,
what to automate, where it breaks, who uses it, what it consists of — and not
by the order of metrics.md.

Each card states its formula in the `?` note next to the title: on a projector
a number without its definition is a claim, and a number with one is a
measurement.
"""

from __future__ import annotations

import pandas as pd
from dash import dash_table, dcc, html

from dashboard import filters as filters_module
from dashboard.metrics import Kpi
from dashboard.theme import Theme

TABLE_COLUMNS = (
    ("request_id", "Запрос", 130),
    ("user_id", "Пользователь", 140),
    ("created_at", "Время UTC", 165),
    ("first_user_message", "Первое сообщение", 340),
    ("use_case", "Сценарий", 190),
    ("complexity", "Сложность", 110),
    ("total_tokens", "Токены", 100),
    ("burned_tokens", "Сожжено", 100),
    ("confidence", "Уверенность", 115),
)


def info(text: str, at_end: bool = False) -> html.Span:
    return html.Span(
        "?",
        className="info info--end" if at_end else "info",
        tabIndex="0",
        **{"data-tip": text, "aria-label": text},
    )


def card_head(title: str, tip: str = "") -> html.Div:
    children: list = [html.H3(title, className="card-title")]
    if tip:
        children.append(info(tip))
    return html.Div(children, className="card-head")


def card(title: str, tip: str, subtitle: str, *children, className: str = "card") -> html.Div:
    body: list = [card_head(title, tip)]
    if subtitle:
        body.append(html.P(subtitle, className="card-subtitle"))
    body.extend(children)
    return html.Div(body, className=className)


def rail(mark: tuple[float, str] | None = None, className: str = "rail") -> html.Div:
    """The measurement rail: a hairline, a comb of ticks, one amber mark.

    ``mark`` places that mark at a position on the scale and labels it, so the
    rail states a value instead of decorating the page. Without a mark it is
    the section divider.
    """

    children = []
    if mark is not None:
        position, label = mark
        children.append(
            html.Span(
                className="rail-mark",
                style={"left": f"{max(0.0, min(100.0, position)):.2f}%"},
                **{"data-label": label},
            )
        )
    return html.Div(children, className=className)


def section(kicker: str, question: str, body: html.Div) -> html.Div:
    """A question and the charts that answer it."""

    return html.Div(
        [
            rail(className="rail section-rail"),
            html.Div(
                [
                    html.Span(kicker, className="section-kicker"),
                    html.H2(question, className="section-title"),
                ],
                className="section-heading",
            ),
            body,
        ],
        className="metric-section",
    )


def hero(headline: list, spend: list) -> html.Div:
    """The thesis of the page: one sentence and the split it comes from."""

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("главное", className="hero-tag"),
                            html.P(headline, id="hero-line", className="hero-line"),
                        ]
                    ),
                    html.Div(spend, id="hero-spend", className="spend"),
                ],
                className="hero-body",
            )
        ],
        className="hero",
    )


def spend_block(parts: list[dict]) -> list:
    """The token split drawn as one bar with the parts named under it."""

    if not parts:
        return [html.Div("нет расхода в выбранных строках", className="chip-none")]
    return [
        html.Div(
            [
                html.Div(
                    className=f"spend-part spend-part-{index}",
                    style={"flexGrow": part["share"] or 0.001},
                    title=f"{part['key']}: {part['value']}",
                )
                for index, part in enumerate(parts)
            ],
            className="spend-bar",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Span(part["key"], className="key"),
                        html.Span(part["percent"], className="val"),
                        html.Span(part["value"], className="sub"),
                    ],
                    className=f"spend-item spend-item-{index}",
                )
                for index, part in enumerate(parts)
            ],
            className="spend-legend",
        ),
    ]


def stat_strip(items: list[tuple[str, str]], element_id: str | None = None) -> html.Div:
    """A row of small supporting numbers under a chart."""

    children = [
        html.Div(
            [
                html.Span(value, className="stat-value"),
                html.Span(label, className="stat-label"),
            ],
            className="stat",
        )
        for label, value in items
    ]
    return html.Div(children, className="stat-strip", **({"id": element_id} if element_id else {}))


def warnings_strip(notes: list[str]) -> html.Div:
    """Only what is wrong with the export, and only when something is.

    A note here means a metric on the page is not measured at all, so it stays
    visible; when the export is clean the strip disappears entirely.
    """

    if not notes:
        return html.Div()
    return html.Div(
        [
            html.Span("В ВЫГРУЗКЕ", className="banner-tag"),
            html.Div(
                [html.Span(note, className="provenance-text") for note in notes],
                className="provenance-notes",
            ),
        ],
        className="provenance",
    )


def filter_bar(frame: pd.DataFrame) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Label(spec.label, className="filter-label"),
                            dcc.Dropdown(
                                id={"type": "filter", "key": spec.key},
                                options=filters_module.options_for(frame, spec),
                                multi=True,
                                placeholder=spec.placeholder,
                                className="filter-input",
                            ),
                        ],
                        className="filter-cell",
                    )
                    for spec in filters_module.FILTERS
                ],
                className="filter-grid",
            ),
            html.Div(
                [
                    dcc.Checklist(
                        id="flag-filters",
                        options=[
                            {"label": f" {spec.label}", "value": spec.key}
                            for spec in filters_module.FLAGS
                            if spec.key in frame
                        ],
                        value=[],
                        inline=True,
                        className="flag-check",
                    ),
                    html.Div(
                        [
                            html.Button("Сбросить", id="reset-filters", className="ghost-button"),
                            html.Button("Экспорт CSV", id="export-button", className="ghost-button"),
                            dcc.Download(id="download-csv"),
                        ],
                        className="filter-actions",
                    ),
                ],
                className="filter-footer",
            ),
        ],
        className="filter-bar",
    )


def kpi_row(cards: list[Kpi]) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Code(card_item.source, className="kpi-source"),
                                    html.Div(card_item.label, className="kpi-label"),
                                ],
                                className="kpi-identity",
                            ),
                            info(card_item.tooltip, at_end=index % 4 == 3) if card_item.tooltip else None,
                        ],
                        className="kpi-head",
                    ),
                    html.Div(
                        [
                            html.Span(card_item.value),
                            html.Span(card_item.unit, className="kpi-unit") if card_item.unit else None,
                        ],
                        className="kpi-value",
                    ),
                    html.Div(card_item.detail, className="kpi-detail"),
                ],
                className="kpi-card",
            )
            for index, card_item in enumerate(cards)
        ],
        className="kpi-row",
    )


def kpi_block(cards: list[Kpi]) -> html.Div:
    """Eight cards in two rows of four, measured first."""

    return html.Div(
        [kpi_row(cards[:4]), kpi_row(cards[4:])] if len(cards) > 4 else [kpi_row(cards)],
        id="kpi-container",
    )


def metric_toggle(control_id: str) -> dcc.RadioItems:
    return dcc.RadioItems(
        id=control_id,
        options=[
            {"label": " Диалоги", "value": "dialogues"},
            {"label": " Токены", "value": "tokens"},
        ],
        value="dialogues",
        inline=True,
        className="card-toggle",
    )


def graph(element_id: str) -> dcc.Graph:
    return dcc.Graph(id=element_id, config={"displayModeBar": False})


def tokens_section() -> html.Div:
    return section(
        "Расход",
        "Куда уходят токены?",
        html.Div(
            [
                card(
                    "Расход по сценариям",
                    "Σ total_tokens внутри кластера. Средний расход на диалог почти "
                    "одинаков во всех сценариях, поэтому этот рейтинг повторяет частоту "
                    "сценария, а не его «дороговизну».",
                    "Какие сценарии съедают бюджет.",
                    graph("chart-tokens-scenario"),
                ),
                card(
                    "Профиль по часам",
                    "Группировка created_at по часу UTC. Это профиль доступного периода, "
                    "а не график роста: в выгрузке один день.",
                    "Когда приходили обращения и расходовались токены.",
                    metric_toggle("hourly-metric"),
                    graph("chart-hourly"),
                ),
            ],
            className="chart-grid",
        ),
    )


def automation_section() -> html.Div:
    return section(
        "Автоматизация",
        "Что автоматизировать первым?",
        html.Div(
            [
                card(
                    "Карта сценариев",
                    "По горизонтали — доля диалогов сценария, по вертикали — доля "
                    "диалогов с automation_candidate = True внутри него. Пунктир — "
                    "медианы обеих осей. Цвет точки — доля простых задач в сценарии.",
                    "Правый верхний квадрант — частые сценарии, которые анализ уже "
                    "отметил как автоматизируемые.",
                    graph("chart-scenario-map"),
                ),
                card(
                    "Сложность и кандидаты",
                    "Распределение complexity, разложенное по automation_candidate. "
                    "Простое и повторяющееся автоматизируется первым.",
                    "Сколько кандидатов в каждой группе сложности.",
                    graph("chart-complexity-auto"),
                ),
            ],
            className="chart-grid",
        ),
    )


def reliability_section() -> html.Div:
    return section(
        "Надёжность",
        "Где агент ломается?",
        html.Div(
            [
                card(
                    "Причины отказов",
                    "Распределение failure_reason среди строк с agent_failed = True.",
                    "Почему агент не справлялся.",
                    graph("chart-failures"),
                    stat_strip([], "stat-problems"),
                ),
                card(
                    "Полезные и бесполезные сообщения",
                    "Σ useful_messages и Σ useless_messages из классификатора сообщений. "
                    "useful_ratio = useful / (useful + useless) × 100.",
                    "Разметка сообщений агента, а не оценка пользователя.",
                    graph("chart-quality"),
                    stat_strip([], "stat-quality"),
                ),
                card(
                    "Уверенность классификации",
                    "Гистограмма поля confidence с порогом 0,5. Диалоги ниже порога "
                    "нельзя считать надёжно размеченными.",
                    "Насколько классификатор уверен в своей разметке.",
                    graph("chart-confidence"),
                ),
            ],
            className="chart-grid chart-grid-three",
        ),
    )


def usage_section() -> html.Div:
    return section(
        "Нагрузка",
        "Кто пользуется?",
        html.Div(
            [
                card(
                    "Использование по пользователям",
                    "Группировка по псевдонимизированному user_id. Клик по столбцу "
                    "сужает таблицу внизу страницы.",
                    "Кто создал больше диалогов и на чьи диалоги пришлось больше токенов.",
                    metric_toggle("users-metric"),
                    graph("chart-users"),
                    className="card card-full",
                ),
            ],
            className="chart-grid chart-grid-even",
        ),
    )


def catalogue_section() -> html.Div:
    return section(
        "Состав",
        "Что это за диалоги?",
        html.Div(
            [
                card(
                    "Сценарии",
                    "Размер кластера пересчитывается по видимым строкам, а не берётся из "
                    "member_count, поэтому цифры сходятся и под фильтром. "
                    "cluster_id = -1 — точки вне кластеров.",
                    "Кластеры, найденные по эмбеддингам диалогов.",
                    graph("chart-clusters"),
                    stat_strip([], "stat-clusters"),
                ),
                card(
                    "Интеграции",
                    "Поле integrations разбирается по «;». Диалог попадает в столбец "
                    "каждой упомянутой в нём интеграции.",
                    "Какие корпоративные системы затрагивают диалоги.",
                    graph("chart-integrations"),
                    stat_strip([], "stat-integrations"),
                ),
                card(
                    "Инструменты агента",
                    "Поле tools разбирается по «;»; avg_tool_calls считается по полю tool_calls.",
                    "Чем агент пользовался внутри диалогов.",
                    graph("chart-tools"),
                ),
            ],
            className="chart-grid chart-grid-three",
        ),
    )


def economics_section(default: dict) -> html.Div:
    """Окупаемость: единственный блок, где на входе стоит допущение.

    Все допущения вынесены в поля ввода на самой странице. Спрятать их внутрь
    числа — обычная практика ROI-слайдов и единственный способ проиграть первый
    же вопрос жюри.
    """

    return section(
        "Экономика",
        "Окупается ли?",
        html.Div(
            [
                card(
                    "Выгода против затрат",
                    "Затраты не зависят от экономии минут — это горизонталь. "
                    "Выгода = запросов × минут × ₽/мин × доля реализации — это луч. "
                    "Пересечение и есть порог безубыточности.",
                    "Минут экономии нет ни в одном логе: нигде не записано, сколько "
                    "задача заняла бы без агента. Поэтому они на оси, а не внутри числа.",
                    graph("chart-breakeven"),
                    stat_strip([], "stat-economics"),
                ),
                card(
                    "Допущения",
                    "Ставка минуты = оклад × 1,30 взносы ÷ 164,33 ч ÷ 60. "
                    "164,33 ч — это 1972 ч производственного календаря РФ 2026 ÷ 12. "
                    "Доля реализации 0,6 — середина полосы Forrester TEI 50–70 %.",
                    "Меняйте цифры: страница пересчитается вместе с ними.",
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Экономия на запрос, мин", className="filter-label"),
                                    dcc.Slider(
                                        id="assume-minutes",
                                        min=0,
                                        max=30,
                                        step=0.5,
                                        value=round(default["breakeven_minutes"], 1),
                                        marks={0: "0", 10: "10", 20: "20", 30: "30"},
                                    ),
                                ],
                                className="assume-cell assume-cell-wide",
                            ),
                            html.Div(
                                [
                                    html.Label("TCO, ₽ в месяц", className="filter-label"),
                                    dcc.Input(
                                        id="assume-tco",
                                        type="number",
                                        value=int(default["tco_month"]),
                                        min=0,
                                        step=1000,
                                        className="assume-input",
                                    ),
                                ],
                                className="assume-cell",
                            ),
                            html.Div(
                                [
                                    html.Label("Запросов в месяц", className="filter-label"),
                                    dcc.Input(
                                        id="assume-requests",
                                        type="number",
                                        value=int(default["requests_month"]),
                                        min=1,
                                        step=100,
                                        className="assume-input",
                                    ),
                                ],
                                className="assume-cell",
                            ),
                            html.Div(
                                [
                                    html.Label("Оклад FTE, ₽ в месяц", className="filter-label"),
                                    dcc.Input(
                                        id="assume-salary",
                                        type="number",
                                        value=int(default["salary_month"]),
                                        min=0,
                                        step=10000,
                                        className="assume-input",
                                    ),
                                ],
                                className="assume-cell",
                            ),
                        ],
                        className="assume-grid",
                    ),
                    html.P(id="economics-verdict", className="verdict"),
                ),
            ],
            className="chart-grid",
        ),
    )


def table_section() -> html.Div:
    """The raw rows. No generated conclusion here — the table is the evidence."""

    return html.Div(
        [
            html.Div(
                [
                    html.Span("Исходный уровень", className="section-kicker"),
                    html.H2("Диалоги без агрегации", className="section-title"),
                ],
                className="section-heading",
            ),
            html.Div(
                [
                    card_head(
                        "Диалоги",
                        "Строки текущего фильтра. Клик по пользователю на диаграмме нагрузки "
                        "дополнительно сужает таблицу.",
                    ),
                    html.P(
                        "Кнопка «Экспорт CSV» выгружает ровно эти строки.",
                        className="card-subtitle",
                    ),
                    dash_table.DataTable(
                        id="dialogs-table",
                        columns=[{"name": title, "id": column} for column, title, _ in TABLE_COLUMNS],
                        page_size=12,
                        page_action="native",
                        sort_action="native",
                        fixed_rows={"headers": True},
                        style_table={"overflowX": "auto", "height": "520px", "overflowY": "auto"},
                        style_header={
                            "backgroundColor": "var(--surface-2)",
                            "color": "var(--text-primary)",
                            "border": "none",
                            "borderBottom": "1px solid var(--border-strong)",
                            "fontWeight": 600,
                        },
                        style_data={
                            "backgroundColor": "var(--surface-1)",
                            "color": "var(--text-primary)",
                            "border": "none",
                            "borderBottom": "1px solid var(--border)",
                        },
                        style_cell={
                            "fontFamily": 'system-ui, -apple-system, "Segoe UI", sans-serif',
                            "fontSize": "13px",
                            "padding": "8px 10px",
                            "textAlign": "left",
                            "whiteSpace": "normal",
                            "height": "auto",
                            "minWidth": "80px",
                        },
                        style_cell_conditional=[
                            {
                                "if": {"column_id": column},
                                "width": f"{width}px",
                                "minWidth": f"{width}px",
                                "maxWidth": f"{width}px",
                            }
                            for column, _, width in TABLE_COLUMNS
                        ],
                    ),
                    ],
                className="card card-full records",
            ),
        ],
        className="metric-section",
    )


def build(
    frame: pd.DataFrame,
    cards: list[Kpi],
    theme: Theme,
    notes: list[str],
    headline: tuple[str, str, str],
    spend: list[dict],
    economics: dict,
) -> html.Div:
    lead, number, tail = headline
    mark = (spend[0]["share"], spend[0]["percent"]) if spend else None
    return html.Div(
        [
            dcc.Store(id="theme-store", data=theme.name),
            dcc.Store(id="selection-store", data=None),
            html.Header(
                [
                    html.Div(
                        [
                            html.Span("КРОК · Промпт-радар", className="brand-mark"),
                            html.H1("Аналитика диалогов с ИИ-агентом", className="app-title"),
                            html.P(
                                "Расход, сценарии и риски по одной выгрузке pipeline",
                                className="app-subtitle",
                            ),
                        ],
                        className="brand-block",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span("в выгрузке", className="header-meta-label"),
                                    html.Strong(f"{len(frame)} диалогов"),
                                ],
                                className="header-meta",
                            ),
                            html.Button(
                                "Сменить тему",
                                id="theme-toggle",
                                className="ghost-button theme-button",
                            ),
                        ],
                        className="header-actions",
                    ),
                ],
                className="app-header",
            ),
            rail(mark),
            hero([lead, html.B(number), tail], spend_block(spend)),
            warnings_strip(notes),
            filter_bar(frame),
            html.Div(
                [
                    html.Button(
                        id="clear-selection",
                        className="chip-selection",
                        title="Снять выбор пользователя",
                        style={"display": "none"},
                    ),
                    html.Div(id="filter-chips", className="chip-list"),
                ],
                className="chip-row",
            ),
            html.Div(id="result-count", className="result-count"),
            kpi_block(cards),
            economics_section(economics),
            tokens_section(),
            automation_section(),
            reliability_section(),
            usage_section(),
            catalogue_section(),
            table_section(),
        ],
        className=f"viz-root theme-{theme.name}",
        id="viz-root",
    )
