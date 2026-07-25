#!/usr/bin/env bash
# Собрать канонический analytics.csv из выхода pipeline и поднять дашборд.
#
#   ./run.sh                                  # данные по умолчанию
#   ./run.sh temp-data-transfer-main          # своя папка с dialogs.csv + use_cases.csv
#   PORT=8060 ./run.sh                        # другой порт
#
# Дашборд не стартует, если файл нарушает контракт: лучше пустой экран, чем
# числа, за которыми не стоит проверка.

set -euo pipefail
cd "$(dirname "$0")"

SRC="${1:-temp-data-transfer-main}"
PORT="${PORT:-8050}"
PY=.venv/bin/python
CLASSES=data/classes_registry.csv
OUT=outputs/analytics.current.csv

[ -x "$PY" ] || { echo "нет .venv — python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 2; }
[ -f "$SRC/dialogs.csv" ] || { echo "нет $SRC/dialogs.csv"; exit 2; }

echo "==> 1/3 адаптер: $SRC -> $OUT"
$PY analytics_export.py \
  --dialogs "$SRC/dialogs.csv" \
  --use-cases "$SRC/use_cases.csv" \
  --classes "$CLASSES" \
  --output "$OUT" \
  --errors outputs/pipeline_errors.csv \
  --report outputs/export_report.json

echo "==> 2/3 валидатор"
$PY -m analytics_contract.validate --analytics "$OUT" --classes "$CLASSES" | tail -5

echo "==> 3/3 дашборд: http://127.0.0.1:$PORT"
lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
exec $PY -m analytics_contract.dashboard.app \
  --input "$OUT" --classes "$CLASSES" --port "$PORT"
