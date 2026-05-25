# AI Project Control Tower

MVP для контроля портфеля банковских проектов. Система собирает данные из проектного контура, tasktracker, бюджета, risk register, коммуникаций и ресурсного плана, а затем считает проектные метрики и готовит объяснения для руководителя проекта.

## Архитектура

- `frontend/`: web-интерфейс на React, Vite, TailwindCSS и daisyUI.
- `backend/`: FastAPI, ORM-модели и бизнес-логика платформы.
- `backend/app/`: слоистая архитектура backend.
- `agents/`: AI-агенты, DOCX parser и LangGraph-сценарии анализа.
- `infra/`: локальная инфраструктура.
- `data/`: синтетические CSV-данные и demo inputs для агентов.
- `docs/`: исходные материалы по кейсу.
- `scripts/`: утилиты для генерации и загрузки данных.
- `docker-compose.yml`: общий compose-файл.

В compose подключены PostgreSQL, backend API, agents API и frontend. Схема БД создается из SQLAlchemy-моделей в `backend/app/database/`. CSV загружаются через `scripts/load_demo_data_to_db.py`.

## Запуск платформы

1. При необходимости переопределить параметры в `.env`.

```bash
cp .env.example .env
```

2. Сгенерировать актуальные CSV:

```bash
python generate_demo_data.py
```

3. Поднять PostgreSQL:

```bash
docker compose up -d postgres
```

4. Создать ORM-таблицы вручную, если нужно только подготовить схему:

```bash
python -m backend.app.database.init_db --drop-existing
```

5. Загрузить CSV в PostgreSQL:

```bash
python scripts/load_demo_data_to_db.py
```

6. Поднять backend API, agents API и frontend:

```bash
docker compose up -d backend agents frontend
```

7. Проверить статус:

```bash
docker compose ps
```

8. Проверить health endpoint:

```bash
curl http://localhost:8000/health
```

9. Открыть frontend:

```bash
http://localhost:5180
```

10. Получить portfolio summary:

```bash
curl "http://localhost:8000/api/v1/summaries/portfolio?as_of=2026-06-19"
```

11. Получить портфельный inbox изменений:

```bash
curl "http://localhost:8000/api/v1/summaries/portfolio/attention?as_of=2026-06-19&lookback_days=7"
```

12. Получить summary по одному проекту:

```bash
curl "http://localhost:8000/api/v1/summaries/projects/P001?as_of=2026-06-19"
```

13. Получить fact context для LLM:

```bash
curl "http://localhost:8000/api/v1/summaries/projects/P001/problem-context?as_of=2026-06-19&max_depth=2"
```

14. Протестировать LLM-агента для brief:

```bash
python -m agents.llm
```

15. Получить AI brief через agents API:

```bash
curl "http://localhost:8010/api/v1/agents/projects/P001/brief?as_of=2026-06-19&max_depth=2"
```

16. Остановить инфраструктуру:

```bash
docker compose down
```

## DOCX agent pipeline

Root `main.py` имитирует поток событий по DOCX-файлам из `data/project_documents`.

Если для файла уже есть JSON в `data/per_file_json`, событие считается `docx_changed`. Если JSON еще нет, событие считается `docx_added`. Затем событие передается в LangGraph workflow `agents/project_control_graph.py`.

`ProjectControlGraph` начинается с узла `route_event`. Он выбирает ветку обработки:

- `docx_added` / `docx_changed` -> `parse_docx` -> `update_project` -> `monitor_project`;
- `task_changed`, `risk_changed`, `budget_changed`, `dependency_changed`, `communication_changed`, `manual_monitoring_requested` -> сразу `monitor_project`.

Для DOCX-событий нужен `file_path`, для событий мониторинга нужен `project_id`.

Основные шаги DOCX-ветки:

1. `parse_docx`: запускает DOCX parsing agent и извлекает проектную JSON-схему.
2. `update_project`: обновляет выбранные поля проекта в таблице `projects`.
3. `monitor_project`: запускает мониторинг проекта и формирует метрики и алерты.

