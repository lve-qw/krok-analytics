# Каталог метрик Prompt Radar

Источник истины — канонический контракт `analytics.csv` (30 полей, см.
`src/prompt_radar/analytics_schema.py`). Метрика попадает в этот каталог только
если она вычисляется из объявленных полей. Ничто здесь не требует LLM: все
формулы — детерминированные агрегаты над валидированным CSV.

Вход любой метрики — файл, прошедший `python -m prompt_radar.validate` без
ошибок. Записи с `error` в дашборд не попадают.

---

## 0. Обозначения и правила интерпретации

| Обозначение | Смысл |
|---|---|
| `N` | число диалогов (строк) после применения фильтров |
| `share(cond)` | `count(cond) / N` |
| `explode(f)` | развернуть список `f` в отдельные строки: один диалог с `k` элементами даёт `k` строк |
| `total_tokens` | `user_tokens + assistant_tokens + tool_tokens` |
| `by(x)` | группировка по `x` |

**Правило знаменателя при multi-label.** `class_ids`, `tools`, `integrations`,
`company_sources`, `requires_generation`, `search_type` — списки. Частоты по ним
считаются как `count(explode(f))`, но доля берётся от `N` **диалогов**, а не от
числа строк после explode. Поэтому доли по классам суммируются больше 100%. Это
не ошибка; на каждой такой диаграмме подпись обязана это указывать.

### Что нельзя утверждать по этим данным

Эти ограничения повторяются в поле `limitations` соответствующих метрик и
обязательны к переносу в подписи дашборда.

| Запрет | Причина |
|---|---|
| `agent_failed == false` ≠ «задача выполнена успешно» | В контракте нет outcome-метки. Поле фиксирует только зарегистрированный сбой. Корректная формулировка — «сбой не зафиксирован». |
| `confidence` ≠ accuracy | Это уверенность модели, а не измеренная доля правильных ответов. Проверить её нечем: gold-разметки в проекте нет. |
| `estimated_cost` ≠ бизнес-ценность | Стоимость измеряет расход, а не пользу. Дорогой сценарий может быть самым ценным. |
| `automation_candidate` ≠ доказанная автоматизируемость | Аналитический признак-гипотеза. Требует подтверждения владельцем процесса. |
| `summary` ≠ исходный запрос | Это производный текст. Показывать можно как краткое содержание, подписывать «резюме», никогда — «запрос пользователя». |
| Любая динамика | В контракте нет timestamp. См. §3. |
| Любой разрез по людям и подразделениям | В контракте нет полей пользователя, команды, направления. См. §3. |

---

# 1. Метрики, рассчитываемые прямо из analytics.csv

## 1.1. Объём и структура использования

| metric_id | name | business_question | formula | source_fields | aggregation | filters | recommended_chart | priority | limitations |
|---|---|---|---|---|---|---|---|---|---|
| `vol.total_dialogues` | Всего диалогов | Каков объём проанализированного использования? | `N = count(request_id)` | `request_id` | count | все | KPI-число | P0 | Объём выборки, а не объём использования ИИ в компании: доля покрытия логов неизвестна |
| `vol.work_share` | Доля рабочих запросов | Используется ли агент по назначению? | `share(is_work == true)` | `is_work` | count, share | все | KPI-число + donut | P0 | Признак присвоен классификатором, не подтверждён пользователем |
| `vol.by_class` | Распределение по классам | Какие типы задач приносят основной объём? | `count(explode(class_ids)) by class_id`, доля от `N` | `class_ids`, `class_names` | count, share | все | горизонтальный bar, топ-15 | P0 | Multi-label: сумма долей > 100%. Частоты синтетической выборки не равны спросу |
| `vol.by_use_case` | Распределение по use case | Какие сценарии применения самые массовые? | `count() by use_case`, доля от `N` | `use_case` | count, share | все | горизонтальный bar, топ-15 | P0 | `use_case` — свободный текст; при отсутствии словаря возможны дубли-синонимы |
| `vol.multilabel_rate` | Доля многоклассовых запросов | Насколько часто один запрос смешивает задачи? | `share(len(class_ids) > 1)` | `class_ids` | share | все | KPI-число | P1 | Высокое значение может означать и сложные запросы, и нечёткую таксономию |
| `vol.class_cooccurrence` | Сочетания классов | Какие типы задач ходят парой? | `count()` по неупорядоченным парам из `class_ids` при `len ≥ 2` | `class_ids` | count по парам | все | heatmap класс × класс | P1 | Пары редки при малом `N`; ниже 5 наблюдений на пару не интерпретировать |
| `vol.by_language` | Языковое распределение | Нужна ли многоязычная поддержка? | `count() by language` | `language` | count, share | все | donut | P2 | Словарь языков не зафиксирован в контракте; значения не нормализуются валидатором |
| `vol.by_complexity` | Распределение по сложности | Насколько тяжёлые задачи ставят агенту? | `count() by complexity` | `complexity` | count, share | все | stacked bar | P1 | `complexity` присвоена моделью, порогов между уровнями в контракте нет |
| `vol.steps_distribution` | Распределение числа шагов | Насколько многошаговые поручения даёт пользователь? | гистограмма `steps_requested` | `steps_requested` | histogram, median | все | гистограмма | P2 | Число *запрошенных* шагов, а не выполненных |

