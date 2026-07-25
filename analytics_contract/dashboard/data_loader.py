"""Load a validated analytics.csv into a DataFrame.

The dashboard refuses to start on a file that violates the contract. Rendering
counts from an invalid file would put numbers in front of a CTO that no check
stands behind, which is exactly what the contract exists to prevent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from analytics_contract.registry import load_project_registries
from analytics_contract.schema import BOOL_COLUMNS, LIST_COLUMNS, NON_NEGATIVE_INT_COLUMNS
from analytics_contract.validation import ValidationResult, validate_analytics


class ContractViolation(RuntimeError):
    """Raised when analytics.csv does not satisfy the canonical contract."""


@dataclass
class Dataset:
    frame: pd.DataFrame
    validation: ValidationResult
    analytics_path: Path
    classes_path: Path

    @property
    def limitations(self) -> list[str]:
        return list(self.validation.limitations)


def load(
    analytics_path: str | Path,
    classes_path: str | Path,
    *,
    enforce_registry: bool = True,
) -> Dataset:
    """Validate, then load. Raises :class:`ContractViolation` on any error."""

    analytics = Path(analytics_path)
    classes = Path(classes_path)

    vocabularies = None
    if enforce_registry:
        loaded = load_project_registries()
        if loaded is not None:
            tools, integrations = loaded
            vocabularies = {"tools": tools, "integrations": integrations}

    result = validate_analytics(analytics, classes, vocabularies=vocabularies)
    if not result.ok:
        preview = "\n".join(
            f"  line {issue.line} [{issue.request_id}] {issue.field}: {issue.message}"
            for issue in result.errors[:10]
        )
        raise ContractViolation(
            f"{analytics} fails the canonical contract with {len(result.errors)} error(s):\n"
            f"{preview}\n\nRun: python -m analytics_contract.validate --analytics {analytics}"
        )

    frame = pd.read_csv(analytics, encoding="utf-8-sig", dtype=str).fillna("")

    for column in LIST_COLUMNS:
        frame[column] = frame[column].map(lambda raw: json.loads(raw) if raw.strip() else [])
    for column in BOOL_COLUMNS:
        frame[column] = frame[column].str.strip().str.lower() == "true"
    for column in NON_NEGATIVE_INT_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    for column in ("confidence", "estimated_cost"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    frame["total_tokens"] = (
        frame["user_tokens"] + frame["assistant_tokens"] + frame["tool_tokens"]
    )

    return Dataset(
        frame=frame, validation=result, analytics_path=analytics, classes_path=classes
    )
