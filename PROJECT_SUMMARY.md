## Назначение

MVP "AI Project Control Tower" показывает, как руководитель проектов банка может видеть состояние проектного портфеля на основе данных из нескольких источников: проектный контур, tasktracker, бюджет, risk register, коммуникации и ресурсный план.

## Текущая структура

- `backend/` — будущий backend API и текущий SQLAlchemy ORM-слой для демо-БД.
- `frontend/` — будущий web-интерфейс.
- `agents/` — будущие AI-агенты и сценарии анализа.
- `infra/` — инфраструктурные файлы и локальные volume-директории.
- `data/` — синтетические CSV-данные для демо.
- `docs/` — исходный контекст кейса и заметки от ментора.
- `docker-compose.yml` — общий compose-файл в корне проекта.

## Локальная инфраструктура

Сейчас в compose подключен только PostgreSQL:

- image: `postgres:16-alpine`
- database: `sdm_hack`
- port: `5432`
- data volume: `./infra/postgres/data`

`infra/postgres/data` игнорируется git, потому что там будут локальные файлы PostgreSQL. Таблицы создаются через ORM-модели в `backend/database/models.py`.

## Датасет

Данные в `data/` являются source-слоем. Платформа должна сама считать производные показатели:

- просрочки;
- блокировки;
- budget deviation;
- ROI;
- resource overload;
- communication delay;
- risk score;
- health score;
- event log изменений.

Дополнительные source-таблицы `dependencies.csv`, `decisions.csv` и `change_requests.csv` нужны для сценариев root cause analysis, decision assistant и weekly status generator.

`metrics_snapshots.csv` намеренно не считается исходной таблицей.

## Ветки

- `main` — базовая структура проекта.
- `dev` — рабочая ветка разработки.
- `playground` — ветка для тестов и экспериментов с датасетом.