## 1.2. Автоматизация

| metric_id | name | business_question | formula | source_fields | aggregation | filters | recommended_chart | priority | limitations |
|---|---|---|---|---|---|---|---|---|---|
| `auto.candidate_share` | Доля кандидатов на автоматизацию | Какая часть нагрузки в принципе автоматизируема? | `share(automation_candidate == true)` | `automation_candidate` | share | все | KPI-число | P0 | Гипотеза классификатора, не подтверждённая возможность |
| `auto.by_class` | Автоматизация по классам | Какие типы задач автоматизировать первыми? | `share(automation_candidate) by explode(class_ids)` | `class_ids`, `automation_candidate` | share по группам | все | bar с долей и объёмом | P1 | Доля без объёма вводит в заблуждение: показывать оба числа |
| `auto.by_use_case` | Автоматизация по сценариям | Какие конкретные сценарии выносить в автоматику? | `share(automation_candidate) by use_case` | `use_case`, `automation_candidate` | share по группам | все | bar | P0 | То же ограничение по объёму группы |
| `auto.by_periodicity` | Автоматизация по периодичности | Регулярна ли автоматизируемая нагрузка? | `count(automation_candidate) by periodicity` | `periodicity`, `automation_candidate` | count | `automation_candidate == true` | stacked bar | P1 | `periodicity` — заявленная пользователем регулярность, не наблюдённая частота |
| `auto.usecase_periodicity_matrix` | Матрица сценарий × периодичность | Где повторяемость и объём совпадают? | `count() by (use_case, periodicity)` | `use_case`, `periodicity` | count | опц. `automation_candidate == true` | heatmap | P0 | Клетки с малым `count` не интерпретировать |
| `auto.recurring_volume` | Массовые повторяющиеся сценарии | Что даст наибольший эффект от автоматизации по объёму? | `count() by use_case` при `automation_candidate == true and periodicity != 'none'`, сортировка по убыванию | `use_case`, `automation_candidate`, `periodicity` | count | — | bar, топ-10 | P0 | Ранжирование по объёму выборки. Денежная экономия не считается: нет данных о времени сотрудников и стоимости труда |

## 1.3. Надёжность агента

Во всём разделе `agent_failed == false` означает «сбой не зафиксирован», а не
«успех».

