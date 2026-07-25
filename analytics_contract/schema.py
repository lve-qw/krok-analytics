"""Canonical contract for ``analytics.csv``.

This module is the single source of truth for the column set, the list-valued
columns, the enumerations and the accepted literal encodings. It carries no
logic so that the validator, the tests and the later dashboard all agree on the
same contract without importing each other.

The schema is multi-label: ``class_ids``/``class_names`` are JSON arrays and are
never collapsed back into a single ``class_id``.
"""

from __future__ import annotations

SCHEMA_VERSION = "analytics.csv/v1"

#: Column order of the canonical contract. Order is normative for writers;
#: the validator checks membership, not position.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "request_id",
    "class_ids",
    "class_names",
    "confidence",
    "summary",
    "goal",
    "intent",
    "is_work",
    "automation_candidate",
    "periodicity",
    "complexity",
    "steps_requested",
    "integrations",
    "integration_count",
    "tools",
    "tool_calls",
    "uses_company_data",
    "company_sources",
    "requires_generation",
    "search_type",
    "contains_sensitive_data",
    "prompt_injection",
    "agent_failed",
    "failure_reason",
    "language",
    "user_tokens",
    "assistant_tokens",
    "tool_tokens",
    "estimated_cost",
    "use_case",
)

#: Columns serialized as JSON arrays of unique, non-blank strings.
LIST_COLUMNS: frozenset[str] = frozenset(
    {
        "class_ids",
        "class_names",
        "integrations",
        "tools",
        "company_sources",
        "requires_generation",
        "search_type",
    }
)

#: List columns that may not be empty.
NON_EMPTY_LIST_COLUMNS: frozenset[str] = frozenset({"class_ids", "class_names"})

BOOL_COLUMNS: frozenset[str] = frozenset(
    {
        "is_work",
        "automation_candidate",
        "uses_company_data",
        "contains_sensitive_data",
        "prompt_injection",
        "agent_failed",
    }
)

NON_NEGATIVE_INT_COLUMNS: tuple[str, ...] = (
    "steps_requested",
    "integration_count",
    "tool_calls",
    "user_tokens",
    "assistant_tokens",
    "tool_tokens",
)

#: Free-text columns that must be present and must not be whitespace-only.
NON_BLANK_TEXT_COLUMNS: tuple[str, ...] = (
    "summary",
    "goal",
    "intent",
    "language",
    "use_case",
)

PERIODICITY_VALUES: frozenset[str] = frozenset({"none", "daily", "weekly", "monthly"})
COMPLEXITY_VALUES: frozenset[str] = frozenset({"simple", "medium", "complex"})
REQUIRES_GENERATION_VALUES: frozenset[str] = frozenset({"text", "excel", "sql", "presentation"})
SEARCH_TYPE_VALUES: frozenset[str] = frozenset({"internet", "internal"})

#: Enumerations keyed by column. Scalar enums and list-element enums are kept
#: together because they share the same "closed vocabulary" semantics.
ENUM_VALUES: dict[str, frozenset[str]] = {
    "periodicity": PERIODICITY_VALUES,
    "complexity": COMPLEXITY_VALUES,
    "requires_generation": REQUIRES_GENERATION_VALUES,
    "search_type": SEARCH_TYPE_VALUES,
}

#: Booleans are deliberately restricted to these literals. ``1``/``0``,
#: ``yes``/``no`` and ``Y``/``N`` are rejected rather than coerced, so that a
#: writer emitting an unexpected encoding is reported instead of silently
#: reinterpreted.
TRUE_LITERALS: frozenset[str] = frozenset({"true"})
FALSE_LITERALS: frozenset[str] = frozenset({"false"})

#: Literals accepted as "no failure reason" in ``failure_reason``.
NULL_LITERALS: frozenset[str] = frozenset({"", "null"})

#: Columns exposed by the drill-down table (task §6.1). Declared here so the
#: dashboard cannot drift from the validated contract.
DRILLDOWN_COLUMNS: tuple[str, ...] = (
    "request_id",
    "class_names",
    "use_case",
    "summary",
    "confidence",
    "complexity",
    "automation_candidate",
    "integrations",
    "tools",
    "agent_failed",
    "failure_reason",
    "estimated_cost",
)
