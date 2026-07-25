# KROK Analytics Pipeline

Система анализа логов корпоративного AI-агента для кейса КРОК.

## Архитектура

Pipeline из 3 этапов:
1. **LLM анализ** (qwen-2.5-7b-instruct) — извлечение аналитических признаков
2. **Zero-shot классификация** (facebook/bart-large-mnli) — категоризация по классам из classes.csv
3. **Кластеризация эмбеддингов** (paraphrase-multilingual-MiniLM-L12-v2 + HDBSCAN) — поиск use cases

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```python
from main import run_pipeline
from pathlib import Path

run_pipeline(
    dialogs_dir=Path("path/to/dataset"),
    outputs_dir=Path("path/to/outputs")
)
```

Или из командной строки:
```bash
python main.py
```

## Выходные файлы

Legacy-выход pipeline (не изменялся):

- `dialogs.csv` — аналитические признаки каждого диалога
- `use_cases.csv` — сценарии использования по кластерам
- `analytics.csv` — итоговый merged dataset

Канонический контракт:

- `analytics.canonical.csv` — 30 полей контракта, JSON-массивы вместо `;`
- `pipeline_errors.csv` — записи, исключённые из-за сбоя аналитического pipeline
- `export_report.json` — количество входных, обработанных и ошибочных записей

## Канонический analytics.csv

Контракт из 30 полей описан в `analytics_contract/schema.py`. Таксономия —
31 официальный класс из `data/classes_31.csv`. Файл `data/classes.csv`
(10 широких категорий) и поле `scenario_id` во входных диалогах считаются
legacy/demo-метаданными и каноническим `class_id` не являются.

### 1. Экспорт в канонический формат

```bash
python analytics_export.py
```

Читает `outputs/dialogs.csv` и `outputs/use_cases.csv`. Pipeline не запускает и
legacy-выход не трогает. Нормализует `tools` и `integrations` по реестрам
`FIXED_TOOLS` / `FIXED_INTEGRATIONS` из `config.py`; неизвестные значения не
проходят молча, а попадают в `export_report.json`.

Строки со сбоем аналитического pipeline (`analysis_status == "parse_error"`)
исключаются в `pipeline_errors.csv` и **не** помечаются `agent_failed`: сбой
парсинга — это отказ нашего инструмента, а не отказ агента.

### 2. Валидация

```bash
python -m analytics_contract.validate \
  --analytics outputs/analytics.canonical.csv \
  --classes data/classes_31.csv
```

Результат — `outputs/validation/validation_report.json` и
`validation_errors.csv`. Коды выхода: `0` — контракт соблюдён, `1` — есть
ошибки, `2` — файл не найден. Флаг `--no-registry-check` отключает проверку по
реестрам, `--fail-on-warning` делает предупреждения блокирующими.

### 3. Dashboard

```bash
python -m analytics_contract.dashboard.app \
  --input outputs/analytics.canonical.csv
```

Открывается на `http://127.0.0.1:8050`. Дашборд не стартует, если входной файл
не проходит валидацию.

7 KPI-карточек, 7 диаграмм, 12 фильтров, drill-down таблица и экспорт
отфильтрованных данных в CSV. Временного графика нет: в контракте нет
пригодного поля времени.

### Тестовые данные

Запуск настоящего pipeline требует GPU и загрузки 7B-модели. Для проверки
цепочки без GPU:

```bash
python3 scripts/make_sample_pipeline_output.py
python analytics_export.py
python -m analytics_contract.validate
```

Генератор создаёт `outputs/dialogs.csv` и `use_cases.csv` в формате pipeline.
Все показатели на этих данных помечены `DEMO / SYNTHETIC DATA`.

### Метрики

`docs/metrics_catalog.md` — формулы, источники полей, ограничения
интерпретации и список метрик, невозможных при текущей схеме.

### Тесты

```bash
python -m unittest discover -s tests -v
```

## Структура проекта

```
krok_analytics/
├── main.py                  # Точка входа
├── config.py                # Конфигурация
├── schemas.py               # Pydantic модели
├── prompts.py               # Промпты для LLM
├── llm.py                   # LLM инференс
├── parser.py                # Парсинг JSON
├── token_counter.py         # Подсчет токенов
├── zero_shot_classifier.py  # BART-MNLI
├── embeddings.py            # Sentence-transformers
├── clustering.py            # HDBSCAN
├── utils.py                 # Утилиты
├── data/
│   ├── dialogs/             # Входные JSON
│   └── classes.csv          # Классы
├── outputs/                 # Результаты
└── models/                  # Кэш моделей
```

## Требования

- Python 3.10+
- GPU с 16GB+ памяти (рекомендуется для A100)
