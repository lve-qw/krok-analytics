#!/usr/bin/env bash
# Разобрать выгрузку pipeline из CSV и поднять локальный дашборд.
#
# Что должно лежать на диске, чтобы это заработало:
#
#   .venv/                     окружение: pip install -r requirements-dashboard.txt
#   outputs/analytics.csv      выгрузка pipeline (dialogs + use_cases уже склеены)
#     ЛИБО
#   outputs/dialogs.csv        одна строка на запрос
#   outputs/use_cases.csv      request_id → cluster_id → use_case (склеит сам дашборд)
#
# Каталог можно передать первым аргументом, файл — тоже.

set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-.venv/bin/python}"
PORT="${PORT:-8050}"
INPUT="${1:-outputs}"

usage() {
    cat <<'TEXT'
Использование:
  ./run_dashboard.sh                      # outputs/ — последняя выгрузка pipeline
  ./run_dashboard.sh outputs/analytics.csv
  ./run_dashboard.sh path/to/выгрузка     # каталог с analytics.csv
                                          # либо с dialogs.csv + use_cases.csv

Другой порт:      PORT=8060 ./run_dashboard.sh
Метрики в текст:  .venv/bin/python -m dashboard.check --input outputs
Демо-заполнение:  .venv/bin/python scripts/fill_synthetic.py
TEXT
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

if [[ -d "$INPUT" ]]; then
    if [[ ! -f "$INPUT/analytics.csv" ]] &&
       { [[ ! -f "$INPUT/dialogs.csv" ]] || [[ ! -f "$INPUT/use_cases.csv" ]]; }; then
        echo "В каталоге $INPUT нет данных для дашборда."
        echo "Нужен один из вариантов:"
        echo "  $INPUT/analytics.csv"
        echo "  $INPUT/dialogs.csv + $INPUT/use_cases.csv"
        echo
        echo "Выгрузку делает pipeline:  python main.py"
        exit 2
    fi
elif [[ ! -f "$INPUT" ]]; then
    echo "Не найден файл или каталог: $INPUT"
    usage
    exit 2
fi

echo "Дашборд: http://127.0.0.1:$PORT   (источник: $INPUT)"
exec "$PYTHON" -m dashboard.app --input "$INPUT" --host 127.0.0.1 --port "$PORT"
