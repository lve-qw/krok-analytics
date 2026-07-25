import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from analytics_contract.dashboard import charts, data_loader, filters, layout, metrics
from analytics_contract.dashboard.app import create_app
from analytics_contract.dashboard.theme import DARK, LIGHT
from analytics_contract.schema import REQUIRED_COLUMNS

CLASSES = [
    ("email_summary", "Сводка по письмам", "длинное описание 1"),
    ("jira_my_tasks", "Задачи в Jira", "длинное описание 2"),
]

BASE_ROW = {
    "request_id": "1", "class_ids": '["email_summary"]', "class_names": '["Сводка по письмам"]',
    "confidence": "0.8", "summary": "Резюме", "goal": "Цель", "intent": "Намерение",
    "is_work": "true", "automation_candidate": "true", "periodicity": "daily",
    "complexity": "medium", "steps_requested": "2", "integrations": '["Exchange"]',
    "integration_count": "1", "tools": '["mail"]', "tool_calls": "2",
    "uses_company_data": "true", "company_sources": '["mailbox"]',
    "requires_generation": '["text"]', "search_type": '["internal"]',
    "contains_sensitive_data": "false", "prompt_injection": "false",
    "agent_failed": "false", "failure_reason": "", "language": "ru",
    "user_tokens": "100", "assistant_tokens": "80", "tool_tokens": "0",
    "estimated_cost": "0.01", "use_case": "Сводка почты",
}


def make_row(index, **overrides):
    row = dict(BASE_ROW, request_id=str(index))
    row.update(overrides)
    return row


class DashboardTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

        self.classes_path = self.dir / "classes_31.csv"
        with self.classes_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["class_id", "class_name", "description"])
            writer.writerows(CLASSES)

        rows = []
        for index in range(1, 31):
            failed = index % 5 == 0
            rows.append(
                make_row(
                    index,
                    agent_failed="true" if failed else "false",
                    failure_reason="tool_timeout" if failed else "",
                    complexity=["simple", "medium", "complex"][index % 3],
                    use_case="Сводка почты" if index % 2 else "Задачи в Jira",
                    estimated_cost=f"{0.01 * index:.4f}",
                    contains_sensitive_data="true" if index % 7 == 0 else "false",
                    search_type='["internet"]' if index % 7 == 0 else '["internal"]',
                )
            )
        self.analytics_path = self.write_analytics(rows)
        self.dataset = data_loader.load(
            self.analytics_path, self.classes_path, enforce_registry=False
        )
        self.frame = self.dataset.frame

    def write_analytics(self, rows) -> Path:
        path = self.dir / "analytics.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_COLUMNS))
            writer.writeheader()
            writer.writerows(rows)
        return path


class LoaderTest(DashboardTestCase):
    def test_list_columns_are_parsed(self):
        self.assertEqual(self.frame.loc[0, "class_ids"], ["email_summary"])
        self.assertEqual(self.frame.loc[0, "tools"], ["mail"])

    def test_booleans_and_numbers_are_typed(self):
        self.assertIs(bool(self.frame.loc[0, "is_work"]), True)
        self.assertEqual(self.frame.loc[0, "user_tokens"], 100)
        self.assertEqual(self.frame.loc[0, "total_tokens"], 180)

    def test_invalid_file_is_refused(self):
        bad = self.write_analytics([make_row(1, confidence="7")])

        with self.assertRaises(data_loader.ContractViolation):
            data_loader.load(bad, self.classes_path, enforce_registry=False)


class MetricsTest(DashboardTestCase):
    def test_seven_kpi_cards(self):
        cards = metrics.kpis(self.frame, 0.5)

        self.assertEqual(len(cards), 7)
        self.assertTrue(all(card.value for card in cards))

    def test_kpis_on_empty_frame_do_not_crash(self):
        cards = metrics.kpis(self.frame.iloc[0:0], 0.5)

        self.assertEqual(len(cards), 1)

    def test_failure_rate_matches_manual_count(self):
        failures = int(self.frame["agent_failed"].sum())

        self.assertEqual(failures, 6)
        by_use_case = metrics.failure_by_use_case(self.frame, min_group=1)
        self.assertAlmostEqual(
            float((by_use_case["failures"]).sum()), failures
        )

    def test_wilson_interval_brackets_the_point_estimate(self):
        low, high = metrics.wilson_interval(3, 10)

        self.assertLess(low, 0.3)
        self.assertGreater(high, 0.3)

    def test_wilson_interval_on_zero_total(self):
        self.assertEqual(metrics.wilson_interval(0, 0), (0.0, 0.0))

    def test_min_group_suppresses_tiny_groups(self):
        result = metrics.failure_by_use_case(self.frame, min_group=1000)

        self.assertTrue(result.empty)

    def test_cost_pareto_is_cumulative_and_bounded(self):
        pareto = metrics.cost_pareto(self.frame)

        self.assertTrue((pareto["cumulative"].diff().dropna() >= 0).all())
        self.assertLessEqual(pareto["cumulative"].max(), 1.0000001)

    def test_review_queue_is_a_union(self):
        mask = metrics.review_queue_mask(self.frame, 0.5)
        manual = (
            (self.frame["confidence"] < 0.5)
            | self.frame["agent_failed"]
            | self.frame["contains_sensitive_data"]
            | self.frame["prompt_injection"]
        )

        self.assertEqual(int(mask.sum()), int(manual.sum()))

    def test_exposure_overlap_counts_only_triple_matches(self):
        overlap = metrics.exposure_overlap(self.frame)

        expected = int(
            (
                self.frame["contains_sensitive_data"]
                & self.frame["uses_company_data"]
                & self.frame["search_type"].map(lambda v: "internet" in v)
            ).sum()
        )
        self.assertEqual(overlap, expected)

    def test_token_split_keeps_complexity_order(self):
        split = metrics.token_split(self.frame)

        self.assertEqual(
            list(split["complexity"]),
            [c for c in ["simple", "medium", "complex"] if c in set(self.frame["complexity"])],
        )


