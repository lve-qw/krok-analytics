"""Adapter: pipeline output -> canonical analytics.csv.

Reads the two files the pipeline already writes (`outputs/dialogs.csv` and
`outputs/use_cases.csv`) and produces the canonical contract file. The pipeline
itself is not invoked and its legacy `outputs/analytics.csv` is left untouched.

    python analytics_export.py

Outputs:

    outputs/analytics.canonical.csv   rows that satisfy the contract
    outputs/pipeline_errors.csv       rows excluded, with the reason
    outputs/export_report.json        input / processed / error counts

Why rows are excluded rather than repaired: a row whose LLM analysis failed
carries default values, not observations. Writing a placeholder would present a
parser failure as an analysis result. `agent_failed` is reserved for the agent
under study and is never set from a pipeline failure.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from analytics_contract.registry import Vocabulary, load_project_registries
from analytics_contract.schema import (
    BOOL_COLUMNS,
    NON_NEGATIVE_INT_COLUMNS,
    REQUIRED_COLUMNS,
    REQUIRES_GENERATION_VALUES,
    SEARCH_TYPE_VALUES,
)

LEGACY_LIST_SEPARATOR = ";"

#: Columns of `outputs/pipeline_errors.csv`. Written with a stable header even
#: when nothing was excluded.
ERROR_COLUMNS: tuple[str, ...] = ("request_id", "stage", "reason", "detail")

#: Value used when HDBSCAN assigned a dialog to the noise cluster. Kept as an
#: explicit label so the dashboard can separate it from a real scenario instead
#: of showing the shared noise-cluster name as if it were one.
UNCLUSTERED = "unclustered"


@dataclass
class ExportReport:
    """Counts and diagnostics for one export run."""

    input_rows: int = 0
    exported_rows: int = 0
    error_rows: int = 0
    errors_by_reason: Counter = field(default_factory=Counter)
    unmapped_tools: Counter = field(default_factory=Counter)
    unmapped_integrations: Counter = field(default_factory=Counter)
    dropped_generation_values: Counter = field(default_factory=Counter)
    dropped_search_values: Counter = field(default_factory=Counter)
    unclustered_rows: int = 0
    registry_enforced: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "data_status": "DEMO / SYNTHETIC DATA",
            "counts": {
                "input_rows": self.input_rows,
                "exported_rows": self.exported_rows,
                "error_rows": self.error_rows,
            },
            "errors_by_reason": dict(sorted(self.errors_by_reason.items())),
            "registry": {
                "enforced": self.registry_enforced,
                "unmapped_tools": dict(sorted(self.unmapped_tools.items())),
                "unmapped_integrations": dict(sorted(self.unmapped_integrations.items())),
            },
            "dropped_enum_values": {
                "requires_generation": dict(sorted(self.dropped_generation_values.items())),
                "search_type": dict(sorted(self.dropped_search_values.items())),
            },
            "unclustered_rows": self.unclustered_rows,
            "limitations": [
                "tool_tokens is 0 for every row because the source dialogs contain no "
                "role='tool' messages. This is missing instrumentation, not evidence "
                "that tool execution is free.",
                "estimated_cost covers LLM/API processing only. Infrastructure, GPU and "
                "licence costs are out of scope, so it is not the total cost of ownership "
                "and cannot support an ROI claim.",
                "The source dialogs are synthetic and evenly distributed across scenarios. "
                "No frequency in this file is observed demand.",
                "scenario_id from the source dialogs is legacy/demo metadata and is never "
                "used as a canonical class_id.",
            ],
        }


def _parse_legacy_list(raw: str) -> list[str]:
    """Split the pipeline's `;`-joined list encoding."""

    text = (raw or "").strip()
    if not text:
        return []
    return [item.strip() for item in text.split(LEGACY_LIST_SEPARATOR) if item.strip()]


