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

#: Cost of one working minute. Monthly salary set by the case authors, grossed
#: up by 1.30 for payroll contributions, divided by the 2026 Russian statutory
#: norm of 1972 hours (164.33 h/month): 400000 * 1.30 / 164.33 / 60.
MINUTE_RATE_RUB = 52.7
SALARY_NOTE = "оклад 400 000 ₽ × 1,30 взносы ÷ 164,33 ч/мес ÷ 60 = 52,7 ₽/мин"

#: Working days per month, for scaling an observed daily rate to the month the
#: TCO is quoted for. 2026 statutory norm: 247 working days over 12 months.
WORKING_DAYS_PER_MONTH = 20.6

#: Share of freed time that converts into output rather than into slack.
#: Forrester's TEI studies apply a productivity capture rate in the 50-70% band
#: for exactly this step; the midpoint is used and stated on the card.
CAPTURE_RATE = 0.6

#: Hours in a month of continuous operation, for the electricity line.
HOURS_PER_MONTH = 730.0

#: The effect calculator starts from a round, deliberately editable
#: assumption. It is never presented as something observed in the logs.
DEFAULT_MINUTES_SAVED = 10.0

#: Same monthly norm used to derive the minute rate above.
WORKING_HOURS_PER_MONTH = 164.33


@dataclass(frozen=True)
class CostModel:
    """What the agent costs to run for a month, by component.

    None of this lives in `analytics.csv`: the contract stops at token counts.
    The model is therefore a declared set of inputs rather than a measurement,
    and every figure derived from it is labelled that way. It is kept as a
    dataclass so a single `--tco-*` flag changes one line and the whole screen
    recomputes consistently.

    The default is a pilot-sized deployment: one inference node, one and a half
    engineers keeping it alive. The team line dominates it deliberately —
    that is the true shape of the cost at this volume, and hiding it behind a
    per-token tariff is what makes token economics misleading.
    """

    server_capex_rub: float = 3_000_000.0
    amortization_months: int = 36
    power_kw: float = 3.0
    #: Power usage effectiveness — cooling and conversion overhead on top of
    #: the node's own draw.
    pue: float = 1.5
    electricity_rub_per_kwh: float = 6.0
    support_fte: float = 1.5
    fte_salary_rub: float = 400_000.0
    payroll_multiplier: float = 1.30
    licenses_rub_per_month: float = 0.0

    def components(self) -> dict[str, float]:
        return {
            "Амортизация сервера": self.server_capex_rub / self.amortization_months,
            "Электроэнергия": (
                self.power_kw * self.pue * HOURS_PER_MONTH * self.electricity_rub_per_kwh
            ),
            "Команда поддержки": (
                self.support_fte * self.fte_salary_rub * self.payroll_multiplier
            ),
            "Лицензии и прочее": self.licenses_rub_per_month,
        }

    @property
    def monthly_rub(self) -> float:
        return sum(self.components().values())

    def breakdown(self) -> str:
        """One line per component, for the card tooltip."""

        total = self.monthly_rub or 1.0
        return "\n".join(
            f"{name}: {value:,.0f} ₽/мес ({value / total:.0%})".replace(",", " ")
            for name, value in self.components().items()
            if value
        )


DEFAULT_COST_MODEL = CostModel()

#: Kept for callers that want a plain number rather than the component model.
DEFAULT_TCO_RUB_PER_MONTH = DEFAULT_COST_MODEL.monthly_rub


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


def gini(values: pd.Series) -> float:
    """Concentration of a non-negative distribution, 0 = flat, 1 = one holder.

    Computed from the sorted cumulative share rather than from pairwise
    differences, which is the same number in O(n log n) and is the quantity the
    Lorenz chart already draws.
    """

    ordered = values.sort_values().to_numpy(dtype=float)
    n = len(ordered)
    total = ordered.sum()
    if n == 0 or total <= 0:
        return 0.0
    index = 2 * (pd.RangeIndex(1, n + 1).to_numpy(dtype=float)) - n - 1
    return float((index * ordered).sum() / (n * total))


def adoption(frame: pd.DataFrame) -> dict[str, float]:
    """Who actually uses the agent, and how evenly.

    The contract has no roster of eligible employees, so this is never a
    penetration rate — the denominator is the users the logs contain. What it
    does support is the shape of the distribution, which is the difference
    between a rolled-out tool and a pilot living on a few enthusiasts.
    """

    per_user = frame.groupby("user_id").size().sort_values(ascending=False)
    if per_user.empty:
        return {"users": 0, "median": 0.0, "top_share": 0.0, "gini": 0.0, "max": 0}
    head = max(1, round(len(per_user) * 0.2))
    return {
        "users": len(per_user),
        "median": float(per_user.median()),
        "max": int(per_user.max()),
        "top_share": float(per_user.head(head).sum() / per_user.sum()),
        "gini": gini(per_user),
    }


