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

- `dialogs.csv` — аналитические признаки каждого диалога
- `use_cases.csv` — сценарии использования по кластерам
- `analytics.csv` — итоговый merged dataset

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
