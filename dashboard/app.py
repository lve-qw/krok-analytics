"""Dash application over the pipeline CSV export.

    python -m dashboard.app --input outputs/analytics.csv

``--input`` also accepts a directory: the app then reads ``analytics.csv`` from
it, or joins ``dialogs.csv`` with ``use_cases.csv`` if the joined file is
missing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from dash import ALL, Dash, Input, Output, State, callback_context, dcc, html, no_update

from dashboard import charts, data, filters, layout, metrics
from dashboard.metrics import LOW_CONFIDENCE, integer, percent
from dashboard.styles import STYLESHEET
from dashboard.theme import get_theme

DEFAULT_INPUT = "outputs"
HIDDEN = {"display": "none"}
MESSAGE_PREVIEW = 120

EXPORT_COLUMNS = [column for column, _, _ in layout.TABLE_COLUMNS]


def _table_records(frame: pd.DataFrame) -> list[dict]:
    if frame.empty:
        return []
    view = pd.DataFrame(index=frame.index)
    view["request_id"] = frame["request_id"]
    view["user_id"] = frame["user_id"]
    view["created_at"] = frame["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("—")
    view["first_user_message"] = frame["first_user_message"].str.slice(0, MESSAGE_PREVIEW)
    view["use_case"] = frame["use_case"]
    view["complexity"] = frame["complexity"]
    view["total_tokens"] = frame["total_tokens"].map(integer)
    view["burned_tokens"] = frame["burned_tokens"].map(integer)
    view["confidence"] = frame["confidence"].map(lambda value: f"{value:.2f}".replace(".", ","))
    return view.to_dict("records")


def _export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [column for column in EXPORT_COLUMNS if column in frame]
    export = frame[columns].copy()
    if "created_at" in export:
        export["created_at"] = export["created_at"].dt.strftime(data.CREATED_AT_FORMAT)
    return export


def _clicked_value(click_data) -> str | None:
    points = (click_data or {}).get("points") or []
    if not points:
        return None
    custom = points[0].get("customdata")
    if isinstance(custom, (list, tuple)) and custom:
        return str(custom[-1])
    return None


def create_app(target: str | Path) -> Dash:
    dataset = data.load(target)
    frame = dataset.frame
    theme = get_theme("light")

    app = Dash(__name__, title="Промпт-радар · метрики")
    app.index_string = f"""<!DOCTYPE html>
