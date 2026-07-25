"""Parse the pipeline CSV exports into one typed DataFrame.

The pipeline writes three files into ``outputs/``: ``dialogs.csv`` (one row per
request), ``use_cases.csv`` (cluster of every request) and ``analytics.csv``
(the two already joined). The dashboard accepts either the joined file or the
pair, so a run that stopped before the join is still viewable.

Every column is cast here and nowhere else. A number shown on the page has to
come from a parsed value, not from a string that happened to look numeric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

CREATED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

#: Written by the LLM analyser and the classifiers, not measured from the log.
DERIVED_COLUMNS = (
    "summary",
    "goal",
    "intent",
    "is_work",
    "automation_candidate",
    "periodicity",
    "complexity",
    "steps_requested",
    "contains_sensitive_data",
    "prompt_injection",
    "agent_failed",
    "failure_reason",
    "class_ids",
    "class_names",
    "confidence",
    "useful_messages",
    "useless_messages",
    "burned_tokens",
    "cluster_id",
    "use_case",
)

BOOL_COLUMNS = (
    "is_work",
    "automation_candidate",
    "uses_company_data",
    "requires_generation",
    "contains_sensitive_data",
    "prompt_injection",
    "agent_failed",
)

INT_COLUMNS = (
    "steps_requested",
    "integration_count",
    "tool_calls",
    "user_tokens",
    "assistant_tokens",
    "tool_tokens",
    "total_tokens",
    "burned_tokens",
    "useful_messages",
    "useless_messages",
    "member_count",
)

FLOAT_COLUMNS = ("confidence", "metadata_confidence", "estimated_cost")

LIST_COLUMNS = ("integrations", "tools", "company_sources", "class_ids", "class_names")

TEXT_COLUMNS = (
    "request_id",
    "dialog_id",
    "user_id",
    "first_user_message",
    "summary",
    "goal",
    "intent",
    "periodicity",
    "complexity",
    "search_type",
    "failure_reason",
    "language",
    "analysis_status",
    "use_case",
)

REQUIRED_COLUMNS = ("request_id", "user_id", "created_at", "total_tokens")

#: Filled in when the pipeline left the field empty, so charts do not silently
#: drop the row and a reader can see that the value is missing rather than zero.
UNKNOWN = "не определено"


class DataError(RuntimeError):
    """Raised when the export cannot be read as a pipeline output."""


@dataclass
class Dataset:
    frame: pd.DataFrame
    source: Path
    notes: list[str] = field(default_factory=list)

    @property
    def rows(self) -> int:
        return len(self.frame)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise DataError(f"Файл не найден: {path}")
    # The pipeline writes UTF-8 with a BOM; without utf-8-sig the first column
    # name arrives as "﻿request_id" and every lookup for it fails.
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    if frame.empty:
        raise DataError(f"В файле нет строк: {path}")
    return frame.fillna("")


def resolve_source(target: str | Path) -> tuple[Path, list[Path]]:
    """Return the analytics file to read, or the pair to join.

    ``target`` may be the joined ``analytics.csv``, or a directory holding the
    pipeline output.
    """

    path = Path(target)
    if path.is_file():
        return path, []
    if not path.is_dir():
        raise DataError(f"Не найден файл или каталог: {path}")
    joined = path / "analytics.csv"
    if joined.exists():
        return joined, []
    dialogs = path / "dialogs.csv"
    use_cases = path / "use_cases.csv"
    if dialogs.exists() and use_cases.exists():
        return dialogs, [use_cases]
    raise DataError(
        f"В каталоге {path} нужен analytics.csv либо пара dialogs.csv + use_cases.csv"
    )


def _split(raw: str) -> list[str]:
    return [item.strip() for item in str(raw).split(";") if item.strip()]


def _cast(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()

    for column in TEXT_COLUMNS:
        if column in frame:
            frame[column] = frame[column].astype(str).str.strip()

    for column in BOOL_COLUMNS:
        if column in frame:
            frame[column] = frame[column].astype(str).str.strip().str.lower() == "true"

    for column in INT_COLUMNS:
        if column in frame:
            frame[column] = (
                pd.to_numeric(frame[column], errors="coerce").fillna(0).astype("int64")
            )

    for column in FLOAT_COLUMNS:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    for column in LIST_COLUMNS:
        if column in frame:
            frame[column] = frame[column].map(_split)

    # -1 is HDBSCAN's label for an outlier, so this column keeps its sign.
    if "cluster_id" in frame:
        frame["cluster_id"] = (
            pd.to_numeric(frame["cluster_id"], errors="coerce").fillna(-1).astype("int64")
        )

    for column, fallback in (("complexity", UNKNOWN), ("periodicity", UNKNOWN),
                             ("language", UNKNOWN), ("use_case", UNKNOWN)):
        if column in frame:
            frame[column] = frame[column].replace("", fallback)

    timestamps = pd.to_datetime(
        frame["created_at"], format=CREATED_AT_FORMAT, utc=True, errors="coerce"
    )
    if timestamps.isna().any():
        # A pipeline run configured with another timestamp format should still
        # open; only values that no format explains are dropped from the axis.
        relaxed = pd.to_datetime(frame["created_at"], utc=True, errors="coerce", format="mixed")
        timestamps = timestamps.fillna(relaxed)
    frame["created_at"] = timestamps

    return frame


def load(target: str | Path) -> Dataset:
    """Read the pipeline export named by ``target`` into a typed frame."""

    primary, extra = resolve_source(target)
    frame = _read_csv(primary)

    notes: list[str] = []
    for use_cases_path in extra:
        clusters = _read_csv(use_cases_path)
        missing = {"request_id", "cluster_id", "use_case", "member_count"} - set(clusters.columns)
        if missing:
            raise DataError(
                f"{use_cases_path}: нет колонок {', '.join(sorted(missing))}"
            )
        # A dialogs.csv that already carries cluster columns would otherwise
        # collide with the joined ones and leave `use_case_x` / `use_case_y`.
        overlap = [column for column in clusters.columns if column != "request_id" and column in frame]
        frame = frame.drop(columns=overlap).merge(
            clusters.drop_duplicates(subset="request_id"), how="left", on="request_id"
        )
        frame = frame.fillna("")
        notes.append(f"Кластеры присоединены из {use_cases_path.name}")

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise DataError(f"{primary}: нет обязательных колонок {', '.join(missing)}")

    frame = _cast(frame)

    duplicates = int(frame["request_id"].duplicated().sum())
    if duplicates:
        notes.append(f"Повторяющихся request_id: {duplicates} — строки оставлены как есть")

    undated = int(frame["created_at"].isna().sum())
    if undated:
        notes.append(f"Строк без разбираемого created_at: {undated} — исключены из графиков по времени")

    # A column that is zero in every row means the step that fills it never
    # ran. Left unsaid, the page would show a confident 0 % where the honest
    # statement is "не измерено".
    for columns, message in (
        (
            ("useful_messages", "useless_messages", "burned_tokens"),
            "Классификатор сообщений не отработал: useful/useless/burned_tokens пусты во всей выгрузке",
        ),
        (("estimated_cost",), "estimated_cost пуст во всей выгрузке"),
    ):
        present = [column for column in columns if column in frame]
        if present and all(frame[column].sum() == 0 for column in present):
            notes.append(message)

    if "analysis_status" in frame:
        incomplete = int((frame["analysis_status"] != "success").sum())
        if incomplete:
            notes.append(
                f"Строк с analysis_status ≠ success: {incomplete} — поля LLM у них пустые"
            )

    return Dataset(frame=frame, source=primary, notes=notes)