Сначала проекты должны быть загружены из CSV, потому что DOCX-пайплайн не создает новые строки в `projects`, а только обновляет существующие проекты `P001`, `P002` и т.д.

Из DOCX в таблицу `projects` записываются только поля:

- `project_name` -> `projects.name`;
- `timeline.start_date` -> `projects.start_date`;
- `timeline.end_date` -> `projects.planned_end_date`;
- `goals` -> `projects.business_goal`;
- `results` -> `projects.expected_result`.

Остальные поля проекта остаются из CSV.

Запуск пайплайна:

```bash
python main.py
```

Результаты сохраняются в:

- `data/per_file_json/`: JSON после парсинга каждого DOCX;
- `data/agents_json/batch_output.json`: общий результат пайплайна;
- `data/agents_json/project_monitoring_output.json`: результат мониторинга.

### Симуляция событий

Для локальной симуляции события можно описать в `data/control_events.jsonl`.
Каждая строка — отдельный JSON-объект:

```json
{"event_type":"docx_changed","file_path":"data/project_documents/project_summary_001.docx"}
{"event_type":"task_changed","project_id":"P001"}
{"event_type":"risk_changed","project_id":"P002"}
```

Запуск симуляции:

```bash
python scripts/simulate_control_events.py
```

Скрипт читает события из `data/control_events.jsonl`, отправляет каждое событие в
`ProjectControlGraph` и сохраняет результат в
`data/agents_json/control_event_simulation_output.json`.
Относительные `file_path` в JSONL считаются относительно корня проекта.

## PostgreSQL

Параметры по умолчанию лежат в `.env.example`:

```env
POSTGRES_DB=sdm_hack
POSTGRES_USER=sdm_hack
POSTGRES_PASSWORD=sdm_hack_password
POSTGRES_HOST=localhost
POSTGRES_INTERNAL_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql://sdm_hack:sdm_hack_password@localhost:5432/sdm_hack
DATABASE_URL_DOCKER=postgresql://sdm_hack:sdm_hack_password@postgres:5432/sdm_hack
BACKEND_PORT=8000
BACKEND_CORS_ORIGINS=http://localhost:5180,http://127.0.0.1:5180
FRONTEND_PORT=5180
VITE_API_URL=http://localhost:8000
VITE_AGENTS_API_URL=http://localhost:8010
AGENTS_PORT=8010
BACKEND_API_URL=http://backend:8000
AGENTS_CORS_ORIGINS=http://localhost:5180,http://127.0.0.1:5180
LOCAL_API_URL=http://localhost:8000
YANDEX_CLOUD_FOLDER=
YANDEX_CLOUD_API_KEY=
YANDEX_CLOUD_MODEL=qwen3.6-35b-a3b/latest
```

Локальные файлы PostgreSQL хранятся в `infra/postgres/data` и не коммитятся.

## Данные

CSV в `data/` являются demo source layer. Производные сущности не должны храниться как исходные данные:

- health score;
- risk level;
- overdue count;
- delay days;
- forecast total spent;
- budget deviation;
- risk score;
- resource overload;
- communication delay;
- dependency risk count;
- pending decision count;
- change request impact;
- metrics snapshots;
- журнал изменений.

Эти значения должна считать платформа.

Журнал изменений не сидится в демо-данных. Его должен формировать backend при изменениях через frontend или importer diff.

Подробное описание таблиц лежит в `DATA_DICTIONARY.md`.

## Backend summary layer

Первый слой бизнес-логики лежит в `backend/app/`:

- `api/`: HTTP endpoints;
- `core/`: конфигурация приложения;
- `schemas/`: Pydantic-контракты для API, фронта и агентов;
- `services/`: чтение source facts и расчет project summary;
- `utils/`: вспомогательные функции;
- `dependencies.py`: зависимости FastAPI;
- `main.py`: точка входа backend.

