"""Filter definitions shared by the layout and the callbacks.

Categorical filters are multi-select and combine as OR inside one field and AND
between fields, which is what a reader assumes when they pick two complexities
and one language. Flags are a separate checklist because each of them narrows
to a subset rather than choosing between values.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FilterSpec:
    key: str
    label: str
    placeholder: str


FILTERS: tuple[FilterSpec, ...] = (
    FilterSpec("user_id", "Пользователь", "Все пользователи"),
    FilterSpec("use_case", "Сценарий", "Все сценарии"),
    FilterSpec("complexity", "Сложность", "Любая"),
    FilterSpec("periodicity", "Периодичность", "Любая"),
    FilterSpec("language", "Язык", "Любой"),
)

FLAGS: tuple[FilterSpec, ...] = (
    FilterSpec("is_work", "Только рабочие", ""),
    FilterSpec("automation_candidate", "Кандидаты на автоматизацию", ""),
    FilterSpec("agent_failed", "С ошибкой агента", ""),
    FilterSpec("prompt_injection", "С prompt injection", ""),
    FilterSpec("contains_sensitive_data", "С чувствительными данными", ""),
)


def options_for(frame: pd.DataFrame, spec: FilterSpec) -> list[dict]:
    if spec.key not in frame:
        return []
    values = sorted({str(value) for value in frame[spec.key].dropna() if str(value).strip()})
    return [{"label": value, "value": value} for value in values]


def apply(frame: pd.DataFrame, selections: dict, flags: list[str] | None = None) -> pd.DataFrame:
    """Narrow the frame by the categorical selections and the active flags."""

    filtered = frame
    for key, chosen in (selections or {}).items():
        if not chosen or key not in filtered:
            continue
        filtered = filtered[filtered[key].astype(str).isin([str(value) for value in chosen])]
    for key in flags or []:
        if key in filtered:
            filtered = filtered[filtered[key]]
    return filtered


def apply_selection(frame: pd.DataFrame, selection: dict | None) -> pd.DataFrame:
    """Apply a click-through selection made on a chart."""

    if not selection:
        return frame
    column = selection.get("column")
    value = selection.get("value")
    if column not in frame or value is None:
        return frame
    return frame[frame[column].astype(str) == str(value)]


def active(selections: dict, flags: list[str] | None = None) -> list[tuple[str, str]]:
    """Human-readable summary of what is currently narrowing the page."""

    chips: list[tuple[str, str]] = []
    by_key = {spec.key: spec for spec in FILTERS}
    for key, chosen in (selections or {}).items():
        if not chosen:
            continue
        spec = by_key.get(key)
        if spec is None:
            continue
        chips.append((spec.label, ", ".join(str(value) for value in chosen)))
    flag_labels = {spec.key: spec.label for spec in FLAGS}
    for key in flags or []:
        if key in flag_labels:
            chips.append(("Признак", flag_labels[key]))
    return chips
