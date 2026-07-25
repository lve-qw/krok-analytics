#!/usr/bin/env bash
# Build the canonical export, validate it and start the local dashboard.

set -euo pipefail

cd "$(dirname "$0")"

PYTHON=".venv/bin/python"
PORT="${PORT:-8050}"
CLASSES="data/classes_31.csv"
OUTPUT="outputs/analytics.canonical.csv"

usage() {
    echo "Использование:"
    echo "  ./run_dashboard.sh data/imports/<набор>"
    echo "  ./run_dashboard.sh --demo"
    echo
    echo "Другой порт: PORT=8060 ./run_dashboard.sh --demo"
}

if [[ ! -x "$PYTHON" ]]; then
    echo "Не найдено окружение .venv."
    echo "Создайте его командами из README.md."
    exit 2
fi

if [[ "${1:-}" == "--demo" ]]; then
    "$PYTHON" scripts/make_sample_pipeline_output.py
    SOURCE_DIR="outputs"
elif [[ -n "${1:-}" ]]; then
    SOURCE_DIR="${1%/}"
else
    usage
    exit 2
fi

DIALOGS="$SOURCE_DIR/dialogs.csv"
USE_CASES="$SOURCE_DIR/use_cases.csv"

if [[ ! -f "$DIALOGS" || ! -f "$USE_CASES" ]]; then
    echo "В папке $SOURCE_DIR нужны dialogs.csv и use_cases.csv."
    exit 2
fi

echo "1/3 Адаптация входных файлов"
"$PYTHON" analytics_export.py \
    --dialogs "$DIALOGS" \
    --use-cases "$USE_CASES" \
    --classes "$CLASSES" \
    --output "$OUTPUT" \
    --errors outputs/pipeline_errors.csv \
    --report outputs/export_report.json

echo "2/3 Проверка канонического контракта"
"$PYTHON" -m analytics_contract.validate \
    --analytics "$OUTPUT" \
    --classes "$CLASSES" \
    --quiet

echo "3/3 Дашборд: http://127.0.0.1:$PORT"
exec "$PYTHON" -m analytics_contract.dashboard.app \
    --input "$OUTPUT" \
    --classes "$CLASSES" \
    --host 127.0.0.1 \
    --port "$PORT"
