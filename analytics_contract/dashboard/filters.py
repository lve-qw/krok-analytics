"""Filter definitions and application.

List-valued columns use "contains any of the selected values"; scalar columns
use "is one of". Boolean filters are tri-state (any / true / false) so that an
unset filter never silently means False.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from analytics_contract.dashboard import labels

ANY = "__any__"


@dataclass(frozen=True)
class FilterSpec:
    key: str
    label: str
    column: str
    kind: str  # "scalar" | "list" | "bool"
    #: Primary filters stay on screen. The rest live behind "Дополнительные
    #: фильтры": twelve dropdowns at once cost more attention than they were
    #: worth, and the active ones are visible as chips either way.
    primary: bool = False


FILTERS: tuple[FilterSpec, ...] = (
    FilterSpec("use_case", "Сценарий", "use_case", "scalar", primary=True),
    FilterSpec("class_names", "Класс", "class_names", "list", primary=True),
    FilterSpec("complexity", "Сложность", "complexity", "scalar", primary=True),
    FilterSpec("periodicity", "Периодичность", "periodicity", "scalar", primary=True),
    FilterSpec("agent_failed", "Зафиксирован сбой", "agent_failed", "bool", primary=True),
    FilterSpec("is_work", "Рабочий запрос", "is_work", "bool"),
    FilterSpec("language", "Язык", "language", "scalar"),
    FilterSpec("integrations", "Интеграция", "integrations", "list"),
    FilterSpec("tools", "Инструмент", "tools", "list"),
    FilterSpec("automation_candidate", "Кандидат на автоматизацию", "automation_candidate", "bool"),
    FilterSpec("contains_sensitive_data", "Чувствительные данные", "contains_sensitive_data", "bool"),
    FilterSpec("prompt_injection", "Prompt injection", "prompt_injection", "bool"),
)

PRIMARY = tuple(spec for spec in FILTERS if spec.primary)
SECONDARY = tuple(spec for spec in FILTERS if not spec.primary)

BOOL_OPTIONS = [
    {"label": "Все", "value": ANY},
    {"label": "Да", "value": "true"},
    {"label": "Нет", "value": "false"},
]


def options_for(frame: pd.DataFrame, spec: FilterSpec) -> list[dict[str, str]]:
    """Distinct values available for a filter, sorted for stable ordering.

    The option's `value` is always the stored value, so a filter still matches
    the data after its caption is translated.
    """

    if spec.kind == "bool":
        return BOOL_OPTIONS
    if spec.kind == "list":
        values = {item for row in frame[spec.column] for item in row}
    else:
        values = {value for value in frame[spec.column] if str(value).strip()}
    return [
        {"label": labels.show(value, spec.column), "value": value}
        for value in sorted(values, key=lambda value: labels.show(value, spec.column))
    ]


#: Columns a chart click can select on. Each is the axis of a chart the user
#: can point at; anything else would let a click mean something the chart never
#: showed.
SELECTABLE = {"use_case": "scalar", "class_names": "list", "user_id": "scalar"}


def apply_selection(frame: pd.DataFrame, selection: dict[str, Any] | None) -> pd.DataFrame:
    """Narrow to one clicked scenario, class or pseudonymous user.

    Kept apart from :func:`apply` on purpose: the dropdowns decide what the
    charts count, the click decides only which rows the Records tab lists.
    """

    if not selection:
        return frame
    column = selection.get("column")
    value = selection.get("value")
    if column not in SELECTABLE or value in (None, ""):
        return frame
    if SELECTABLE[column] == "list":
        return frame[frame[column].map(lambda row: value in row)]
    return frame[frame[column] == value]


def active(selections: dict[str, Any]) -> list[tuple[FilterSpec, str]]:
    """Filters that currently narrow the data, as (spec, readable value).

    Drives the chip row. A filter the user cannot see is a filter they will
    forget, and a forgotten filter is how a wrong number reaches a slide.
    """

    result: list[tuple[FilterSpec, str]] = []
    for spec in FILTERS:
        selected = selections.get(spec.key)
        if selected in (None, [], "", ANY):
            continue
        if spec.kind == "bool":
            text = "да" if selected == "true" else "нет"
        else:
            chosen = selected if isinstance(selected, list) else [selected]
            text = ", ".join(labels.show(value, spec.column) for value in chosen)
        result.append((spec, text))
    return result


def apply(frame: pd.DataFrame, selections: dict[str, Any]) -> pd.DataFrame:
    """Apply every active selection. An empty or ANY selection is a no-op."""

    result = frame
    for spec in FILTERS:
        selected = selections.get(spec.key)
        if selected in (None, [], "", ANY):
            continue
        if spec.kind == "bool":
            result = result[result[spec.column] == (selected == "true")]
        elif spec.kind == "list":
            wanted = set(selected if isinstance(selected, list) else [selected])
            result = result[result[spec.column].map(lambda row: bool(wanted & set(row)))]
        else:
            wanted = set(selected if isinstance(selected, list) else [selected])
            result = result[result[spec.column].isin(wanted)]
    return result
