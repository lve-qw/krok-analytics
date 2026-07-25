# INTEGRATION_PLAN

План интеграции канонического контракта `analytics.csv`, валидатора, каталога
метрик и будущего Dash-дашборда в основной репозиторий `krok-analytics`.

Документ описывает **только план**. Существующий pipeline на этом шаге не
изменяется.

- Ветка: `feat/analytics-contract-integration`
- База: `main` @ `2163679`
- Дата аудита: 2026-07-25

---

## 1. Что основной pipeline делает сейчас

`main.run_pipeline()` выполняет шесть шагов и пишет три файла в `outputs/`:

| Шаг | Модуль | Результат |
|---|---|---|
| 1 | `parser.DialogParser` | 115 диалогов из `data/dialogs/*.json` |
| 2 | `utils.load_classes` | 10 классов из `data/classes.csv` |
| 3–4 | `llm.LLMAnalyzer` (Qwen2.5-7B) + `zero_shot_classifier` + `token_counter` | `DialogAnalysis` на диалог → `outputs/dialogs.csv` |
| 5 | `embeddings` + `clustering` (HDBSCAN + LLM-именование) | `outputs/use_cases.csv` |
| 6 | `utils.save_analytics_csv` | `outputs/analytics.csv` = `dialogs.csv` LEFT JOIN `use_cases.csv` по `request_id` |

Итоговый `analytics.csv` содержит **38 колонок**: 35 из `dialogs.csv` плюс
`cluster_id`, `use_case`, `member_count`.

Файл `outputs/analytics.csv` в репозиторий не закоммичен, поэтому аудит
проведён по коду, который его порождает (`utils.save_dialogs_csv`,
`utils.save_analytics_csv`, `schemas.py`, `llm.py`), и по входным данным.

---

## 2. Точное сопоставление полей

Статусы:

| Статус | Смысл |
|---|---|
| `DIRECT` | переносится как есть |
| `TRANSFORM` | нужна конвертация значения или сериализации |
| `BLOCKED` | требует решения команды, автоматически переносить нельзя |
| `EXTRA` | есть в pipeline, в контракте отсутствует |

### 2.1. Поля, сопоставимые напрямую

| current field | canonical field | transformation | status |
|---|---|---|---|
| `request_id` (int) | `request_id` | `str()`; в CSV уже пишется как непустая строка | `DIRECT` |
| `summary` | `summary` | — | `DIRECT` ⚠ пустая строка при parse error, см. §5.1 |
| `goal` | `goal` | — | `DIRECT` ⚠ то же |
| `intent` | `intent` | — | `DIRECT` ⚠ то же |
| `is_work` (bool) | `is_work` | pandas пишет `True`/`False`; валидатор принимает без учёта регистра | `DIRECT` |
| `automation_candidate` | `automation_candidate` | то же | `DIRECT` |
| `uses_company_data` | `uses_company_data` | то же | `DIRECT` |
| `contains_sensitive_data` | `contains_sensitive_data` | то же | `DIRECT` |
| `prompt_injection` | `prompt_injection` | то же | `DIRECT` |
| `agent_failed` | `agent_failed` | то же | `DIRECT` ⚠ семантика загрязнена, см. §5.2 |
| `periodicity` | `periodicity` | словарь совпадает точно (`none/daily/weekly/monthly`), нормализация уже есть в `llm.py:120` | `DIRECT` |
| `complexity` | `complexity` | словарь совпадает точно (`simple/medium/complex`), `llm.py:125` | `DIRECT` |
| `steps_requested` | `steps_requested` | int, приведение в `llm.py:144` | `DIRECT` |
| `integration_count` | `integration_count` | `len(integrations)` в `llm.py:156` — инвариант контракта соблюдён по построению | `DIRECT` |
| `tool_calls` | `tool_calls` | int | `DIRECT` ⚠ см. §5.4 |
| `user_tokens` | `user_tokens` | int из `tiktoken` | `DIRECT` |
| `assistant_tokens` | `assistant_tokens` | int | `DIRECT` |
| `tool_tokens` | `tool_tokens` | int | `DIRECT` ⚠ всегда 0, см. §5.5 |
| `estimated_cost` | `estimated_cost` | float ≥ 0 | `DIRECT` ⚠ фиктивный тариф, см. §5.6 |
| `language` | `language` | — | `DIRECT` |
| `failure_reason` | `failure_reason` | `None → ""` уже делается в `utils.py:34` | `DIRECT` |
| `confidence` | `confidence` | float ∈ [0,1] | `DIRECT` ⚠ инверсия при fallback, см. §5.3 |
| `use_case` | `use_case` | — | `DIRECT` ⚠ NaN при промахе join, см. §5.7 |

