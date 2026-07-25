"""Generate SYNTHETIC pipeline output for testing the adapter and dashboard.

Running the real pipeline needs a GPU and a 7B model download, so this script
produces `outputs/dialogs.csv` and `outputs/use_cases.csv` in exactly the shape
`utils.save_dialogs_csv` / `save_use_cases_csv` write them: `;`-joined lists,
free-form tool names, and a few `parse_error` rows. Feeding it to
`analytics_export.py` exercises the whole chain end to end.

    python3 scripts/make_sample_pipeline_output.py

DEMO / SYNTHETIC DATA. Class assignment here is pseudo-random, not the output
of a classifier. `scenario_id` from the source dialogs is deliberately not
consulted: it is legacy metadata and must never become a canonical class_id.
No frequency in these files is observed demand.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import config

#: Row count matches the 115 real dialogs in data/dialogs/.
DEFAULT_ROWS = 115

FAILURE_REASONS = [
    "tool_timeout",
    "missing_permission",
    "integration_unavailable",
    "ambiguous_request",
    "no_matching_records",
]

COMPANY_SOURCES = ["crm", "mailbox", "jira", "isup", "confluence", "calendar", "project_board"]

#: Free-form spellings the LLM realistically emits. Some resolve through the
#: registry aliases, some do not: the unresolvable ones must show up in
#: export_report.json rather than reaching the canonical file.
NOISY_TOOL_NAMES = ["почта", "Web Search", "CRM", "эксель", "quantum_tool", "jira"]
NOISY_INTEGRATION_NAMES = ["Почта", "срм", "Jira", "ISUP", "холодильник", "Excel"]

USE_CASE_NAMES = [
    "Сводка входящей почты",
    "Подготовка отчётности по CRM",
    "Работа с задачами и тикетами",
    "Планирование встреч",
    "Поиск во внутренней базе знаний",
    "Ответы клиентам",
    "Выгрузка данных в Excel",
]

DIALOGS_COLUMNS = [
    "request_id", "dialog_id", "first_user_message", "summary", "goal", "intent",
    "is_work", "automation_candidate", "periodicity", "complexity", "steps_requested",
    "integrations", "integration_count", "tools", "tool_calls", "uses_company_data",
    "company_sources", "requires_generation", "search_type", "contains_sensitive_data",
    "prompt_injection", "agent_failed", "failure_reason", "language", "class_ids",
    "class_names", "classification_scores", "confidence", "user_tokens",
    "assistant_tokens", "tool_tokens", "total_tokens", "estimated_cost",
    "analysis_status", "metadata_confidence",
]


def load_classes(path: Path) -> list[tuple[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [(row["class_id"], row["class_name"]) for row in csv.DictReader(handle)]


def build(rows: int, seed: int, classes: list[tuple[str, str]]):
    rng = random.Random(seed)
    dialogs, use_cases = [], []

    for index in range(1, rows + 1):
        # ~4% of rows fail LLM parsing, as the pipeline's default metadata path
        # does. The adapter must route these to pipeline_errors.csv without
        # ever marking them agent_failed.
        parse_error = rng.random() < 0.04

        selected = rng.sample(classes, k=1 if rng.random() > 0.18 else 2)
        complexity = rng.choices(["simple", "medium", "complex"], weights=[4, 4, 2])[0]
        steps = {"simple": rng.randint(1, 2), "medium": rng.randint(2, 4),
                 "complex": rng.randint(4, 8)}[complexity]

        tools = rng.sample(NOISY_TOOL_NAMES, k=rng.randint(0, 3))
        integrations = rng.sample(NOISY_INTEGRATION_NAMES, k=rng.randint(0, 3))
        tool_calls = 0 if not tools else len(tools) + rng.randint(0, 3)

        failed = rng.random() < {"simple": 0.05, "medium": 0.12, "complex": 0.26}[complexity]
        uses_company = rng.random() < 0.65
        sources = rng.sample(COMPANY_SOURCES, k=rng.randint(1, 2)) if uses_company else []

        user_tokens = rng.randint(120, 2400)
        assistant_tokens = rng.randint(150, 1800)
        # Always zero: the source dialogs carry no role='tool' messages.
        tool_tokens = 0
        total = user_tokens + assistant_tokens + tool_tokens

        scores = [round(rng.uniform(0.31, 0.98), 4) for _ in selected]

        if parse_error:
            dialogs.append({
                "request_id": index, "dialog_id": index,
                "first_user_message": f"[SYNTHETIC] запрос {index}",
                "summary": "", "goal": "", "intent": "",
                "is_work": True, "automation_candidate": False,
                "periodicity": "none", "complexity": "simple", "steps_requested": 1,
                "integrations": "", "integration_count": 0, "tools": "", "tool_calls": 0,
                "uses_company_data": False, "company_sources": "",
                "requires_generation": "", "search_type": "",
                "contains_sensitive_data": False, "prompt_injection": False,
                "agent_failed": True, "failure_reason": "LLM parse error",
                "language": "ru", "class_ids": "", "class_names": "",
                "classification_scores": "", "confidence": 0.0,
                "user_tokens": user_tokens, "assistant_tokens": assistant_tokens,
                "tool_tokens": 0, "total_tokens": total,
                "estimated_cost": round(total / 1000 * 0.0001, 8),
                "analysis_status": "parse_error", "metadata_confidence": 0.0,
            })
        else:
            dialogs.append({
                "request_id": index, "dialog_id": index,
                "first_user_message": f"[SYNTHETIC] запрос {index}",
                "summary": f"[SYNTHETIC] Диалог {index}: {selected[0][1]}.",
                "goal": f"Закрыть задачу «{selected[0][1]}»",
                "intent": f"Поручить агенту «{selected[0][1]}»",
                "is_work": rng.random() < 0.93,
                "automation_candidate": rng.random() < 0.42,
                "periodicity": rng.choices(
                    ["none", "daily", "weekly", "monthly"], weights=[5, 3, 2, 1])[0],
                "complexity": complexity, "steps_requested": steps,
                "integrations": ";".join(integrations), "integration_count": len(integrations),
                "tools": ";".join(tools), "tool_calls": tool_calls,
                "uses_company_data": uses_company, "company_sources": ";".join(sources),
                "requires_generation": ";".join(
                    rng.sample(["text", "excel", "sql", "presentation", "pdf"], k=rng.randint(0, 2))),
                "search_type": ";".join(
                    rng.sample(["internet", "internal"], k=rng.randint(0, 2))),
                "contains_sensitive_data": rng.random() < 0.14,
                "prompt_injection": rng.random() < 0.03,
                "agent_failed": failed,
                "failure_reason": rng.choice(FAILURE_REASONS) if failed else "",
                "language": "ru" if rng.random() < 0.92 else "en",
                "class_ids": ";".join(cid for cid, _ in selected),
                "class_names": ";".join(name for _, name in selected),
                "classification_scores": ";".join(str(s) for s in scores),
                "confidence": max(scores),
                "user_tokens": user_tokens, "assistant_tokens": assistant_tokens,
                "tool_tokens": tool_tokens, "total_tokens": total,
                "estimated_cost": round(total / 1000 * 0.0001, 8),
                "analysis_status": "success", "metadata_confidence": 1.0,
            })

        # HDBSCAN leaves a share of dialogs as noise (cluster -1).
        noise = rng.random() < 0.12
        cluster_id = -1 if noise else rng.randrange(len(USE_CASE_NAMES))
        use_cases.append({
            "request_id": index,
            "cluster_id": cluster_id,
            "use_case": "Прочее" if noise else USE_CASE_NAMES[cluster_id],
            "member_count": rng.randint(5, 30),
        })

    return dialogs, use_cases


def write(rows: list[dict], columns: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument("--outputs", default=str(ROOT / "outputs"))
    args = parser.parse_args()

    classes = load_classes(config.paths.classes_file)
    dialogs, use_cases = build(args.rows, args.seed, classes)

    outputs = Path(args.outputs)
    write(dialogs, DIALOGS_COLUMNS, outputs / "dialogs.csv")
    write(use_cases, ["request_id", "cluster_id", "use_case", "member_count"],
          outputs / "use_cases.csv")

    used = {cid for row in dialogs for cid in row["class_ids"].split(";") if cid}
    print("DEMO / SYNTHETIC DATA")
    print(f"wrote {len(dialogs)} rows to {outputs}/dialogs.csv and use_cases.csv")
    print(f"classes represented: {len(used)}/{len(classes)}")
    print("Class assignment is pseudo-random, not classifier output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
