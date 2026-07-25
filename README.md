# KROK Analytics Pipeline

Система анализа логов корпоративного AI-агента для кейса КРОК.

## Логика работы

Pipeline обрабатывает сырые JSON-логи диалогов пользователей с AI-агентом и превращает их в структурированную аналитику use cases.

### Входные данные

В папке `data/dialogs/` лежат файлы вида `session_*.json`:
```json
{
  "user_id": "usr_abc123",
  "session_id": "sess_20260725_000032",
  "created_at": "2026-07-25T11:24:38Z",
  "scenario_type": "email_summary",
  "messages": [
    {"role": "user", "content": "Посмотри почту за сегодня"},
    {"role": "assistant", "content": "Хорошо, проверяю..."},
    {"role": "tool", "tool_name": "gmail.search", "arguments": {...}, "result": {...}}
  ]
}
```

### Этап 1: LLM-анализ

**Файл:** `llm.py`  
**Модель:** `Qwen/Qwen2.5-7B-Instruct` (локально на GPU)

Для каждого диалога LLM извлекает 20+ признаков:
- `summary` — краткое содержание
- `goal` — цель пользователя  
- `intent` — намерение
- `is_work` — рабочий запрос или нет
- `automation_candidate` — можно ли автоматизировать
- `periodicity` — периодичность (none/daily/weekly/monthly)
- `complexity` — сложность (simple/medium/complex)
- `integrations` — какие системы затрагиваются (CRM, Jira, Mail...)
- `tools` — какие инструменты использовал агент
- `agent_failed` — была ли ошибка у агента

**Выход:** enriched диалоги с метаданными.

---

### Этап 2: Zero-shot классификация

**Файл:** `zero_shot_classifier.py`  
**Модель:** `blanchefort/rubert-base-mnli` (русская MNLI)

Классифицирует каждый диалог по заранее заданным классам из `data/classes.csv`:

| id | class_name |
|----|------------|
| 1 | Генерация текста и документов |
| 2 | Поиск и сбор информации |
| 3 | Анализ данных и отчетность |
| 4 | Работа с задачами и проектами |
| 5 | Планирование и календарь |
| 6 | Управление коммуникациями |
| 7 | Помощь с кодом и техническими вопросами |
| 8 | Обучение и объяснение |
| 9 | Автоматизация рабочих процессов |
| 10 | Общие вопросы и нерабочие запросы |

Модель возвращает top-N классов с confidence > 0.5. Если ни один класс не прошёл порог — назначается класс по умолчанию (`other`).

**Выход:** для каждого диалога — список классов с вероятностями.

---

### Этап 3: Кластеризация (Use Cases)

**Файл:** `clustering.py`  
**Модель:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`  
**Алгоритм:** HDBSCAN

1. Первые сообщения пользователей кодируются в эмбеддинги (384-dim)
2. UMAP уменьшает размерность до 5
3. HDBSCAN находит кластеры (min_cluster_size=6)
4. Для каждого кластера LLM генерирует название use case на основе топ-30 запросов

**Выход:** mapping `request_id → cluster_id → use_case_name`

Пример кластеров:
- Cluster 0: "Поиск и фиксация информации" (86 диалогов)
- Cluster 1: "Задачи и проекты" (24 диалога)
- Cluster -1: выбросы (не распознанные сценарии)

---

## Выходные файлы

| Файл | Описание |
|------|----------|
| `outputs/dialogs.csv` | 100 строк с LLM-признаками, классами и токенами |
| `outputs/use_cases.csv` | mapping request_id → cluster → use_case |
| `outputs/analytics.csv` | итоговый merged dataset для анализа |

---

## Установка и запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск pipeline
python main.py
```

Pipeline автоматически:
1. Читает все `session_*.json` из `data/dialogs/`
2. Запускает 3 этапа
3. Сохраняет результаты в `outputs/`

---

## Дашборд

Дашборд генерируется автоматически в конце pipeline и сохраняет интерактивный HTML-отчёт с графиками.

### Автоматическая генерация

```bash
python main.py  # В конце pipeline создаётся outputs/report.html
```

### Ручная генерация

```bash
python dashboard_generator.py  # outputs/analytics.csv → outputs/report.html
python dashboard_generator.py outputs/analytics.csv /path/to/report.html
```

### Что в дашборде

Все метрики из [`metrics.md`](metrics.md) с интерактивными графиками (plotly.js):

| Раздел | Метрики и графики |
|--------|------------------|
| Общая статистика | Диалоги, пользователи, период |
| Токены и стоимость | Гистограмма токенов, burned tokens, стоимость |
| Качество агента | Useful vs Useless messages, useful ratio |
| Классификация | Сложность (pie), периодичность (pie), automation candidates |
| Интеграции и инструменты | Топ-10 интеграций (bar), топ-10 инструментов (bar) |
| Use Cases | Топ-5 кластеров (bar), outliers |
| Проблемы | Причины провалов (bar), prompt injections, sensitive data |
| Языки | Распределение (pie) |
| Уверенность | Гистограмма confidence |
| Активность | Топ пользователей (bar), диалоги по датам (line) |

Графики интерактивные: наведение, зум, сохранение в PNG.

### Требования

- `pandas` (уже в `requirements.txt`)
- Plotly.js загружается через CDN (без зависимостей)

---

## Структура проекта

```
krok_analytics/
├── main.py                  # Точка входа, оркестрация pipeline
├── config.py                # Конфигурация моделей и путей
├── schemas.py               # Pydantic модели (Dialog, Message, etc.)
├── prompts.py               # Промпты для LLM-анализа
├── llm.py                   # LLM инференс + парсинг JSON-ответов
├── parser.py                # Парсинг JSON из сырых файлов
├── token_counter.py         # Подсчёт токенов (user/assistant/tool)
├── zero_shot_classifier.py  # Классификация по классам
├── embeddings.py            # Генерация эмбеддингов
├── clustering.py            # HDBSCAN + именование кластеров
├── utils.py                # Вспомогательные функции
├── dashboard/              # Дашборд по выгрузке (Dash + Plotly)
│   ├── data.py             # Разбор CSV в типизированный DataFrame
│   ├── metrics.py          # Все метрики из metrics.md
│   ├── charts.py           # Графики
│   ├── layout.py           # Композиция страницы
│   ├── filters.py          # Фильтры и выборка
│   ├── theme.py            # Светлая и тёмная палитры
│   ├── styles.py           # CSS
│   ├── app.py              # Dash-приложение и колбэки
│   └── check.py            # Те же метрики текстом
├── run_dashboard.sh        # Запуск дашборда
├── tests/                  # Тесты разбора CSV и метрик
├── data/
│   ├── dialogs/            # Входные session_*.json
│   └── classes.csv         # Справочник классов
├── outputs/                # Результаты (dialogs.csv, use_cases.csv, analytics.csv)
└── models/                 # Кэш моделей (локально)
```

---

## Требования

- Python 3.10+
- GPU с 16GB+ памяти (A100 рекомендуется)
- Модели загружаются автоматически с HuggingFace

---

## Экономика

Стоимость инференса считается по формуле:
```
cost = (total_tokens / 1000) * $0.0001
```

Это условная оценка для локального GPU (электричество + амортизация).
