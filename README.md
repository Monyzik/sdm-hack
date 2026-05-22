# AI Project Control Tower demo dataset

Синтетический демо-датасет для MVP системы контроля банковских проектов. Данные имитируют выгрузки из проектного контура, tasktracker, бюджета, карты рисков, коммуникаций и ресурсного планирования.

## Запуск

```bash
python generate_demo_data.py
```

Скрипт использует Python 3.11+, `pandas` и фиксированный `random.seed(42)`. CSV-файлы сохраняются в `./data`.

Если в окружении нет `pandas`:

```bash
python -m pip install pandas
```

## Таблицы-источники

- `projects.csv` — портфель из 5 банковских проектов, текущий статус `green/yellow/red`, владелец, цель, ожидаемый результат и бизнес-ценность.
- `tasks.csv` — 130 задач из tasktracker. Это аналог выгрузки из Jira/Сферы: статус, приоритет, исполнитель, due date, факт завершения, оценки, spent hours, blocked-флаг и причина блокировки.
- `milestones.csv` — этапы проектов, плановые и фактические даты, статус этапа и ответственная команда.
- `budgets.csv` — бюджетный план, факт, прогноз, ожидаемый экономический эффект, Cost of Delay за день.
- `budget_items.csv` — детализация бюджета по статьям: трудозатраты, инфраструктура, лицензии, вендоры, аудит, данные, обучение и резерв. Суммы по статьям сходятся с `budgets.csv`.
- `risks.csv` — карта рисков с типом, probability, impact, владельцем, mitigation plan и ссылкой на задачу. `risk_score` не хранится, платформа считает его как `probability * impact`.
- `communications.csv` — карта коммуникаций между командами, каналы, даты последнего сообщения, ожидаемые ответы, статус и ссылки на задачи. Просрочку считает платформа по датам.
- `resources.csv` — справочник участников, ролей, команд, доступной недельной емкости и ставки.
- `capacity_plan.csv` — выгрузка из PMO capacity plan: кто на какой проект выделен, на какой период, сколько часов в неделю было запланировано и сколько фактически тратится. Процент загрузки не хранится, его считает платформа.

`metrics_snapshots.csv` и `project_events.csv` намеренно не генерируются. Health Score, Risk Level, overdue count, delay days, budget deviation, resource overload, dependency risk count и event log должны быть результатом расчета платформы, а не частью исходной демо-БД.

## Отслеживаемые сигналы

- Просроченные задачи: `tasks.status != Done` и `planned_due_date < current_date`.
- Blocked-задачи: `tasks.is_blocked = true`.
- Задержка этапа: разница между `planned_end_date` и `actual_end_date`, либо статус `Delayed`/`At Risk`.
- Risk score: `risks.probability * risks.impact`.
- Бюджетное отклонение: `(forecast_total_spent - planned_budget) / planned_budget`.
- Драйверы перерасхода: сравнение `budget_items.forecast_amount` с `budget_items.planned_amount` по категориям.
- ROI: `(expected_economic_effect - forecast_total_spent) / forecast_total_spent`.
- Risk-adjusted ROI можно считать через дисконтирование эффекта на открытые high-risk риски. Для P001 уже есть отрицательный ROI: эффект 57 млн RUB против прогноза затрат 62 млн RUB.
- Cost of Delay по проекту из `budgets.csv`. Изменение Cost of Delay платформа должна находить сравнением предыдущей и текущей выгрузки.
- Resource overload: сумма `actual_hours_per_week` по ресурсу относительно `available_hours_per_week`. Например, backend `R003` загружен на 145%.
- Communication delay: просрочка ожидаемых ответов между командами.
- Dependency risk: high-risk риски типов `Dependency`, `Integration`, `Security`, `Vendor`.
- Health Score и Risk Level — агрегированные показатели, которые должна считать платформа поверх этих сигналов.
- Event log — результат сравнения двух состояний данных. Например, если в новой выгрузке задача стала blocked или milestone получил новую дату, платформа должна сама создать событие.

## Демо-сценарии

1. P001 “Скоринговый модуль МСБ” деградирует из yellow в red.
   Security review сдвигается с 2026-06-12 на 2026-06-26, задача `SMB-SCR-001` становится blocked, прогноз бюджета растет с 54 млн до 62 млн RUB, Cost of Delay растет с 850 тыс. до 1,25 млн RUB в день, backend перегружается до 145%. Платформа должна пересчитать Health Score и перевести проект в `red`.
   Drill-down по `budget_items.csv` показывает, что перерасход идет не только из-за труда команды, но и из-за Security review, инфраструктуры, model registry и интеграционных доработок.

2. P002 “Антифрод real-time” показывает красный проект с интеграционной задержкой.
   Основные причины: перенос окна подключения процессинга, latency выше целевого лимита, задержки compliance-коммуникаций и высокий dependency risk.

3. P003 “Мобильный банк 2.0” служит healthy baseline.
   У проекта мало blocked/overdue задач, умеренная загрузка ресурсов, низкие риски и стабильный `green` статус.

4. P004 “Платёжный gateway” показывает yellow-проект с vendor и PCI DSS рисками.
   Есть задержка сертификатов СБП, блокировка задачи, рост forecast_total_spent и перегрузка backend.

5. Портфельный сценарий по ресурсам.
   Можно агрегировать `capacity_plan.csv` по `resource_id` и показать, что одни и те же backend/security специалисты распределены между critical-проектами выше 100%, что объясняет просадки Health Score.

Данные рассчитаны так, чтобы AI-агенты могли строить объяснение не из сырых документов, а из summary и метрик поверх этих таблиц.