| metric_id | name | business_question | formula | source_fields | aggregation | filters | recommended_chart | priority | limitations |
|---|---|---|---|---|---|---|---|---|---|
| `fail.rate` | Доля зафиксированных сбоев | Насколько надёжен агент в целом? | `share(agent_failed == true)` | `agent_failed` | share | все | KPI-число | P0 | Нижняя граница проблем: молчаливо неверные ответы сюда не попадают |
| `fail.by_class` | Сбои по классам | Какие типы задач агент тянет хуже? | `share(agent_failed) by explode(class_ids)` | `class_ids`, `agent_failed` | share по группам | `count ≥ min_group` | bar | P1 | Требует минимального размера группы, иначе шум |
| `fail.by_use_case` | Сбои по сценариям | Какие сценарии чинить в первую очередь? | `share(agent_failed) by use_case` | `use_case`, `agent_failed` | share по группам | `count ≥ min_group` | scatter: объём × доля сбоев | P0 | Сценарии с 1–2 записями дают долю 0% или 100% без смысла |
| `fail.by_complexity` | Сбои по сложности | Ломается ли агент именно на сложном? | `share(agent_failed) by complexity` | `complexity`, `agent_failed` | share по группам | все | bar | P1 | `complexity` присвоена моделью, а не измерена |
| `fail.by_tool` | Сбои по инструментам | Какие инструменты подводят? | `share(agent_failed) by explode(tools)` | `tools`, `agent_failed` | share по группам | `count ≥ min_group` | bar | P0 | Связь корреляционная: сбой приписан всем инструментам диалога, виновник не идентифицирован |
| `fail.by_integration` | Сбои по интеграциям | Какие внешние системы создают проблемы? | `share(agent_failed) by explode(integrations)` | `integrations`, `agent_failed` | share по группам | `count ≥ min_group` | bar | P0 | То же ограничение атрибуции |
| `fail.reasons` | Причины сбоев | Что именно ломается? | `count() by failure_reason` при `agent_failed == true` | `failure_reason`, `agent_failed` | count | `agent_failed == true` | горизонтальный bar | P0 | Справочник причин не зафиксирован в контракте; свободный текст даёт разнобой формулировок |
| `fail.among_automation` | Сбои среди кандидатов на автоматизацию | Не автоматизируем ли мы то, что ломается? | `share(agent_failed) при automation_candidate == true` | `agent_failed`, `automation_candidate` | share | `automation_candidate == true` | KPI-число + bar по сценариям | P0 | Пересечение двух модельных признаков; накопленная неопределённость выше, чем у каждого по отдельности |
| `fail.cost` | Стоимость сбоев | Сколько стоят неудачные диалоги? | `sum(estimated_cost)` и `sum(total_tokens)` при `agent_failed == true` | `estimated_cost`, `user_tokens`, `assistant_tokens`, `tool_tokens`, `agent_failed` | sum, share от общей | `agent_failed == true` | KPI-число + bar по сценариям | P1 | Расход, а не потери: часть работы могла быть полезной до сбоя |

## 1.4. Качество классификации

| metric_id | name | business_question | formula | source_fields | aggregation | filters | recommended_chart | priority | limitations |
|---|---|---|---|---|---|---|---|---|---|
| `clf.confidence_central` | Средняя и медианная уверенность | Насколько модель уверена в разметке? | `mean(confidence)`, `median(confidence)` | `confidence` | mean, median | все | KPI-число | P1 | Не accuracy. Гарантий калибровки нет |
| `clf.low_share` | Доля низкой уверенности | Какая часть аналитики опирается на шаткую разметку? | `share(confidence < low_confidence_threshold)` | `confidence` | share | все | KPI-число | P0 | Зависит от порога; порог конфигурируем, значение обязано выводиться рядом |
| `clf.low_by_class` | Низкая уверенность по классам | Какие классы модель различает плохо? | `share(confidence < threshold) by explode(class_ids)` | `class_ids`, `confidence` | share по группам | `count ≥ min_group` | bar | P1 | Указывает на проблему класса ИЛИ таксономии — различить нечем |
| `clf.most_uncertain` | Самые неопределённые классы | Какие определения классов переписать? | топ-N по `mean(1 - confidence) by explode(class_ids)` | `class_ids`, `confidence` | mean по группам | `count ≥ min_group` | bar, топ-10 | P1 | То же |
| `clf.vs_complexity` | Уверенность против сложности | Падает ли качество разметки на сложном? | `mean(confidence) by complexity` | `confidence`, `complexity` | mean по группам | все | bar / box | P2 | Оба поля от одной модели; согласованность не является независимым подтверждением |
| `clf.vs_failure` | Уверенность против сбоев | Предсказывает ли низкая уверенность проблемы? | `mean(confidence)` раздельно при `agent_failed == true/false` | `confidence`, `agent_failed` | mean по группам | все | сгруппированный bar | P1 | Корреляция, не причинность |

**Порог низкой уверенности.** Значение по умолчанию — `0.5`, задано в
`prompt_radar.validation.DEFAULT_LOW_CONFIDENCE`, меняется флагом
`--low-confidence`. Обоснование: калибровочных данных нет, поэтому любой порог
произволен; `0.5` выбран как нейтральная граница «модель скорее не уверена», не
привязанная к конкретной модели. Как только появится размеченный набор, порог
подлежит пересчёту по кривой precision/recall, а до тех пор он остаётся
настройкой, а не измерением.

