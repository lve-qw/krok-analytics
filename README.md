# КРОК «Промпт-радар»

Аналитика логов обращений к корпоративным ИИ-агентам: файловый адаптер,
валидатор канонического контракта и локальный Dash-дашборд.

## Быстрый запуск дашборда

Для адаптера и дашборда GPU и тяжёлые зависимости pipeline не нужны.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dashboard.txt
./run_dashboard.sh
```

Последняя команда берёт готовый демонстрационный набор проекта, собирает из него
канонический `outputs/analytics.canonical.csv`, проверяет данные и поднимает
готовый сайт со всеми дашбордами. После запуска откройте
<http://127.0.0.1:8050>.

Ничего дополнительно копировать в проект для этого запуска не нужно.

## Запуск на другой выгрузке

Только если нужно заменить готовые данные своими, создайте отдельную папку и
положите в неё два файла:

```text
data/imports/current/
├── dialogs.csv
└── use_cases.csv
```

Запустите:

```bash
./run_dashboard.sh data/imports/current
```

Подробности о формате находятся в
[`data/imports/README.md`](data/imports/README.md). Другой порт:

```bash
PORT=8060 ./run_dashboard.sh
```

Скрипт последовательно запускает адаптер, валидатор и локальный сервер. Если
канонический файл не проходит проверку, сервер не стартует. Результаты пишутся в
`outputs/`, которая исключена из Git.

## Архитектура

Pipeline из 3 этапов:
1. **LLM анализ** (qwen-2.5-7b-instruct) — извлечение аналитических признаков
2. **Zero-shot классификация** (facebook/bart-large-mnli) — категоризация по классам из classes.csv
3. **Кластеризация эмбеддингов** (paraphrase-multilingual-MiniLM-L12-v2 + HDBSCAN) — поиск use cases

## Полный processing pipeline

Этот раздел нужен только для обработки исходных JSON с помощью моделей. Запуск
требует GPU, загрузки Qwen2.5-7B и полного набора зависимостей.

### Установка

```bash
pip install -r requirements.txt
```

### Запуск

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

### Выходные файлы

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
.venv/bin/python analytics_export.py
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
.venv/bin/python -m analytics_contract.validate \
  --analytics outputs/analytics.canonical.csv \
  --classes data/classes_31.csv
```

Результат — `outputs/validation/validation_report.json` и
`validation_errors.csv`. Коды выхода: `0` — контракт соблюдён, `1` — есть
ошибки, `2` — файл не найден. Флаг `--no-registry-check` отключает проверку по
реестрам, `--fail-on-warning` делает предупреждения блокирующими.

### 3. Dashboard

```bash
.venv/bin/python -m analytics_contract.dashboard.app \
  --input outputs/analytics.canonical.csv
```

Открывается на `http://127.0.0.1:8050`. Дашборд не стартует, если входной файл
не проходит валидацию.

Четыре вкладки под общей панелью управления: **Обзор** (7 KPI и топ сценариев),
**Сценарии и автоматизация**, **Надёжность, стоимость и риски**, **Записи**.
Фильтры, чипы активных фильтров и счётчик записей находятся над вкладками и
действуют на все вкладки сразу. Временного графика нет: в контракте нет
пригодного поля времени.

Как это устроено:

- **Тема** задаётся классом на `#viz-root` и хранится в `theme-store`. Правила
  `prefers-color-scheme` нет намеренно: медиазапрос не видит store, и при
  расхождении страница уходила в тёмную тему, пока Plotly продолжал рисовать на
  белом листе. Таблица и выпадающие списки окрашены через `var(--…)`, поэтому
  следуют за темой без отдельного callback.
- **Подписи** живут в `analytics_contract/dashboard/labels.py` и меняют только
  текст на экране. В данных, в фильтрах и в экспорте значения остаются
  каноническими: `unclustered` показывается как «Сценарий не определён», но в
  CSV уходит как `unclustered`.
- **Клик по столбцу или точке** выбирает сценарий: подсвечивает его на
  диаграммах, фильтрует вкладку «Записи» и показывает чип с крестиком. Повторный
  клик по той же метке снимает выбор. Выбор не меняет KPI и диаграммы — часть
  остаётся видна в контексте целого.
- **KPI** несут формулу и оговорки в подсказке, поэтому число на проекторе может
  ответить, откуда оно взялось, без слов докладчика.
- **Полоса происхождения** под шапкой показывает цепочку «на входе → в отчёте →
  отброшено» из `export_report.json`, если он лежит рядом с входным файлом.

Проверено вживую в Firefox на ширинах 1440, 1280 и 1024 px в обеих темах.

### Тестовые данные

Запуск настоящего pipeline требует GPU и загрузки 7B-модели. Для проверки
цепочки без GPU:

```bash
./run_dashboard.sh
```

Генератор создаёт `outputs/dialogs.csv` и `use_cases.csv` в формате pipeline.
Все показатели на этих данных помечены `DEMO / SYNTHETIC DATA`.

### Метрики

`docs/metrics_catalog.md` — формулы, источники полей, ограничения
интерпретации и список метрик, невозможных при текущей схеме.

### Тесты

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Структура проекта

```text
krok-analytics/
├── analytics_contract/      # Контракт, валидатор и дашборд
├── data/
│   ├── dialogs/             # Демо-JSON для полного pipeline
│   ├── imports/             # Локальные CSV-выгрузки
│   └── classes_31.csv       # Официальная таксономия
├── docs/                    # Каталог метрик и пояснения
├── scripts/                 # Генератор синтетического выхода
├── tests/
├── analytics_export.py      # Файловый адаптер
├── run_dashboard.sh         # Адаптер → валидатор → сервер
├── requirements-dashboard.txt
├── main.py                  # GPU processing pipeline
└── requirements.txt         # Полные зависимости pipeline
```

## Требования

- дашборд: Python 3.10+, GPU не нужен;
- полный pipeline: GPU с 16 GB+ памяти (рекомендуется A100).
