"""Dash application entry point.

    python -m analytics_contract.dashboard.app \
        --input outputs/analytics.canonical.csv

The app refuses to start unless the input passes the canonical contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from dash import ALL, Dash, Input, Output, State, callback_context, dcc, html, no_update

from analytics_contract.dashboard import (
    charts,
    data_loader,
    filters as filters_module,
    labels,
    layout,
    metrics,
)
from analytics_contract.dashboard.styles import STYLESHEET
from analytics_contract.dashboard.theme import get_theme
from analytics_contract.schema import DRILLDOWN_COLUMNS

DEFAULT_INPUT = "outputs/analytics.canonical.csv"
DEFAULT_CLASSES = "data/classes_31.csv"

#: Charts a click can select from. Each one draws a scenario the user can point
#: at; the trailing element of every point's customdata is the stored value.
SELECTABLE_CHARTS = ("chart-volume", "chart-failure", "chart-cost")

HIDDEN = {"display": "none"}
VISIBLE = {"display": "block"}


def _drilldown_records(frame: pd.DataFrame) -> list[dict]:
    """Table rows, with every stored value passed through the label layer."""

    if frame.empty:
        return []
    view = frame[list(DRILLDOWN_COLUMNS)].copy()
    view["class_names"] = view["class_names"].map(labels.joined)
    view["integrations"] = view["integrations"].map(lambda v: labels.joined(v, "integrations"))
    view["tools"] = view["tools"].map(lambda v: labels.joined(v, "tools"))
    view["use_case"] = view["use_case"].map(labels.use_case)
    view["complexity"] = view["complexity"].map(lambda v: labels.show(v, "complexity"))
    view["failure_reason"] = view["failure_reason"].map(
        lambda v: labels.show(v, "failure_reason") if str(v).strip() else "—"
    )
    view["confidence"] = view["confidence"].map(lambda value: f"{value:.2f}")
    view["estimated_cost"] = view["estimated_cost"].map(lambda value: f"{value:.5f}")
    for column in ("automation_candidate", "agent_failed"):
        view[column] = view[column].map({True: "да", False: "нет"})
    return view.to_dict("records")


def _clicked_value(click_data) -> str | None:
    """The stored value behind a clicked mark, or None."""

    if not click_data:
        return None
    points = click_data.get("points") or []
    if not points:
        return None
    custom = points[0].get("customdata")
    if isinstance(custom, (list, tuple)) and custom:
        return str(custom[-1])
    return None


def _load_report(analytics_path: str) -> dict:
    """The adapter's report, if it sits next to the input."""

    report = Path(analytics_path).parent / "export_report.json"
    if not report.exists():
        return {}
    try:
        return json.loads(report.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_counts(analytics_path: str) -> dict | None:
    """Row counts from the adapter's report, if it sits next to the input."""

    counts = _load_report(analytics_path).get("counts")
    if not counts or not {"input_rows", "exported_rows", "error_rows"} <= set(counts):
        return None
    return counts


def create_app(
    analytics_path: str,
    classes_path: str,
    low_confidence: float = 0.5,
    cost_model: metrics.CostModel = metrics.DEFAULT_COST_MODEL,
    demo_badge: bool = False,
) -> Dash:
    dataset = data_loader.load(analytics_path, classes_path)
    frame = dataset.frame
    theme = get_theme("light")

    # Ingest-side facts the contract file cannot carry: how many rows the
    # adapter saw, and how many failed dialogues never made it through the
    # analyser. Both are needed for the observability card to state the size of
    # its own blind spot instead of implying there isn't one.
    report = _load_report(analytics_path)
    input_rows = (report.get("counts") or {}).get("input_rows")
    dropped_failures = report.get("dropped_agent_failures", 0)

    def _cards(
        subset: pd.DataFrame,
        minutes_saved: float = metrics.DEFAULT_MINUTES_SAVED,
    ) -> list[metrics.Kpi]:
        # Ingest counts describe the whole file, so they are only meaningful
        # while the view is unfiltered; a filtered view reports itself.
        whole = len(subset) == len(frame)
        return metrics.kpis(
            subset,
            low_confidence,
            model=cost_model,
            dropped_failures=dropped_failures if whole else 0,
            input_rows=input_rows if whole else None,
            minutes_saved=minutes_saved,
        )

    app = Dash(__name__, title="Prompt Radar")
    app.index_string = f"""<!DOCTYPE html>
<html>
<head>{{%metas%}}<title>{{%title%}}</title>{{%favicon%}}{{%css%}}<style>{STYLESHEET}</style></head>
<body>{{%app_entry%}}<footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer></body>
</html>"""

    app.layout = layout.build(
        frame,
        _cards(frame),
        dataset.limitations,
        theme,
        _load_counts(analytics_path),
        demo_badge,
    )

    filter_inputs = Input({"type": "filter", "key": ALL}, "value")
    filter_states = State({"type": "filter", "key": ALL}, "id")

    def _selections(values, ids) -> dict:
        return {identifier["key"]: value for identifier, value in zip(ids, values)}

    @app.callback(
        Output("kpi-container", "children"),
        Output("result-count", "children"),
        Output("chart-adoption", "figure"),
        Output("chart-hourly", "figure"),
        Output("chart-economics", "figure"),
        Output("chart-automation", "figure"),
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
        Input("usage-metric", "value"),
        Input("reliability-dimension", "value"),
        Input("minutes-saved", "value"),
        Input("theme-store", "data"),
        Input("selection-store", "data"),
        filter_states,
    )
    def refresh(
        values,
        volume_dimension,
        usage_metric,
        reliability_dimension,
        minutes_saved,
        theme_name,
        selection,
        ids,
    ):
        active = get_theme(theme_name)
        filtered = filters_module.apply(frame, _selections(values, ids))
        records = filters_module.apply_selection(filtered, selection)

        # The highlight only applies to the chart whose axis the value lives
        # on: a selected class must not dim the scenario bars.
        chosen = (selection or {}).get("value")
        chosen_column = (selection or {}).get("column")
        volume_selected = chosen if chosen_column == volume_dimension else None
        scenario_selected = chosen if chosen_column == "use_case" else None

        usage_data = metrics.usage_ranking(filtered, volume_dimension, usage_metric)
        usage_total = {
            "dialogues": len(filtered),
            "tokens": float(filtered["total_tokens"].sum()),
            "tool_calls": float(filtered["tool_calls"].sum()),
        }[usage_metric]
        overlap = metrics.exposure_overlap(filtered)
        capacity = metrics.saved_capacity(filtered, minutes_saved)

        count = [
            f"Показано {len(filtered)} из {len(frame)} диалогов. ",
            f"Совпадение чувствительных данных, корпоративных источников и внешнего "
            f"поиска в одном диалоге: {overlap} — каждая такая запись требует "
            f"ручного разбора.",
        ]
        if len(records) != len(filtered):
            count.insert(1, f"В таблице «Записи» — {len(records)} по выбору на диаграмме. ")

        return (
            layout.kpi_row(_cards(filtered, minutes_saved)),
            count,
            charts.lorenz_curve(
                metrics.lorenz(filtered), active, metrics.adoption(filtered)["gini"]
            ),
            charts.hourly_profile(metrics.hourly_load(filtered), active),
            charts.economics_curve(
                metrics.economics_curve(filtered, cost_model),
                active,
                metrics.breakeven_minutes(filtered, cost_model.monthly_rub),
                cost_model.monthly_rub,
                minutes_saved,
                capacity["fte"],
            ),
            charts.automation_bubbles(metrics.automation_matrix(filtered), active),
            charts.usage_bar(
                usage_data,
                active,
                volume_dimension,
                usage_metric,
                volume_selected,
                usage_total,
            ),
            charts.periodicity_heatmap(metrics.use_case_periodicity(filtered), active),
            charts.failure_scatter(metrics.failure_by_use_case(filtered), active, scenario_selected),
            charts.reliability_bar(
                metrics.reliability(filtered, reliability_dimension),
                active,
                reliability_dimension,
            ),
            charts.cost_pareto(metrics.cost_pareto(filtered), active, scenario_selected),
            charts.token_split_bar(metrics.token_split(filtered), active),
            charts.security_heatmap(metrics.security_matrix(filtered), active),
            _drilldown_records(records),
        )

    @app.callback(
        Output("selection-store", "data"),
        Input("chart-volume", "clickData"),
        Input("chart-failure", "clickData"),
        Input("chart-cost", "clickData"),
        Input("clear-selection", "n_clicks"),
        Input("reset-filters", "n_clicks"),
        State("volume-dimension", "value"),
        State("selection-store", "data"),
        prevent_initial_call=True,
    )
    def select(volume_click, failure_click, cost_click, _clear, _reset, dimension, current):
        trigger = callback_context.triggered_id
        if trigger in ("clear-selection", "reset-filters"):
            return None
        if trigger not in SELECTABLE_CHARTS:
            return no_update

        clicks = {
            "chart-volume": volume_click,
            "chart-failure": failure_click,
            "chart-cost": cost_click,
        }
        value = _clicked_value(clicks[trigger])
        if value is None:
            return no_update

        column = dimension if trigger == "chart-volume" else "use_case"
        chosen = {"column": column, "value": value}
        # Clicking the selected mark again clears it, so the chart itself is
        # always a way out of the state it put you in.
        return None if current == chosen else chosen

    @app.callback(
        Output("filter-chips", "children"),
        Output("clear-selection", "children"),
        Output("clear-selection", "style"),
        filter_inputs,
        Input("selection-store", "data"),
        filter_states,
    )
    def chips(values, selection, ids):
        """Everything currently narrowing the data, shown as removable state.

        A filter nobody can see is a filter everybody forgets, and a forgotten
        filter is how a wrong number ends up on a slide.
        """

        active = filters_module.active(_selections(values, ids))
        children = [
            html.Span([f"{spec.label}: ", html.B(text)], className="chip")
            for spec, text in active
        ]
        if not active and not selection:
            children.append(
                html.Span("Фильтры не заданы — показаны все записи", className="chip-none")
            )

        if not selection:
            return children, None, HIDDEN

        label = labels.show(selection["value"], selection["column"])
        return (
            children,
            [
                html.Span(["Выбрано на диаграмме: ", html.B(label)]),
                html.Span("✕", className="chip-x"),
            ],
            {"display": "inline-flex"},
        )

    @app.callback(
        Output("panel-overview", "style"),
        Output("panel-scenarios", "style"),
        Output("panel-reliability", "style"),
        Output("panel-records", "style"),
        Input("tabs", "value"),
    )
    def switch_tab(value):
        return tuple(VISIBLE if key == value else HIDDEN for key, _ in layout.TABS)

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
        State("selection-store", "data"),
        prevent_initial_call=True,
    )
    def export(_clicks, ids, values, selection):
        filtered = filters_module.apply(frame, _selections(values, ids))
        export_frame = filters_module.apply_selection(filtered, selection).copy()
        # Stored values, not captions: the export has to load back into the
        # same contract it came from.
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
    # Cost inputs live outside analytics.csv, so they are flags rather than
    # constants: the whole economics screen recomputes from these four numbers.
    default = metrics.DEFAULT_COST_MODEL
    parser.add_argument("--server-capex", type=float, default=default.server_capex_rub,
                        help="Стоимость сервера, ₽ (амортизируется за --amortization-months)")
    parser.add_argument("--amortization-months", type=int, default=default.amortization_months)
    parser.add_argument("--support-fte", type=float, default=default.support_fte,
                        help="Инженеров поддержки, FTE")
    parser.add_argument("--power-kw", type=float, default=default.power_kw,
                        help="Потребление сервера, кВт (без учёта PUE)")
    parser.add_argument("--licenses-rub", type=float, default=default.licenses_rub_per_month,
                        help="Лицензии и прочее, ₽/мес")
    parser.add_argument("--demo-badge", action="store_true",
                        help="Показать плашку «данные синтетические»")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    if not Path(args.input).exists():
        print(f"error: {args.input} not found. Run analytics_export.py first.", file=sys.stderr)
        return 2

    try:
        app = create_app(
            args.input,
            args.classes,
            args.low_confidence,
            metrics.CostModel(
                server_capex_rub=args.server_capex,
                amortization_months=args.amortization_months,
                power_kw=args.power_kw,
                support_fte=args.support_fte,
                licenses_rub_per_month=args.licenses_rub,
            ),
            args.demo_badge,
        )
    except data_loader.ContractViolation as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
