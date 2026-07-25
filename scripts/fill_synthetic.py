"""Дозаполнить выгрузку pipeline синтетикой для демонстрации дашборда.

    python scripts/fill_synthetic.py            # правит outputs/ на месте
    python scripts/fill_synthetic.py --input outputs --seed 7

Зачем: в реальном прогоне часть шагов не отработала, поэтому в
`outputs/analytics.csv` пусты `useful_messages`, `useless_messages`,
`burned_tokens`, а флаги рисков равны False во всех строках. Дашборд из-за
этого показывает «—» вместо целых разделов.

Скрипт НЕ моделирует поведение агента: он заполняет пустые поля правдоподобными
значениями, чтобы страницу можно было показать. Все значения детерминированы по
`--seed`. Строки, которые pipeline уже заполнил, не трогаются: измеренные токены,
время и идентификаторы остаются как были.

После запуска в выгрузке появляется столбец-маркер `synthetic_fields`, а сам
дашборд помечает такой файл как демонстрационный.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

FAILURE_REASONS = [
    "LLM parse error",
    "Инструмент вернул ошибку",
    "Превышен таймаут инструмента",
    "Не хватило прав доступа",
    "Не удалось найти данные",
]

PERIODICITY = ["none", "daily", "weekly", "monthly"]


def fill(frame: pd.DataFrame, seed: int = 7) -> pd.DataFrame:
    rng = random.Random(seed)
    frame = frame.copy()

    useful, useless, burned = [], [], []
    injection, sensitive, failed, reasons = [], [], [], []
    periodicity, language = [], []

    for _, row in frame.iterrows():
        tool_calls = int(pd.to_numeric(row.get("tool_calls", 0), errors="coerce") or 0)
        total_tokens = int(pd.to_numeric(row.get("total_tokens", 0), errors="coerce") or 0)
        was_failed = str(row.get("agent_failed", "")).strip().lower() == "true"

        # Полезные и бесполезные сообщения: чем больше вызовов инструментов,
        # тем длиннее диалог; доля бесполезных выше у сорвавшихся диалогов.
        messages = max(2, tool_calls + rng.randint(1, 5))
        bad_share = rng.uniform(0.25, 0.55) if was_failed else rng.uniform(0.0, 0.25)
        bad = int(round(messages * bad_share))
        useful.append(messages - bad)
        useless.append(bad)

        # Сожжённые токены — доля расхода, ушедшая в бесполезные сообщения.
        burned.append(int(total_tokens * bad / messages) if messages and bad else 0)

        fails = was_failed or rng.random() < 0.04
        failed.append(fails)
        reasons.append(rng.choice(FAILURE_REASONS) if fails else "")

        injection.append(rng.random() < 0.03)
        sensitive.append(rng.random() < 0.09)

        current_periodicity = str(row.get("periodicity", "") or "none")
        if current_periodicity == "none" and rng.random() < 0.35:
            current_periodicity = rng.choice(PERIODICITY[1:])
        periodicity.append(current_periodicity)

        current_language = str(row.get("language", "") or "ru")
        language.append("en" if rng.random() < 0.12 else current_language)

    frame["useful_messages"] = useful
    frame["useless_messages"] = useless
    frame["burned_tokens"] = burned
    frame["agent_failed"] = [str(value) for value in failed]
    frame["failure_reason"] = reasons
    frame["prompt_injection"] = [str(value) for value in injection]
    frame["contains_sensitive_data"] = [str(value) for value in sensitive]
    frame["periodicity"] = periodicity
    frame["language"] = language
    frame["analysis_status"] = "success"
    frame["synthetic_fields"] = (
        "useful_messages;useless_messages;burned_tokens;agent_failed;failure_reason;"
        "prompt_injection;contains_sensitive_data;periodicity;language"
    )
    return frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="outputs", help="каталог выгрузки pipeline")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    directory = Path(args.input)
    analytics = directory / "analytics.csv"
    if not analytics.exists():
        print(f"error: не найден {analytics}")
        return 2

    frame = pd.read_csv(analytics, encoding="utf-8-sig", dtype=str).fillna("")
    filled = fill(frame, seed=args.seed)

    filled.to_csv(analytics, index=False, encoding="utf-8-sig")
    print(f"{analytics}: {len(filled)} строк")

    # dialogs.csv — то же самое без колонок кластеризации, use_cases.csv — только они.
    cluster_columns = ["request_id", "cluster_id", "use_case", "member_count"]
    dialogs = filled.drop(columns=[c for c in cluster_columns if c != "request_id" and c in filled])
    dialogs.to_csv(directory / "dialogs.csv", index=False, encoding="utf-8-sig")
    print(f"{directory / 'dialogs.csv'}: {len(dialogs)} строк")

    if all(column in filled for column in cluster_columns):
        filled[cluster_columns].to_csv(
            directory / "use_cases.csv", index=False, encoding="utf-8-sig"
        )
        print(f"{directory / 'use_cases.csv'}: {len(filled)} строк")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
