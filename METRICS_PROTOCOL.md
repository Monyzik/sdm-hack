# Протокол проектных метрик

Документ фиксирует, какие метрики нужны MVP AI Project Control Tower, как их читать руководителю проекта и какие показатели стоит добавить следующими. Метрики должны считаться поверх source-таблиц, а не храниться в CSV как готовые агрегаты.

## Цель

Метрики нужны не для декоративного дашборда, а для еженедельного управленческого контура:

- быстро понять, ухудшился ли проект;
- увидеть причину ухудшения;
- найти владельца проблемы;
- оценить влияние на срок, бюджет и эффект;
- сформировать список решений и эскалаций для РП, PMO или steering committee.

## Базовый протокол

1. Все метрики считаются на дату среза `as_of`.
2. Source layer: `projects`, `tasks`, `task_history`, `task_comments`, `milestones`, `budgets`, `risks`, `communications`, `resource_allocations`, `dependencies`, `decisions`, `change_requests`.
3. Derived layer: health score, risk level, forecast total spent, overdue count, budget deviation, ROI, overload, delay, pending decisions и другие агрегаты.
4. Для каждой красной или желтой метрики нужен не только числовой показатель, но и объяснение: объект, владелец, причина, связанная задача/веха.
5. Для РП главный выход системы: executive summary, key signals, список решений, список эскалаций.

Программный контракт лежит в `backend/app/services/metrics.py`:

- `ProjectMetricContext` — вход расчета метрик: source-данные проекта и дата среза;
- `ProjectMetric` — protocol интерфейса метрики;
- `FunctionMetric` — реализация protocol для метрик на функциях;
- `PROJECT_METRIC_PROTOCOL` — реестр доступных метрик с источниками, описанием и action для РП;
- `calculate_<metric>()` — отдельная функция расчета для каждой метрики;
- `calculate_project_metrics()` — сборка полного snapshot метрик для summary API.

Агентский граф `agents/project_monitor_graph.py` также должен использовать этот слой: граф может адаптировать названия полей под промпты и алерты, но не должен повторно реализовывать формулы метрик.

## Текущие метрики

| Метрика | Как считается | Как помогает РП |
|---|---|---|
| `completion_percent` | `done / total tasks * 100` | Показывает фактический прогресс, но не должен использоваться без просрочек и блокеров. |
| `overdue_tasks_count` | открытые задачи с `planned_due_date < as_of` | Показывает накопленное отставание и помогает выбрать задачи для weekly status. |
| `delayed_milestones_count` | открытые вехи с `planned_end_date < as_of` | Показывает срыв ключевых этапов, который важнее отдельных просроченных задач. |
| `blocked_tasks_count` | задачи с `is_blocked=true` или статусом `Blocked` | Показывает, где команда не может двигаться без внешнего действия. |
| `high_risk_count` | открытые риски с `probability * impact >= 15` | Фокусирует РП на рисках, которые уже требуют mitigation или эскалации. |
| `budget_deviation_percent` | `(calculated_forecast_total_spent - planned_budget) / planned_budget * 100`; forecast считается из план/факт-статей бюджета и CR, а не хранится в CSV | Показывает ожидаемый перерасход до того, как он полностью попал в факт. |
| `roi_percent` | `(expected_economic_effect - calculated_forecast_total_spent) / calculated_forecast_total_spent * 100` | Показывает, сохраняет ли проект экономический смысл. |
| `risk_adjusted_roi_percent` | ROI после дисконта эффекта на давление high-risk рисков | Помогает не переоценивать эффект проекта при большом risk exposure. |
| `resource_overload_percent` | максимальный перегруз ресурса сверх доступной емкости | Показывает, кто является узким местом и где нужен перераспределенный capacity. |
| `max_communication_delay_days` | максимальная просрочка ответа по открытым коммуникациям; pending с будущей датой ответа не считается задержкой | Показывает, какие согласования или ответы тормозят проект. |
| `dependency_risk_count` | critical/high зависимости в статусах `pending`, `delayed`, `blocked` или overdue | Объясняет blocked-задачи через внешнюю команду, систему, approval или вендора. |
| `pending_decision_count` | решения в статусах `pending`, `under_review` | Показывает, что проект может стоять не из-за команды, а из-за непринятого управленческого решения. |
| `open_change_request_count` | CR в статусах `pending`, `under_review`, `proposed` | Показывает активные изменения scope, бюджета и сроков, которые меняют прогноз проекта. |
| `project_health_score` | 100 минус штрафы за просрочки, блокеры, бюджет, риски, перегруз, коммуникации, зависимости, решения и CR | Единый индекс для сортировки проектов и быстрого выбора проблемных инициатив. |
| `risk_level` | `red <= 55`, `yellow <= 75`, иначе `green` | Простая зона внимания для портфельного обзора и PMO. |
| `portfolio_health_score` | средний `project_health_score` по портфелю | Показывает общее состояние портфеля и динамику нагрузки на РП/PMO. |

## Как читать метрики

`completion_percent` сам по себе опасен: проект может быть готов на 70%, но иметь critical dependency и отрицательный ROI. Поэтому РП должен читать метрики в связке:

1. `risk_level` и `project_health_score` отвечают на вопрос “насколько всё плохо”.
2. `key_signals` отвечают на вопрос “почему стало плохо”.
3. `blocked_tasks`, `dependencies`, `communications` отвечают на вопрос “кто блокирует”.
4. `budget`, `change_requests`, `decisions` отвечают на вопрос “какой impact и какое решение нужно”.
5. `resources` отвечают на вопрос “есть ли capacity для восстановления плана”.

