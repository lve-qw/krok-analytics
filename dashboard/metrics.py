"""Every metric listed in metrics.md, computed from the parsed export.

The module is organised in the ten sections of metrics.md and each function
returns plain numbers or a small frame, so a value on the page can be traced to
one expression here. Where metrics.md is ambiguous the docstring says which
reading is implemented.

All shares are computed over the rows currently visible, so a filtered view
stays internally consistent instead of mixing a filtered numerator with a
whole-export denominator.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from dashboard.data import UNKNOWN

COMPLEXITY_ORDER = ("simple", "medium", "complex")
PERIODICITY_ORDER = ("none", "daily", "weekly", "monthly")
LOW_CONFIDENCE = 0.5


@dataclass(frozen=True)
class Kpi:
    """A displayed number together with its formula and its caveat."""

    label: str
    value: str
    detail: str = ""
    unit: str = ""
    source: str = "measured"
    formula: str = ""
    note: str = ""

    @property
    def tooltip(self) -> str:
        return "\n\n".join(part for part in (self.formula, self.note) if part)


def integer(value: float | int) -> str:
    return f"{value:,.0f}".replace(",", " ")


def percent(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _share(part: float, whole: float) -> float:
    return float(part) / float(whole) * 100 if whole else 0.0


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame:
        return frame[name]
    return pd.Series([], dtype="float64")


# --- 1. Общая статистика ------------------------------------------------


def overview(frame: pd.DataFrame) -> dict:
    """total_dialogs, total_users, date_range."""

    timestamps = _column(frame, "created_at").dropna()
    start = timestamps.min() if not timestamps.empty else None
    end = timestamps.max() if not timestamps.empty else None
    return {
        "total_dialogs": int(len(frame)),
        "total_users": int(frame["user_id"].nunique()) if "user_id" in frame else 0,
        "date_min": start,
        "date_max": end,
        "days": (end.date() - start.date()).days + 1 if start is not None and end is not None else 0,
    }


# --- 2. Токены ----------------------------------------------------------


def tokens(frame: pd.DataFrame) -> dict:
    """total_tokens, avg_tokens_per_dialog, burned_tokens, burned_ratio, cost."""

    total = float(_column(frame, "total_tokens").sum())
    burned = float(_column(frame, "burned_tokens").sum())
    return {
        "total_tokens": int(total),
        "avg_tokens_per_dialog": total / len(frame) if len(frame) else 0.0,
        "median_tokens_per_dialog": float(_column(frame, "total_tokens").median()) if len(frame) else 0.0,
        "total_burned_tokens": int(burned),
        "burned_ratio": _share(burned, total),
        "total_estimated_cost": float(_column(frame, "estimated_cost").sum()),
        "user_tokens": int(_column(frame, "user_tokens").sum()),
        "assistant_tokens": int(_column(frame, "assistant_tokens").sum()),
        "tool_tokens": int(_column(frame, "tool_tokens").sum()),
    }


# --- 3. Качество работы агента ------------------------------------------


def quality(frame: pd.DataFrame) -> dict:
    """useful/useless messages and the token cost of the failed ones.

    ``avg_burned_per_failed_dialog`` averages over dialogues that actually
    burned tokens, which is the only subset where the value is defined.
    """

    useful = float(_column(frame, "useful_messages").sum())
    useless = float(_column(frame, "useless_messages").sum())
    burned_column = _column(frame, "burned_tokens")
    with_burned = burned_column[burned_column > 0]
    return {
        "useful_messages_total": int(useful),
        "useless_messages_total": int(useless),
        "useful_ratio": _share(useful, useful + useless),
        "dialogs_with_burned": int(len(with_burned)),
        "avg_burned_per_failed_dialog": float(with_burned.mean()) if len(with_burned) else 0.0,
    }


# --- 4. Классификация ---------------------------------------------------


def classification(frame: pd.DataFrame) -> dict:
    """work_dialogs and automation_candidates with their shares."""

    total = len(frame)
    work = int(_column(frame, "is_work").sum())
    automation = int(_column(frame, "automation_candidate").sum())
    return {
        "work_dialogs": work,
        "work_ratio": _share(work, total),
        "automation_candidates": automation,
        "automation_ratio": _share(automation, total),
    }


# --- 5. Сложность и периодичность ---------------------------------------


def _ordered_counts(frame: pd.DataFrame, column: str, order: tuple[str, ...]) -> pd.DataFrame:
    """Value counts in a fixed order, with unexpected values kept at the end."""

    if column not in frame or frame.empty:
        return pd.DataFrame(columns=["key", "dialogs"])
    counts = frame[column].value_counts()
    keys = [key for key in order if key in counts.index]
    keys += [key for key in counts.index if key not in order]
    return pd.DataFrame({"key": keys, "dialogs": [int(counts[key]) for key in keys]})


def complexity_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    return _ordered_counts(frame, "complexity", COMPLEXITY_ORDER)


def periodicity_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    return _ordered_counts(frame, "periodicity", PERIODICITY_ORDER)


# --- 6. Интеграции и инструменты ----------------------------------------


def _explode_counts(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in frame or frame.empty:
        return pd.DataFrame(columns=["key", "dialogs"])
    exploded = frame[column].explode().dropna()
    exploded = exploded[exploded != ""]
    if exploded.empty:
        return pd.DataFrame(columns=["key", "dialogs"])
    counts = exploded.value_counts()
    return pd.DataFrame({"key": counts.index, "dialogs": counts.to_numpy(dtype=int)})


def integrations(frame: pd.DataFrame) -> dict:
    """Coverage of integrations and tools across the visible dialogues."""

    integration_counts = _explode_counts(frame, "integrations")
    tool_counts = _explode_counts(frame, "tools")
    counted = _column(frame, "integration_count")
    return {
        "dialogs_with_integrations": int((counted > 0).sum()) if len(counted) else 0,
        "unique_integrations": int(len(integration_counts)),
        "unique_tools": int(len(tool_counts)),
        "avg_tool_calls": float(_column(frame, "tool_calls").mean()) if len(frame) else 0.0,
        "integration_counts": integration_counts,
        "tool_counts": tool_counts,
    }


# --- 7. Use Cases (кластеры) --------------------------------------------


def clusters(frame: pd.DataFrame) -> dict:
    """Cluster structure of the visible rows.

    ``total_clusters`` counts distinct clusters, not the dialogues inside them,
    and sizes are recounted from the visible rows rather than read from
    ``member_count``, so the numbers still add up under a filter.
    """

    if "cluster_id" not in frame or frame.empty:
        return {
            "total_clusters": 0,
            "outliers": 0,
            "avg_cluster_size": 0.0,
            "sizes": pd.DataFrame(columns=["cluster_id", "use_case", "label", "dialogs"]),
        }
    named = frame[frame["cluster_id"] != -1]
    outliers = int((frame["cluster_id"] == -1).sum())
    if named.empty:
        sizes = pd.DataFrame(columns=["cluster_id", "use_case", "label", "dialogs"])
    else:
        grouped = named.groupby("cluster_id")
        sizes = pd.DataFrame(
            {
                "cluster_id": grouped.size().index,
                "use_case": grouped["use_case"].agg(
                    lambda values: values.iloc[0] if len(values) else UNKNOWN
                ).to_numpy(),
                "dialogs": grouped.size().to_numpy(dtype=int),
            }
        ).sort_values("dialogs", ascending=False)
        # The namer can give two clusters the same title. Two bars sharing a
        # category label would be drawn on top of each other, so the id is
        # appended wherever a name is not unique.
        repeated = sizes["use_case"].duplicated(keep=False)
        sizes["label"] = sizes["use_case"].where(
            ~repeated, sizes["use_case"] + " · #" + sizes["cluster_id"].astype(str)
        )
    return {
        "total_clusters": int(len(sizes)),
        "outliers": outliers,
        "avg_cluster_size": float(sizes["dialogs"].mean()) if len(sizes) else 0.0,
        "sizes": sizes.reset_index(drop=True),
    }


def top_clusters(frame: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    """top_5_clusters by number of dialogues."""

    return clusters(frame)["sizes"].head(limit)


# --- 8. Проблемы --------------------------------------------------------


def problems(frame: pd.DataFrame) -> dict:
    """Failures, injections and sensitive data in the visible rows."""

    failed = _column(frame, "agent_failed")
    reasons = pd.DataFrame(columns=["key", "dialogs"])
    if "agent_failed" in frame and "failure_reason" in frame and failed.any():
        raw = frame.loc[failed, "failure_reason"].replace("", UNKNOWN)
        counts = raw.value_counts()
        reasons = pd.DataFrame({"key": counts.index, "dialogs": counts.to_numpy(dtype=int)})
    return {
        "agent_failures": int(failed.sum()) if len(failed) else 0,
        "prompt_injections": int(_column(frame, "prompt_injection").sum()) if len(frame) else 0,
        "sensitive_data": int(_column(frame, "contains_sensitive_data").sum()) if len(frame) else 0,
        "failure_reasons": reasons,
    }


# --- 9. Языки -----------------------------------------------------------


def language_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    return _ordered_counts(frame, "language", ("ru", "en"))


# --- 10. Уверенность классификации --------------------------------------


def confidence(frame: pd.DataFrame) -> dict:
    """avg_confidence and the number of dialogues below the threshold."""

    values = _column(frame, "confidence")
    return {
        "avg_confidence": float(values.mean()) if len(values) else 0.0,
        "low_confidence_dialogs": int((values < LOW_CONFIDENCE).sum()) if len(values) else 0,
        "values": values,
    }


# --- derived views for the charts ---------------------------------------


def usage_ranking(frame: pd.DataFrame, metric: str = "dialogues", limit: int = 15) -> pd.DataFrame:
    """Users ranked by dialogues or by consumed tokens."""

    if frame.empty or metric not in {"dialogues", "tokens"}:
        return pd.DataFrame(columns=["key", "dialogues", "tokens"])
    grouped = frame.groupby("user_id").agg(
        dialogues=("request_id", "count"),
        tokens=("total_tokens", "sum"),
    )
    grouped = grouped[grouped[metric] > 0].sort_values(metric, ascending=False).head(limit)
    return grouped.reset_index().rename(columns={"user_id": "key"})


def hourly_load(frame: pd.DataFrame) -> pd.DataFrame:
    """Dialogues and tokens by UTC hour of ``created_at``."""

    hours = pd.DataFrame({"hour": range(24)})
    dated = frame.dropna(subset=["created_at"]) if "created_at" in frame else frame.iloc[0:0]
    if dated.empty:
        return hours.assign(dialogues=0, tokens=0)
    grouped = dated.assign(hour=dated["created_at"].dt.hour).groupby("hour").agg(
        dialogues=("request_id", "count"),
        tokens=("total_tokens", "sum"),
    )
    return hours.merge(grouped, how="left", on="hour").fillna(0)


def token_split(frame: pd.DataFrame) -> pd.DataFrame:
    """Where the tokens went: prompt, answer or tool traffic."""

    measured = tokens(frame)
    return pd.DataFrame(
        {
            "key": ["Пользователь", "Ассистент", "Инструменты"],
            "tokens": [
                measured["user_tokens"],
                measured["assistant_tokens"],
                measured["tool_tokens"],
            ],
        }
    )


def kpis(frame: pd.DataFrame) -> list[Kpi]:
    """The eight headline numbers, four measured and four model-derived."""

    if frame.empty:
        return [Kpi("Нет данных", "0", "Фильтры не оставили ни одной строки")]

    base = overview(frame)
    token_stats = tokens(frame)
    quality_stats = quality(frame)
    class_stats = classification(frame)
    cluster_stats = clusters(frame)
    confidence_stats = confidence(frame)

    period = (
        f"{base['date_min']:%d.%m.%Y} — {base['date_max']:%d.%m.%Y} UTC"
        if base["date_min"] is not None
        else "время в выгрузке отсутствует"
    )

    return [
        Kpi(
            label="Диалоги",
            value=integer(base["total_dialogs"]),
            unit="шт.",
            detail=f"{base['total_users']} пользователей · {period}",
            formula="count(request_id) по видимым строкам.",
            note="Это объём выгрузки, а не всё использование агента в компании.",
        ),
        Kpi(
            label="Потрачено токенов",
            value=integer(token_stats["total_tokens"]),
            unit="токенов",
            detail=(
                f"в среднем {integer(token_stats['avg_tokens_per_dialog'])} · "
                f"медиана {integer(token_stats['median_tokens_per_dialog'])} на диалог"
            ),
            formula="Σ total_tokens = Σ (user_tokens + assistant_tokens + tool_tokens).",
            note="Измеренный расход. Перевода в деньги здесь нет.",
        ),
        Kpi(
            label="Оценка стоимости",
            value=f"{token_stats['total_estimated_cost']:.2f}".replace(".", ","),
            unit="у.е.",
            detail=f"поле estimated_cost, {integer(base['total_dialogs'])} строк",
            formula="Σ estimated_cost из выгрузки pipeline.",
            note=(
                "Значение зависит от тарифа, зашитого в pipeline. Это оценка, "
                "а не счёт от провайдера."
            ),
        ),
        # A zero here means the message classifier never filled the column, not
        # that the agent burned nothing, so the card says so instead of showing
        # a clean 0 %.
        Kpi(
            label="Сожжённые токены",
            value=percent(token_stats["burned_ratio"]) if token_stats["total_burned_tokens"] else "—",
            unit="%" if token_stats["total_burned_tokens"] else "",
            detail=(
                f"{integer(token_stats['total_burned_tokens'])} токенов в "
                f"{quality_stats['dialogs_with_burned']} диалогах"
                if token_stats["total_burned_tokens"]
                else "поле burned_tokens пусто во всей выгрузке"
            ),
            source="derived",
            formula="Σ burned_tokens / Σ total_tokens × 100.",
            note="burned_tokens размечает классификатор сообщений, а не лог агента.",
        ),
        Kpi(
            label="Полезные сообщения",
            value=(
                percent(quality_stats["useful_ratio"])
                if quality_stats["useful_messages_total"] + quality_stats["useless_messages_total"]
                else "—"
            ),
            unit=(
                "%"
                if quality_stats["useful_messages_total"] + quality_stats["useless_messages_total"]
                else ""
            ),
            detail=(
                f"{integer(quality_stats['useful_messages_total'])} полезных · "
                f"{integer(quality_stats['useless_messages_total'])} бесполезных"
                if quality_stats["useful_messages_total"] + quality_stats["useless_messages_total"]
                else "классификатор сообщений не заполнил поля"
            ),
            source="derived",
            formula="useful / (useful + useless) × 100 по видимым строкам.",
            note="Полезность определяет LLM-классификатор; это не оценка пользователя.",
        ),
        Kpi(
            label="Рабочие диалоги",
            value=percent(class_stats["work_ratio"]),
            unit="%",
            detail=(
                f"{class_stats['work_dialogs']} рабочих · "
                f"{class_stats['automation_candidates']} кандидатов на автоматизацию "
                f"({percent(class_stats['automation_ratio'])} %)"
            ),
            source="derived",
            formula="count(is_work) / count(request_id) × 100.",
            note="is_work и automation_candidate проставляет LLM-анализ диалога.",
        ),
        Kpi(
            label="Сценарии",
            value=integer(cluster_stats["total_clusters"]),
            unit="кластеров",
            detail=(
                f"средний размер {cluster_stats['avg_cluster_size']:.1f} · "
                f"вне кластеров {cluster_stats['outliers']}".replace(".", ",")
            ),
            source="derived",
            formula="count(distinct cluster_id), кроме cluster_id = -1.",
            note="Кластеризация HDBSCAN по эмбеддингам; -1 — точки, не вошедшие ни в один кластер.",
        ),
        Kpi(
            label="Уверенность разметки",
            value=f"{confidence_stats['avg_confidence']:.2f}".replace(".", ","),
            unit="ср.",
            detail=(
                f"{confidence_stats['low_confidence_dialogs']} диалогов ниже "
                f"{LOW_CONFIDENCE}".replace(".", ",")
            ),
            source="derived",
            formula=f"avg(confidence); порог низкой уверенности — {LOW_CONFIDENCE}.",
            note="Низкая уверенность означает, что класс диалога спорный и его нельзя считать фактом.",
        ),
    ]
