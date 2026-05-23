# AI Project Control Tower

MVP для контроля портфеля банковских проектов. Система будет собирать данные из проектного контура, tasktracker, бюджета, risk register, коммуникаций и ресурсного плана, а затем считать проектные метрики и готовить объяснения для руководителя проекта.

## Архитектура

- `frontend/`: web-интерфейс.
- `backend/`: API, ORM-модели и бизнес-логика платформы.
- `agents/`: AI-агенты и сценарии анализа.
- `infra/`: локальная инфраструктура.
- `data/`: синтетические CSV-данные для демо.
- `docs/`: исходные материалы по кейсу.
- `scripts/`: утилиты для генерации и загрузки данных.
- `docker-compose.yml`: общий compose-файл.

Сейчас в compose подключены PostgreSQL, backend API и frontend. В `backend/app/database/` есть SQLAlchemy-модели и инициализация схемы. Загрузчик CSV в БД лежит в `scripts/`. В `backend/app/` лежит слоистая backend-архитектура. В `agents/` лежит тестовый LLM-агент для brief по project summary.

## Запуск

1. Создать локальный env-файл:

```bash
cp .env.example .env
```

2. Поднять PostgreSQL:

```bash
docker compose up -d postgres
```

3. Сгенерировать актуальные CSV:

```bash
python generate_demo_data.py
```

4. Создать таблицы:

```bash
python -m backend.app.database.init_db --drop-existing
```

5. Загрузить CSV в PostgreSQL:

```bash
python scripts/load_demo_data_to_db.py
```

6. Поднять backend API и frontend:

```bash
docker compose up -d backend frontend
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

11. Получить summary по одному проекту:

```bash
curl "http://localhost:8000/api/v1/summaries/projects/P001?as_of=2026-06-19"
```

12. Протестировать LLM-агента:

```bash
python -m agents.llm
```

13. Остановить инфраструктуру:

```bash
docker compose down
```

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
```

Локальные файлы PostgreSQL хранятся в `infra/postgres/data` и не коммитятся. Схема создается из SQLAlchemy-моделей в `backend/app/database/models.py`.

## Данные

CSV в `data/` пока являются демо-источником. Производные сущности не должны храниться как исходные данные:

- health score;
- risk level;
- overdue count;
- delay days;
- budget deviation;
- resource overload;
- журнал изменений.

Эти значения должна считать платформа.

Журнал изменений не сидится в демо-данных. Его должен формировать backend при изменениях через фронт или importer diff.

## Backend summary layer

Первый слой бизнес-логики лежит в `backend/app/`:

- `api/`: HTTP endpoints;
- `core/`: конфигурация приложения;
- `schemas/`: Pydantic-контракты для API, фронта и агентов;
- `services/`: чтение source facts и расчёт project summary;
- `utils/`: вспомогательные функции;
- `dependencies.py`: зависимости FastAPI;
- `main.py`: точка входа приложения.

Summary считает completion, blocked и overdue задачи, high risks, бюджетное отклонение, ROI, risk-adjusted ROI, коммуникационные задержки, перегруз ресурсов, рискованные зависимости, pending decisions, change requests, health score и risk level.

## Frontend

Минимальный frontend лежит в `frontend/`:

- React и Vite;
- TailwindCSS и daisyUI;
- проектный dashboard по endpoint `/api/v1/summaries/*`;
- выбор проекта из портфеля;
- вывод health score, зоны риска, бюджета, блокеров, рисков, коммуникаций и перегрузки ресурсов.