### 2.2. Поля, требующие преобразования

| current field | canonical field | transformation | status |
|---|---|---|---|
| `integrations` | `integrations` | `";".join(...)` → JSON-массив строк | `TRANSFORM` |
| `tools` | `tools` | то же | `TRANSFORM` |
| `company_sources` | `company_sources` | то же | `TRANSFORM` |
| `requires_generation` | `requires_generation` | то же **плюс** фильтрация по словарю `{text, excel, sql, presentation}` — в `llm.py:136` фильтра нет, в отличие от `search_type` | `TRANSFORM` |
| `search_type` | `search_type` | `";".join(...)` → JSON-массив; словарь уже отфильтрован в `llm.py:140` | `TRANSFORM` |

Разделитель `;` прямо запрещён контрактом: списковые поля обязаны быть
корректными JSON-массивами. Это единственная чисто механическая правка
сериализации, и она затрагивает пять полей.

### 2.3. Поля, заблокированные таксономией

| current field | canonical field | transformation | status |
|---|---|---|---|
| `class_ids` (`List[int]`, из 10 широких классов) | `class_ids` (`List[str]` из 31 фиксированного класса) | требуется полная замена таксономии, не переименование | `BLOCKED` |
| `class_names` (названия 10 широких классов) | `class_names` | то же | `BLOCKED` |

Подробно — §4.

### 2.4. Поля pipeline вне контракта

Ни одно не удаляется из `dialogs.csv`; они просто не попадают в канонический
`analytics.csv`.

| current field | что это | статус |
|---|---|---|
| `dialog_id` | дубликат `request_id` (`main.py:75–76`) | `EXTRA` |
| `first_user_message` | **исходный текст запроса** | `EXTRA` — см. §6, самый ценный кандидат на расширение контракта |
| `classification_scores` | скоры по каждому присвоенному классу | `EXTRA` |
| `total_tokens` | сумма трёх полей токенов | `EXTRA` — выводится из контракта, дублировать не нужно |
| `analysis_status` | `success` / `parse_error` | `EXTRA` — но нужен адаптеру, см. §5.1 |
| `metadata_confidence` | 1.0 / 0.0 по `analysis_status` | `EXTRA` — нужен адаптеру |
| `cluster_id` | id кластера HDBSCAN, `-1` = шум | `EXTRA` |
| `member_count` | размер кластера | `EXTRA` |

### 2.5. Полей контракта, которых pipeline не создаёт

**Таких нет.** Все 30 канонических полей имеют источник в текущем pipeline.
Блокирует интеграцию не отсутствие полей, а таксономия (§4) и качество
значений (§5).

---

## 3. Где разместить adapter/exporter

### Рекомендация: отдельный standalone-экспортер, ноль изменений в pipeline

```text
krok-analytics/
├── analytics_contract/          # НОВОЕ: переносится из nuclear-hack
│   ├── __init__.py
│   ├── schema.py                # канонический контракт из 30 полей
│   ├── validation.py            # переиспользуемый валидатор
│   ├── validate.py              # CLI: python -m analytics_contract.validate
│   └── dashboard/               # Phase 3, позже
├── analytics_export.py          # НОВОЕ: адаптер pipeline → контракт
├── data/
│   ├── classes.csv              # НЕ ТРОГАЕМ: 10 широких классов, их читает zero-shot
│   └── classes_31.csv           # НОВОЕ: 31 фиксированный класс
├── docs/metrics_catalog.md      # НОВОЕ
├── scripts/make_sample_analytics.py  # НОВОЕ
└── tests/test_validation.py     # НОВОЕ
```

`analytics_export.py` читает `outputs/dialogs.csv` и `outputs/use_cases.csv`,
которые pipeline уже пишет, и создаёт `outputs/analytics.canonical.csv`:

```bash
python main.py                              # без изменений
python analytics_export.py                  # новый шаг
python -m analytics_contract.validate \
  --analytics outputs/analytics.canonical.csv \
  --classes data/classes_31.csv
```