Summary считает completion, blocked и overdue задачи, high risks, расчетный forecast бюджета, бюджетное отклонение, ROI, risk-adjusted ROI, коммуникационные задержки, перегруз ресурсов, рискованные зависимости, pending decisions, change requests, health score и risk level.

Главный сценарий для руководителя проекта лежит в портфельном inbox:

```text
GET /api/v1/summaries/portfolio/attention
```

Он показывает, что изменилось за период по всем проектам: новые блокировки, сдвиги сроков, эскалации, открытые change requests, просроченные коммуникации и зависшие решения. Это основной слой для проблемы "сложно смотреть за изменениями нескольких проектов".

Внутренние уведомления, которые создает monitoring pipeline, доступны через endpoint:

```text
GET /api/v1/notifications
GET /api/v1/notifications?project_id=P001&unread_only=true
PATCH /api/v1/notifications/{notification_id}/read
```

Уведомления лежат в таблице `notifications`. Monitoring graph сохраняет их после `ProjectInternalNotificationAgent`, если `notification_draft.should_create=true`.

Если база уже была поднята до появления этой таблицы, создай недостающие ORM-таблицы без удаления данных:

```bash
python -m backend.app.database.init_db
```

Для LLM используется отдельный fact endpoint:

```text
GET /api/v1/summaries/projects/{project_id}/problem-context
```

Он не возвращает готовый executive summary или ключевые выводы. В ответе только факты: проблемные задачи, граф зависимостей вокруг них, связанные риски, коммуникации, решения, бюджет и ресурсы. Выводы и рекомендации формирует агент.

Agents API отдает результат агента для frontend:

```text
GET /api/v1/agents/projects/{project_id}/brief
```

Endpoint забирает `problem-context` из backend, вызывает LLM через Yandex provider, валидирует ответ через Pydantic и возвращает строгий JSON. Для работы нужны `YANDEX_CLOUD_FOLDER`, `YANDEX_CLOUD_API_KEY` и `YANDEX_CLOUD_MODEL` в `.env`. `YANDEX_CLOUD_MODEL` можно задать коротко, например `qwen3.6-35b-a3b/latest`, или полным URI `gpt://folder_id/qwen3.6-35b-a3b/latest`.

## LangGraph monitoring

Основной workflow цифрового руководителя лежит в `agents/project_control_graph.py`. Отдельный граф мониторинга лежит в `agents/project_monitor_graph.py`.

1. загружает проект и связанные сущности из `projects`, `tasks`, `milestones`, `risks`, `communications`, `dependencies`, `decisions`, `budgets`;
2. детерминированно считает базовые метрики;
3. классифицирует алерты;
4. запускает `ProjectAnalystAgent`, который по метрикам и алертам готовит управленческую сводку, причины проблем, рекомендации, вопросы тимлиду и флаг эскалации;
5. запускает `ProjectInternalNotificationAgent`, который готовит `notification_draft` для внутреннего push-уведомления в сервисе;
6. сохраняет уведомление в `notifications`, если draft требует создать уведомление.


В основном пайплайне этот граф вызывает главный оркестратор
`agents/project_control_graph.py`, а полный запуск проекта остается через `python main.py`.

Для изолированной проверки мониторинга одного проекта можно запустить подграф напрямую:

```bash
python -m agents.project_monitor_graph P001
```

Запуск на конкретную дату:

```bash
python -m agents.project_monitor_graph P001 --as-of 2026-06-15
```

Базовые метрики и алерты считаются обычным кодом. LLM-узлы получают уже посчитанный контекст и формируют управленческую сводку, вопросы, рекомендации и draft уведомления.

## Frontend

Минимальный frontend лежит в `frontend/`:

- React и Vite;
- TailwindCSS и daisyUI;
- проектный dashboard по endpoint `/api/v1/summaries/*`;
- вкладка уведомлений по endpoint `/api/v1/notifications`;
- выбор проекта из портфеля;
- вывод health score, зоны риска, бюджета, блокеров, рисков, коммуникаций и перегрузки ресурсов.
