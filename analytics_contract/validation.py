"""Reusable validation of ``analytics.csv`` against the canonical contract.

The validator never modifies the input file. It returns a
:class:`ValidationResult` holding every issue found, each carrying the CSV line
number, the ``request_id``, the offending field and a stable machine-readable
code.

Two severities are used:

``error``
    the CSV contract is violated; the file must not be consumed downstream.
``warning``
    the row is contractually valid but the combination of values is
    suspicious. Warnings never fail the run on their own.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from analytics_contract.registry import Vocabulary
from analytics_contract.schema import (
    BOOL_COLUMNS,
    CREATED_AT_FORMAT,
    ENUM_VALUES,
    FALSE_LITERALS,
    LIST_COLUMNS,
    NON_BLANK_TEXT_COLUMNS,
    NON_EMPTY_LIST_COLUMNS,
    NON_NEGATIVE_INT_COLUMNS,
    NULL_LITERALS,
    REQUIRED_COLUMNS,
    SCHEMA_VERSION,
    TRUE_LITERALS,
)

ERROR = "error"
WARNING = "warning"

#: Below this confidence a row is flagged for review. Configurable because the
#: right cut-off depends on the classifier, which is not selected yet.
DEFAULT_LOW_CONFIDENCE = 0.5

#: A row is flagged as a cost/token outlier when its value exceeds this factor
#: times the sample median. A median-relative rule is used instead of a
#: mean/standard-deviation rule because the distribution is expected to be
#: heavy-tailed, which would inflate the standard deviation and hide outliers.
DEFAULT_OUTLIER_FACTOR = 10.0

#: Below this many rows the sample is too small for a median-relative outlier
#: rule to mean anything, so the statistical warnings are skipped.
MIN_ROWS_FOR_OUTLIER_CHECK = 20

#: Stable header of ``validation_errors.csv``. Written even when there are no
#: issues, so downstream consumers can rely on the columns existing.
ERROR_CSV_HEADER: tuple[str, ...] = ("line", "request_id", "field", "severity", "code", "message")

#: Column names accepted as the human-readable class name in ``classes.csv``.
_CLASS_NAME_COLUMNS = ("class_name", "name", "title", "label")


@dataclass(frozen=True)
class Issue:
    """One validation finding.

    ``line`` is the physical line number in the CSV file (the header is line 1),
    so it points at what an operator sees when opening the file. It is ``0`` for
    file-level issues that belong to no particular row.
    """

    line: int
    request_id: str
    field: str
    severity: str
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "request_id": self.request_id,
            "field": self.field,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    """Outcome of one validation run."""

    issues: list[Issue] = field(default_factory=list)
    row_count: int = 0
    missing_columns: list[str] = field(default_factory=list)
    unknown_columns: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    analytics_path: str = ""
    classes_path: str = ""

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == WARNING]

    @property
    def ok(self) -> bool:
        """True when the file honours the contract. Warnings do not fail it."""

        return not self.errors

    @property
    def status(self) -> str:
        if self.errors:
            return "fail"
        return "pass_with_warnings" if self.warnings else "pass"

    def report(self) -> dict[str, Any]:
        """Machine-readable summary written to ``validation_report.json``."""

        by_code: dict[str, int] = {}
        for issue in self.issues:
            by_code[issue.code] = by_code.get(issue.code, 0) + 1
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "analytics_path": self.analytics_path,
            "classes_path": self.classes_path,
            "row_count": self.row_count,
            "columns": {
                "missing": sorted(self.missing_columns),
                "unknown": sorted(self.unknown_columns),
            },
            "counts": {
                ERROR: len(self.errors),
                WARNING: len(self.warnings),
            },
            "by_code": dict(sorted(by_code.items())),
            "config": dict(sorted(self.config.items())),
            "limitations": list(self.limitations),
        }


class ClassRegistry:
    """``classes.csv`` loaded into an id set and an optional id->name map.

    The delivered ``classes.csv`` carries only ``class_id`` and a long
    ``description``. A long description is not a usable class *name*, so the
    name column is treated as optional: when it is absent, ``class_names``
    cannot be verified against the registry and the caller records that as an
    explicit limitation rather than inventing short names.
    """

    def __init__(self, ids: list[str], names: dict[str, str] | None, name_column: str | None):
        self.ids = set(ids)
        self.ordered_ids = ids
        self.names = names
        self.name_column = name_column

    @property
    def has_names(self) -> bool:
        return self.names is not None


def load_class_registry(path: str | Path) -> ClassRegistry:
    """Read ``classes.csv``. Raises ``ValueError`` on a malformed registry."""

    registry_path = Path(path)
    with registry_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if "class_id" not in fieldnames:
            raise ValueError(f"{registry_path}: missing required column 'class_id'")
        name_column = next((column for column in _CLASS_NAME_COLUMNS if column in fieldnames), None)

        ids: list[str] = []
        names: dict[str, str] = {}
        for row in reader:
            class_id = (row.get("class_id") or "").strip()
            if not class_id:
                raise ValueError(f"{registry_path}: empty class_id on line {reader.line_num}")
            if class_id in ids:
                raise ValueError(f"{registry_path}: duplicate class_id {class_id!r}")
            ids.append(class_id)
            if name_column is not None:
                names[class_id] = (row.get(name_column) or "").strip()

    if not ids:
        raise ValueError(f"{registry_path}: registry is empty")
    return ClassRegistry(ids, names if name_column is not None else None, name_column)


def _parse_json_list(raw: str) -> tuple[list[str] | None, str | None]:
    """Parse a JSON array of strings. Returns ``(value, error_message)``."""

    text = (raw or "").strip()
    if not text:
        return None, "value is empty; expected a JSON array such as []"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        return None, f"not valid JSON ({error.msg}); pipe/comma separated values are not accepted"
    if not isinstance(parsed, list):
        return None, f"expected a JSON array, got {type(parsed).__name__}"
    if not all(isinstance(item, str) for item in parsed):
        return None, "all array elements must be strings"
    if any(not item.strip() for item in parsed):
        return None, "array contains a blank string"
    return [item.strip() for item in parsed], None


def _parse_bool(raw: str) -> bool | None:
    text = (raw or "").strip().lower()
    if text in TRUE_LITERALS:
        return True
    if text in FALSE_LITERALS:
        return False
    return None


def _parse_int(raw: str) -> tuple[int | None, bool]:
    """Parse a non-negative integer. Returns ``(value, was_float_encoded)``.

    ``5.0`` is accepted as ``5`` because a CSV written by a dataframe with any
    missing value in the column will encode integers as floats. The float
    encoding is reported back so the caller can raise a warning.
    """

    text = (raw or "").strip()
    if not text:
        return None, False
    try:
        return int(text), False
    except ValueError:
        pass
    try:
        as_float = float(text)
    except ValueError:
        return None, False
    if math.isfinite(as_float) and as_float.is_integer():
        return int(as_float), True
    return None, False


def _parse_float(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


class _RowValidator:
    """Validates one row and collects its issues and parsed values."""

    def __init__(
        self,
        line: int,
        row: dict[str, str],
        registry: ClassRegistry,
        config: dict[str, Any],
        vocabularies: dict[str, Vocabulary] | None = None,
    ):
        self.line = line
        self.row = row
        self.registry = registry
        self.config = config
        self.vocabularies = vocabularies or {}
        self.issues: list[Issue] = []
        self.values: dict[str, Any] = {}
        self.request_id = (row.get("request_id") or "").strip()

    def add(self, field_name: str, severity: str, code: str, message: str) -> None:
        self.issues.append(
            Issue(
                line=self.line,
                request_id=self.request_id,
                field=field_name,
                severity=severity,
                code=code,
                message=message,
            )
        )

    def run(self) -> None:
        self._check_request_id()
        self._check_created_at()
        self._check_lists()
        self._check_vocabularies()
        self._check_classes()
        self._check_confidence()
        self._check_text()
        self._check_scalar_enums()
        self._check_numbers()
        self._check_booleans()
        self._check_cross_fields()

    def _check_request_id(self) -> None:
        if not self.request_id:
            self.add("request_id", ERROR, "request_id_blank", "request_id must be a non-empty string")
        self.values["request_id"] = self.request_id

    def _check_created_at(self) -> None:
        """Parse ``created_at`` as a UTC instant, rejecting anything looser.

        The value is stored parsed so the dashboard never re-parses strings and
        cannot disagree with the validator about what a timestamp means.
        """

        raw = (self.row.get("created_at") or "").strip()
        if not raw:
            self.add("created_at", ERROR, "created_at_blank", "created_at must be a UTC timestamp")
            return
        try:
            self.values["created_at"] = datetime.strptime(raw, CREATED_AT_FORMAT).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            self.add(
                "created_at",
                ERROR,
                "created_at_malformed",
                f"expected {CREATED_AT_FORMAT} in UTC, got {raw!r}",
            )

    def _check_lists(self) -> None:
        for column in sorted(LIST_COLUMNS):
            if column not in self.row:
                continue
            parsed, error = _parse_json_list(self.row[column])
            if error is not None:
                self.add(column, ERROR, "list_malformed", error)
                continue
            if len(set(parsed)) != len(parsed):
                duplicates = sorted({item for item in parsed if parsed.count(item) > 1})
                self.add(
                    column,
                    ERROR,
                    "list_duplicates",
                    f"duplicate values are not allowed: {', '.join(duplicates)}",
                )
                continue
            if not parsed and column in NON_EMPTY_LIST_COLUMNS:
                self.add(column, ERROR, "list_empty", "must contain at least one value")
                continue
            allowed = ENUM_VALUES.get(column)
            if allowed is not None:
                unknown = sorted(set(parsed) - allowed)
                if unknown:
                    self.add(
                        column,
                        ERROR,
                        "enum_unknown",
                        f"unknown value(s) {', '.join(unknown)}; allowed: {', '.join(sorted(allowed))}",
                    )
                    continue
            self.values[column] = parsed

    def _check_vocabularies(self) -> None:
        """Check `tools` and `integrations` against the closed registries.

        Only runs when a vocabulary was supplied. The adapter is expected to
        have normalized these values already, so anything unknown here means a
        free-form name reached the canonical file.
        """

        for column, vocabulary in self.vocabularies.items():
            values = self.values.get(column)
            if values is None:
                continue
            unknown = [value for value in values if value not in vocabulary]
            if unknown:
                self.add(
                    column,
                    ERROR,
                    "registry_unknown",
                    f"not in the {vocabulary.name} registry: {', '.join(sorted(unknown))}",
                )

    def _check_classes(self) -> None:
        class_ids = self.values.get("class_ids")
        class_names = self.values.get("class_names")
        if class_ids is None or class_names is None:
            return
        if len(class_ids) != len(class_names):
            self.add(
                "class_names",
                ERROR,
                "class_length_mismatch",
                f"class_ids has {len(class_ids)} item(s) but class_names has {len(class_names)}",
            )
            return
        unknown = [class_id for class_id in class_ids if class_id not in self.registry.ids]
        if unknown:
            self.add(
                "class_ids",
                ERROR,
                "class_id_unknown",
                f"not present in classes.csv: {', '.join(sorted(unknown))}",
            )
        if not self.registry.has_names:
            return
        for class_id, class_name in zip(class_ids, class_names):
            expected = self.registry.names.get(class_id)
            if expected is not None and class_name != expected:
                self.add(
                    "class_names",
                    ERROR,
                    "class_name_mismatch",
                    f"{class_id!r} is named {expected!r} in classes.csv, got {class_name!r}",
                )

    def _check_confidence(self) -> None:
        if "confidence" not in self.row:
            return
        value = _parse_float(self.row["confidence"])
        if value is None:
            self.add("confidence", ERROR, "number_malformed", "must be a finite number")
            return
        if not 0.0 <= value <= 1.0:
            self.add("confidence", ERROR, "confidence_out_of_range", f"must be within [0, 1], got {value}")
            return
        self.values["confidence"] = value
        if value < self.config["low_confidence_threshold"]:
            self.add(
                "confidence",
                WARNING,
                "confidence_low",
                f"{value} is below the review threshold {self.config['low_confidence_threshold']}",
            )

    def _check_text(self) -> None:
        for column in NON_BLANK_TEXT_COLUMNS:
            if column not in self.row:
                continue
            value = self.row[column]
            if not isinstance(value, str) or not value.strip():
                self.add(column, ERROR, "text_blank", "must be a non-blank string")
                continue
            self.values[column] = value.strip()

    def _check_scalar_enums(self) -> None:
        for column in ("periodicity", "complexity"):
            if column not in self.row:
                continue
            value = (self.row[column] or "").strip()
            allowed = ENUM_VALUES[column]
            if value not in allowed:
                self.add(
                    column,
                    ERROR,
                    "enum_unknown",
                    f"unknown value {value!r}; allowed: {', '.join(sorted(allowed))}",
                )
                continue
            self.values[column] = value

    def _check_numbers(self) -> None:
        for column in NON_NEGATIVE_INT_COLUMNS:
            if column not in self.row:
                continue
            value, float_encoded = _parse_int(self.row[column])
            if value is None:
                self.add(column, ERROR, "int_malformed", "must be an integer")
                continue
            if value < 0:
                self.add(column, ERROR, "int_negative", f"must be >= 0, got {value}")
                continue
            if float_encoded:
                self.add(
                    column,
                    WARNING,
                    "int_float_encoded",
                    f"integer written as a float ({self.row[column].strip()!r})",
                )
            self.values[column] = value

        if "estimated_cost" in self.row:
            cost = _parse_float(self.row["estimated_cost"])
            if cost is None:
                self.add("estimated_cost", ERROR, "number_malformed", "must be a finite number")
            elif cost < 0:
                self.add("estimated_cost", ERROR, "cost_negative", f"must be >= 0, got {cost}")
            else:
                self.values["estimated_cost"] = cost

    def _check_booleans(self) -> None:
        for column in sorted(BOOL_COLUMNS):
            if column not in self.row:
                continue
            value = _parse_bool(self.row[column])
            if value is None:
                self.add(
                    column,
                    ERROR,
                    "bool_unrecognized",
                    f"expected 'true' or 'false' (case-insensitive), got {(self.row[column] or '').strip()!r}",
                )
                continue
            self.values[column] = value

    def _check_cross_fields(self) -> None:
        self._check_integration_count()
        self._check_tools()
        self._check_company_data()
        self._check_failure()
        self._check_automation()
        self._check_complexity_steps()

    def _check_integration_count(self) -> None:
        integrations = self.values.get("integrations")
        count = self.values.get("integration_count")
        if integrations is None or count is None:
            return
        if count != len(integrations):
            self.add(
                "integration_count",
                ERROR,
                "integration_count_mismatch",
                f"expected {len(integrations)} (len of integrations), got {count}",
            )

    def _check_tools(self) -> None:
        tools = self.values.get("tools")
        tool_calls = self.values.get("tool_calls")
        if tools is None or tool_calls is None:
            return
        # tool_calls may exceed len(tools): the same tool can be called repeatedly.
        if tools and tool_calls == 0:
            self.add(
                "tool_calls",
                ERROR,
                "tools_without_calls",
                f"tools lists {len(tools)} tool(s) but tool_calls is 0",
            )
        elif not tools and tool_calls > 0:
            self.add(
                "tools",
                WARNING,
                "calls_without_tools",
                f"tool_calls is {tool_calls} but no tool names were recorded",
            )

    def _check_company_data(self) -> None:
        uses = self.values.get("uses_company_data")
        sources = self.values.get("company_sources")
        if uses is None or sources is None:
            return
        if not uses and sources:
            self.add(
                "company_sources",
                ERROR,
                "company_sources_unexpected",
                f"must be empty when uses_company_data is false, got {sources}",
            )
        elif uses and not sources:
            # Downgraded to a warning: the source is not always identifiable
            # from the payload, and losing the whole row over it would hide the
            # company-data signal itself.
            self.add(
                "company_sources",
                WARNING,
                "company_sources_missing",
                "uses_company_data is true but no source is identified",
            )

    def _check_failure(self) -> None:
        failed = self.values.get("agent_failed")
        if failed is None or "failure_reason" not in self.row:
            return
        reason = (self.row["failure_reason"] or "").strip()
        is_null = reason.lower() in NULL_LITERALS
        if failed and is_null:
            self.add(
                "failure_reason",
                ERROR,
                "failure_reason_missing",
                "must be a non-empty string when agent_failed is true",
            )
        elif not failed and not is_null:
            self.add(
                "failure_reason",
                ERROR,
                "failure_reason_unexpected",
                f"must be empty or null when agent_failed is false, got {reason!r}",
            )
        else:
            self.values["failure_reason"] = "" if is_null else reason

    def _check_automation(self) -> None:
        candidate = self.values.get("automation_candidate")
        periodicity = self.values.get("periodicity")
        if candidate and periodicity == "none":
            self.add(
                "periodicity",
                WARNING,
                "automation_without_periodicity",
                "automation_candidate is true but the request is not recurring",
            )

    def _check_complexity_steps(self) -> None:
        complexity = self.values.get("complexity")
        steps = self.values.get("steps_requested")
        if complexity == "complex" and steps == 0:
            self.add(
                "steps_requested",
                WARNING,
                "complex_without_steps",
                "complexity is 'complex' but no steps were requested",
            )


def _outlier_issues(
    rows: list[tuple[int, dict[str, Any]]],
    column: str,
    code: str,
    factor: float,
    label: str,
) -> list[Issue]:
    """Flag rows whose value exceeds ``factor`` times the sample median."""

    samples = [
        (line, str(values.get("request_id", "")), values[column])
        for line, values in rows
        if isinstance(values.get(column), (int, float))
    ]
    if len(samples) < MIN_ROWS_FOR_OUTLIER_CHECK:
        return []
    median = statistics.median(value for _, _, value in samples)
    if median <= 0:
        return []
    threshold = median * factor
    return [
        Issue(
            line=line,
            request_id=request_id,
            field=column,
            severity=WARNING,
            code=code,
            message=f"{label} {value:g} exceeds {factor:g}x the sample median ({median:g})",
        )
        for line, request_id, value in samples
        if value > threshold
    ]


def validate_analytics(
    analytics_path: str | Path,
    classes_path: str | Path,
    *,
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE,
    outlier_factor: float = DEFAULT_OUTLIER_FACTOR,
    vocabularies: dict[str, Vocabulary] | None = None,
) -> ValidationResult:
    """Validate ``analytics.csv`` against the canonical contract.

    The input file is only read. Rows are validated independently first, then
    file-level checks (uniqueness, statistical outliers) run over the parsed
    values.

    ``vocabularies`` maps a list column onto a closed
    :class:`~analytics_contract.registry.Vocabulary`. Supply
    ``{"tools": ..., "integrations": ...}`` to enforce the project registries;
    omit it to check those columns for shape only.
    """

    analytics = Path(analytics_path)
    registry = load_class_registry(classes_path)
    config = {
        "low_confidence_threshold": low_confidence_threshold,
        "outlier_factor": outlier_factor,
        "min_rows_for_outlier_check": MIN_ROWS_FOR_OUTLIER_CHECK,
        "registry_checks": sorted(vocabularies) if vocabularies else [],
    }
    result = ValidationResult(
        config=config,
        analytics_path=str(analytics),
        classes_path=str(Path(classes_path)),
    )

    if not registry.has_names:
        result.limitations.append(
            "classes.csv carries no class-name column (only class_id and description), "
            "so class_names cannot be verified against the registry; only the class_ids "
            "themselves and the class_ids/class_names length agreement are checked."
        )
    if not vocabularies:
        result.limitations.append(
            "No tools/integrations vocabulary was supplied, so those columns are checked "
            "for shape and uniqueness only. Pass the project registries to close them."
        )
    result.limitations.append(
        "The contract carries no request_text, so verbatim-request checks are out of "
        "scope by construction."
    )
    result.limitations.append(
        "tool_tokens counts only messages with role='tool'. A zero total means no such "
        "message was present in the source logs, not that tool execution was free."
    )
    result.limitations.append(
        "estimated_cost covers LLM/API processing only. Infrastructure, GPU and license "
        "costs are outside the contract, so it is not the total cost of ownership."
    )

    with analytics.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])

        present = set(fieldnames)
        result.missing_columns = [column for column in REQUIRED_COLUMNS if column not in present]
        result.unknown_columns = [column for column in fieldnames if column not in REQUIRED_COLUMNS]

        for column in result.missing_columns:
            result.issues.append(
                Issue(0, "", column, ERROR, "column_missing", "required column is absent from the header")
            )
        for column in result.unknown_columns:
            hint = (
                f"; the header is also missing {', '.join(result.missing_columns)} — check for a renamed column"
                if result.missing_columns
                else ""
            )
            result.issues.append(
                Issue(0, "", column, WARNING, "column_unknown", f"column is not part of the contract{hint}")
            )

        parsed_rows: list[tuple[int, dict[str, Any]]] = []
        seen_request_ids: dict[str, int] = {}
        for row in reader:
            line = reader.line_num
            result.row_count += 1
            validator = _RowValidator(line, row, registry, config, vocabularies)
            validator.run()
            result.issues.extend(validator.issues)
            parsed_rows.append((line, validator.values))

            request_id = validator.request_id
            if request_id:
                first_line = seen_request_ids.get(request_id)
                if first_line is not None:
                    result.issues.append(
                        Issue(
                            line,
                            request_id,
                            "request_id",
                            ERROR,
                            "request_id_duplicate",
                            f"already used on line {first_line}",
                        )
                    )
                else:
                    seen_request_ids[request_id] = line

    result.issues.extend(
        _outlier_issues(parsed_rows, "estimated_cost", "cost_outlier", outlier_factor, "estimated_cost")
    )
    total_token_rows = [
        (
            line,
            {
                **values,
                "total_tokens": sum(
                    values.get(column, 0)
                    for column in ("user_tokens", "assistant_tokens", "tool_tokens")
                    if isinstance(values.get(column), int)
                ),
            },
        )
        for line, values in parsed_rows
    ]
    result.issues.extend(
        _outlier_issues(total_token_rows, "total_tokens", "tokens_outlier", outlier_factor, "total tokens")
    )
    result.limitations.extend(_derived_limitations(total_token_rows))

    result.issues.sort(key=lambda issue: (issue.line, issue.field, issue.code, issue.request_id))
    return result


def _derived_limitations(rows: list[tuple[int, dict[str, Any]]]) -> list[str]:
    """Limitations the file itself proves, rather than ones assumed up front.

    Both checks below exist because the numbers they qualify look informative
    and are not. They are emitted from the data so that a future export which
    fixes the underlying pipeline stops carrying the caveat automatically.
    """

    limitations: list[str] = []

    ratios = {
        round(values["estimated_cost"] / values["total_tokens"], 12)
        for _, values in rows
        if values.get("total_tokens") and isinstance(values.get("estimated_cost"), float)
    }
    if len(ratios) == 1:
        rate = next(iter(ratios))
        limitations.append(
            f"estimated_cost is exactly total_tokens * {rate:g} on every row, so it carries "
            "no information the token count does not already carry. Any ranking or "
            "concentration computed on cost is the same ranking computed on volume, and "
            "a per-model or per-tier tariff is needed before cost can be read as cost."
        )

    dates = {values["created_at"].date() for _, values in rows if values.get("created_at")}
    if len(dates) == 1:
        limitations.append(
            f"Every created_at falls on {next(iter(dates))}, so the export supports an "
            "hour-of-day load profile but no trend, no retention and no monthly active "
            "users. Any figure quoted per month is an extrapolation from a single day."
        )

    return limitations


def write_reports(result: ValidationResult, output_dir: str | Path) -> tuple[Path, Path]:
    """Write ``validation_report.json`` and ``validation_errors.csv``.

    ``validation_errors.csv`` is always written with its stable header, even
    when there is nothing to report.
    """

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    report_path = directory / "validation_report.json"
    report_path.write_text(
        json.dumps(result.report(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    errors_path = directory / "validation_errors.csv"
    with errors_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(ERROR_CSV_HEADER)
        for issue in result.issues:
            writer.writerow([issue.line, issue.request_id, issue.field, issue.severity, issue.code, issue.message])

    return report_path, errors_path


def format_summary(result: ValidationResult, *, max_issues: int = 20) -> str:
    """Human-readable console summary."""

    lines = [
        f"analytics: {result.analytics_path}",
        f"classes:   {result.classes_path}",
        f"rows:      {result.row_count}",
        f"status:    {result.status.upper()}  ({len(result.errors)} error(s), {len(result.warnings)} warning(s))",
    ]
    shown: Iterable[Issue] = result.errors + result.warnings
    shown = list(shown)[:max_issues]
    if shown:
        lines.append("")
        for issue in shown:
            location = f"line {issue.line}" if issue.line else "header"
            request = f" [{issue.request_id}]" if issue.request_id else ""
            lines.append(
                f"  {issue.severity.upper():<7} {location}{request} {issue.field}: {issue.message} ({issue.code})"
            )
        remaining = len(result.issues) - len(shown)
        if remaining > 0:
            lines.append(f"  ... {remaining} more issue(s); see validation_errors.csv")
    if result.limitations:
        lines.append("")
        lines.append("Limitations of this validation:")
        lines.extend(f"  - {limitation}" for limitation in result.limitations)
    return "\n".join(lines)
