"""Display labels.

A single place that turns a stored value into the text a human reads. Nothing
here touches the data: `use_case` stays `unclustered` in every file, in the CSV
export and in every filter value — only the string drawn on screen changes.

Keeping this in one module is what makes the rule checkable. If a raw
identifier ever reaches the screen, it is because a caller skipped this layer,
not because a translation is missing somewhere in a chart.
"""

from __future__ import annotations

#: The clustering step leaves HDBSCAN noise under this literal. It is a real
#: value in the data, not an absence, so it is shown rather than hidden.
UNCLUSTERED = "unclustered"

USE_CASE = {UNCLUSTERED: "Сценарий не определён"}

COMPLEXITY = {"simple": "простой", "medium": "средний", "complex": "сложный"}

PERIODICITY = {
    "none": "разовые",
    "daily": "ежедневно",
    "weekly": "еженедельно",
    "monthly": "ежемесячно",
}

LANGUAGE = {"ru": "русский", "en": "английский"}

#: Canonical tool ids from `config.ToolsConfig.FIXED_TOOLS`. The id stays the
#: join key everywhere; this is the caption only.
TOOL = {
    "web_search": "Веб-поиск",
    "browser": "Браузер",
    "mail": "Почта",
    "calendar": "Календарь",
    "contacts": "Контакты",
    "crm": "CRM",
    "jira": "Jira",
    "confluence": "Confluence",
    "python": "Python",
    "sql": "SQL",
    "excel": "Excel",
    "filesystem": "Файлы",
    "presentation": "Презентации",
    "word": "Word",
    "powerpoint": "PowerPoint",
    "ocr": "Распознавание текста",
    "speech_to_text": "Речь в текст",
    "text_to_speech": "Текст в речь",
    "translator": "Переводчик",
    "summarizer": "Суммаризация",
    "image_generation": "Генерация изображений",
}

#: Integrations are product names in `config.IntegrationsConfig` and are shown
#: as they are stored; the map exists for the few that are abbreviations.
INTEGRATION = {"ISUP": "ИСУП", "REST API": "REST API"}

FAILURE_REASON = {
    "tool_timeout": "таймаут инструмента",
    "integration_unavailable": "интеграция недоступна",
    "missing_permission": "нет прав доступа",
    "no_matching_records": "ничего не найдено",
    "ambiguous_request": "неоднозначный запрос",
}

SEARCH_TYPE = {"internet": "внешний поиск", "internal": "внутренний поиск"}

REQUIRES_GENERATION = {
    "text": "текст",
    "excel": "таблица",
    "sql": "SQL",
    "presentation": "презентация",
}

RISK_COLUMN = {
    "sensitive": "чувствительные данные",
    "company": "корпоративные данные",
    "injection": "prompt injection",
}

#: Column -> map, so a caller can translate by column name without a chain of
#: ifs. Columns absent here are shown verbatim.
BY_COLUMN = {
    "use_case": USE_CASE,
    "complexity": COMPLEXITY,
    "periodicity": PERIODICITY,
    "language": LANGUAGE,
    "tools": TOOL,
    "integrations": INTEGRATION,
    "failure_reason": FAILURE_REASON,
    "search_type": SEARCH_TYPE,
    "requires_generation": REQUIRES_GENERATION,
}


def show(value: object, column: str | None = None) -> str:
    """Caption for one stored value. Unknown values pass through unchanged."""

    text = "" if value is None else str(value)
    if column is None:
        return text
    return BY_COLUMN.get(column, {}).get(text, text)


def use_case(value: object) -> str:
    return show(value, "use_case")


def show_all(values, column: str | None = None) -> list[str]:
    return [show(value, column) for value in values]


def joined(values, column: str | None = None, empty: str = "—") -> str:
    """List column rendered for a table cell."""

    labels = show_all(values, column)
    return ", ".join(labels) if labels else empty


#: Longest caption drawn on a chart axis before it is cut. Chosen so that the
#: widest scenario name in the demo set survives at 1024px without pushing the
#: plot area below half the card.
AXIS_LIMIT = 26


def truncate(text: str, limit: int = AXIS_LIMIT) -> str:
    """Shorten a caption for an axis. The full text still goes to the hover."""

    text = str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


#: The validator states its limitations in English because it is a CLI shared
#: with the pipeline. The dashboard is Russian end to end, so the captions are
#: translated here rather than in `validation.py` — the validator's own output
#: has to stay exactly as the contract tests expect it.
LIMITATION = {
    "The contract carries no timestamp and no request_text, so time-series and "
    "verbatim-request checks are out of scope by construction.":
        "В контракте нет ни отметки времени, ни исходного текста запроса, поэтому "
        "динамика во времени и проверки по дословному запросу невозможны "
        "по построению.",
    "tool_tokens counts only messages with role='tool'. A zero total means no such "
    "message was present in the source logs, not that tool execution was free.":
        "tool_tokens считает только сообщения с ролью tool. Нулевая сумма означает, "
        "что таких сообщений не было в исходных логах, а не что вызовы инструментов "
        "ничего не стоили.",
    "estimated_cost covers LLM/API processing only. Infrastructure, GPU and license "
    "costs are outside the contract, so it is not the total cost of ownership.":
        "estimated_cost покрывает только обработку LLM/API. Инфраструктура, GPU и "
        "лицензии в контракт не входят, поэтому это не стоимость владения системой.",
    "classes.csv carries no class-name column (only class_id and description), "
    "so class_names cannot be verified against the registry; only the class_ids "
    "themselves and the class_ids/class_names length agreement are checked.":
        "В classes.csv нет колонки с названием класса (только class_id и описание), "
        "поэтому class_names не сверяются с реестром: проверяются лишь сами class_ids "
        "и совпадение длин class_ids и class_names.",
    "No tools/integrations vocabulary was supplied, so those columns are checked "
    "for shape and uniqueness only. Pass the project registries to close them.":
        "Реестр инструментов и интеграций не передан, поэтому эти колонки проверены "
        "только на форму и уникальность значений.",
}


def limitation(text: str) -> str:
    """Russian caption for a validator limitation; unknown text passes through."""

    return LIMITATION.get(" ".join(str(text).split()), str(text))


def axis(values, column: str | None = None, limit: int = AXIS_LIMIT) -> list[str]:
    """Axis captions: translated, then shortened. Pair with a hover that
    carries the full name — never let the short form be the only copy."""

    return [truncate(show(value, column), limit) for value in values]
