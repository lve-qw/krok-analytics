import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics_contract.registry import load_project_registries
from analytics_contract.schema import REQUIRED_COLUMNS
from analytics_contract.validate import main
from analytics_contract.validation import ERROR_CSV_HEADER, validate_analytics, write_reports

CLASSES = [
    ("email_summary", "Сводка по письмам за день"),
    ("jira_my_tasks", "Список задач в Jira"),
    ("crm_to_excel", "Выгрузка данных CRM в Excel"),
]

VALID_ROW = {
    "request_id": "req-001",
    "user_id": "usr-001",
    "created_at": "2026-07-25T09:15:00Z",
    "class_ids": '["email_summary"]',
    "class_names": '["Сводка по письмам"]',
    "confidence": "0.87",
    "summary": "Пользователь попросил сводку по непрочитанной почте, агент её сформировал.",
    "goal": "Быстро понять содержание почты за день",
    "intent": "Получить структурированную сводку писем",
    "is_work": "true",
    "automation_candidate": "true",
    "periodicity": "daily",
    "complexity": "medium",
    "steps_requested": "2",
    "integrations": '["Exchange"]',
    "integration_count": "1",
    "tools": '["mail"]',
    "tool_calls": "3",
    "uses_company_data": "true",
    "company_sources": '["mailbox"]',
    "requires_generation": '["text"]',
    "search_type": '["internal"]',
    "contains_sensitive_data": "false",
    "prompt_injection": "false",
    "agent_failed": "false",
    "failure_reason": "",
    "language": "ru",
    "user_tokens": "1200",
    "assistant_tokens": "800",
    "tool_tokens": "4300",
    "estimated_cost": "0.042",
    "use_case": "Ежедневная сводка почты",
}


def row_with(**overrides):
    row = dict(VALID_ROW)
    row.update(overrides)
    return row