<html>
<head>{{%metas%}}<title>{{%title%}}</title>{{%favicon%}}{{%css%}}<style>{STYLESHEET}</style></head>
<body>{{%app_entry%}}<footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer></body>
</html>"""

    # The source path belongs in the terminal, not on a page shown to a room.
    print(f"Источник: {dataset.source} · строк: {dataset.rows}", file=sys.stderr)
    for note in dataset.notes:
        print(f"  ! {note}", file=sys.stderr)

    app.layout = layout.build(frame, metrics.kpis(frame), theme, dataset.notes)

    filter_inputs = Input({"type": "filter", "key": ALL}, "value")
    filter_states = State({"type": "filter", "key": ALL}, "id")

    def _selections(values, ids) -> dict:
        return {identifier["key"]: value for identifier, value in zip(ids, values)}

    @app.callback(
        Output("kpi-container", "children"),
        Output("result-count", "children"),
        Output("chart-token-split", "figure"),
        Output("chart-tokens-scenario", "figure"),
        Output("chart-scenario-map", "figure"),
        Output("chart-complexity-auto", "figure"),
        Output("chart-failures", "figure"),
        Output("stat-problems", "children"),
        Output("chart-quality", "figure"),
        Output("stat-quality", "children"),
        Output("chart-confidence", "figure"),
        Output("chart-users", "figure"),
        Output("chart-hourly", "figure"),
        Output("chart-clusters", "figure"),
        Output("stat-clusters", "children"),
        Output("chart-integrations", "figure"),
        Output("stat-integrations", "children"),
        Output("chart-tools", "figure"),
        Output("dialogs-table", "data"),
        filter_inputs,
        Input("flag-filters", "value"),
        Input("users-metric", "value"),
        Input("hourly-metric", "value"),
        Input("theme-store", "data"),
        Input("selection-store", "data"),
        filter_states,
    )
    def refresh(values, flags, users_metric, hourly_metric, theme_name, selection, ids):
        active_theme = get_theme(theme_name)
        filtered = filters.apply(frame, _selections(values, ids), flags)
        rows = filters.apply_selection(filtered, selection)

        quality = metrics.quality(filtered)
        token_stats = metrics.tokens(filtered)
        cluster_stats = metrics.clusters(filtered)
        integration_stats = metrics.integrations(filtered)
        problem_stats = metrics.problems(filtered)
        confidence_stats = metrics.confidence(filtered)
        cards = metrics.kpis(filtered)

        result = f"Показано {len(filtered)} из {len(frame)} диалогов."
        if len(rows) != len(filtered):
            selected = (selection or {}).get("value")
            result += f" В таблице — {len(rows)} диалогов пользователя {selected}."

        return (
            [layout.kpi_row(cards[:4]), layout.kpi_row(cards[4:])],
            result,
            # Куда уходят токены?
            charts.donut(metrics.token_split(filtered), active_theme),
            charts.ranked_bar(
                metrics.tokens_by_scenario(filtered),
                active_theme,
                value="tokens",
                limit=10,
                unit="токенов",
                divisor=1000,
                axis_title="Токены, тыс.",
                color=active_theme.series[0],
            ),
            # Что автоматизировать первым?
            charts.scenario_scatter(metrics.scenario_map(filtered), active_theme),
            charts.grouped_bar(
                metrics.complexity_by_automation(filtered),
                active_theme,
                left=("candidates", "Кандидаты"),
                right=("rest", "Остальные"),
            ),
            # Где агент ломается?
            charts.ranked_bar(
                problem_stats["failure_reasons"],
                active_theme,
                limit=8,
                color=active_theme.critical,
                height=260,
            ),
            layout.stat_strip(
                [
                    ("отказов агента", integer(problem_stats["agent_failures"])),
                    ("prompt injection", integer(problem_stats["prompt_injections"])),
                    ("с чувствительными данными", integer(problem_stats["sensitive_data"])),
                ]
            ).children,
            charts.stacked_pair(
                active_theme,
                left_label="Полезные",
                left_value=quality["useful_messages_total"],
                right_label="Бесполезные",
                right_value=quality["useless_messages_total"],
            ),
            layout.stat_strip(
                [
                    ("полезных сообщений", f"{percent(quality['useful_ratio'])} %"),
                    ("диалогов с сожжёнными токенами", integer(quality["dialogs_with_burned"])),
                    (
                        "сожжено в среднем на такой диалог",
                        integer(quality["avg_burned_per_failed_dialog"]),
                    ),
                    ("доля сожжённых токенов", f"{percent(token_stats['burned_ratio'])} %"),
                ]
            ).children,
            charts.confidence_histogram(confidence_stats["values"], active_theme, LOW_CONFIDENCE),
            # Кто и когда пользуется?
            charts.usage_bar(
                metrics.usage_ranking(filtered, users_metric),
                active_theme,
                users_metric,
                (selection or {}).get("value"),
            ),
            charts.hourly_profile(metrics.hourly_load(filtered), active_theme, hourly_metric),
            # Что это за диалоги?
            charts.ranked_bar(
                cluster_stats["sizes"],
                active_theme,
                label="label",
                limit=10,
                color=active_theme.series[0],
            ),
            layout.stat_strip(
                [
                    ("кластеров", integer(cluster_stats["total_clusters"])),
                    ("диалогов вне кластеров", integer(cluster_stats["outliers"])),
                    (
                        "средний размер кластера",
                        f"{cluster_stats['avg_cluster_size']:.1f}".replace(".", ","),
                    ),
                ]
            ).children,
            charts.ranked_bar(
                integration_stats["integration_counts"],
                active_theme,
                limit=12,
                color=active_theme.series[2],
            ),
            layout.stat_strip(
                [
                    (
                        "диалогов с интеграциями",
                        integer(integration_stats["dialogs_with_integrations"]),
                    ),
                    ("уникальных интеграций", integer(integration_stats["unique_integrations"])),
                    ("уникальных инструментов", integer(integration_stats["unique_tools"])),
                    (
                        "вызовов инструментов на диалог",
                        f"{integration_stats['avg_tool_calls']:.1f}".replace(".", ","),
                    ),
                ]
            ).children,
            charts.ranked_bar(
                integration_stats["tool_counts"],
                active_theme,
                limit=12,
                color=active_theme.series[1],
            ),
            _table_records(rows),
        )

    @app.callback(
        Output("selection-store", "data"),
        Input("chart-users", "clickData"),
        Input("clear-selection", "n_clicks"),
        Input("reset-filters", "n_clicks"),
        State("selection-store", "data"),
        prevent_initial_call=True,
    )
    def select(users_click, _clear, _reset, current):
        trigger = callback_context.triggered_id
        if trigger in ("clear-selection", "reset-filters"):
            return None
        if trigger != "chart-users":
            return no_update
        value = _clicked_value(users_click)
        if value is None:
            return no_update
        chosen = {"column": "user_id", "value": value}
        return None if current == chosen else chosen

    @app.callback(
        Output("filter-chips", "children"),
        Output("clear-selection", "children"),
        Output("clear-selection", "style"),
        filter_inputs,
        Input("flag-filters", "value"),
        Input("selection-store", "data"),
        filter_states,
    )
    def chips(values, flags, selection, ids):
        active = filters.active(_selections(values, ids), flags)
        children = [
            html.Span([f"{label}: ", html.B(text)], className="chip") for label, text in active
        ]
        if not active and not selection:
            children.append(html.Span("Показаны все диалоги", className="chip-none"))
        if not selection:
            return children, None, HIDDEN
        return (
            children,
            [
                html.Span(["Выбран пользователь: ", html.B(selection["value"])]),
                html.Span("✕", className="chip-x"),
            ],
            {"display": "inline-flex"},
        )

    @app.callback(
        Output({"type": "filter", "key": ALL}, "value"),
        Output("flag-filters", "value"),
        Input("reset-filters", "n_clicks"),
        filter_states,
        prevent_initial_call=True,
    )
    def reset(_clicks, ids):
        return [[] for _identifier in ids], []

    @app.callback(
        Output("download-csv", "data"),
        Input("export-button", "n_clicks"),
        filter_states,
        State({"type": "filter", "key": ALL}, "value"),
        State("flag-filters", "value"),
        State("selection-store", "data"),
        prevent_initial_call=True,
    )
    def export(_clicks, ids, values, flags, selection):
        filtered = filters.apply(frame, _selections(values, ids), flags)
        rows = filters.apply_selection(filtered, selection)
        return dcc.send_data_frame(_export_frame(rows).to_csv, "dialogs_filtered.csv", index=False)

    @app.callback(
        Output("theme-store", "data"),
        Output("viz-root", "className"),
        Input("theme-toggle", "n_clicks"),
        State("theme-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_theme(_clicks, current):
        next_theme = "dark" if current == "light" else "light"
        return next_theme, f"viz-root theme-{next_theme}"

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=DEFAULT_INPUT, help="CSV файл или каталог выгрузки")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    try:
        app = create_app(args.input)
    except data.DataError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
