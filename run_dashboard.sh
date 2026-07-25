#!/usr/bin/env bash
# Разобрать выгрузку pipeline из CSV и поднять локальный дашборд.

set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-.venv/bin/python}"
PORT="${PORT:-8050}"
INPUT="${1:-outputs}"

usage() {
    echo "Использование:"
    echo "  ./run_dashboard.sh                      # outputs/ — последняя выгрузка pipeline"
    echo "  ./run_dashboard.sh outputs/analytics.csv"
    echo "  ./run_dashboard.sh path/to/выгрузка     # каталог с analytics.csv"
    echo "                                          # либо с dialogs.csv + use_cases.csv"
    echo
    echo "Другой порт:      PORT=8060 ./run_dashboard.sh"
    echo "Метрики в текст:  $PYTHON -m dashboard.check --input outputs"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ ! -x "$PYTHON" ]]; then
    echo "Не найден интерпретатор $PYTHON."
    echo "Создайте окружение:"
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements-dashboard.txt"
    exit 2
fi

if [[ ! -e "$INPUT" ]]; then
    echo "Не найден файл или каталог: $INPUT"
    echo "Сначала запустите pipeline (python main.py) — он пишет CSV в outputs/."
    exit 2
fi

echo "Дашборд: http://127.0.0.1:$PORT   (источник: $INPUT)"
exec "$PYTHON" -m dashboard.app --input "$INPUT" --host 127.0.0.1 --port "$PORT"