Обоснование выбора:

1. **`main.py` и `utils.py` не меняются.** Экспортер работает по файлам, а не
   по внутренним объектам, поэтому не связан с сигнатурами pipeline.
2. **Легаси-выход сохраняется.** `outputs/analytics.csv` продолжает
   создаваться как раньше; канонический файл живёт рядом под другим именем.
   Переключение имён — отдельное решение, когда контракт стабилизируется.
3. **Пакет вместо плоских модулей.** Корень основного репозитория плоский и уже
   занял имена `config.py`, `schemas.py`, `utils.py`. Пакет `analytics_contract/`
   исключает будущие коллизии и даёт CLI вида `python -m`.
4. **`data/classes.csv` не перезаписывается.** Его читает
   `zero_shot_classifier` через `utils.load_classes`, ожидая колонки `id` и
   `название_класса`. 31 класс кладётся рядом отдельным файлом.

Альтернатива, которую я отклонил: встроить экспорт прямо в
`utils.save_analytics_csv`. Это переписало бы работающий выход pipeline на
первом же шаге, что задача прямо запрещает.

---

## 4. Конфликты с 31 фиксированным классом

Это главный блокер. В проекте сосуществуют **три разные таксономии**.

| Таксономия | Где | Мощность | Формат id |
|---|---|---|---|
| A. 10 широких категорий | `data/classes.csv`, используется `ZeroShotClassifier` | 10 | int `1..10` |
| B. 23 сценария | `scenario_id` внутри каждого `data/dialogs/*.json` | 23 | строка |
| C. 31 фиксированный класс | требование задачи, `classes.csv` из nuclear-hack | 31 | строка |

### 4.1. Конфликт A против C

- `data/classes.csv` содержит `Генерация текста и документов`,
  `Поиск и сбор информации` и ещё 8 широких категорий — это другой уровень
  абстракции, а не другие имена тех же классов.
- `utils.load_classes` (`utils.py:87`) читает колонки `id` и
  `название_класса`; канонический `classes.csv` имеет `class_id` и
  `description`. Форматы несовместимы.
- `ZeroShotClassifier` строится на `class_names` из таксономии A
  (`zero_shot_classifier.py:13`).
- Fallback при непрохождении порога выдаёт `class_ids=[0]`,
  `class_names=["other"]` (`zero_shot_classifier.py:53–55`). Id `0` отсутствует
  даже в собственном файле репозитория, где id идут с 1. Контракт такое
  значение отвергнет: `other` не входит в 31 класс.

### 4.2. Конфликт B против C — и почему он важнее

Диалоги уже содержат **эталонную метку сценария**: поле `scenario_id`, плюс
короткое `scenario_title` и длинное `scenario_description`. Проверено на всех
115 файлах:

- 23 уникальных `scenario_id`, ровно по 5 диалогов на каждый;
- `scenario_title` стабилен внутри `scenario_id` (разночтений нет);
- с 31 классом совпадают **точно только два**: `email_summary` и
  `tomorrow_meetings`;
- остальные 21 — близкие, но иначе названные варианты тех же сценариев;
- 7 из 31 класса не представлены в данных ни одним диалогом.

То есть `scenario_id` — это почти таксономия C, но не она. Автоматически
склеивать их нельзя: `jira_tasks` соответствует **двум** классам сразу.

Предлагаемое сопоставление (**требует утверждения человеком, не применять
молча**):

| `scenario_id` (B) | `class_id` (C) | примечание |
|---|---|---|
| `email_summary` | `email_summary` | точное совпадение |
| `tomorrow_meetings` | `tomorrow_meetings` | точное совпадение |
| `client_research` | `company_client_research` | |
| `email_monitoring` | `email_monitoring_unanswered` | |
| `sales_notification` | `weekly_tender_notification` | |
| `project_team_info` | `project_team_vendor` | |
| `company_open_source` | `company_open_source_summary` | |
| `crm_excel_report` | `crm_to_excel` | |
| `feedback_review` | `coolfeedback_review` | |
| `ticket_management` | `isu_ticket_create_edit` | |
| `jira_tasks` | `jira_my_tasks` **и** `jira_priority_tasks` | **неоднозначно 1→2** |
| `supplier_news` | `supplier_blog_search` | |
| `confluence_search` | `confluence_process_search` | |
| `calendar_management` | `calendar_free_time_assistant` | спорно: возможен `large_meeting_scheduling` |
| `meeting_room` | `meeting_room_search` | |
| `client_response` | `client_email_reply` | |
| `meeting_notes` | `meeting_notes_quick` | |
| `client_contacts` | `client_contacts_by_company` | |
| `group_meeting` | `large_meeting_scheduling` | |
| `meeting_attachments` | `meeting_body_attachment_info` | |
| `task_reminders` | `reminders_planned_tasks` | |
| `email_to_tickets` | `project_tickets_from_emails` | |
| `project_status_monitoring` | `isup_status_monitoring` | |

