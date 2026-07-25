"""Metric computations for the dashboard.

Every function here implements a metric declared in `docs/metrics_catalog.md`
and computes it from validated contract fields only. Nothing calls an LLM and
nothing invents a value.

Denominator rule for list columns: frequencies are counted over exploded rows,
but shares are taken over dialogues. Shares across classes therefore sum to more
than 100%, which is a property of multi-label data and is stated in the chart
subtitles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

#: Groups smaller than this are not given a rate: a share over 1-2 rows is 0% or
#: 100% and carries no information.
DEFAULT_MIN_GROUP = 5

#: `estimated_cost` is produced in `token_counter.py` as tokens/1000 * 0.0001.
#: The pipeline never names a currency, so the dashboard does not name one
#: either — it labels the figure as conventional units and states the rate.
COST_UNIT = "у.е."
COST_RATE_NOTE = "0,0001 у.е. за 1000 токенов (token_counter.py)"


@dataclass(frozen=True)
class Kpi:
    """One first-screen card.

    `formula` and `caveat` exist because a number shown to a jury has to be
    able to answer "where is that from?" without anyone speaking. They are
    rendered in the card's tooltip, which keeps the face of the card down to a
    label, a figure and one line of context.
    """

    label: str
    value: str
    detail: str
    note: str = ""
    unit: str = ""
    formula: str = ""

    @property
    def tooltip(self) -> str:
        return "\n\n".join(part for part in (self.formula, self.caveat) if part)

    @property
    def caveat(self) -> str:
        return self.note


def _share(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def explode(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """One row per list element, dropping rows with an empty list."""

    exploded = frame[[column, *[c for c in frame.columns if c != column]]].explode(column)
    return exploded[exploded[column].notna()]


def review_queue_mask(frame: pd.DataFrame, low_confidence: float) -> pd.Series:
    """Rows a human should look at before any number is trusted.

    Four unlike signals joined by OR. This is an attention filter, not a risk
    score: the signals are not weighted against each other.
    """

    if frame.empty:
        return pd.Series(dtype=bool)
    return (
        (frame["confidence"] < low_confidence)
        | frame["agent_failed"]
        | frame["contains_sensitive_data"]
        | frame["prompt_injection"]
    )


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Honest about small groups, unlike a bare share."""

    if total == 0:
        return 0.0, 0.0
    phat = successes / total
    denominator = 1 + z**2 / total
    centre = (phat + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(phat * (1 - phat) / total + z**2 / (4 * total**2)) / denominator
    return max(centre - margin, 0.0), min(centre + margin, 1.0)


def kpis(frame: pd.DataFrame, low_confidence: float, top_n: int = 5) -> list[Kpi]:
    """The seven first-screen cards selected in the metrics catalog."""

    total = len(frame)
    if total == 0:
        return [Kpi("Нет данных", "0", "Фильтры не оставили ни одной записи")]

    work = int(frame["is_work"].sum())
    failed = int(frame["agent_failed"].sum())
    automation = int(frame["automation_candidate"].sum())

    cost_total = float(frame["estimated_cost"].sum())
    cost_median = float(frame["estimated_cost"].median())

    by_use_case = frame.groupby("use_case")["estimated_cost"].sum().sort_values(ascending=False)
    concentration = _share(float(by_use_case.head(top_n).sum()), cost_total) if cost_total else 0.0

    review = int(review_queue_mask(frame, low_confidence).sum())
    sensitive = int(frame["contains_sensitive_data"].sum())
    injection = int(frame["prompt_injection"].sum())

    return [
        Kpi(
            label="Проанализировано диалогов",
            value=f"{total}",
            detail=f"рабочих — {_pct(_share(work, total))}",
            formula="Число строк после фильтров. Доля рабочих = Σ is_work ÷ число строк.",
            note="Строки, отброшенные из-за сбоя аналитического pipeline, сюда не "
                 "входят: они лежат в outputs/pipeline_errors.csv.",
        ),
        Kpi(
            label="Зафиксировано сбоев",
            value=_pct(_share(failed, total)),
            detail=f"{failed} из {total}",
            formula="Σ agent_failed ÷ число диалогов.",
            note="«Сбой не зафиксирован» не означает успешно выполненную задачу: "
                 "контракт фиксирует только явный отказ агента.",
        ),
        Kpi(
            label="Кандидаты на автоматизацию",
            value=_pct(_share(automation, total)),
            detail=f"{automation} диалогов",
            formula="Σ automation_candidate ÷ число диалогов.",
            note="Признак поставлен LLM при разборе диалога. Это гипотеза для "
                 "проверки, а не подтверждённая возможность автоматизации.",
        ),
        Kpi(
            label="Стоимость обработки",
            value=f"{cost_total:.4f}",
            unit=COST_UNIT,
            detail=f"медиана диалога — {cost_median:.5f} {COST_UNIT}",
            formula=f"Σ estimated_cost. Тариф — {COST_RATE_NOTE}.",
            note="Только LLM/API-обработка. Инфраструктура, GPU и лицензии в "
                 "контракт не входят, поэтому это не стоимость владения системой. "
                 "Валюта в pipeline не объявлена, поэтому единицы условные.",
        ),
        Kpi(
            label=f"Концентрация расходов, топ-{top_n}",
            value=_pct(concentration),
            detail=f"из {len(by_use_case)} сценариев",
            formula=f"Стоимость {top_n} самых дорогих сценариев ÷ общая стоимость.",
            note="Показывает, на скольких сценариях сосредоточены расходы, — "
                 "точка приложения усилий по оптимизации.",
        ),
        Kpi(
            label="Требуют ручного разбора",
            value=_pct(_share(review, total)),
            detail=f"{review} записей",
            formula="Объединение по ИЛИ: confidence ниже порога, либо agent_failed, "
                    "либо contains_sensitive_data, либо prompt_injection.",
            note="Фильтр внимания, а не оценка риска: сигналы не взвешены между "
                 "собой и один диалог может попасть сюда по нескольким причинам.",
        ),
        Kpi(
            label="Индикаторы риска данных",
            value=f"{_pct(_share(sensitive, total))} / {_pct(_share(injection, total))}",
            detail="чувствительные данные / prompt injection",
            formula="Σ contains_sensitive_data ÷ N и Σ prompt_injection ÷ N.",
            note="Фиксируется обнаружение признака, а не успешность атаки и не "
                 "факт утечки.",
        ),
    ]


def top_use_cases(frame: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    counts = frame["use_case"].value_counts().head(limit)
    return pd.DataFrame({"use_case": counts.index, "count": counts.values})


def top_classes(frame: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    exploded = explode(frame, "class_names")
    counts = exploded["class_names"].value_counts().head(limit)
    return pd.DataFrame({"use_case": counts.index, "count": counts.values})


def use_case_periodicity(frame: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    """Counts by scenario and declared periodicity — the automation matrix."""

    keep = frame["use_case"].value_counts().head(limit).index
    subset = frame[frame["use_case"].isin(keep)]
    if subset.empty:
        return pd.DataFrame()
    matrix = subset.pivot_table(
        index="use_case", columns="periodicity", values="request_id", aggfunc="count"
    ).fillna(0)
    for column in ("none", "daily", "weekly", "monthly"):
        if column not in matrix.columns:
            matrix[column] = 0
    return matrix[["none", "daily", "weekly", "monthly"]]


def failure_by_use_case(frame: pd.DataFrame, min_group: int = DEFAULT_MIN_GROUP) -> pd.DataFrame:
    grouped = frame.groupby("use_case").agg(
        volume=("request_id", "count"),
        failures=("agent_failed", "sum"),
        cost=("estimated_cost", "sum"),
    )
    grouped = grouped[grouped["volume"] >= min_group]
    if grouped.empty:
        return pd.DataFrame()
    grouped["failure_rate"] = grouped["failures"] / grouped["volume"]
    return grouped.reset_index()


def reliability(
    frame: pd.DataFrame, column: str, min_group: int = DEFAULT_MIN_GROUP, limit: int = 12
) -> pd.DataFrame:
    """Failure rate per tool or integration, with Wilson intervals.

    The failure is attributed to every tool used in the dialogue: the contract
    has no per-call events, so the true culprit is unknown. This is an upper
    bound on blame, not a measurement of it.
    """

    exploded = explode(frame, column)
    if exploded.empty:
        return pd.DataFrame()
    grouped = exploded.groupby(column).agg(
        volume=("request_id", "count"), failures=("agent_failed", "sum")
    )
    grouped = grouped[grouped["volume"] >= min_group]
    if grouped.empty:
        return pd.DataFrame()
    grouped["failure_rate"] = grouped["failures"] / grouped["volume"]
    bounds = grouped.apply(
        lambda row: wilson_interval(int(row["failures"]), int(row["volume"])), axis=1
    )
    grouped["low"] = [bound[0] for bound in bounds]
    grouped["high"] = [bound[1] for bound in bounds]
    return grouped.sort_values("failure_rate", ascending=False).head(limit).reset_index()


def cost_pareto(frame: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    """Cost share per scenario plus the cumulative share.

    Both series are shares of the same total, so they share one axis. A second
    y-axis would be the classic dual-scale chart and is not used.
    """

    total = float(frame["estimated_cost"].sum())
    if total <= 0:
        return pd.DataFrame()
    grouped = (
        frame.groupby("use_case")["estimated_cost"].sum().sort_values(ascending=False).head(limit)
    )
    result = pd.DataFrame({"use_case": grouped.index, "cost": grouped.values})
    result["share"] = result["cost"] / total
    result["cumulative"] = result["share"].cumsum()
    return result


def token_split(frame: pd.DataFrame) -> pd.DataFrame:
    """Mean tokens by role and complexity."""

    order = ["simple", "medium", "complex"]
    grouped = frame.groupby("complexity")[
        ["user_tokens", "assistant_tokens", "tool_tokens"]
    ].mean()
    grouped = grouped.reindex([level for level in order if level in grouped.index])
    return grouped.reset_index()


def security_matrix(frame: pd.DataFrame, min_group: int = DEFAULT_MIN_GROUP, limit: int = 12) -> pd.DataFrame:
    """Share of sensitive data, company data and injection per scenario."""

    grouped = frame.groupby("use_case").agg(
        volume=("request_id", "count"),
        sensitive=("contains_sensitive_data", "mean"),
        company=("uses_company_data", "mean"),
        injection=("prompt_injection", "mean"),
    )
    grouped = grouped[grouped["volume"] >= min_group]
    if grouped.empty:
        return pd.DataFrame()
    return grouped.sort_values("volume", ascending=False).head(limit)[
        ["sensitive", "company", "injection"]
    ]


def exposure_overlap(frame: pd.DataFrame) -> int:
    """Dialogues combining sensitive data, company sources and external search.

    Co-occurrence within one dialogue. Not evidence that anything left the
    perimeter; every such row needs a human read.
    """

    if frame.empty:
        return 0
    external = frame["search_type"].map(lambda values: "internet" in values)
    return int((frame["contains_sensitive_data"] & frame["uses_company_data"] & external).sum())
