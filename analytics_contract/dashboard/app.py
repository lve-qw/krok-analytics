"""Dash application entry point.

    python -m analytics_contract.dashboard.app \
        --input outputs/analytics.canonical.csv

The app refuses to start unless the input passes the canonical contract.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from dash import ALL, Dash, Input, Output, State, callback_context, dcc, html

from analytics_contract.dashboard import charts, data_loader, filters as filters_module, layout, metrics
from analytics_contract.dashboard.styles import STYLESHEET
from analytics_contract.dashboard.theme import get_theme
from analytics_contract.schema import DRILLDOWN_COLUMNS

DEFAULT_INPUT = "outputs/analytics.canonical.csv"
DEFAULT_CLASSES = "data/classes_31.csv"


def _drilldown_records(frame: pd.DataFrame) -> list[dict]:
    if frame.empty:
        return []
    view = frame[list(DRILLDOWN_COLUMNS)].copy()
    for column in ("class_names", "integrations", "tools"):
        view[column] = view[column].map(lambda values: ", ".join(values) if values else "—")
    view["confidence"] = view["confidence"].map(lambda value: f"{value:.2f}")
    view["estimated_cost"] = view["estimated_cost"].map(lambda value: f"{value:.5f}")
    for column in ("automation_candidate", "agent_failed"):
        view[column] = view[column].map({True: "да", False: "нет"})
    view["failure_reason"] = view["failure_reason"].replace("", "—")
    return view.to_dict("records")


def create_app(analytics_path: str, classes_path: str, low_confidence: float = 0.5) -> Dash:
    dataset = data_loader.load(analytics_path, classes_path)
    frame = dataset.frame
    theme = get_theme("light")

    app = Dash(__name__, title="Prompt Radar")
    app.index_string = f"""<!DOCTYPE html>
<html>
<head>{{%metas%}}<title>{{%title%}}</title>{{%favicon%}}{{%css%}}<style>{STYLESHEET}</style></head>
<body>{{%app_entry%}}<footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer></body>
</html>"""

    app.layout = layout.build(
        frame, metrics.kpis(frame, low_confidence), dataset.limitations, theme
    )

    filter_inputs = Input({"type": "filter", "key": ALL}, "value")
    filter_states = State({"type": "filter", "key": ALL}, "id")

    def _selections(values, ids) -> dict:
        return {identifier["key"]: value for identifier, value in zip(ids, values)}

    @app.callback(
        Output("kpi-container", "children"),
        Output("result-count", "children"),
        Output("chart-volume", "figure"),
        Output("chart-periodicity", "figure"),
        Output("chart-failure", "figure"),
        Output("chart-reliability", "figure"),
        Output("chart-cost", "figure"),
        Output("chart-tokens", "figure"),
        Output("chart-security", "figure"),
        Output("drilldown", "data"),
        filter_inputs,
        Input("volume-dimension", "value"),
        Input("reliability-dimension", "value"),
        Input("theme-store", "data"),
        filter_states,
    )
    def refresh(values, volume_dimension, reliability_dimension, theme_name, ids):
        active = get_theme(theme_name)
        filtered = filters_module.apply(frame, _selections(values, ids))

        volume_data = (
            metrics.top_use_cases(filtered)
            if volume_dimension == "use_case"
            else metrics.top_classes(filtered)
        )
        overlap = metrics.exposure_overlap(filtered)

        count_text = (
            f"Показано {len(filtered)} из {len(frame)} диалогов. "
            f"Пересечение чувствительных данных, корпоративных источников и "
            f"внешнего поиска: {overlap} записей — каждая требует ручного разбора."
        )

        return (
            layout.kpi_row(metrics.kpis(filtered, low_confidence)),
            count_text,
            charts.volume_bar(volume_data, active),
            charts.periodicity_heatmap(metrics.use_case_periodicity(filtered), active),
            charts.failure_scatter(metrics.failure_by_use_case(filtered), active),
            charts.reliability_bar(
                metrics.reliability(filtered, reliability_dimension),
                active,
                reliability_dimension,
            ),
            charts.cost_pareto(metrics.cost_pareto(filtered), active),
            charts.token_split_bar(metrics.token_split(filtered), active),
            charts.security_heatmap(metrics.security_matrix(filtered), active),
            _drilldown_records(filtered),
        )

    @app.callback(
        Output({"type": "filter", "key": ALL}, "value"),
        Input("reset-filters", "n_clicks"),
        filter_states,
        prevent_initial_call=True,
    )
    def reset(_clicks, ids):
        return [
            filters_module.ANY
            if next(spec for spec in filters_module.FILTERS if spec.key == identifier["key"]).kind
            == "bool"
            else []
            for identifier in ids
        ]

    @app.callback(
        Output("download-csv", "data"),
        Input("export-button", "n_clicks"),
        filter_states,
        State({"type": "filter", "key": ALL}, "value"),
        prevent_initial_call=True,
    )
    def export(_clicks, ids, values):
        filtered = filters_module.apply(frame, _selections(values, ids))
        export_frame = filtered.copy()
        for column in ("class_ids", "class_names", "integrations", "tools",
                       "company_sources", "requires_generation", "search_type"):
            export_frame[column] = export_frame[column].map(lambda values: "; ".join(values))
        return dcc.send_data_frame(
            export_frame.to_csv, "analytics_filtered_DEMO_SYNTHETIC.csv", index=False
        )

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
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--classes", default=DEFAULT_CLASSES)
    parser.add_argument("--low-confidence", type=float, default=0.5)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    if not Path(args.input).exists():
        print(f"error: {args.input} not found. Run analytics_export.py first.", file=sys.stderr)
        return 2

    try:
        app = create_app(args.input, args.classes, args.low_confidence)
    except data_loader.ContractViolation as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
