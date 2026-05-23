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
3. Derived layer: health score, risk level, overdue count, budget deviation, ROI, overload, delay, pending decisions и другие агрегаты.
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
| `budget_deviation_percent` | `(forecast_total_spent - planned_budget) / planned_budget * 100` | Показывает ожидаемый перерасход до того, как он полностью попал в факт. |
| `roi_percent` | `(expected_economic_effect - forecast_total_spent) / forecast_total_spent * 100` | Показывает, сохраняет ли проект экономический смысл. |
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

## Рекомендуемые новые метрики

| Метрика | Источник | Зачем добавить |
|---|---|---|
| `milestone_slip_days` | `milestones` | Покажет сдвиг ключевых этапов, а не только отдельных задач. |
| `critical_path_delay_days` | `task_dependencies`, `tasks`, `milestones` | Позволит объяснять, какие зависимости реально двигают финальную дату проекта. |
| `blocked_age_days` | `task_history`, `tasks` | Отличит новый блокер от старого, который уже требует эскалации. |
| `decision_age_days` | `decisions` | Покажет, сколько дней управленческое решение висит без владельца. |
| `net_change_request_impact_days` | `change_requests` | Суммарно покажет влияние открытых CR на срок. |
| `net_change_request_impact_budget` | `change_requests` | Суммарно покажет влияние открытых CR на бюджет. |
| `dependency_sla_breach_count` | `dependencies` | Покажет команды/вендоров, которые системно нарушают ожидаемые даты. |
| `scope_churn_rate` | `change_requests`, `task_history` | Покажет нестабильность scope: много изменений означает риск по сроку и бюджету. |
| `burn_rate_percent` | `budgets`, `milestones`, `tasks` | Сравнит расход бюджета с фактическим прогрессом. |
| `schedule_variance_percent` | `tasks`, `milestones` | Покажет отставание от календарного плана в процентах. |
| `risk_trend` | `risks`, `task_history` или будущие snapshots | Покажет, рисковый профиль улучшается или ухудшается за неделю. |
| `communication_silence_days` | `communication_messages`, `task_comments` | Найдет зависшие темы, где давно не было ответа или follow-up. |
| `data_freshness_days` | все source-таблицы | Покажет, можно ли доверять summary: старые данные дают ложную уверенность. |
| `owner_action_load` | `tasks`, `decisions`, `dependencies`, `change_requests` | Покажет, сколько действий висит на конкретном владельце или команде. |
| `cost_of_delay_exposure` | `budgets`, `milestones`, `dependencies` | Оценит денежный ущерб от текущей задержки. |

## Приоритет внедрения

1. `milestone_slip_days`, `critical_path_delay_days`, `blocked_age_days`.
2. `decision_age_days`, `net_change_request_impact_days`, `net_change_request_impact_budget`.
3. `burn_rate_percent`, `schedule_variance_percent`, `cost_of_delay_exposure`.
4. `risk_trend`, `scope_churn_rate`, `data_freshness_days`.

Первый блок нужен для объяснения “почему проект красный”. Второй блок нужен для списка управленческих решений. Третий блок нужен для финансового разговора с заказчиком и PMO. Четвертый блок нужен для качества прогноза и долгосрочного контроля портфеля.

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
