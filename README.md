# AI Project Control Tower

MVP для контроля портфеля банковских проектов. Система будет собирать данные из проектного контура, tasktracker, бюджета, risk register, коммуникаций и ресурсного плана, а затем считать проектные метрики и готовить объяснения для руководителя проекта.

## Архитектура

- `frontend/`: web-интерфейс.
- `backend/`: API, ORM-модели и бизнес-логика платформы.
- `agents/`: AI-агенты и сценарии анализа.
- `infra/`: локальная инфраструктура.
- `data/`: синтетические CSV-данные для демо.
- `docs/`: исходные материалы по кейсу.
- `docker-compose.yml`: общий compose-файл.

Сейчас в compose поднят PostgreSQL, а в `backend/database/` добавлен SQLAlchemy ORM-слой для создания таблиц демо-БД.

## Запуск

1. При необходимости переопределить параметры в `.env`.

2. Сгенерировать демо-данные:

```bash
python generate_demo_data.py
```

3. Поднять PostgreSQL:

```bash
docker compose up -d postgres
```

4. Создать ORM-таблицы вручную, если нужно только подготовить схему:

```bash
python -m backend.database.init_db --drop-existing
```

5. Загрузить CSV в БД. Скрипт по умолчанию пересоздаёт ORM-таблицы и загружает все демо-данные:

```bash
python load_demo_data_to_db.py
```

6. Запустить основной пайплайн:

```bash
python main.py
```

Основной пайплайн имитирует поток уведомлений по DOCX-файлам из `data/project_documents`.
Если для файла уже есть JSON в `data/per_file_json`, он превращается в событие
`docx_changed`; если JSON еще нет — в `docx_added`. Затем событие передается в основной
LangGraph workflow `agents/project_control_graph.py`.

Workflow выполняет цепочку:

1. `parse_docx` — запускает DOCX parsing agent и извлекает проектную JSON-схему;
2. `update_project` — обновляет выбранные поля проекта в таблице `projects`;
3. `monitor_project` — запускает LangGraph-мониторинг проекта и формирует метрики/алерты.

В боевом режиме источник события можно заменить на файловый watcher, webhook или очередь:
`docx_added` будет означать появление нового паспорта проекта, `docx_changed` — обновление
существующего паспорта. Логика внутри графа при этом остается той же.

Сначала проекты должны быть загружены из CSV, потому что DOCX-пайплайн не создает новые строки в `projects`, а только обновляет существующие проекты `P001`, `P002` и т.д.
Это важно: из DOCX берутся только поля ниже, а обязательные поля вроде `owner_name`, `status`, `priority`, `business_value` приходят из CSV.

Из DOCX в таблицу `projects` записываются только поля:

- `project_name` -> `projects.name`;
- `timeline.start_date` -> `projects.start_date`;
- `timeline.end_date` -> `projects.planned_end_date`;
- `goals` -> `projects.business_goal`;
- `results` -> `projects.expected_result`.

Остальные поля проекта (`owner_name`, `status`, `priority`, `business_value` и другие) остаются из CSV.

Результаты сохраняются в:

- `data/per_file_json/` — JSON после парсинга каждого DOCX;
- `data/batch_output.json` — общий результат пайплайна;
- `data/project_monitoring_output.json` — результат LangGraph-мониторинга.

7. Проверить статус:

```bash
docker compose ps
```

8. Остановить инфраструктуру:

```bash
docker compose down
```

## PostgreSQL

Параметры по умолчанию лежат в `.env`:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=sdm_hack
POSTGRES_USER=sdm_hack
POSTGRES_PASSWORD=sdm_hack_password
DATABASE_URL=postgresql+psycopg2://sdm_hack:sdm_hack_password@localhost:5432/sdm_hack
```

Локальные файлы PostgreSQL хранятся в `infra/postgres/data` и не коммитятся. ORM-модели лежат в `backend/database/models.py`, CLI создания схемы — в `backend/database/init_db.py`.

## Данные

CSV в `data/` пока являются демо-источником. Производные сущности не должны храниться как исходные данные:

- health score;
- risk level;
- overdue count;
- delay days;
- budget deviation;
- risk score;
- resource overload;
- communication delay;
- dependency risk count;
- event log изменений.

Эти значения должна считать платформа.

Дополнительные source-таблицы для сценариев РП:

- `dependencies.csv` — внешние и межкомандные зависимости проекта;
- `decisions.csv` — управленческие решения и их статус;
- `change_requests.csv` — изменения scope, бюджета и сроков.

Подробное описание всех таблиц см. в `DATA_DICTIONARY.md`.

## LangGraph-ядро мониторинга

Основной workflow цифрового руководителя лежит в `agents/project_control_graph.py`.
Он принимает событие по DOCX-файлу, запускает parsing agent, обновляет БД и передает проект
в мониторинг.

Отдельный граф мониторинга лежит в `agents/project_monitor_graph.py`.

Он строится вокруг существующей PostgreSQL-базы:

1. загружает проект и связанные сущности из `projects`, `tasks`, `milestones`, `risks`, `communications`, `dependencies`, `decisions`, `budgets`;
2. детерминированно считает базовые метрики;
3. классифицирует алерты.

Запуск для одного проекта:

```bash
python -m agents.project_monitor_graph P001
```

Запуск на конкретную дату:

```bash
python -m agents.project_monitor_graph P001 --as-of 2026-06-15
```

LLM в этот граф пока не встроена намеренно: сначала метрики и алерты считаются обычным кодом, а следующим шагом отдельный LangGraph-узел будет генерировать рекомендации, объяснять причины, готовить сообщение тимлиду или запускать human-in-the-loop подтверждение действий.