## 1.5. Инструменты и интеграции

| metric_id | name | business_question | formula | source_fields | aggregation | filters | recommended_chart | priority | limitations |
|---|---|---|---|---|---|---|---|---|---|
| `tool.frequency` | Частота инструментов | Какие возможности реально востребованы? | `count(explode(tools))`, доля от `N` | `tools` | count, share | все | горизонтальный bar | P0 | Значения нормализованы по реестру `FIXED_TOOLS` из `config.py`; не опознанные имена отброшены адаптером и перечислены в `export_report.json` |
| `intg.frequency` | Частота интеграций | Какие системы нагружены больше всего? | `count(explode(integrations))`, доля от `N` | `integrations` | count, share | все | горизонтальный bar | P0 | Значения нормализованы по реестру `FIXED_INTEGRATIONS`; отброшенные имена перечислены в `export_report.json` |
| `tool.per_dialogue` | Инструментов на диалог | Насколько составные задачи решает агент? | `mean/median(len(tools))`, гистограмма | `tools` | mean, median | все | гистограмма | P2 | Уникальные инструменты, не число вызовов |
| `intg.per_dialogue` | Интеграций на диалог | Насколько связаны между собой системы? | `mean/median(integration_count)` | `integration_count` | mean, median | все | гистограмма | P2 | — |
| `tool.call_intensity` | Интенсивность вызовов | Где агент вызывает инструменты повторно? | `mean(tool_calls / len(tools))` при `len(tools) > 0` | `tool_calls`, `tools` | mean по группам | `len(tools) > 0` | bar по инструментам | P2 | Повторные вызовы приписаны всем инструментам диалога поровну |
| `tool.cost` | Стоимость по инструментам | Какие инструменты дороже обходятся? | `mean(estimated_cost)`, `sum(tool_tokens)` по `explode(tools)` | `tools`, `estimated_cost`, `tool_tokens` | sum, mean | `count ≥ min_group` | bar | P1 | Стоимость диалога делится не между инструментами, а дублируется на каждый — суммы по группам не складываются в общий итог |
| `tool.cooccurrence` | Сочетания инструментов | Какие цепочки инструментов устойчивы? | `count()` по неупорядоченным парам из `tools` | `tools` | count по парам | `len(tools) ≥ 2` | heatmap | P2 | Порядок вызовов не фиксируется — это совместная встречаемость, а не последовательность |
| `intg.load_ranking` | Наиболее нагруженные системы | Куда идут запросы на пропускную способность? | `count(explode(integrations))`, `sum(tool_calls)` по интеграции | `integrations`, `tool_calls` | count, sum | все | bar с двумя мерами | P1 | `tool_calls` не разделены по интеграциям, приписываются целиком |

`fail.by_tool` и `fail.by_integration` относятся к этому семейству тоже; они
определены в §1.3 и не дублируются.

## 1.6. Стоимость и токены