def observed_days(frame: pd.DataFrame) -> int:
    """Inclusive calendar span covered by the current filtered view."""

    if frame.empty or "created_at" not in frame:
        return 0
    timestamps = frame["created_at"].dropna()
    if timestamps.empty:
        return 0
    return max(1, (timestamps.max().date() - timestamps.min().date()).days + 1)


def mau(frame: pd.DataFrame, window_days: int = 28) -> int:
    """Unique users in the latest rolling 28-day window.

    The card only calls this MAU when the export itself covers at least the
    whole window. On a shorter export the same user identifier supports an
    active-user count, but not a monthly one.
    """

    if frame.empty or "created_at" not in frame:
        return 0
    latest = frame["created_at"].max()
    cutoff = latest - pd.Timedelta(days=window_days - 1)
    return int(frame.loc[frame["created_at"] >= cutoff, "user_id"].nunique())


def lorenz(frame: pd.DataFrame) -> pd.DataFrame:
    """Cumulative share of dialogues against cumulative share of users.

    Both axes are shares of their own total, so the figure keeps one scale and
    the 45-degree line is a built-in reference for perfectly even use.
    """

    per_user = frame.groupby("user_id").size().sort_values()
    if per_user.empty:
        return pd.DataFrame()
    share_users = (pd.RangeIndex(1, len(per_user) + 1) / len(per_user)).to_numpy(dtype=float)
    share_dialogues = (per_user.cumsum() / per_user.sum()).to_numpy(dtype=float)
    return pd.DataFrame(
        {
            "users": [0.0, *share_users],
            "dialogues": [0.0, *share_dialogues],
            "label": ["", *(f"{name}: {count}" for name, count in per_user.items())],
        }
    )


def hourly_load(frame: pd.DataFrame) -> pd.DataFrame:
    """Dialogues by hour of day, UTC.

    Every timestamp in the current export falls on a single date, so this is a
    load profile and never a trend. The dashboard labels it as such: the same
    column drawn against a date axis would be one bar and would invite a
    growth story the data cannot support.
    """

    if frame.empty or "created_at" not in frame:
        return pd.DataFrame()
    hours = frame["created_at"].dt.hour
    counts = hours.value_counts().reindex(range(24), fill_value=0).sort_index()
    return pd.DataFrame({"hour": counts.index, "count": counts.to_numpy()})


def automation_matrix(frame: pd.DataFrame, min_group: int = DEFAULT_MIN_GROUP) -> pd.DataFrame:
    """Complexity x reliance on company data, with the automation share.

    These two axes are chosen because they are the two that actually vary in
    the data and because they separate the work differently: complexity says
    how hard a task is to hand over, company data says whether an external tool
    could ever do it. The cell colour is the share of dialogues the analyser
    marked as automatable, so the chart answers "where do we build first".
    """

    if frame.empty:
        return pd.DataFrame()
    grouped = frame.groupby(["complexity", "uses_company_data"]).agg(
        volume=("request_id", "count"),
        automation=("automation_candidate", "mean"),
        steps=("steps_requested", "median"),
    )
    return grouped[grouped["volume"] >= min_group].reset_index()


def monthly_requests(frame: pd.DataFrame) -> float:
    """Requests per month implied by the observed rate.

    The TCO is quoted per month while the export covers a fraction of one, so
    dividing by the raw row count would inflate the threshold by however short
    the sample happens to be. The observed span is scaled to a month of working
    days instead, and every card built on it says that it is an extrapolation.
    """

    if frame.empty:
        return 0.0
    days = frame["created_at"].dt.date.nunique()
    return len(frame) / days * WORKING_DAYS_PER_MONTH


def breakeven_minutes(
    frame: pd.DataFrame,
    tco_rub: float = DEFAULT_TCO_RUB_PER_MONTH,
    capture_rate: float = CAPTURE_RATE,
) -> float:
    """Minutes one dialogue must save for the system to pay for itself.

    This is the inverse of the usual "we saved N hours" claim and is preferred
    to it deliberately. Every saved-time figure needs a minutes-per-request
    constant that somebody assigns by hand; this metric contains no such
    constant, so it cannot be attacked as an invented number. The reader
    supplies the judgement — whether a dialogue plausibly saves more than the
    threshold — instead of the dashboard supplying it for them.

    It is the exact solution of `benefit_rub(...) == tco_rub`, so the value on
    the card and the crossing point on the economics curve are one number
    computed once.
    """

    per_month = monthly_requests(frame)
    if not per_month or not capture_rate:
        return 0.0
    return tco_rub / (per_month * MINUTE_RATE_RUB * capture_rate)


