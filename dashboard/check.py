"""Print every metric from metrics.md as text.

    python -m dashboard.check --input outputs

The dashboard and this command read the same functions, so the printout is the
way to verify a number before it is quoted out loud, without opening a browser.
"""

from __future__ import annotations

import argparse
import sys

from dashboard import data, metrics
from dashboard.metrics import LOW_CONFIDENCE


def _line(label: str, value) -> str:
    return f"  {label:<34} {value}"


def report(target: str) -> str:
    dataset = data.load(target)
    frame = dataset.frame
    out: list[str] = [f"Источник: {dataset.source}", f"Строк: {dataset.rows}"]
    for note in dataset.notes:
        out.append(f"  ! {note}")

    base = metrics.overview(frame)
    out += [
        "",
        "1. Общая статистика",
        _line("total_dialogs", base["total_dialogs"]),
        _line("total_users", base["total_users"]),
        _line("date_range", f"{base['date_min']} — {base['date_max']} ({base['days']} дн.)"),
    ]

    token_stats = metrics.tokens(frame)
    out += [
        "",
        "2. Токены",
        _line("total_tokens", token_stats["total_tokens"]),
        _line("avg_tokens_per_dialog", f"{token_stats['avg_tokens_per_dialog']:.1f}"),
        _line("total_burned_tokens", token_stats["total_burned_tokens"]),
        _line("burned_ratio", f"{token_stats['burned_ratio']:.2f} %"),
        _line("total_estimated_cost", f"{token_stats['total_estimated_cost']:.4f}"),
    ]

    quality = metrics.quality(frame)
    out += [
        "",
        "3. Качество работы агента",
        _line("useful_messages_total", quality["useful_messages_total"]),
        _line("useless_messages_total", quality["useless_messages_total"]),
        _line("useful_ratio", f"{quality['useful_ratio']:.2f} %"),
        _line("dialogs_with_burned", quality["dialogs_with_burned"]),
        _line("avg_burned_per_failed_dialog", f"{quality['avg_burned_per_failed_dialog']:.1f}"),
    ]

    class_stats = metrics.classification(frame)
    out += [
        "",
        "4. Классификация",
        _line("work_dialogs", class_stats["work_dialogs"]),
        _line("work_ratio", f"{class_stats['work_ratio']:.2f} %"),
        _line("automation_candidates", class_stats["automation_candidates"]),
        _line("automation_ratio", f"{class_stats['automation_ratio']:.2f} %"),
    ]

    out += ["", "5. Сложность и периодичность", "  complexity_distribution"]
    for row in metrics.complexity_distribution(frame).itertuples():
        out.append(_line(f"    {row.key}", row.dialogs))
    out.append("  periodicity_distribution")
    for row in metrics.periodicity_distribution(frame).itertuples():
        out.append(_line(f"    {row.key}", row.dialogs))

    integration_stats = metrics.integrations(frame)
    out += [
        "",
        "6. Интеграции и инструменты",
        _line("dialogs_with_integrations", integration_stats["dialogs_with_integrations"]),
        _line("unique_integrations", integration_stats["unique_integrations"]),
        _line("unique_tools", integration_stats["unique_tools"]),
        _line("avg_tool_calls", f"{integration_stats['avg_tool_calls']:.2f}"),
    ]

    cluster_stats = metrics.clusters(frame)
    out += [
        "",
        "7. Use cases",
        _line("total_clusters", cluster_stats["total_clusters"]),
        _line("outliers", cluster_stats["outliers"]),
        _line("avg_cluster_size", f"{cluster_stats['avg_cluster_size']:.2f}"),
        "  top_5_clusters",
    ]
    for row in metrics.top_clusters(frame).itertuples():
        out.append(_line(f"    {row.use_case} (id {row.cluster_id})", row.dialogs))

    problem_stats = metrics.problems(frame)
    out += [
        "",
        "8. Проблемы",
        _line("agent_failures", problem_stats["agent_failures"]),
        _line("prompt_injections", problem_stats["prompt_injections"]),
        _line("sensitive_data", problem_stats["sensitive_data"]),
        "  failure_reasons",
    ]
    for row in problem_stats["failure_reasons"].itertuples():
        out.append(_line(f"    {row.key}", row.dialogs))

    out += ["", "9. Языки"]
    for row in metrics.language_distribution(frame).itertuples():
        out.append(_line(f"    {row.key}", row.dialogs))

    confidence_stats = metrics.confidence(frame)
    out += [
        "",
        "10. Уверенность классификации",
        _line("avg_confidence", f"{confidence_stats['avg_confidence']:.3f}"),
        _line(f"low_confidence (< {LOW_CONFIDENCE})", confidence_stats["low_confidence_dialogs"]),
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="outputs", help="CSV файл или каталог выгрузки")
    args = parser.parse_args(argv)
    try:
        print(report(args.input))
    except data.DataError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