Классы из 31 без единого диалога: `pre_monitoring_note`,
`weekly_tender_report_userstory`, `manager_observation_fix`,
`analysis_excel_export`, `data_excel_export`, `task_confirmation`,
`task_history_complete`.

### 4.3. Недостающая колонка имени класса

Канонический `classes.csv` содержит `class_id` и длинное описание, но не
короткое имя. Валидатор поэтому не может проверить соответствие
`class_id → class_name` и фиксирует это как явное ограничение.

`scenario_title` из диалогов закрывает эту дыру: это готовые короткие имена
(`email_summary` → `Сводка по письмам за день`), пригодные для подписей на
диаграммах. При утверждении сопоставления §4.2 в `data/classes_31.csv` можно
добавить колонку `class_name`, после чего проверка включится автоматически —
код валидатора менять не нужно, он ищет колонку `class_name`/`name`/`title`.

### 4.4. Варианты решения

| Вариант | Суть | Цена | Риск |
|---|---|---|---|
| **1. Использовать `scenario_id` как эталон** | Утвердить сопоставление §4.2, взять метку из данных, zero-shot оставить для сравнения | Низкая | Оценивает не классификатор, а качество генерации данных |
| **2. Перенастроить zero-shot на 31 класс** | Заменить реестр классификатора на 31 класс, `scenario_id` держать как gold | Средняя | 31 длинное описание как `candidate_labels` в MNLI работает хуже коротких; нужны короткие имена — их даёт `scenario_title` |
| **3. Оставить обе таксономии** | 10 широких как группировку, 31 как основную метку | Средняя | Два набора чисел в дашборде путают читателя |

Рекомендую **вариант 2 с эталоном из варианта 1**: классификатор
перенастраивается на 31 класс с короткими именами из `scenario_title`, а
`scenario_id` служит эталонной меткой для измерения качества. Впервые за проект
появляется возможность посчитать настоящую accuracy классификации — сейчас её
измерить нечем. Это выходит за рамки текущего шага и требует подтверждения.

---

## 5. Качество значений: что валидатор отвергнет

Проверено по коду, порождающему CSV. Каждый пункт — ожидаемый класс ошибок при
первом прогоне валидатора на реальном выходе pipeline.

### 5.1. Пустые `summary`, `goal`, `intent` при parse error

`llm._get_default_metadata()` (`llm.py:174`) ставит пустые строки. Контракт
требует непустой текст → `error: text_blank`.

Решение адаптера: строки с `analysis_status == "parse_error"` **исключать** из
канонического файла и записывать их количество в отчёт. Подставлять заглушки
нельзя — это выдало бы сбой парсинга за результат анализа.

### 5.2. `agent_failed` смешивает две разные вещи

`_get_default_metadata` ставит `agent_failed=True` и
`failure_reason="LLM parse error"`. Это сбой **нашего pipeline**, а не сбой
агента. Попав в метрики, он завысит `fail.rate` и отравит все разрезы сбоев.

Контракт формально не нарушается — устраняется тем же исключением
`parse_error`-строк из §5.1.

### 5.3. Инверсия `confidence` при fallback

`zero_shot_classifier.py:53–58`: если ни один класс не прошёл порог, ставится
`scores=[1.0]` и, следовательно, `confidence=1.0`. Наименее уверенные записи
получают **максимальную** уверенность.

Контракт этого не ловит: `1.0` лежит в `[0, 1]`. Ломается метрика
`clf.low_share` и всё семейство §1.4 каталога. Требует правки классификатора —
за рамками текущего шага, но до включения дашборда.