def monthly_tokens(frame: pd.DataFrame) -> float:
    """Tokens per month implied by the observed rate, same scaling as requests."""

    if frame.empty:
        return 0.0
    days = frame["created_at"].dt.date.nunique()
    return float(frame["total_tokens"].sum()) / days * WORKING_DAYS_PER_MONTH


def saved_capacity(
    frame: pd.DataFrame, minutes_saved: float = DEFAULT_MINUTES_SAVED
) -> dict[str, float]:
    """Monthly hours and FTE implied by an explicit time-saving assumption."""

    hours = monthly_requests(frame) * max(minutes_saved, 0.0) / 60
    return {
        "hours": hours,
        "fte": hours / WORKING_HOURS_PER_MONTH,
    }


def cost_per_million_tokens(frame: pd.DataFrame, model: CostModel) -> float:
    """Fully loaded rouble cost of a million generated tokens.

    This is the answer to "can we price a token?" and the answer is: only
    together with a volume. The numerator is the whole monthly cost of running
    the thing, so the result is a unit cost at the observed utilisation, not a
    property of the model or the hardware. Double the traffic on the same node
    and this figure roughly halves without anything getting cheaper.
    """

    tokens = monthly_tokens(frame)
    return model.monthly_rub / (tokens / 1e6) if tokens else 0.0


def benefit_rub(
    requests_per_month: float, minutes_saved: float, capture_rate: float = CAPTURE_RATE
) -> float:
    """B — money value of the time saved, at a stated minutes-per-request.

    `minutes_saved` is an input, never a measurement: nothing in the contract
    records how long a task would have taken without the agent. The capture
    rate is applied because freed minutes are not automatically re-spent on
    work, which is the step most ROI decks skip.
    """

    return requests_per_month * minutes_saved * MINUTE_RATE_RUB * capture_rate


def economics_curve(
    frame: pd.DataFrame, model: CostModel, max_minutes: float = 20.0, steps: int = 41
) -> pd.DataFrame:
    """B against A over a range of assumed minutes saved per request.

    Drawn as a curve rather than reported as a single ROI number on purpose.
    A single number would hide the one input nobody can measure; a curve puts
    that input on the x-axis and lets the reader place their own judgement on
    it. Where the lines cross is the break-even threshold — the same figure the
    KPI card shows, so the two can be checked against each other.
    """

    requests = monthly_requests(frame)
    if not requests:
        return pd.DataFrame()
    minutes = [max_minutes * index / (steps - 1) for index in range(steps)]
    return pd.DataFrame(
        {
            "minutes": minutes,
            "benefit": [benefit_rub(requests, value) for value in minutes],
            "cost": [model.monthly_rub] * steps,
        }
    )


