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


def plural(count: int, one: str, few: str, many: str) -> str:
    """Russian plural agreement: 1 диалог, 2 диалога, 5 диалогов.

    Generated sentences are read out loud at a defence, and «94 диалогов»
    is the kind of detail that makes a jury stop listening to the number.
    """

    count = abs(int(count))
    if count % 100 in range(11, 15):
        return many
    last = count % 10
    if last == 1:
        return one
    if last in (2, 3, 4):
        return few
    return many


def counted(count: int, one: str, few: str, many: str) -> str:
    return f"{integer(count)} {plural(count, one, few, many)}"


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
    declared = _column(frame, "integration_count")
    return {
        "dialogs_with_integrations": int((declared > 0).sum()) if len(declared) else 0,
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


def scenario_map(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per cluster: scale, readiness for automation, composition.

    The two axes of the map are the two halves of the automation question —
    how often the scenario happens, and how often it was marked as a candidate.
    Token spend is deliberately not encoded: the average cost per dialogue is
    the same in every cluster, so a size channel would only repeat the x axis.
    """

    columns = ["cluster_id", "label", "use_case", "dialogs", "share", "automation_share",
               "simple_share", "tokens", "avg_tokens", "failures"]
    if "cluster_id" not in frame or frame.empty:
        return pd.DataFrame(columns=columns)
    named = frame[frame["cluster_id"] != -1]
    if named.empty:
        return pd.DataFrame(columns=columns)

    grouped = named.groupby("cluster_id")
    table = pd.DataFrame(
        {
            "cluster_id": grouped.size().index,
            "use_case": grouped["use_case"].agg(lambda values: values.iloc[0]).to_numpy(),
            "dialogs": grouped.size().to_numpy(dtype=int),
            "automation": grouped["automation_candidate"].sum().to_numpy(dtype=int),
            "simple": grouped["complexity"].agg(lambda values: int((values == "simple").sum())).to_numpy(),
            "tokens": grouped["total_tokens"].sum().to_numpy(dtype="int64"),
            "failures": grouped["agent_failed"].sum().to_numpy(dtype=int),
        }
    )
    table["share"] = table["dialogs"] / len(frame) * 100
    table["automation_share"] = table["automation"] / table["dialogs"] * 100
    table["simple_share"] = table["simple"] / table["dialogs"] * 100
    table["avg_tokens"] = table["tokens"] / table["dialogs"]
    repeated = table["use_case"].duplicated(keep=False)
    table["label"] = table["use_case"].where(
        ~repeated, table["use_case"] + " · #" + table["cluster_id"].astype(str)
    )
    return table.sort_values("dialogs", ascending=False)[columns].reset_index(drop=True)


def tokens_by_scenario(frame: pd.DataFrame) -> pd.DataFrame:
    """Total spend per cluster, for the ranked bar next to the split."""

    table = scenario_map(frame)
    if table.empty:
        return pd.DataFrame(columns=["key", "tokens"])
    return table.sort_values("tokens", ascending=False)[["label", "tokens"]].rename(
        columns={"label": "key"}
    )


def complexity_by_automation(frame: pd.DataFrame) -> pd.DataFrame:
    """Candidates and the rest, split by complexity.

    Simple and repeatable is what gets automated first, so the two fields are
    shown together rather than as two separate distributions.
    """

    if frame.empty or "complexity" not in frame or "automation_candidate" not in frame:
        return pd.DataFrame(columns=["key", "candidates", "rest"])
    counts = _ordered_counts(frame, "complexity", COMPLEXITY_ORDER)
    candidates = frame[frame["automation_candidate"]]["complexity"].value_counts()
    counts["candidates"] = [int(candidates.get(key, 0)) for key in counts["key"]]
    counts["rest"] = counts["dialogs"] - counts["candidates"]
    return counts[["key", "candidates", "rest"]]


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


def insights(frame: pd.DataFrame) -> dict[str, str]:
    """One sentence per section, assembled from the visible rows.

    These lines are generated rather than written, because a filtered page with
    a hand-written conclusion above a recomputed chart is how a dashboard ends
    up contradicting itself in front of a room.
    """

    empty = "Фильтры не оставили ни одной строки."
    if frame.empty:
        return {key: empty for key in ("tokens", "automation", "failures", "usage", "catalogue", "profile")}

    total = len(frame)
    token_stats = tokens(frame)
    class_stats = classification(frame)
    cluster_stats = clusters(frame)
    problem_stats = problems(frame)
    scenarios = scenario_map(frame)

    # --- tokens
    if token_stats["total_tokens"] == 0:
        tokens_line = "В выбранных строках нет израсходованных токенов."
    else:
        tool_share = _share(token_stats["tool_tokens"], token_stats["total_tokens"])
        answer_share = _share(token_stats["assistant_tokens"], token_stats["total_tokens"])
        tokens_line = (
            f"{percent(tool_share)} % расхода — трафик инструментов "
            f"({integer(token_stats['tool_tokens'])} из {integer(token_stats['total_tokens'])} токенов), "
            f"на ответы пользователю ушло {percent(answer_share)} %. "
            f"Средний диалог стоит {counted(token_stats['avg_tokens_per_dialog'], 'токен', 'токена', 'токенов')}."
        )

    # --- automation
    if class_stats["automation_candidates"] == 0:
        automation_line = (
            f"Ни один из {counted(total, 'диалога', 'диалогов', 'диалогов')} "
            "не помечен кандидатом на автоматизацию."
        )
    else:
        simple_candidates = int(
            ((frame["automation_candidate"]) & (frame["complexity"] == "simple")).sum()
        )
        automation_line = (
            f"Кандидатов на автоматизацию — {class_stats['automation_candidates']} "
            f"из {integer(total)} ({percent(class_stats['automation_ratio'])} %), "
            f"простых среди них {simple_candidates}."
        )
        ready = scenarios[scenarios["automation_share"] > 0].sort_values(
            "automation_share", ascending=False
        )
        if not ready.empty:
            top = ready.iloc[0]
            automation_line += (
                f" Плотнее всего — «{top['use_case']}»: {int(top['dialogs'] * top['automation_share'] / 100)} "
                f"из {counted(top['dialogs'], 'диалога', 'диалогов', 'диалогов')}."
            )

    # --- failures
    if problem_stats["agent_failures"] == 0:
        failures_line = (
            f"Ни в одном из {counted(total, 'диалога', 'диалогов', 'диалогов')} "
            "агент не отметил отказ."
        )
    else:
        failures_line = (
            f"Отказов — {problem_stats['agent_failures']} из {integer(total)} "
            f"({percent(_share(problem_stats['agent_failures'], total))} %)."
        )
        reasons = problem_stats["failure_reasons"]
        if not reasons.empty:
            top = reasons.iloc[0]
            failures_line += f" Чаще всего: «{top['key']}» — {int(top['dialogs'])}."

    # --- usage
    per_user = frame.groupby("user_id").size().sort_values(ascending=False)
    top_count = max(1, round(len(per_user) * 0.2))
    top_share = _share(per_user.head(top_count).sum(), per_user.sum())
    usage_line = (
        f"{counted(len(per_user), 'пользователь', 'пользователя', 'пользователей')}, "
        f"медиана {counted(per_user.median(), 'диалог', 'диалога', 'диалогов')} на человека; "
        f"на верхние 20 % приходится {percent(top_share)} % обращений."
    )
    hours = hourly_load(frame)
    if hours["dialogues"].sum():
        peak = hours.loc[hours["dialogues"].idxmax()]
        usage_line += (
            f" Пик — {int(peak['hour']):02d}:00 UTC "
            f"({counted(peak['dialogues'], 'диалог', 'диалога', 'диалогов')})."
        )

    # --- catalogue
    covered = total - cluster_stats["outliers"]
    if cluster_stats["total_clusters"] == 0:
        catalogue_line = "Кластеризация не выделила ни одного сценария в выбранных строках."
    else:
        catalogue_line = (
            f"{counted(cluster_stats['total_clusters'], 'сценарий', 'сценария', 'сценариев')} "
            f"покрывают {counted(covered, 'диалог', 'диалога', 'диалогов')} "
            f"из {integer(total)}, вне кластеров осталось {cluster_stats['outliers']}."
        )
        if not scenarios.empty:
            top = scenarios.iloc[0]
            catalogue_line += f" Самый частый — «{top['label']}» ({int(top['dialogs'])})."

    # --- profile: the two distributions too flat to deserve a chart
    parts = []
    languages = language_distribution(frame)
    if not languages.empty:
        top = languages.iloc[0]
        parts.append(f"язык: {percent(_share(top['dialogs'], total))} % {top['key']}")
    periodicity = periodicity_distribution(frame)
    if not periodicity.empty:
        repeating = int(periodicity[periodicity["key"] != "none"]["dialogs"].sum())
        parts.append(
            f"повторяющихся задач — {repeating} из {integer(total)}"
            if repeating
            else "повторяющихся задач нет — все разовые"
        )
    profile_line = " · ".join(parts).capitalize() if parts else ""

    return {
        "tokens": tokens_line,
        "automation": automation_line,
        "failures": failures_line,
        "usage": usage_line,
        "catalogue": catalogue_line,
        "profile": profile_line,
    }


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