### 5.4. `tools` без вызовов

`tool_calls` берётся из ответа LLM независимо от списка `tools`
(`llm.py:158`). При непустом `tools` и `tool_calls == 0` контракт даёт
`error: tools_without_calls`. Частота неизвестна до первого прогона.

### 5.5. `tool_tokens` всегда 0

В 115 диалогах присутствуют только роли `user` и `assistant`; сообщений с
`role == "tool"` нет ни одного (42 077 сообщений проверено).
`token_counter.count_messages` поэтому всегда даёт `tool_tokens == 0`.

Контракт не нарушается, но обесцениваются `cost.token_split` и `tool.cost` из
каталога. В дашборде разложение токенов честно покажет нулевой сегмент
инструментов — это факт о данных, а не ошибка.

### 5.6. `estimated_cost` — не тариф

`token_counter.py`: `(total / 1000) * 0.0001`. Единая ставка-заглушка, не
привязанная к модели и не разделяющая input/output. Метрики стоимости
корректны как **пропорции**, но абсолютные рубли называть нельзя.

### 5.7. `use_case` может быть пустым

`save_analytics_csv` делает LEFT JOIN. При промахе `use_case` станет NaN →
`error: text_blank`. Кроме того, весь шум HDBSCAN (`cluster_id == -1`) получает
одно общее имя кластера (`clustering.py:141–151`), то есть разнородные диалоги
сливаются в псевдо-сценарий.

Адаптер должен подставлять явное `unclustered` для `cluster_id == -1` и
выделять эту группу в дашборде отдельно, никогда не показывая её как настоящий
сценарий.

### 5.8. `requires_generation` не отфильтрован

`llm.py:136` не проверяет словарь, в отличие от `search_type`. Любое значение
вне `{text, excel, sql, presentation}` даст `error: enum_unknown`. Адаптер
фильтрует и считает отброшенные значения.

### 5.9. Справочники `tools` и `integrations` существуют, но не применяются

`config.IntegrationsConfig.FIXED_INTEGRATIONS` (23 значения) и
`config.ToolsConfig.FIXED_TOOLS` (21 значение) объявлены, но **нигде не
используются**: ни `llm.py`, ни `prompts.py` на них не ссылаются, значения
приходят от LLM свободным текстом.

Это отменяет ограничение, записанное в каталоге метрик со стороны nuclear-hack
(«справочника нет»). Реестры есть, их нужно подключить: передать в промпт как
закрытый список и включить в валидаторе проверку по словарю. Тогда
`tool.frequency` и `intg.frequency` перестанут дробиться на синонимы.

---

## 6. Ограничения данных, подтверждённые аудитом

### 6.1. Временной динамики по-прежнему нет

Поля времени существуют, но непригодны:

- `Dialog.created_at`: все 115 диалогов созданы в интервале **0,64 секунды**
  25.07.2026 — это метка генерации датасета, а не время обращения;
- `Message.timestamp`: 42 077 меток укладываются в 3 календарных дня, тоже
  сгенерированы синтетически.

Вывод каталога метрик не меняется: временных графиков, трендов и роста use
cases не строим. Наличие поля `created_at` не должно вводить в заблуждение —
экспортировать его в контракт не следует, иначе оно спровоцирует ложную
динамику.

### 6.2. Разрезов по людям и командам нет

В `Dialog` нет ни `user_id`, ни команды, ни подразделения. Раздел §3 каталога
метрик остаётся в силе.

### 6.3. Исходный текст запроса есть, но вне контракта

`first_user_message` — настоящий текст первого пользовательского сообщения.
Контракт его не содержит, поэтому drill-down по-прежнему показывает `summary`
с подписью «Резюме диалога».

Это лучший кандидат на расширение контракта: он снимает ограничение «настоящие
примеры запросов невозможны» из каталога метрик. Требует решения о политике
показа чувствительного текста и потому выносится отдельно.

### 6.4. Данные синтетические

115 диалогов сгенерированы по 23 сценариям ровно по 5 штук на сценарий.
Равномерность искусственная. Ни одну частоту нельзя называть наблюдаемым
спросом — ограничение §5 каталога метрик сохраняется полностью.

---

## 7. Что переносится из nuclear-hack