def kpis(
    frame: pd.DataFrame,
    low_confidence: float,
    top_n: int = 5,
    model: CostModel = DEFAULT_COST_MODEL,
    dropped_failures: int = 0,
    input_rows: int | None = None,
    minutes_saved: float = DEFAULT_MINUTES_SAVED,
) -> list[Kpi]:
    """The five first-screen cards.

    Five rather than seven: a card earns its place only if the underlying field
    both varies in the data and changes a decision. Cards built on
    `estimated_cost` were dropped because that column is `total_tokens` times a
    constant — its correlation with the token count is exactly 1.0 — so a cost
    card is a dialogue count wearing a currency sign. The sensitive-data and
    injection detectors never fire on any row, and a flat 0% is not a finding.
    """

    total = len(frame)
    if total == 0:
        return [Kpi("Нет данных", "0", "Фильтры не оставили ни одной записи")]

    tco_rub = model.monthly_rub
    reach = adoption(frame)
    threshold = breakeven_minutes(frame, tco_rub)
    per_month = monthly_requests(frame)
    token_total = int(frame["total_tokens"].sum())
    token_median = float(frame["total_tokens"].median())
    assistant_share = _share(int(frame["assistant_tokens"].sum()), token_total)
    user_share = _share(int(frame["user_tokens"].sum()), token_total)
    tool_share = _share(int(frame["tool_tokens"].sum()), token_total)
    tool_calls = int(frame["tool_calls"].sum())
    dialogues_with_tools = int((frame["tool_calls"] > 0).sum())
    days = observed_days(frame)
    is_full_month = days >= 28
    active_users = mau(frame) if is_full_month else int(reach["users"])
    capacity = saved_capacity(frame, minutes_saved)

    if token_total >= 1_000_000:
        token_value = f"{token_total / 1_000_000:.1f}".replace(".", ",")
        token_unit = "млн токенов"
    elif token_total >= 1_000:
        token_value = f"{token_total / 1_000:.0f}".replace(".", ",")
        token_unit = "тыс. токенов"
    else:
        token_value = f"{token_total}"
        token_unit = "токенов"

    token_median_text = f"{token_median:,.0f}".replace(",", " ")
    token_detail = (
        f"медиана {token_median_text} на диалог · запрос {user_share:.0%} · "
        f"ответ {assistant_share:.0%} · инструменты {tool_share:.0%}"
    )

    return [
        Kpi(
            label="Порог безубыточности",
            value=f"{threshold:.1f}",
            unit="мин/запрос",
            detail=f"при TCO {tco_rub / 1000:.0f} тыс ₽/мес и ~{per_month:,.0f} запросах в месяц"
                   .replace(",", " "),
            formula=f"Решение уравнения «выгода = затраты»: TCO ÷ (запросов в месяц "
                    f"× {MINUTE_RATE_RUB} ₽/мин × {CAPTURE_RATE:g} коэффициент "
                    f"реализации). Ставка: {SALARY_NOTE}. Запросов в месяц = {total} "
                    f"диалогов за наблюдаемый период, пересчитанные на "
                    f"{WORKING_DAYS_PER_MONTH:g} рабочих дня.\n\n"
                    f"Состав TCO:\n{model.breakdown()}",
            note="Это та же точка, где пересекаются линии на графике «Выгода против "
                 "затрат». Метрика не утверждает, сколько времени сэкономлено, — она "
                 "показывает, сколько нужно экономить на запросе, чтобы выйти в ноль. "
                 "Состав TCO и коэффициент реализации 0,6 (полоса Forrester 50–70%) "
                 "заданы снаружи контракта.",
        ),
        Kpi(
            label="Потреблено токенов",
            value=token_value,
            unit=token_unit,
            detail=token_detail,
            formula="Σ (user_tokens + assistant_tokens + tool_tokens) по показанным "
                    "диалогам. Медиана и доли ролей считаются по тем же строкам.",
            note="Это измеренный расход в доступной выгрузке без пересчёта в месяц "
                 "и без перевода в рубли. Токены инструментов отражают сообщения "
                 "с ролью tool, а не число вызовов.",
        ),
        Kpi(
            label="MAU" if is_full_month else "Активных пользователей",
            value=f"{active_users}",
            unit="чел.",
            detail=f"{days} дн. данных · медиана {reach['median']:.0f} запросов на человека",
            formula=(
                "Уникальные user_id за последние 28 дней выгрузки."
                if is_full_month
                else "Уникальные user_id за весь доступный период выгрузки."
            ),
            note=(
                "Скользящий MAU по последним 28 дням. Для доли проникновения всё ещё "
                "нужен список сотрудников, которым выдан доступ."
                if is_full_month
                else "Это ещё не MAU: доступный период короче 28 дней. После загрузки "
                "полного месяца карточка автоматически переключится на MAU."
            ),
        ),
        Kpi(
            label="Обращения к агенту",
            value=f"{total}",
            unit="диалогов",
            detail=f"инструментальных вызовов: {tool_calls} · "
                   f"в {dialogues_with_tools} из {total} диалогов",
            formula="Число строк после фильтров; вызовы инструментов = Σ tool_calls.",
            note="tool_calls показывает объём инструментальной работы, но не "
                 "успешность отдельных вызовов: пошаговых результатов в контракте нет.",
        ),
        Kpi(
            label="Оценка высвобождённого ресурса",
            value=f"{capacity['fte']:.2f}",
            unit="FTE/мес",
            detail=f"≈ {capacity['hours']:.0f} ч/мес при {minutes_saved:g} мин на запрос",
            formula="Запросов в месяц × выбранные минуты экономии ÷ 60 ÷ "
                    f"{WORKING_HOURS_PER_MONTH:g} рабочих часа в месяц.",
            note="Минуты экономии задаются ползунком и не измерены по логам. Это "
                 "сценарная оценка высвобождённой ёмкости, а не обещание сокращения "
                 "штата.",
        ),
    ]


def usage_ranking(
    frame: pd.DataFrame,
    dimension: str = "use_case",
    metric: str = "dialogues",
    limit: int = 15,
) -> pd.DataFrame:
    """Rank scenarios, classes or users by one measured usage indicator."""

    dimensions = {"use_case", "class_names", "user_id"}
    metrics = {
        "dialogues": ("request_id", "count"),
        "tokens": ("total_tokens", "sum"),
        "tool_calls": ("tool_calls", "sum"),
    }
    if dimension not in dimensions or metric not in metrics or frame.empty:
        return pd.DataFrame()

    source = explode(frame, dimension) if dimension == "class_names" else frame
    grouped = source.groupby(dimension).agg(
        dialogues=("request_id", "count"),
        tokens=("total_tokens", "sum"),
        tool_calls=("tool_calls", "sum"),
    )
    grouped = grouped[grouped[metric] > 0].sort_values(metric, ascending=False).head(limit)
    if grouped.empty:
        return pd.DataFrame()
    return grouped.reset_index().rename(columns={dimension: "key"})


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