| metric_id | name | business_question | formula | source_fields | aggregation | filters | recommended_chart | priority | limitations |
|---|---|---|---|---|---|---|---|---|---|
| `cost.total` | Суммарная стоимость | Сколько стоит LLM/API-обработка выборки? | `sum(estimated_cost)` | `estimated_cost` | sum | все | KPI-число | P0 | **Только LLM/API-обработка.** Инфраструктура, GPU, лицензии и поддержка не входят: это не полная стоимость эксплуатации и не база для ROI |
| `cost.per_dialogue` | Стоимость диалога | Сколько стоит типичное обращение? | `mean`, `median`, `p90` от `estimated_cost` | `estimated_cost` | mean, median, p90 | все | KPI-число + box | P0 | Распределение тяжелохвостое: среднее без медианы вводит в заблуждение |
| `cost.by_class` | Стоимость по классам | Какие типы задач съедают бюджет? | `sum(estimated_cost) by explode(class_ids)` | `class_ids`, `estimated_cost` | sum, mean | все | bar | P1 | Multi-label: стоимость дублируется на каждый класс, сумма по классам > общей |
| `cost.by_use_case` | Стоимость по сценариям | Какие сценарии дороже всего? | `sum`, `mean(estimated_cost) by use_case` | `use_case`, `estimated_cost` | sum, mean | все | bar | P0 | Сценарий назначается ровно один, поэтому здесь суммы складываются корректно |
| `cost.token_split` | Разложение токенов | На что уходит контекст: на пользователя, ответ или инструменты? | `sum(user_tokens)`, `sum(assistant_tokens)`, `sum(tool_tokens)`, доли от `total_tokens` | `user_tokens`, `assistant_tokens`, `tool_tokens` | sum, share | все | stacked bar | P0 | **На текущем наборе `tool_tokens = 0` во всех строках:** в исходных диалогах нет сообщений с ролью `tool`. Это пробел инструментирования, а не свидетельство того, что инструменты бесплатны |
| `cost.by_complexity` | Токены и стоимость по сложности | Оправдана ли цена сложных задач? | `mean(total_tokens)`, `mean(estimated_cost) by complexity` | `complexity`, токены, `estimated_cost` | mean | все | сгруппированный bar | P1 | — |
| `cost.top_use_cases` | Самые дорогие сценарии | Где оптимизировать промпты и контекст? | топ-N по `sum(estimated_cost) by use_case` | `use_case`, `estimated_cost` | sum | — | bar, топ-10 | P0 | Дорогой ≠ бесполезный: без метрики ценности выводы об отключении сценария недопустимы |
| `cost.concentration` | Концентрация расходов | Даст ли работа с немногими сценариями основную экономию? | `sum(estimated_cost)` топ-N сценариев / `sum(estimated_cost)`, N по умолчанию 5 | `use_case`, `estimated_cost` | share | все | Парето: bar + кумулятивная линия | P0 | Зависит от N; значение N выводить в подписи |
| `cost.failed` | Стоимость сбойных диалогов | Сколько уходит на неудачные обращения? | см. `fail.cost` | — | — | — | — | P1 | Определена в §1.3 |

## 1.7. Корпоративные данные и безопасность

| metric_id | name | business_question | formula | source_fields | aggregation | filters | recommended_chart | priority | limitations |
|---|---|---|---|---|---|---|---|---|---|
| `sec.company_data_share` | Доля обращений к корпданным | Насколько глубоко агент встроен во внутренний контур? | `share(uses_company_data == true)` | `uses_company_data` | share | все | KPI-число | P1 | — |
| `sec.top_sources` | Основные внутренние источники | Какие хранилища критичны для агента? | `count(explode(company_sources))` | `company_sources` | count, share | `uses_company_data == true` | bar | P1 | Валидатор помечает warning, когда источник не определён; такие диалоги выпадают из знаменателя |
| `sec.sensitive_rate` | Доля чувствительных данных | Какой объём нагрузки требует режима повышенного контроля? | `share(contains_sensitive_data == true)` | `contains_sensitive_data` | share | все | KPI-число | P0 | Признак присвоен моделью; ни точность, ни полнота детектора не измерены |
| `sec.injection_rate` | Доля prompt injection | Атакуют ли агента через контекст? | `share(prompt_injection == true)` | `prompt_injection` | share | все | KPI-число | P0 | Фиксируется **попытка/обнаружение**, а не успешность атаки. Пропуски детектора невидимы |
| `sec.sensitive_by_use_case` | Чувствительные данные по сценариям | Где вводить дополнительный контроль? | `share(contains_sensitive_data) by use_case` | `use_case`, `contains_sensitive_data` | share по группам | `count ≥ min_group` | heatmap / bar | P1 | — |
| `sec.injection_by_use_case` | Injection по сценариям | Какие сценарии наиболее уязвимы? | `share(prompt_injection) by use_case` | `use_case`, `prompt_injection` | share по группам | `count ≥ min_group` | bar | P1 | События редкие: доли по малым группам нестабильны |
| `sec.failures_on_company_data` | Сбои на внутренних данных | Надёжен ли агент там, где он уже интегрирован? | `share(agent_failed) при uses_company_data == true`, сравнение с `false` | `agent_failed`, `uses_company_data` | share по группам | все | сгруппированный bar | P1 | — |
| `sec.exposure_overlap` | Пересечение риска утечки | Есть ли путь наружу для чувствительных внутренних данных? | `count(contains_sensitive_data == true and uses_company_data == true and 'internet' in search_type)` | `contains_sensitive_data`, `uses_company_data`, `search_type` | count, share | все | KPI-число + drill-down | P0 | Совместная встречаемость в одном диалоге, а не доказанная передача данных вовне. Каждая запись требует ручного разбора |