def _parse_bool(raw: str) -> bool | None:
    text = (raw or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _parse_int(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_float(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _dedupe(values: list[str]) -> list[str]:
    """Drop duplicates, preserving first-seen order."""

    seen: set[str] = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _normalize_against(
    values: list[str], vocabulary: Vocabulary | None, unmapped: Counter
) -> list[str]:
    """Map values onto a closed vocabulary, recording what did not match.

    Unmatched names are dropped from the canonical field and counted in the
    export report. They are never passed through silently: a free-form name in
    the canonical file would fragment `tool.frequency` into synonyms.
    """

    if vocabulary is None:
        return _dedupe(values)
    normalized = []
    for value in values:
        canonical = vocabulary.normalize(value)
        if canonical is None:
            unmapped[value] += 1
            continue
        normalized.append(canonical)
    return _dedupe(normalized)


class _RowConverter:
    """Converts one legacy row, or explains why it cannot be converted."""

    def __init__(
        self,
        row: dict[str, str],
        class_registry: dict[str, str],
        vocabularies: dict[str, Vocabulary | None],
        report: ExportReport,
    ):
        self.row = row
        self.class_registry = class_registry
        self.vocabularies = vocabularies
        self.report = report
        self.request_id = (row.get("request_id") or "").strip()

    def convert(self) -> tuple[dict[str, Any] | None, tuple[str, str, str] | None]:
        """Return ``(canonical_row, None)`` or ``(None, (stage, reason, detail))``."""

        rejection = self._rejection()
        if rejection is not None:
            return None, rejection

        integrations = _normalize_against(
            _parse_legacy_list(self.row.get("integrations", "")),
            self.vocabularies.get("integrations"),
            self.report.unmapped_integrations,
        )
        tools = _normalize_against(
            _parse_legacy_list(self.row.get("tools", "")),
            self.vocabularies.get("tools"),
            self.report.unmapped_tools,
        )

        generation = []
        for value in _dedupe(_parse_legacy_list(self.row.get("requires_generation", ""))):
            if value in REQUIRES_GENERATION_VALUES:
                generation.append(value)
            else:
                self.report.dropped_generation_values[value] += 1

        search = []
        for value in _dedupe(_parse_legacy_list(self.row.get("search_type", ""))):
            if value in SEARCH_TYPE_VALUES:
                search.append(value)
            else:
                self.report.dropped_search_values[value] += 1

        agent_failed = _parse_bool(self.row.get("agent_failed", ""))
        failure_reason = (self.row.get("failure_reason") or "").strip()
        if not agent_failed:
            failure_reason = ""

        uses_company_data = _parse_bool(self.row.get("uses_company_data", ""))
        company_sources = _dedupe(_parse_legacy_list(self.row.get("company_sources", "")))
        if not uses_company_data:
            # The contract forbids sources without the flag. Trust the flag and
            # record the discrepancy rather than flipping the flag silently.
            company_sources = []

        use_case = (self.row.get("use_case") or "").strip()
        cluster_id = _parse_int(self.row.get("cluster_id", ""))
        if not use_case or cluster_id == -1:
            use_case = UNCLUSTERED
            self.report.unclustered_rows += 1

        class_ids = _dedupe(_parse_legacy_list(self.row.get("class_ids", "")))
        class_names = [self.class_registry[class_id] for class_id in class_ids]

        # tool_calls must be > 0 whenever tools are listed. Registry
        # normalization can only shrink the tool list, so re-check afterwards.
        tool_calls = _parse_int(self.row.get("tool_calls", "")) or 0
        if tools and tool_calls == 0:
            tool_calls = len(tools)

        return {
            "request_id": self.request_id,
            "class_ids": class_ids,
            "class_names": class_names,
            "confidence": _parse_float(self.row.get("confidence", "")) or 0.0,
            "summary": (self.row.get("summary") or "").strip(),
            "goal": (self.row.get("goal") or "").strip(),
            "intent": (self.row.get("intent") or "").strip(),
            "is_work": _parse_bool(self.row.get("is_work", "")),
            "automation_candidate": _parse_bool(self.row.get("automation_candidate", "")),
            "periodicity": (self.row.get("periodicity") or "").strip(),
            "complexity": (self.row.get("complexity") or "").strip(),
            "steps_requested": max(_parse_int(self.row.get("steps_requested", "")) or 0, 0),
            "integrations": integrations,
            "integration_count": len(integrations),
            "tools": tools,
            "tool_calls": max(tool_calls, 0),
            "uses_company_data": uses_company_data,
            "company_sources": company_sources,
            "requires_generation": generation,
            "search_type": search,
            "contains_sensitive_data": _parse_bool(self.row.get("contains_sensitive_data", "")),
            "prompt_injection": _parse_bool(self.row.get("prompt_injection", "")),
            "agent_failed": agent_failed,
            "failure_reason": failure_reason,
            "language": (self.row.get("language") or "").strip() or "ru",
            "user_tokens": max(_parse_int(self.row.get("user_tokens", "")) or 0, 0),
            "assistant_tokens": max(_parse_int(self.row.get("assistant_tokens", "")) or 0, 0),
            "tool_tokens": max(_parse_int(self.row.get("tool_tokens", "")) or 0, 0),
            "estimated_cost": max(_parse_float(self.row.get("estimated_cost", "")) or 0.0, 0.0),
            "use_case": use_case,
        }, None

    def _rejection(self) -> tuple[str, str, str] | None:
        """Reasons a row cannot become a canonical record."""

        if not self.request_id:
            return ("ingest", "missing_request_id", "request_id is empty")

        if (self.row.get("analysis_status") or "").strip() == "parse_error":
            # Decision 5: a pipeline failure is not an agent failure. The row is
            # excluded and counted; agent_failed is left alone.
            return ("llm_analysis", "llm_parse_error", "LLM response could not be parsed")

        for column in ("summary", "goal", "intent"):
            if not (self.row.get(column) or "").strip():
                return ("llm_analysis", "empty_text_field", f"{column} is empty")

        class_ids = _dedupe(_parse_legacy_list(self.row.get("class_ids", "")))
        if not class_ids:
            return ("classification", "no_class_assigned", "class_ids is empty")
        unknown = [class_id for class_id in class_ids if class_id not in self.class_registry]
        if unknown:
            return (
                "classification",
                "unknown_class_id",
                f"not in the 31-class registry: {', '.join(sorted(unknown))}",
            )

        for column in ("is_work", "automation_candidate", "uses_company_data",
                       "contains_sensitive_data", "prompt_injection", "agent_failed"):
            if _parse_bool(self.row.get(column, "")) is None:
                return ("ingest", "unparsable_boolean", f"{column}={self.row.get(column)!r}")

        confidence = _parse_float(self.row.get("confidence", ""))
        if confidence is None or not 0.0 <= confidence <= 1.0:
            return ("classification", "confidence_out_of_range", f"confidence={self.row.get('confidence')!r}")

        agent_failed = _parse_bool(self.row.get("agent_failed", ""))
        if agent_failed and not (self.row.get("failure_reason") or "").strip():
            return ("llm_analysis", "failure_without_reason", "agent_failed is true with no reason")

        return None


def load_class_registry(path: Path) -> dict[str, str]:
    """Load `class_id -> class_name` from the canonical 31-class registry."""

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if "class_id" not in fieldnames or "class_name" not in fieldnames:
            raise ValueError(f"{path}: expected columns 'class_id' and 'class_name'")
        registry = {row["class_id"].strip(): row["class_name"].strip() for row in reader}
    if not registry:
        raise ValueError(f"{path}: registry is empty")
    return registry


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _serialize(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def export(
    dialogs_path: Path,
    use_cases_path: Path,
    output_path: Path,
    errors_path: Path,
    report_path: Path,
    classes_path: Path,
    *,
    enforce_registry: bool = True,
) -> ExportReport:
    """Convert the pipeline output into the canonical contract file."""

    class_registry = load_class_registry(classes_path)

    vocabularies: dict[str, Vocabulary | None] = {"tools": None, "integrations": None}
    report = ExportReport()
    if enforce_registry:
        loaded = load_project_registries()
        if loaded is not None:
            tools, integrations = loaded
            vocabularies = {"tools": tools, "integrations": integrations}
            report.registry_enforced = True

    dialogs = _read_rows(dialogs_path)
    use_cases = {
        (row.get("request_id") or "").strip(): row for row in _read_rows(use_cases_path)
    } if use_cases_path.exists() else {}

    canonical_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, str]] = []

    for row in dialogs:
        report.input_rows += 1
        merged = dict(row)
        merged.update(
            {
                key: value
                for key, value in (use_cases.get((row.get("request_id") or "").strip()) or {}).items()
                if key != "request_id"
            }
        )
        converted, rejection = _RowConverter(merged, class_registry, vocabularies, report).convert()
        if rejection is not None:
            stage, reason, detail = rejection
            report.error_rows += 1
            report.errors_by_reason[reason] += 1
            error_rows.append(
                {
                    "request_id": (row.get("request_id") or "").strip(),
                    "stage": stage,
                    "reason": reason,
                    "detail": detail,
                }
            )
            continue
        report.exported_rows += 1
        canonical_rows.append(converted)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(REQUIRED_COLUMNS)
        for canonical in canonical_rows:
            writer.writerow([_serialize(canonical[column]) for column in REQUIRED_COLUMNS])

    with errors_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ERROR_COLUMNS))
        writer.writeheader()
        writer.writerows(error_rows)

    report_path.write_text(
        json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dialogs", default="outputs/dialogs.csv")
    parser.add_argument("--use-cases", default="outputs/use_cases.csv")
    parser.add_argument("--classes", default="data/classes_31.csv")
    parser.add_argument("--output", default="outputs/analytics.canonical.csv")
    parser.add_argument("--errors", default="outputs/pipeline_errors.csv")
    parser.add_argument("--report", default="outputs/export_report.json")
    parser.add_argument(
        "--no-registry-check",
        action="store_true",
        help="do not normalize tools/integrations against the project registries",
    )
    args = parser.parse_args(argv)

    dialogs_path = Path(args.dialogs)
    if not dialogs_path.exists():
        print(f"error: {dialogs_path} not found; run the pipeline first", file=sys.stderr)
        return 2

    try:
        report = export(
            dialogs_path,
            Path(args.use_cases),
            Path(args.output),
            Path(args.errors),
            Path(args.report),
            Path(args.classes),
            enforce_registry=not args.no_registry_check,
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print("DEMO / SYNTHETIC DATA")
    print(f"input rows:     {report.input_rows}")
    print(f"exported rows:  {report.exported_rows}  -> {args.output}")
    print(f"error rows:     {report.error_rows}  -> {args.errors}")
    if report.errors_by_reason:
        for reason, count in sorted(report.errors_by_reason.items()):
            print(f"  {reason}: {count}")
    if report.unmapped_tools or report.unmapped_integrations:
        print("unmapped registry values (dropped, see export_report.json):")
        for name, counter in (("tools", report.unmapped_tools), ("integrations", report.unmapped_integrations)):
            if counter:
                print(f"  {name}: {', '.join(sorted(counter))}")
    print(f"report:         {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
