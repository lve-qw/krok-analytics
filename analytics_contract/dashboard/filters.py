"""Filter definitions and application.

List-valued columns use "contains any of the selected values"; scalar columns
use "is one of". Boolean filters are tri-state (any / true / false) so that an
unset filter never silently means False.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

ANY = "__any__"


@dataclass(frozen=True)
class FilterSpec:
    key: str
    label: str
    column: str
    kind: str  # "scalar" | "list" | "bool"


FILTERS: tuple[FilterSpec, ...] = (
    FilterSpec("is_work", "Рабочий запрос", "is_work", "bool"),
    FilterSpec("class_names", "Класс", "class_names", "list"),
    FilterSpec("use_case", "Сценарий", "use_case", "scalar"),
    FilterSpec("complexity", "Сложность", "complexity", "scalar"),
    FilterSpec("periodicity", "Периодичность", "periodicity", "scalar"),
    FilterSpec("language", "Язык", "language", "scalar"),
    FilterSpec("integrations", "Интеграция", "integrations", "list"),
    FilterSpec("tools", "Инструмент", "tools", "list"),
    FilterSpec("automation_candidate", "Кандидат на автоматизацию", "automation_candidate", "bool"),
    FilterSpec("agent_failed", "Зафиксирован сбой", "agent_failed", "bool"),
    FilterSpec("contains_sensitive_data", "Чувствительные данные", "contains_sensitive_data", "bool"),
    FilterSpec("prompt_injection", "Prompt injection", "prompt_injection", "bool"),
)

BOOL_OPTIONS = [
    {"label": "Все", "value": ANY},
    {"label": "Да", "value": "true"},
    {"label": "Нет", "value": "false"},
]


def options_for(frame: pd.DataFrame, spec: FilterSpec) -> list[dict[str, str]]:
    """Distinct values available for a filter, sorted for stable ordering."""

    if spec.kind == "bool":
        return BOOL_OPTIONS
    if spec.kind == "list":
        values = {item for row in frame[spec.column] for item in row}
    else:
        values = {value for value in frame[spec.column] if str(value).strip()}
    return [{"label": value, "value": value} for value in sorted(values)]


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