## 1.8. Генерация и поиск

| metric_id | name | business_question | formula | source_fields | aggregation | filters | recommended_chart | priority | limitations |
|---|---|---|---|---|---|---|---|---|---|
| `gen.format_distribution` | Требуемые форматы результата | Какие форматы вывода нужно поддерживать? | `count(explode(requires_generation))`, доля от `N` | `requires_generation` | count, share | все | bar | P1 | Закрытый словарь: `text`, `excel`, `sql`, `presentation`. Всё прочее контракт не выражает |
| `gen.search_split` | Внешний против внутреннего поиска | Куда агент ходит за информацией? | `count(explode(search_type))`, доля от `N` | `search_type` | count, share | все | donut / bar | P1 | Диалог может содержать оба типа |
| `gen.heavy_output_use_cases` | Сценарии с Excel, SQL и презентациями | Где нужны специализированные генераторы? | `count() by use_case` при пересечении `requires_generation` с `{excel, sql, presentation}` | `use_case`, `requires_generation` | count | — | bar | P1 | — |
| `gen.output_vs_outcome` | Формат против стоимости и сбоев | Дорого ли и надёжно ли даётся тяжёлый вывод? | `mean(estimated_cost)`, `share(agent_failed)`, распределение `complexity` по `explode(requires_generation)` | `requires_generation`, `estimated_cost`, `agent_failed`, `complexity` | mean, share | `count ≥ min_group` | сгруппированный bar | P1 | Формат дублируется на диалог с несколькими форматами |

---

# 2. Производные метрики, требующие явных допущений

Каждая метрика этого раздела вводит допущение, которого нет в данных. Все они
дефолтом **выключены** и включаются только с явной подписью допущения на
диаграмме.

| metric_id | name | business_question | formula | source_fields | aggregation | filters | recommended_chart | priority | limitations |
|---|---|---|---|---|---|---|---|---|---|
| `drv.automation_backlog` | Приоритет очереди автоматизации | С какого сценария начинать? | `count(use_case) × w(periodicity)` при `automation_candidate == true`, где `w` — заданный вручную множитель частоты (`daily` > `weekly` > `monthly`) | `use_case`, `periodicity`, `automation_candidate` | взвешенный count | `automation_candidate == true` | bar, топ-10 | P1 | **Допущение:** веса периодичности назначены человеком, в данных их нет. Меняя веса, меняешь ранжирование. Веса выводить рядом с диаграммой |
| `drv.problem_score` | Проблемность сценария | Какие сценарии чинить первыми? | нормированное `share(agent_failed) × count × mean(estimated_cost)` по `use_case` | `use_case`, `agent_failed`, `estimated_cost` | композит | `count ≥ min_group` | bar / bubble | P1 | **Допущение:** три несопоставимые величины сведены в один балл при равных весах. Ранжирование зависит от нормировки; составляющие показывать раздельно |
| `drv.review_queue` | Очередь ручного разбора | Какие записи смотреть человеку? | `confidence < threshold` ИЛИ `agent_failed` ИЛИ `contains_sensitive_data` ИЛИ `prompt_injection` | `confidence`, `agent_failed`, `contains_sensitive_data`, `prompt_injection` | count, share | все | KPI-число + drill-down | P0 | **Допущение:** четыре разнородных сигнала объединены по ИЛИ и считаются равносрочными. Это фильтр внимания, а не оценка риска |
| `drv.tool_reliability` | Индекс надёжности инструмента | Какие инструменты стабилизировать? | `1 - share(agent_failed)` по `explode(tools)`, с интервалом Уилсона | `tools`, `agent_failed` | share + CI | `count ≥ min_group` | bar с интервалами | P1 | **Допущение:** сбой диалога приписан каждому использованному инструменту. При нескольких инструментах виновник не определён — метрика верхняя оценка вины |
| `drv.cost_at_risk` | Расход на сбои в пересчёте | Сколько стоит ненадёжность? | `sum(estimated_cost при agent_failed) / sum(estimated_cost)` | `estimated_cost`, `agent_failed` | share | все | KPI-число | P2 | **Допущение:** выборка репрезентативна для всего потока. Проверить нечем: покрытие логов неизвестно. Экстраполяция на период невозможна — нет времени |

