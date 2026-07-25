"""Tests for the CSV parsing and the metrics behind the dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import data, filters, metrics  # noqa: E402

HEADER = (
    "request_id,user_id,created_at,is_work,automation_candidate,agent_failed,"
    "prompt_injection,contains_sensitive_data,complexity,periodicity,language,"
    "integrations,tools,integration_count,tool_calls,user_tokens,assistant_tokens,"
    "tool_tokens,total_tokens,estimated_cost,burned_tokens,useful_messages,"
    "useless_messages,confidence,failure_reason,first_user_message,analysis_status,"
    "cluster_id,use_case,member_count"
)

ROWS = [
    # id, user, time, is_work, auto, failed, inj, sens, complexity, periodicity, lang,
    "r1,u1,2026-07-25T08:00:00Z,True,True,False,False,False,simple,daily,ru,"
    "Jira;CRM,jira;mail,2,4,10,90,100,200,0.02,20,8,2,0.9,,Найди задачи,success,1,Задачи,2",
    "r2,u1,2026-07-25T09:00:00Z,True,False,True,False,True,medium,none,ru,"
    "Jira,jira,1,2,10,40,50,100,0.01,0,4,1,0.4,timeout,Собери отчёт,success,1,Задачи,2",
    "r3,u2,2026-07-26T10:00:00Z,False,False,False,True,False,complex,weekly,en,"
    ",,0,0,10,10,0,20,0.00,0,1,0,0.8,,Hi,success,-1,,0",
]


def write_csv(path: Path, rows: list[str] = None) -> Path:
    path.write_text("\n".join([HEADER, *(rows if rows is not None else ROWS)]), encoding="utf-8-sig")
    return path


@pytest.fixture
def frame(tmp_path: Path) -> pd.DataFrame:
    return data.load(write_csv(tmp_path / "analytics.csv")).frame


# --- parsing ------------------------------------------------------------


def test_load_casts_every_column_group(frame: pd.DataFrame):
    assert frame["is_work"].dtype == bool
    assert frame["total_tokens"].dtype.kind == "i"
    assert frame["confidence"].dtype.kind == "f"
    assert frame["integrations"].iloc[0] == ["Jira", "CRM"]
    assert frame["created_at"].iloc[0].hour == 8


def test_missing_categorical_values_get_a_visible_placeholder(frame: pd.DataFrame):
    assert frame["use_case"].iloc[2] == data.UNKNOWN


def test_cluster_outliers_keep_their_negative_label(frame: pd.DataFrame):
    assert frame["cluster_id"].tolist() == [1, 1, -1]


def test_directory_without_analytics_joins_the_pair(tmp_path: Path):
    write_csv(tmp_path / "dialogs.csv")
    (tmp_path / "use_cases.csv").write_text(
        "request_id,cluster_id,use_case,member_count\nr1,1,Задачи,2\nr2,1,Задачи,2\nr3,-1,,0",
        encoding="utf-8-sig",
    )
    dataset = data.load(tmp_path)
    assert dataset.source.name == "dialogs.csv"
    assert dataset.frame["use_case"].iloc[0] == "Задачи"
    assert any("use_cases.csv" in note for note in dataset.notes)


def test_missing_required_column_is_refused(tmp_path: Path):
    path = tmp_path / "analytics.csv"
    path.write_text("request_id,user_id\nr1,u1", encoding="utf-8-sig")
    with pytest.raises(data.DataError):
        data.load(path)


def test_all_zero_classifier_columns_are_reported(tmp_path: Path):
    rows = [row.replace(",20,8,2,0.9,", ",0,0,0,0.9,").replace(",0,4,1,0.4,", ",0,0,0,0.4,")
            for row in ROWS]
    rows = [row.replace(",0,1,0,0.8,", ",0,0,0,0.8,") for row in rows]
    dataset = data.load(write_csv(tmp_path / "analytics.csv", rows))
    assert any("Классификатор сообщений" in note for note in dataset.notes)


# --- metrics ------------------------------------------------------------


def test_overview_counts_rows_users_and_days(frame: pd.DataFrame):
    base = metrics.overview(frame)
    assert (base["total_dialogs"], base["total_users"], base["days"]) == (3, 2, 2)


def test_token_totals_and_burned_share(frame: pd.DataFrame):
    stats = metrics.tokens(frame)
    assert stats["total_tokens"] == 320
    assert stats["total_burned_tokens"] == 20
    assert stats["burned_ratio"] == pytest.approx(6.25)
    assert stats["total_estimated_cost"] == pytest.approx(0.03)


def test_useful_ratio_and_burned_subset(frame: pd.DataFrame):
    stats = metrics.quality(frame)
    assert (stats["useful_messages_total"], stats["useless_messages_total"]) == (13, 3)
    assert stats["useful_ratio"] == pytest.approx(13 / 16 * 100)
    # Averaged over dialogues that burned something, not over all of them.
    assert stats["dialogs_with_burned"] == 1
    assert stats["avg_burned_per_failed_dialog"] == pytest.approx(20)


def test_classification_shares(frame: pd.DataFrame):
    stats = metrics.classification(frame)
    assert (stats["work_dialogs"], stats["automation_candidates"]) == (2, 1)
    assert stats["work_ratio"] == pytest.approx(200 / 3)


def test_distributions_keep_the_documented_order(frame: pd.DataFrame):
    assert metrics.complexity_distribution(frame)["key"].tolist() == ["simple", "medium", "complex"]
    assert metrics.periodicity_distribution(frame)["key"].tolist() == ["none", "daily", "weekly"]


def test_integrations_and_tools_are_counted_per_dialogue(frame: pd.DataFrame):
    stats = metrics.integrations(frame)
    assert stats["dialogs_with_integrations"] == 2
    assert stats["unique_integrations"] == 2
    assert stats["unique_tools"] == 2
    assert stats["avg_tool_calls"] == pytest.approx(2.0)
    counts = dict(zip(stats["integration_counts"]["key"], stats["integration_counts"]["dialogs"]))
    assert counts == {"Jira": 2, "CRM": 1}


def test_clusters_count_clusters_not_dialogues(frame: pd.DataFrame):
    stats = metrics.clusters(frame)
    assert stats["total_clusters"] == 1
    assert stats["outliers"] == 1
    assert stats["avg_cluster_size"] == pytest.approx(2.0)


def test_clusters_recount_sizes_under_a_filter(frame: pd.DataFrame):
    one_dialogue = frame[frame["request_id"] == "r1"]
    sizes = metrics.clusters(one_dialogue)["sizes"]
    # member_count in the file says 2; only one row is visible.
    assert sizes["dialogs"].tolist() == [1]


def test_clusters_with_the_same_name_get_distinct_labels(tmp_path: Path):
    rows = list(ROWS) + [
        "r4,u3,2026-07-25T11:00:00Z,True,False,False,False,False,simple,none,ru,"
        ",,0,0,5,5,0,10,0.00,0,1,0,0.7,,Ещё,success,7,Задачи,1"
    ]
    frame = data.load(write_csv(tmp_path / "analytics.csv", rows)).frame
    labels = metrics.clusters(frame)["sizes"]["label"].tolist()
    assert sorted(labels) == ["Задачи · #1", "Задачи · #7"]


def test_problems_group_failure_reasons(frame: pd.DataFrame):
    stats = metrics.problems(frame)
    assert (stats["agent_failures"], stats["prompt_injections"], stats["sensitive_data"]) == (1, 1, 1)
    assert stats["failure_reasons"]["key"].tolist() == ["timeout"]


def test_confidence_threshold(frame: pd.DataFrame):
    stats = metrics.confidence(frame)
    assert stats["avg_confidence"] == pytest.approx(0.7)
    assert stats["low_confidence_dialogs"] == 1


def test_kpi_says_not_measured_instead_of_zero_percent(tmp_path: Path):
    rows = [row.replace(",20,8,2,", ",0,0,0,").replace(",0,4,1,", ",0,0,0,").replace(",0,1,0,", ",0,0,0,")
            for row in ROWS]
    frame = data.load(write_csv(tmp_path / "analytics.csv", rows)).frame
    cards = {card.label: card for card in metrics.kpis(frame)}
    assert cards["Полезные сообщения"].value == "—"
    assert cards["Сожжённые токены"].value == "—"


def test_kpis_on_an_empty_frame_do_not_raise(frame: pd.DataFrame):
    assert metrics.kpis(frame.iloc[0:0])[0].value == "0"


# --- scenario map and generated conclusions -----------------------------


def test_scenario_map_reports_scale_and_readiness(frame: pd.DataFrame):
    table = metrics.scenario_map(frame)
    assert table["cluster_id"].tolist() == [1]
    row = table.iloc[0]
    # Two of three dialogues sit in cluster 1, one of them is a candidate.
    assert row["dialogs"] == 2
    assert row["share"] == pytest.approx(200 / 3)
    assert row["automation_share"] == pytest.approx(50.0)
    assert row["simple_share"] == pytest.approx(50.0)
    assert row["avg_tokens"] == pytest.approx(150.0)


def test_scenario_map_ignores_outliers(frame: pd.DataFrame):
    assert "r3" not in metrics.scenario_map(frame).get("label", pd.Series(dtype=str)).tolist()


def test_tokens_by_scenario_is_ranked(tmp_path: Path):
    rows = list(ROWS) + [
        "r4,u3,2026-07-25T11:00:00Z,True,False,False,False,False,simple,none,ru,"
        ",,0,0,5,5,0,1000,0.00,0,1,0,0.7,,Ещё,success,7,Крупный,1"
    ]
    frame = data.load(write_csv(tmp_path / "analytics.csv", rows)).frame
    ranked = metrics.tokens_by_scenario(frame)
    assert ranked["key"].tolist()[0] == "Крупный"
    assert ranked["tokens"].tolist() == [1000, 300]


def test_complexity_by_automation_splits_each_group(frame: pd.DataFrame):
    table = metrics.complexity_by_automation(frame)
    rows = {row.key: (row.candidates, row.rest) for row in table.itertuples()}
    assert rows["simple"] == (1, 0)
    assert rows["medium"] == (0, 1)
    assert rows["complex"] == (0, 1)


def test_insights_quote_the_visible_numbers(frame: pd.DataFrame):
    lines = metrics.insights(frame)
    assert "46,9 %" in lines["tokens"]  # 150 of 320 tokens are tool traffic
    assert "1 из 3" in lines["automation"]
    assert "timeout" in lines["failures"]
    assert "2 пользователя" in lines["usage"]
    assert "вне кластеров осталось 1" in lines["catalogue"]


def test_insights_follow_the_filter(frame: pd.DataFrame):
    only_first = frame[frame["request_id"] == "r1"]
    assert "1 из 1" in metrics.insights(only_first)["automation"]


def test_insights_say_when_a_thing_never_happened(frame: pd.DataFrame):
    calm = frame[frame["request_id"] == "r1"]
    assert "не отметил отказ" in metrics.insights(calm)["failures"]


def test_insights_on_an_empty_frame_do_not_raise(frame: pd.DataFrame):
    lines = metrics.insights(frame.iloc[0:0])
    assert set(lines) == {"tokens", "automation", "failures", "usage", "catalogue", "profile"}
    assert all("Фильтры" in line for line in lines.values())


@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "диалог"), (2, "диалога"), (5, "диалогов"), (11, "диалогов"), (21, "диалог"), (94, "диалога")],
)
def test_russian_plural_agreement(count: int, expected: str):
    assert metrics.plural(count, "диалог", "диалога", "диалогов") == expected


# --- filters ------------------------------------------------------------


def test_categorical_filters_combine_as_and(frame: pd.DataFrame):
    filtered = filters.apply(frame, {"user_id": ["u1"], "complexity": ["simple"]})
    assert filtered["request_id"].tolist() == ["r1"]


def test_flags_narrow_to_the_subset(frame: pd.DataFrame):
    assert filters.apply(frame, {}, ["agent_failed"])["request_id"].tolist() == ["r2"]
    assert filters.apply(frame, {}, ["is_work"])["request_id"].tolist() == ["r1", "r2"]


def test_chart_selection_narrows_to_one_user(frame: pd.DataFrame):
    selected = filters.apply_selection(frame, {"column": "user_id", "value": "u2"})
    assert selected["request_id"].tolist() == ["r3"]


def test_active_describes_filters_and_flags(frame: pd.DataFrame):
    chips = filters.active({"user_id": ["u1"]}, ["is_work"])
    assert chips == [("Пользователь", "u1"), ("Признак", "Только рабочие")]