class FilterTest(DashboardTestCase):
    def test_no_selection_is_a_no_op(self):
        self.assertEqual(len(filters.apply(self.frame, {})), len(self.frame))
        self.assertEqual(
            len(filters.apply(self.frame, {"agent_failed": filters.ANY})), len(self.frame)
        )

    def test_boolean_filter(self):
        failed = filters.apply(self.frame, {"agent_failed": "true"})

        self.assertEqual(len(failed), 6)
        self.assertTrue(failed["agent_failed"].all())

    def test_list_filter_matches_any_selected(self):
        result = filters.apply(self.frame, {"tools": ["mail"]})

        self.assertEqual(len(result), len(self.frame))
        self.assertEqual(len(filters.apply(self.frame, {"tools": ["python"]})), 0)

    def test_scalar_filter(self):
        result = filters.apply(self.frame, {"use_case": ["Задачи в Jira"]})

        self.assertTrue((result["use_case"] == "Задачи в Jira").all())

    def test_filters_compose(self):
        result = filters.apply(
            self.frame, {"agent_failed": "true", "use_case": ["Сводка почты"]}
        )

        self.assertTrue(result["agent_failed"].all())
        self.assertTrue((result["use_case"] == "Сводка почты").all())

    def test_options_cover_every_declared_filter(self):
        for spec in filters.FILTERS:
            self.assertIsInstance(filters.options_for(self.frame, spec), list)


class ChartTest(DashboardTestCase):
    def _all_figures(self, theme):
        return {
            "volume": charts.volume_bar(metrics.top_use_cases(self.frame), theme),
            "classes": charts.volume_bar(metrics.top_classes(self.frame), theme),
            "periodicity": charts.periodicity_heatmap(
                metrics.use_case_periodicity(self.frame), theme
            ),
            "failure": charts.failure_scatter(
                metrics.failure_by_use_case(self.frame, min_group=1), theme
            ),
            "reliability": charts.reliability_bar(
                metrics.reliability(self.frame, "tools", min_group=1), theme, "tools"
            ),
            "cost": charts.cost_pareto(metrics.cost_pareto(self.frame), theme),
            "tokens": charts.token_split_bar(metrics.token_split(self.frame), theme),
            "security": charts.security_heatmap(
                metrics.security_matrix(self.frame, min_group=1), theme
            ),
        }

    def test_every_chart_builds_in_both_themes(self):
        for theme in (LIGHT, DARK):
            for name, figure in self._all_figures(theme).items():
                with self.subTest(theme=theme.name, chart=name):
                    self.assertGreaterEqual(len(figure.data), 1)
                    self.assertEqual(figure.layout.paper_bgcolor, theme.surface)

    def test_no_chart_uses_a_secondary_y_axis(self):
        # A dual-scale chart is the one form this dashboard must never produce.
        for theme in (LIGHT, DARK):
            for name, figure in self._all_figures(theme).items():
                with self.subTest(chart=name):
                    axes = [
                        key
                        for key in figure.layout.to_plotly_json()
                        if key.startswith("yaxis") and key != "yaxis"
                    ]
                    self.assertEqual(axes, [], f"{name} declares a second y-axis")
                    for trace in figure.data:
                        self.assertIn(getattr(trace, "yaxis", None), (None, "y"))

    def test_empty_data_yields_a_placeholder_not_a_crash(self):
        empty = self.frame.iloc[0:0]
        figure = charts.failure_scatter(metrics.failure_by_use_case(empty), LIGHT)

        self.assertEqual(len(figure.layout.annotations), 1)

    def test_pareto_series_share_one_axis(self):
        figure = charts.cost_pareto(metrics.cost_pareto(self.frame), LIGHT)

        self.assertEqual(len(figure.data), 2)
        self.assertEqual({trace.yaxis for trace in figure.data}, {None})


class AppTest(DashboardTestCase):
    def test_app_builds_with_expected_callbacks(self):
        app = create_app(str(self.analytics_path), str(self.classes_path))

        self.assertEqual(len(app.callback_map), 4)

    def test_layout_defines_every_id_the_callbacks_output(self):
        app = create_app(str(self.analytics_path), str(self.classes_path))

        defined = set()

        def walk(component):
            identifier = getattr(component, "id", None)
            if isinstance(identifier, str):
                defined.add(identifier)
            elif isinstance(identifier, dict):
                defined.add(identifier.get("type"))
            for child in (getattr(component, "children", None) or []):
                if hasattr(child, "id") or hasattr(child, "children"):
                    walk(child)

        walk(app.layout)

        for key in app.callback_map:
            for target in key.strip(".").split("..."):
                component_id = target.rsplit(".", 1)[0]
                if component_id.startswith("{"):
                    component_id = json.loads(component_id).get("type")
                self.assertIn(component_id, defined, f"{component_id} missing from layout")

    def test_drilldown_columns_match_the_contract(self):
        from analytics_contract.dashboard.app import _drilldown_records

        records = _drilldown_records(self.frame)

        self.assertEqual(len(records), len(self.frame))
        self.assertEqual(set(records[0]), set(charts_drilldown_columns()))


def charts_drilldown_columns():
    from analytics_contract.schema import DRILLDOWN_COLUMNS

    return DRILLDOWN_COLUMNS


if __name__ == "__main__":
    unittest.main()