Пример управленческой интерпретации:

> P001 в красной зоне не просто из-за просроченных задач. Основная причина: Security approval просрочен, DWH dependency delayed, forecast бюджета выше плана, есть pending decision по scope cut.

## Реализованные дополнительные метрики

Эти метрики больше не являются roadmap: они реализованы в `backend/app/services/metrics.py`, включены в `PROJECT_METRIC_PROTOCOL`, возвращаются через `ProjectSummary` и используются агентским графом `agents/project_monitor_graph.py`.

| Метрика | Источник | Как помогает РП |
|---|---|---|
| `milestone_slip_days` | `milestones` | Показывает максимальный сдвиг ключевой вехи, а не только количество задержанных вех. |
| `critical_path_delay_days` | `task_dependencies`, `tasks` | Показывает, какая задержка на critical path реально двигает срок проекта. |
| `blocked_age_days` | `task_history`, `tasks` | Отличает новый блокер от старого блокера, который уже требует эскалации. |
| `decision_age_days` | `decisions` | Показывает, сколько дней висит самое старое управленческое решение. |
| `net_change_request_impact_days` | `change_requests.requested_timeline_delta_days` | Суммирует запрошенную дельту срока по открытым CR. |
| `net_change_request_impact_budget` | `change_requests.requested_budget_delta` | Суммирует запрошенную дельту бюджета по открытым CR. |
| `dependency_sla_breach_count` | `dependencies` | Показывает открытые зависимости, где expected date уже нарушена. |
| `scope_churn_rate` | `change_requests`, `task_history`, `tasks` | Показывает нестабильность scope через CR и изменения сроков/оценок задач. |
| `burn_rate_percent` | `budgets` | Показывает долю потраченного бюджета от плана. |
| `schedule_variance_percent` | `tasks` | Сравнивает фактическую готовность с плановой готовностью по due dates. |
| `risk_trend` | `risks` | Даёт текущий proxy-тренд рисков по статусам high-risk записей. |
| `communication_silence_days` | `communications` | Находит открытые коммуникации, где давно не было последнего сообщения. |
| `data_freshness_days` | source layer events | Показывает, можно ли доверять summary: старые данные дают ложную уверенность. |
| `owner_action_load` | `tasks`, `dependencies`, `decisions`, `change_requests`, `communications` | Показывает, на ком сконцентрированы блокеры, решения, CR и просроченные коммуникации. |
| `cost_of_delay_exposure` | `budgets`, `milestones`, `task_dependencies`, `dependencies`, `communications` | Переводит текущую задержку в денежный exposure через cost of delay per day. |

## Метрики из файла "Поля и метрики"

Из `docs/Поля и метрики.xlsx` взяты только метрики, которые можно посчитать из текущей модели данных без выдуманных полей и ML-заглушек.

| Метрика | Источник | Как помогает РП |
|---|---|---|
| `stale_tasks_count` | `task_history`, `tasks` | Показывает открытые задачи без смены статуса больше 5 дней. |
| `max_status_age_days` | `task_history`, `tasks` | Показывает максимальный возраст текущего статуса среди открытых задач. |
| `estimate_overrun_percent` | `tasks` | Показывает отклонение `spent_hours` от `estimated_hours`. |
| `workload_imbalance_index` | `tasks` | Показывает, насколько неравномерно открытые задачи распределены по исполнителям. |
| `key_person_dependency_percent` | `tasks` | Показывает максимальную долю открытых задач на одном исполнителе. |
| `critical_task_silence_days` | `tasks`, `task_comments` | Показывает, сколько дней нет комментариев по critical/high задачам. |

## Осознанно не реализовано

Часть метрик из Excel пока нельзя посчитать корректно из текущих таблиц:

- `deadline_slip_probability`, `completion_forecast`, `budget_overrun_forecast`, `quality_forecast`, `burnout` требуют отдельной прогнозной модели или исторических snapshots.
- `test_coverage`, `bug/story ratio`, `reopen percent`, `technical debt` требуют таблиц по тестам, дефектам, reopen-событиям и техдолгу.
- `sprint_goal_risk`, `velocity drop`, `meetings load` требуют сущностей sprint, velocity history и календаря встреч.
- `negative tone`, `conflict signals`, `unanswered questions` требуют NLP-разбора сообщений и отдельной разметки коммуникаций.

Их лучше добавлять после расширения source layer, чтобы метрики не стали декоративными числами без управленческой достоверности.

## Минимальный weekly status для РП

Каждый weekly status должен собираться из метрик в таком формате:

1. Зона проекта: `risk_level`, `project_health_score`, изменение относительно прошлого среза.
2. Прогресс: `completion_percent`, `milestone_slip_days`, ключевая ближайшая веха.
3. Основные причины: top-3 `key_signals`.
4. Блокеры: critical `blocked_tasks`, `dependencies`, `communications`.
5. Финансы: `budget_deviation_percent`, `roi_percent`, `risk_adjusted_roi_percent`, `cost_of_delay_exposure`.
6. Решения: `pending_decisions` с владельцами и сроком ожидания.
7. Изменения: open `change_requests` и суммарный impact по дням/бюджету.
8. Следующее действие: что должен сделать РП, владелец зависимости или steering committee.

## Итог

Для MVP уже достаточно метрик, чтобы показать не просто “красный/зеленый” статус, а причинно-следственную цепочку: задача заблокирована -> зависимость просрочена -> CR увеличил срок и бюджет -> нужно управленческое решение. Следующий шаг — добавить метрики возраста блокеров, сдвига вех, critical path и net impact change requests, чтобы система могла готовить более точный weekly status и список решений для РП.