class ValidationTestCase(unittest.TestCase):
    """Base class writing a throwaway analytics.csv and classes.csv."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

        self.classes_path = self.dir / "classes.csv"
        with self.classes_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["class_id", "description"])
            writer.writerows(CLASSES)

    def write_analytics(self, rows, columns=REQUIRED_COLUMNS) -> Path:
        path = self.dir / "analytics.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(columns))
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row.get(column, "") for column in columns})
        return path

    def validate(self, rows, columns=REQUIRED_COLUMNS):
        return validate_analytics(self.write_analytics(rows, columns), self.classes_path)

    def assertCodes(self, result, *expected_codes, severity="error"):
        """Assert that exactly the expected codes are present at ``severity``."""

        issues = result.errors if severity == "error" else result.warnings
        self.assertEqual(sorted({issue.code for issue in issues}), sorted(expected_codes))

    def assertNoErrors(self, result):
        self.assertEqual([issue.as_dict() for issue in result.errors], [])


class ValidRowTest(ValidationTestCase):
    def test_valid_row_passes(self) -> None:
        result = self.validate([VALID_ROW])

        self.assertNoErrors(result)
        self.assertTrue(result.ok)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.missing_columns, [])
        self.assertEqual(result.unknown_columns, [])

    def test_multi_label_row_is_not_collapsed(self) -> None:
        result = self.validate(
            [
                row_with(
                    class_ids='["email_summary", "jira_my_tasks"]',
                    class_names='["Сводка по письмам", "Задачи в Jira"]',
                )
            ]
        )

        self.assertNoErrors(result)

    def test_status_and_report_shape(self) -> None:
        result = self.validate([VALID_ROW])
        report = result.report()

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["row_count"], 1)
        self.assertEqual(report["counts"], {"error": 0, "warning": 0})
        # classes.csv here has no name column, so the limitation must be stated.
        self.assertTrue(any("class_names" in item for item in report["limitations"]))


class ColumnTest(ValidationTestCase):
    def test_missing_column_is_an_error(self) -> None:
        columns = [column for column in REQUIRED_COLUMNS if column != "use_case"]

        result = self.validate([VALID_ROW], columns=columns)

        self.assertIn("column_missing", {issue.code for issue in result.errors})
        self.assertEqual(result.missing_columns, ["use_case"])
        self.assertFalse(result.ok)

    def test_renamed_column_reports_both_missing_and_unknown(self) -> None:
        columns = ["usecase" if column == "use_case" else column for column in REQUIRED_COLUMNS]
        row = row_with(usecase=VALID_ROW["use_case"])

        result = self.validate([row], columns=columns)

        self.assertEqual(result.missing_columns, ["use_case"])
        self.assertEqual(result.unknown_columns, ["usecase"])
        self.assertIn("column_unknown", {issue.code for issue in result.warnings})

    def test_extra_column_alone_is_only_a_warning(self) -> None:
        columns = list(REQUIRED_COLUMNS) + ["note"]

        result = self.validate([row_with(note="anything")], columns=columns)

        self.assertNoErrors(result)
        self.assertEqual(result.unknown_columns, ["note"])


class IdentifierTest(ValidationTestCase):
    def test_duplicate_request_id(self) -> None:
        result = self.validate([VALID_ROW, row_with(summary="Другой диалог")])

        self.assertCodes(result, "request_id_duplicate")

    def test_blank_request_id(self) -> None:
        result = self.validate([row_with(request_id="   ")])

        self.assertCodes(result, "request_id_blank")


class ListTest(ValidationTestCase):
    def test_malformed_json_list(self) -> None:
        result = self.validate([row_with(tools="[email_search")])

        self.assertCodes(result, "list_malformed")

    def test_pipe_separated_values_are_rejected(self) -> None:
        result = self.validate([row_with(tools="crm_lookup|email_search")])

        self.assertCodes(result, "list_malformed")

    def test_non_string_elements_are_rejected(self) -> None:
        result = self.validate([row_with(tools="[1, 2]")])

        self.assertCodes(result, "list_malformed")

    def test_duplicates_within_a_list(self) -> None:
        result = self.validate([row_with(integrations='["exchange", "exchange"]', integration_count="2")])

        self.assertCodes(result, "list_duplicates")

    def test_empty_class_ids(self) -> None:
        result = self.validate([row_with(class_ids="[]", class_names="[]")])

        self.assertCodes(result, "list_empty")


class ClassTest(ValidationTestCase):
    def test_unknown_class_id(self) -> None:
        result = self.validate([row_with(class_ids='["not_a_class"]')])

        self.assertCodes(result, "class_id_unknown")

    def test_class_ids_and_names_length_mismatch(self) -> None:
        result = self.validate(
            [row_with(class_ids='["email_summary", "jira_my_tasks"]', class_names='["Сводка"]')]
        )

        self.assertCodes(result, "class_length_mismatch")

    def test_class_name_mismatch_when_registry_has_names(self) -> None:
        # A registry that does carry a name column must enforce id -> name.
        classes_path = self.dir / "named_classes.csv"
        with classes_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["class_id", "class_name", "description"])
            writer.writerow(["email_summary", "Email summary", "long description"])

        analytics = self.write_analytics([row_with(class_names='["Wrong name"]')])
        result = validate_analytics(analytics, classes_path)

        self.assertIn("class_name_mismatch", {issue.code for issue in result.errors})

    def test_names_are_not_checked_without_a_registry_name_column(self) -> None:
        result = self.validate([row_with(class_names='["любое имя"]')])

        self.assertNoErrors(result)


class ConfidenceTest(ValidationTestCase):
    def test_confidence_above_one(self) -> None:
        result = self.validate([row_with(confidence="1.4")])

        self.assertCodes(result, "confidence_out_of_range")

    def test_confidence_below_zero(self) -> None:
        result = self.validate([row_with(confidence="-0.1")])

        self.assertCodes(result, "confidence_out_of_range")

    def test_low_confidence_is_a_warning_not_an_error(self) -> None:
        result = self.validate([row_with(confidence="0.11")])

        self.assertNoErrors(result)
        self.assertIn("confidence_low", {issue.code for issue in result.warnings})


class EnumTest(ValidationTestCase):
    def test_unknown_periodicity(self) -> None:
        result = self.validate([row_with(periodicity="hourly")])

        self.assertCodes(result, "enum_unknown")

    def test_unknown_complexity(self) -> None:
        result = self.validate([row_with(complexity="hard")])

        self.assertCodes(result, "enum_unknown")

    def test_unknown_generation_format(self) -> None:
        result = self.validate([row_with(requires_generation='["pdf"]')])

        self.assertCodes(result, "enum_unknown")

    def test_unknown_search_type(self) -> None:
        result = self.validate([row_with(search_type='["intranet"]')])

        self.assertCodes(result, "enum_unknown")


class NumericTest(ValidationTestCase):
    def test_negative_tokens(self) -> None:
        result = self.validate([row_with(user_tokens="-5")])

        self.assertCodes(result, "int_negative")

    def test_non_integer_tokens(self) -> None:
        result = self.validate([row_with(assistant_tokens="12.5")])

        self.assertCodes(result, "int_malformed")

    def test_float_encoded_integer_is_accepted_with_a_warning(self) -> None:
        result = self.validate([row_with(tool_tokens="4300.0")])

        self.assertNoErrors(result)
        self.assertIn("int_float_encoded", {issue.code for issue in result.warnings})

    def test_negative_cost(self) -> None:
        result = self.validate([row_with(estimated_cost="-0.01")])

        self.assertCodes(result, "cost_negative")


class BooleanTest(ValidationTestCase):
    def test_numeric_boolean_is_rejected(self) -> None:
        result = self.validate([row_with(is_work="1")])

        self.assertCodes(result, "bool_unrecognized")

    def test_yes_is_rejected(self) -> None:
        result = self.validate([row_with(prompt_injection="yes")])

        self.assertCodes(result, "bool_unrecognized")

    def test_capitalised_literals_are_accepted(self) -> None:
        result = self.validate([row_with(is_work="True", contains_sensitive_data="FALSE")])

        self.assertNoErrors(result)


class IntegrationTest(ValidationTestCase):
    def test_integration_count_mismatch(self) -> None:
        result = self.validate([row_with(integrations='["exchange", "crm"]', integration_count="1")])

        self.assertCodes(result, "integration_count_mismatch")

    def test_empty_integrations_with_zero_count(self) -> None:
        result = self.validate([row_with(integrations="[]", integration_count="0")])

        self.assertNoErrors(result)


class ToolTest(ValidationTestCase):
    def test_tools_present_but_no_calls(self) -> None:
        result = self.validate([row_with(tools='["email_search"]', tool_calls="0")])

        self.assertCodes(result, "tools_without_calls")

    def test_calls_may_exceed_unique_tools(self) -> None:
        result = self.validate([row_with(tools='["email_search"]', tool_calls="7")])

        self.assertNoErrors(result)

    def test_calls_without_tool_names_is_a_warning(self) -> None:
        result = self.validate([row_with(tools="[]", tool_calls="2")])

        self.assertNoErrors(result)
        self.assertIn("calls_without_tools", {issue.code for issue in result.warnings})


class CompanyDataTest(ValidationTestCase):
    def test_sources_without_company_data_is_an_error(self) -> None:
        result = self.validate([row_with(uses_company_data="false", company_sources='["crm"]')])

        self.assertCodes(result, "company_sources_unexpected")

    def test_company_data_without_sources_is_a_warning(self) -> None:
        result = self.validate([row_with(uses_company_data="true", company_sources="[]")])

        self.assertNoErrors(result)
        self.assertIn("company_sources_missing", {issue.code for issue in result.warnings})


class FailureTest(ValidationTestCase):
    def test_failure_without_reason(self) -> None:
        result = self.validate([row_with(agent_failed="true", failure_reason="")])

        self.assertCodes(result, "failure_reason_missing")

    def test_reason_without_failure(self) -> None:
        result = self.validate([row_with(agent_failed="false", failure_reason="timeout")])

        self.assertCodes(result, "failure_reason_unexpected")

    def test_null_literal_counts_as_no_reason(self) -> None:
        result = self.validate([row_with(agent_failed="false", failure_reason="null")])

        self.assertNoErrors(result)

    def test_failure_with_reason_passes(self) -> None:
        result = self.validate([row_with(agent_failed="true", failure_reason="tool timeout")])

        self.assertNoErrors(result)


class TextTest(ValidationTestCase):
    def test_whitespace_only_summary(self) -> None:
        result = self.validate([row_with(summary="   ")])

        self.assertCodes(result, "text_blank")

    def test_empty_use_case(self) -> None:
        result = self.validate([row_with(use_case="")])

        self.assertCodes(result, "text_blank")


class SoftWarningTest(ValidationTestCase):
    def test_automation_candidate_without_periodicity(self) -> None:
        result = self.validate([row_with(automation_candidate="true", periodicity="none")])

        self.assertNoErrors(result)
        self.assertIn("automation_without_periodicity", {issue.code for issue in result.warnings})

    def test_complex_request_with_zero_steps(self) -> None:
        result = self.validate([row_with(complexity="complex", steps_requested="0")])

        self.assertNoErrors(result)
        self.assertIn("complex_without_steps", {issue.code for issue in result.warnings})

    def test_cost_outlier_needs_a_large_enough_sample(self) -> None:
        rows = [row_with(request_id=f"req-{index:03d}") for index in range(5)]
        rows.append(row_with(request_id="req-999", estimated_cost="99.0"))

        result = self.validate(rows)

        self.assertNoErrors(result)
        self.assertNotIn("cost_outlier", {issue.code for issue in result.warnings})

    def test_cost_outlier_flagged_on_a_large_enough_sample(self) -> None:
        rows = [row_with(request_id=f"req-{index:03d}") for index in range(24)]
        rows.append(row_with(request_id="req-999", estimated_cost="99.0"))

        result = self.validate(rows)

        self.assertNoErrors(result)
        outliers = [issue for issue in result.warnings if issue.code == "cost_outlier"]
        self.assertEqual([issue.request_id for issue in outliers], ["req-999"])


class IssueLocationTest(ValidationTestCase):
    def test_issue_points_at_the_physical_line_and_request(self) -> None:
        rows = [VALID_ROW, row_with(request_id="req-002", confidence="9")]

        result = self.validate(rows)
        issue = result.errors[0]

        # Header is line 1, first data row is line 2, so the bad row is line 3.
        self.assertEqual(issue.line, 3)
        self.assertEqual(issue.request_id, "req-002")
        self.assertEqual(issue.field, "confidence")


class ReportOutputTest(ValidationTestCase):
    def test_errors_csv_has_a_stable_header_when_clean(self) -> None:
        result = self.validate([VALID_ROW])

        _, errors_path = write_reports(result, self.dir / "out")

        with errors_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows, [list(ERROR_CSV_HEADER)])

    def test_reports_are_written_and_parseable(self) -> None:
        result = self.validate([row_with(confidence="5")])

        report_path, errors_path = write_reports(result, self.dir / "out")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["counts"]["error"], 1)
        with errors_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["code"], "confidence_out_of_range")
        self.assertEqual(rows[0]["severity"], "error")

    def test_input_file_is_not_modified(self) -> None:
        analytics = self.write_analytics([VALID_ROW])
        before = analytics.read_bytes()

        result = validate_analytics(analytics, self.classes_path)
        write_reports(result, self.dir / "out")

        self.assertEqual(analytics.read_bytes(), before)


class RegistryTest(ValidationTestCase):
    """Closed-vocabulary checks for tools and integrations."""

    def _vocabularies(self):
        loaded = load_project_registries()
        self.assertIsNotNone(loaded, "config.py must expose FIXED_TOOLS / FIXED_INTEGRATIONS")
        tools, integrations = loaded
        return {"tools": tools, "integrations": integrations}

    def _validate(self, rows):
        return validate_analytics(
            self.write_analytics(rows), self.classes_path, vocabularies=self._vocabularies()
        )

    def test_registry_values_pass(self) -> None:
        result = self._validate([row_with(tools='["mail"]', integrations='["Exchange"]')])

        self.assertNoErrors(result)

    def test_unknown_tool_is_an_error(self) -> None:
        result = self._validate([row_with(tools='["quantum_tool"]')])

        self.assertIn("registry_unknown", {issue.code for issue in result.errors})

    def test_unknown_integration_is_an_error(self) -> None:
        result = self._validate([row_with(integrations='["холодильник"]', integration_count="1")])

        self.assertIn("registry_unknown", {issue.code for issue in result.errors})

    def test_registry_is_case_sensitive_in_the_canonical_file(self) -> None:
        # The adapter is responsible for normalizing case. By the time a value
        # reaches analytics.csv it must already be the canonical spelling.
        result = self._validate([row_with(integrations='["exchange"]')])

        self.assertIn("registry_unknown", {issue.code for issue in result.errors})

    def test_without_vocabularies_shape_only(self) -> None:
        result = self.validate([row_with(tools='["quantum_tool"]')])

        self.assertNoErrors(result)
        self.assertTrue(any("vocabulary" in item for item in result.report()["limitations"]))


class CliTest(ValidationTestCase):
    def _main(self, argv):
        """Run the CLI with its console output captured."""

        with io.StringIO() as out, io.StringIO() as err:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                return main(argv)

    def _run(self, rows, *extra):
        analytics = self.write_analytics(rows)
        return self._main(
            [
                "--analytics", str(analytics),
                "--classes", str(self.classes_path),
                "--out-dir", str(self.dir / "out"),
                "--quiet",
                *extra,
            ]
        )

    def test_clean_file_exits_zero(self) -> None:
        self.assertEqual(self._run([VALID_ROW]), 0)

    def test_invalid_file_exits_one(self) -> None:
        self.assertEqual(self._run([row_with(periodicity="hourly")]), 1)

    def test_warnings_alone_exit_zero(self) -> None:
        self.assertEqual(self._run([row_with(confidence="0.1")]), 0)

    def test_fail_on_warning_flag(self) -> None:
        self.assertEqual(self._run([row_with(confidence="0.1")], "--fail-on-warning"), 1)

    def test_missing_input_exits_two(self) -> None:
        exit_code = self._main(
            [
                "--analytics", str(self.dir / "nope.csv"),
                "--classes", str(self.classes_path),
                "--out-dir", str(self.dir / "out"),
            ]
        )

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
