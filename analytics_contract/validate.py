"""CLI entry point for analytics.csv validation.

    python -m analytics_contract.validate \
        --analytics outputs/analytics.canonical.csv \
        --classes data/classes_31.csv

Exits with code 1 when the file violates the contract, 0 otherwise. Warnings do
not change the exit code unless ``--fail-on-warning`` is passed.

The `tools` and `integrations` registries declared in `config.py` are enforced
by default; pass ``--no-registry-check`` to check those columns for shape only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from analytics_contract.registry import load_project_registries
from analytics_contract.validation import (
    DEFAULT_LOW_CONFIDENCE,
    DEFAULT_OUTLIER_FACTOR,
    format_summary,
    validate_analytics,
    write_reports,
)

DEFAULT_ANALYTICS = "outputs/analytics.canonical.csv"
DEFAULT_CLASSES = "data/classes_31.csv"
DEFAULT_OUTPUT_DIR = "outputs/validation"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m analytics_contract.validate",
        description="Validate analytics.csv against the canonical contract.",
    )
    parser.add_argument("--analytics", default=DEFAULT_ANALYTICS, help="path to analytics.csv")
    parser.add_argument("--classes", default=DEFAULT_CLASSES, help="path to the 31-class registry")
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="directory for validation_report.json and validation_errors.csv",
    )
    parser.add_argument(
        "--low-confidence",
        type=float,
        default=DEFAULT_LOW_CONFIDENCE,
        help="confidence below this value raises a warning",
    )
    parser.add_argument(
        "--outlier-factor",
        type=float,
        default=DEFAULT_OUTLIER_FACTOR,
        help="cost/token values above this multiple of the sample median raise a warning",
    )
    parser.add_argument(
        "--no-registry-check",
        action="store_true",
        help="do not enforce the FIXED_TOOLS / FIXED_INTEGRATIONS vocabularies",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="also exit non-zero when only warnings were found",
    )
    parser.add_argument("--quiet", action="store_true", help="print nothing but the status line")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    analytics = Path(args.analytics)
    classes = Path(args.classes)
    for label, path in (("analytics", analytics), ("classes", classes)):
        if not path.exists():
            print(f"error: {label} file not found: {path}", file=sys.stderr)
            return 2

    vocabularies = None
    if not args.no_registry_check:
        loaded = load_project_registries()
        if loaded is None:
            print(
                "warning: config.py is not importable; tools/integrations registries "
                "are not enforced for this run",
                file=sys.stderr,
            )
        else:
            tools, integrations = loaded
            vocabularies = {"tools": tools, "integrations": integrations}

    try:
        result = validate_analytics(
            analytics,
            classes,
            low_confidence_threshold=args.low_confidence,
            outlier_factor=args.outlier_factor,
            vocabularies=vocabularies,
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    report_path, errors_path = write_reports(result, args.out_dir)

    if args.quiet:
        print(f"{result.status.upper()} rows={result.row_count} "
              f"errors={len(result.errors)} warnings={len(result.warnings)}")
    else:
        print(format_summary(result))
        print()
        print(f"report: {report_path}")
        print(f"issues: {errors_path}")

    if result.errors:
        return 1
    if result.warnings and args.fail_on_warning:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