**Чего в этом разделе намеренно нет.** Денежной экономии от автоматизации,
ROI внедрения и высвобожденных человеко-часов. Для них нужны длительность
ручного выполнения сценария и стоимость труда; ни того, ни другого контракт не
содержит, а подставлять отраслевые средние — значит выдать допущение за
измерение.

---

# 3. Метрики, невозможные при текущей схеме

Не обходить, не аппроксимировать, не показывать в дашборде. Каждая строка —
кандидат на расширение контракта, если заказчик подтвердит потребность.

| Метрика | Чего не хватает | Минимальное расширение контракта |
|---|---|---|
| Динамика объёма, тренды, сезонность | Нет timestamp | `timestamp` (ISO 8601, UTC) |
| Рост и затухание use cases | Нет измерения времени | `timestamp` |
| Появление новых сценариев | Нет времени и истории версий таксономии | `timestamp` + версия таксономии |
| Сравнение периодов и эффект изменений | Нет времени | `timestamp` |
| Разрезы по сотрудникам, командам, направлениям | Нет полей пользователя и оргструктуры | `user_id` (псевдонимизированный), `team`, `business_unit` |
| Adoption: число активных пользователей, повторное использование, retention | Нет идентификатора пользователя | `user_id` |
| Анализ на уровне сессии, длина диалога, число ходов | Нет `session_id` и числа сообщений | `session_id`, `turn_count` |
| Реальные примеры пользовательских запросов | Нет `request_text`; `summary` — производный текст | `request_text` + политика редактирования |
| Настоящий success rate | Нет outcome-метки, отличной от `agent_failed` | `outcome` (`completed` / `partial` / `failed` / `unknown`) |
| Accuracy, precision, recall классификации | Нет эталонной разметки | набор gold-меток с двойной аннотацией |
| Полнота и качество ответа | Нет оценки результата | `completeness` или человеческая оценка |
| Задержка и время ответа | Нет полей длительности | `latency_ms` |
| Сравнение моделей и версий агента | Нет идентификатора модели | `model_id`, `agent_version` |
| Реальные денежные затраты | `estimated_cost` — оценка, тарифы не зафиксированы | тарифная карта + фактический биллинг |
| Успешность prompt injection | Флаг фиксирует обнаружение, не результат | `injection_outcome` |
| Атрибуция сбоя конкретному инструменту | Нет пошаговых событий | лог tool-call с результатом каждого вызова |
| Экономия времени и ROI | Нет длительности ручного выполнения и стоимости труда | нормативы процесса от бизнеса |

---

# 4. Выбранные KPI и диаграммы первого экрана

## 4.1. KPI-карточки (5)

| # | Карточка | Метрики | Управленческий вопрос | Возможное действие |
|---|---|---|---|---|
| 1 | Порог безубыточности | `drv.breakeven_minutes` | Сколько минут должен экономить один запрос, чтобы заданный TCO окупился? | Проверить порог на нормативах реальных процессов |
| 2 | Потреблено токенов | сумма токенов по ролям | Какой измеренный объём инференса прошёл за период? | Управлять лимитами и контекстом |
| 3 | MAU / активные пользователи | уникальные `user_id` | Сколько сотрудников реально пользовались агентом? | Сравнивать использование с числом выданных доступов |
| 4 | Обращения к агенту | число диалогов, `tool_calls` | Каков объём работы агента и инструментов? | Находить сценарии с реальной инструментальной нагрузкой |
| 5 | Оценка высвобождённого ресурса | запросы × выбранные минуты | Какой объём часов и FTE соответствует принятому допущению? | Проверить допущение на замерах «до / после» |

Токены, диалоги, вызовы инструментов и пользователи считаются из выгрузки.
Порог безубыточности использует заданный снаружи TCO, а FTE — выбранное
ползунком время экономии. Эти допущения показываются на экране и не смешиваются
с измеренными величинами.

## 4.2. Основные диаграммы (7)

