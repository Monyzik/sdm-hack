# AI Project Control Tower

MVP для контроля портфеля банковских проектов. Система будет собирать данные из проектного контура, tasktracker, бюджета, risk register, коммуникаций и ресурсного плана, а затем считать проектные метрики и готовить объяснения для руководителя проекта.

## Архитектура

- `frontend/`: web-интерфейс.
- `backend/`: API и бизнес-логика платформы.
- `agents/`: AI-агенты и сценарии анализа.
- `infra/`: локальная инфраструктура.
- `data/`: синтетические CSV-данные для демо.
- `docs/`: исходные материалы по кейсу.
- `docker-compose.yml`: общий compose-файл.

Сейчас в compose поднят только PostgreSQL. Backend, frontend и agents пока оставлены пустыми директориями под будущую разработку.

## Запуск

1. Создать локальный env-файл:

```bash
cp .env.example .env
```

2. Поднять PostgreSQL:

```bash
docker compose up -d postgres
```

3. Проверить статус:

```bash
docker compose ps
```

4. Остановить инфраструктуру:

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
```

Локальные файлы PostgreSQL хранятся в `infra/postgres/data` и не коммитятся. SQL-таблицы и миграции пока не заведены: их должен добавить backend, когда появится модель хранения.

## Данные

CSV в `data/` пока являются демо-источником. Производные сущности не должны храниться как исходные данные:

- health score;
- risk level;
- overdue count;
- delay days;
- budget deviation;
- resource overload;
- event log изменений.

Эти значения должна считать платформа.