| Компонент | Источник | Назначение | Изменения при переносе |
|---|---|---|---|
| Каноническая схема | `src/prompt_radar/analytics_schema.py` | `analytics_contract/schema.py` | только import-путь |
| Валидатор | `src/prompt_radar/validation.py` | `analytics_contract/validation.py` | только import-путь |
| CLI | `src/prompt_radar/validate.py` | `analytics_contract/validate.py` | пути по умолчанию под структуру основного репозитория |
| Тесты (73) | `tests/test_validation.py` | `tests/test_validation.py` | только import-путь |
| 31 класс | `inputs/dataset/classes.csv` | `data/classes_31.csv` | `class_id` и описания без изменений; колонка `class_name` — после утверждения §4.2 |
| Каталог метрик | `docs/metrics_catalog.md` | `docs/metrics_catalog.md` | правки по §5.9 и §6.1 |
| Генератор sample | `scripts/make_sample_analytics.py` | `scripts/make_sample_analytics.py` | без изменений |
| Адаптер | новый | `analytics_export.py` | пишется под §2 и §5 |
| Dash-дашборд | не реализован | `analytics_contract/dashboard/` | Phase 3 |

Новые зависимости: `dash`, `plotly` — только для дашборда. Валидатор написан на
стандартной библиотеке и `requirements.txt` не расширяет.

---

## 8. Порядок работ

| Шаг | Содержание | Трогает существующий код |
|---|---|---|
| 0 | Этот документ | нет |
| 1 | Перенести `analytics_contract/`, тесты, `data/classes_31.csv`, каталог метрик, генератор | нет |
| 2 | Написать `analytics_export.py` по §2 и §5, выход в `outputs/analytics.canonical.csv` | нет |
| 3 | Прогнать pipeline и валидатор, зафиксировать реальный профиль ошибок | нет |
| 4 | Dash-дашборд по `docs/metrics_catalog.md` | нет |
| 5 | Правки качества: §5.3 (`confidence`), §5.9 (реестры), §4 (таксономия) | **да, отдельными PR** |

Шаги 0–4 не изменяют ни одного существующего файла. Всё, что требует правки
работающего pipeline, вынесено в шаг 5 и разбито по отдельным решениям.

---

## 9. Решения, которые нужны от команды

Блокирующие для шага 2:

1. **Сопоставление таксономий §4.2.** Утвердить таблицу, в частности
   `jira_tasks` → два класса, и `calendar_management`. Без этого канонические
   `class_ids` заполнить нечем.
2. **Судьба строк `parse_error`.** Подтвердить исключение из канонического
   файла (§5.1). Альтернатива — отдельный статус в контракте, но это меняет
   схему.

Блокирующие для шага 4:

3. **Инверсия `confidence` (§5.3).** До исправления метрики уверенности в
   дашборде показывать нельзя.

Не блокирующие, но важные:

4. Подключать ли `FIXED_TOOLS` и `FIXED_INTEGRATIONS` к промпту и валидатору (§5.9).
5. Добавлять ли `request_text` в контракт и по какой политике показа (§6.3).
6. Переименовывать ли `outputs/analytics.canonical.csv` в `analytics.csv` после стабилизации.

---

## 10. Факты, допущения, непроверенное

**Факты** (проверены по коду и данным):

- 38 колонок в текущем `analytics.csv`; все 30 канонических полей имеют источник;
- 5 списковых полей сериализуются через `;` вместо JSON;
- `class_ids` — целые из таксономии на 10 классов;
- 115 диалогов, 23 `scenario_id`, ровно 2 совпадения с 31 классом, 7 классов без данных;
- ролей `tool` в данных нет; `tool_tokens` всегда 0;
- `created_at` укладывается в 0,64 секунды;
- `FIXED_TOOLS` и `FIXED_INTEGRATIONS` объявлены и нигде не используются.

**Допущения:**

- сопоставление §4.2 построено по сходству имён и описаний, а не по разметке человеком;
- частота ошибок §5.4 и §5.8 оценена по коду; настоящие числа даст только прогон.

**Не проверено:**

- реальный `outputs/analytics.csv` — в репозитории его нет, pipeline не запускался (нужен GPU и загрузка Qwen2.5-7B);
- поведение `use_case` при NaN — зависит от результата HDBSCAN на реальных эмбеддингах;
- качество извлечения признаков LLM — сравнивать не с чем, эталона по этим полям нет.