| # | Диаграмма | Тип | Метрики | Отвечает на вопрос |
|---|---|---|---|---|
| 1 | Карта использования | интерактивный горизонтальный bar, топ-15 | диалоги / токены / `tool_calls` по сценарию / классу / `user_id` | Кто пользуется агентом и на что расходуются ресурсы? |
| 2 | Сценарий × периодичность | heatmap | `auto.usecase_periodicity_matrix`, `auto.recurring_volume` | Какие сценарии подходят для автоматизации? |
| 3 | Объём против доли сбоев | scatter, размер точки — стоимость | `fail.by_use_case`, `vol.by_use_case`, `cost.by_use_case` | Где агент чаще ломается и насколько это дорого? |
| 4 | Надёжность инструментов и интеграций | bar с интервалами | `fail.by_tool`, `fail.by_integration`, `drv.tool_reliability` | Какие tools и integrations создают проблемы? |
| 5 | Парето расходов по сценариям | bar + кумулятивная линия | `cost.by_use_case`, `cost.concentration` | Куда уходят токены и стоимость? |
| 6 | Разложение токенов по сложности | stacked bar | `cost.token_split`, `cost.by_complexity` | Что именно съедает контекст? |
| 7 | Риски данных по сценариям | heatmap | `sec.sensitive_by_use_case`, `sec.injection_by_use_case`, `sec.exposure_overlap` | Где есть риски данных и prompt injection? |

Причины сбоев (`fail.reasons`) и распределение классов (`vol.by_class`) не
получают отдельных диаграмм: первое раскрывается по клику из диаграммы 3,
второе — переключателем в диаграмме 1. Тот же переключатель позволяет
атрибутировать токены и вызовы инструментов псевдонимизированным пользователям.

**Временного графика нет.** В контракте нет надёжного поля времени, поэтому
диаграмма динамики не строится ни в каком виде.

## 4.3. Drill-down таблица (1)

Колонки — `analytics_schema.DRILLDOWN_COLUMNS`:

```text
request_id, class_names, use_case, summary, confidence, complexity,
automation_candidate, integrations, tools, agent_failed, failure_reason,
estimated_cost
```

Колонка `summary` подписывается «Резюме диалога». Формулировка «запрос
пользователя» запрещена: исходного текста в контракте нет.

Таблица подчиняется всем фильтрам и служит выходом из карточки 6 и диаграмм 3
и 7.

## 4.4. Фильтры

`is_work`, класс, use case, `complexity`, `periodicity`, `language`,
интеграция, инструмент, `automation_candidate`, `agent_failed`,
`contains_sensitive_data`, `prompt_injection`.

Фильтры по классам, интеграциям и инструментам работают по логике «содержит
любой из выбранных» над списковыми полями. Порог `min_group` и порог низкой
уверенности выведены в настройки и отображаются рядом с зависящими от них
величинами.

---

# 5. Что этот каталог не берётся утверждать

## 5.0. Статус данных: DEMO / SYNTHETIC DATA

Все показатели в дашборде и в этом каталоге на текущем наборе построены на
синтетических данных. 115 исходных диалогов сгенерированы по 23 сценариям
ровно по 5 штук на сценарий, а `outputs/dialogs.csv` для проверки цепочки
создаётся `scripts/make_sample_pipeline_output.py` с псевдослучайным
присвоением классов. Ни одну частоту нельзя называть наблюдаемым спросом.

Семь из 31 класса не представлены в наборе. Это принято как факт: диалоги под
них не досоздавались, поскольку искусственное выравнивание частот сделало бы
распределение ещё менее похожим на реальное.



1. Частоты **сгенерированы**, см. §5.0. До появления настоящей выгрузки
   дашборд демонстрирует методику, а не результаты.
2. Ни одна метрика не измеряет пользу от ИИ. Контракт содержит расход, сбои и
   модельные признаки, но не содержит ценности, времени и результата.
3. Все признаки, кроме токенов и стоимости, присвоены классификатором и не
   верифицированы человеком. Их качество не измерено, потому что эталонной
   разметки в проекте нет.
4. ROI, экономия человеко-часов и полная стоимость владения не рассчитываются
   ни в одной метрике. `estimated_cost` покрывает только LLM/API-обработку;
   инфраструктурная стоимость, стоимость труда и длительность ручного
   выполнения сценариев в контракте отсутствуют.
