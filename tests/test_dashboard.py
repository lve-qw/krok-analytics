import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from analytics_contract.dashboard import charts, data_loader, filters, labels, layout, metrics
from analytics_contract.dashboard.app import create_app
from analytics_contract.dashboard.styles import STYLESHEET
from analytics_contract.dashboard.theme import DARK, LIGHT, THEMES
from analytics_contract.schema import DRILLDOWN_COLUMNS, REQUIRED_COLUMNS

CLASSES = [
    ("email_summary", "Сводка по письмам", "длинное описание 1"),
    ("jira_my_tasks", "Задачи в Jira", "длинное описание 2"),
]

BASE_ROW = {
    "request_id": "1", "user_id": "usr-001", "created_at": "2026-07-25T09:15:00Z",
    "class_ids": '["email_summary"]', "class_names": '["Сводка по письмам"]',
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
    def test_five_kpi_cards(self):
        cards = metrics.kpis(self.frame, 0.5)

        self.assertEqual(len(cards), 5)
        self.assertTrue(all(card.value for card in cards))

    def test_every_kpi_carries_a_formula_for_its_tooltip(self):
        for card in metrics.kpis(self.frame, 0.5):
            with self.subTest(card=card.label):
                self.assertTrue(card.formula, "a number on a projector must state its source")
                self.assertIn(card.formula, card.tooltip)

    def test_token_kpi_is_measured_and_does_not_depend_on_the_cost_model(self):
        """Token consumption comes from logs, not from an invented TCO."""

        cheap = metrics.CostModel(support_fte=1.0)
        rich = metrics.CostModel(support_fte=4.0)

        def value(cards, needle):
            return next(c for c in cards if needle in c.label).value

        cheap_cards = metrics.kpis(self.frame, 0.5, model=cheap)
        rich_cards = metrics.kpis(self.frame, 0.5, model=rich)

        self.assertEqual(value(cheap_cards, "Потреблено токенов"), value(rich_cards, "Потреблено токенов"))
        self.assertNotEqual(value(cheap_cards, "безубыточности"), value(rich_cards, "безубыточности"))
        token_card = next(c for c in cheap_cards if "Потреблено токенов" in c.label)
        self.assertNotIn("₽", token_card.tooltip)
        self.assertIn("без перевода в рубли", token_card.caveat)

    def test_breakeven_is_exactly_where_benefit_equals_cost(self):
        """The card and the crossing on the chart must be one number."""

        model = metrics.CostModel()
        threshold = metrics.breakeven_minutes(self.frame, model.monthly_rub)
        benefit = metrics.benefit_rub(metrics.monthly_requests(self.frame), threshold)

        self.assertAlmostEqual(benefit, model.monthly_rub, places=4)

    def test_cost_per_million_tokens_falls_when_traffic_doubles(self):
        """It is a unit cost at a utilisation, not a property of the hardware."""

        doubled = pd.concat([self.frame, self.frame.assign(request_id="dup")])
        model = metrics.CostModel()

        self.assertLess(
            metrics.cost_per_million_tokens(doubled, model),
            metrics.cost_per_million_tokens(self.frame, model),
        )

    def test_breakeven_states_that_its_inputs_come_from_outside_the_contract(self):
        card = next(c for c in metrics.kpis(self.frame, 0.5) if "безубыточности" in c.label)

        self.assertEqual(card.unit, "мин/запрос")
        self.assertIn(str(metrics.MINUTE_RATE_RUB), card.formula)
        self.assertIn("снаружи контракта", card.caveat)
        self.assertIn("не утверждает", card.caveat)

    def test_breakeven_scales_the_sample_to_a_month(self):
        """A month of TCO must not be divided by a few days of requests."""

        threshold = metrics.breakeven_minutes(self.frame, tco_rub=500_000.0)
        per_month = metrics.monthly_requests(self.frame)

        self.assertGreater(per_month, len(self.frame))
        self.assertAlmostEqual(
            threshold,
            500_000.0 / (per_month * metrics.MINUTE_RATE_RUB * metrics.CAPTURE_RATE),
            places=6,
        )

    def test_fte_card_changes_with_the_visible_time_assumption(self):
        low = next(
            c for c in metrics.kpis(self.frame, 0.5, minutes_saved=5)
            if "высвобождённого" in c.label
        )
        high = next(
            c for c in metrics.kpis(self.frame, 0.5, minutes_saved=15)
            if "высвобождённого" in c.label
        )

        self.assertLess(float(low.value), float(high.value))
        self.assertIn("ползунком", low.caveat)
        self.assertIn("5 мин", low.detail)

    def test_adoption_reports_shape_not_penetration(self):
        card = next(c for c in metrics.kpis(self.frame, 0.5) if "Активных" in c.label)

        self.assertIn("не MAU", card.caveat)
        self.assertEqual(card.value, str(self.frame["user_id"].nunique()))

    def test_usage_card_carries_dialogues_and_tool_calls(self):
        card = next(c for c in metrics.kpis(self.frame, 0.5) if "Обращения" in c.label)

        self.assertEqual(card.value, str(len(self.frame)))
        self.assertIn(str(int(self.frame["tool_calls"].sum())), card.detail)

    def test_usage_ranking_attributes_tokens_to_users(self):
        ranking = metrics.usage_ranking(self.frame, "user_id", "tokens")

        self.assertEqual(int(ranking["tokens"].sum()), int(self.frame["total_tokens"].sum()))
        self.assertEqual(set(ranking["key"]), set(self.frame["user_id"]))

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
            "usage": charts.usage_bar(
                metrics.usage_ranking(self.frame, "user_id", "tokens"),
                theme,
                "user_id",
                "tokens",
                total=float(self.frame["total_tokens"].sum()),
            ),
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


class LabelTest(DashboardTestCase):
    def test_unclustered_is_named_not_hidden(self):
        # The clustering step's noise bucket is a real value; it gets a caption
        # rather than being dropped or shown as a raw identifier.
        self.assertEqual(labels.use_case("unclustered"), "Сценарий не определён")

    def test_unknown_values_pass_through(self):
        self.assertEqual(labels.show("совершенно новый", "use_case"), "совершенно новый")
        self.assertEqual(labels.show("mail", None), "mail")

    def test_every_stored_enum_has_a_russian_caption(self):
        for column, values in (
            ("complexity", ["simple", "medium", "complex"]),
            ("periodicity", ["none", "daily", "weekly", "monthly"]),
            ("search_type", ["internet", "internal"]),
        ):
            for value in values:
                with self.subTest(column=column, value=value):
                    self.assertNotEqual(labels.show(value, column), value)

    def test_truncation_keeps_the_full_name_available(self):
        long = "Подготовка отчётности по CRM за прошлый квартал"
        short = labels.truncate(long, 20)

        self.assertEqual(len(short), 20)
        self.assertTrue(short.endswith("…"))
        self.assertEqual(labels.show(long, "use_case"), long)

    def test_validator_limitations_are_translated(self):
        for text in self.dataset.limitations:
            with self.subTest(text=text[:40]):
                self.assertNotEqual(labels.limitation(text), text)


class TableTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        from analytics_contract.dashboard.app import _drilldown_records

        self.records = _drilldown_records(self.frame)

    def test_every_contract_column_has_a_header_and_a_width(self):
        for column in DRILLDOWN_COLUMNS:
            with self.subTest(column=column):
                self.assertIn(column, layout.DRILLDOWN_LABELS)
                self.assertIn(column, layout.DRILLDOWN_WIDTHS)

    def test_columns_fit_a_1440_viewport(self):
        # Wider than this and the last column is cut off on the demo laptop.
        self.assertLessEqual(sum(layout.DRILLDOWN_WIDTHS.values()), 1345)

    def test_lists_and_booleans_are_rendered_as_text(self):
        row = self.records[0]

        self.assertEqual(row["tools"], "Почта")
        self.assertEqual(row["agent_failed"], "нет")
        self.assertEqual(row["complexity"], "средний")

    def test_empty_list_shows_a_dash_not_an_empty_cell(self):
        frame = self.frame.copy()
        frame.at[0, "integrations"] = []
        from analytics_contract.dashboard.app import _drilldown_records

        self.assertEqual(_drilldown_records(frame)[0]["integrations"], "—")

    def test_table_is_styled_from_theme_variables(self):
        table = _find(layout.drilldown_table(), "drilldown")

        self.assertTrue(table.style_header["backgroundColor"].startswith("var(--"))
        self.assertTrue(table.style_data["backgroundColor"].startswith("var(--"))
        self.assertTrue(table.style_data["color"].startswith("var(--"))
        self.assertEqual(table.fixed_rows, {"headers": True})
        self.assertEqual(table.sort_action, "native")

    def test_wrapping_is_enabled_for_long_text(self):
        table = _find(layout.drilldown_table(), "drilldown")

        self.assertEqual(table.style_cell["whiteSpace"], "normal")
        self.assertEqual(table.style_cell["height"], "auto")


class ThemeTest(DashboardTestCase):
    def test_theme_class_is_always_explicit(self):
        # The bug this guards: with the class left off, an OS-level dark
        # preference styled the page while the store still said light, so
        # Plotly kept drawing on white paper inside a dark card.
        page = layout.build(self.frame, metrics.kpis(self.frame, 0.5), [], LIGHT)

        self.assertIn("theme-light", page.className)

    def test_stylesheet_declares_no_os_level_theme_rule(self):
        self.assertNotIn("prefers-color-scheme", STYLESHEET)

    def test_both_themes_define_every_token(self):
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                for field in ("surface", "page", "dim", "guide", "grid", "axis"):
                    self.assertTrue(getattr(theme, field).startswith("#"))


class SelectionTest(DashboardTestCase):
    def test_selection_narrows_to_one_scenario(self):
        result = filters.apply_selection(
            self.frame, {"column": "use_case", "value": "Задачи в Jira"}
        )

        self.assertTrue((result["use_case"] == "Задачи в Jira").all())
        self.assertLess(len(result), len(self.frame))

    def test_selection_on_a_list_column_matches_membership(self):
        result = filters.apply_selection(
            self.frame, {"column": "class_names", "value": "Сводка по письмам"}
        )

        self.assertEqual(len(result), len(self.frame))

    def test_selection_on_a_user_narrows_to_that_users_dialogues(self):
        chosen = self.frame["user_id"].iloc[0]
        result = filters.apply_selection(
            self.frame, {"column": "user_id", "value": chosen}
        )

        self.assertTrue((result["user_id"] == chosen).all())

    def test_unknown_or_missing_selection_is_a_no_op(self):
        for selection in (None, {}, {"column": "summary", "value": "x"}):
            with self.subTest(selection=selection):
                self.assertEqual(
                    len(filters.apply_selection(self.frame, selection)), len(self.frame)
                )

    def test_clicked_value_is_the_stored_key_not_the_caption(self):
        from analytics_contract.dashboard.app import _clicked_value

        figure = charts.volume_bar(metrics.top_use_cases(self.frame), LIGHT)
        custom = figure.data[0].customdata

        self.assertEqual(_clicked_value({"points": [{"customdata": custom[0]}]}), custom[0][-1])
        self.assertIn(custom[0][-1], set(self.frame["use_case"]))

    def test_no_click_yields_no_selection(self):
        from analytics_contract.dashboard.app import _clicked_value

        self.assertIsNone(_clicked_value(None))
        self.assertIsNone(_clicked_value({"points": []}))

    def test_selected_mark_keeps_its_hue_and_the_rest_are_dimmed(self):
        data = metrics.top_use_cases(self.frame)
        chosen = data["use_case"].iloc[0]
        figure = charts.volume_bar(data, LIGHT, chosen)
        colours = list(figure.data[0].marker.color)

        self.assertEqual(colours.count(LIGHT.series[0]), 1)
        self.assertEqual(colours.count(LIGHT.dim), len(colours) - 1)


class ChipTest(DashboardTestCase):
    def test_no_selection_produces_no_chips(self):
        self.assertEqual(filters.active({}), [])
        self.assertEqual(filters.active({"agent_failed": filters.ANY}), [])

    def test_chip_text_uses_captions_not_stored_values(self):
        by_key = {
            spec.key: text
            for spec, text in filters.active(
                {"complexity": ["simple"], "agent_failed": "true"}
            )
        }

        self.assertEqual(by_key["complexity"], "простой")
        self.assertEqual(by_key["agent_failed"], "да")

    def test_primary_and_secondary_filters_partition_the_set(self):
        self.assertEqual(
            set(filters.PRIMARY) | set(filters.SECONDARY), set(filters.FILTERS)
        )
        self.assertEqual(set(filters.PRIMARY) & set(filters.SECONDARY), set())
        self.assertTrue(0 < len(filters.PRIMARY) < len(filters.FILTERS))


def _find(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component
    for child in (getattr(component, "children", None) or []):
        if hasattr(child, "children") or hasattr(child, "id"):
            found = _find(child, target_id)
            if found is not None:
                return found
    return None


class AppTest(DashboardTestCase):
    def test_app_builds_with_expected_callbacks(self):
        app = create_app(str(self.analytics_path), str(self.classes_path))

        self.assertEqual(len(app.callback_map), 7)

    def test_every_panel_is_in_the_initial_layout(self):
        # Panels are hidden with CSS rather than built on demand, so a chart on
        # an unopened tab still has an id for its callback to write to.
        app = create_app(str(self.analytics_path), str(self.classes_path))

        for key, _ in layout.TABS:
            with self.subTest(panel=key):
                self.assertIsNotNone(_find(app.layout, f"panel-{key}"))

    def test_clear_selection_button_exists_before_anything_is_selected(self):
        app = create_app(str(self.analytics_path), str(self.classes_path))
        button = _find(app.layout, "clear-selection")

        self.assertIsNotNone(button)
        self.assertEqual(button.style, {"display": "none"})

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
