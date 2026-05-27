<p align="center">
  <img src="https://raw.githubusercontent.com/Monyzik/sdm-hack/main/frontend/public/favicon.svg" width="64" height="64" alt="AI Project Control Tower" onerror="this.style.display='none'"/>
  <h1 align="center">AI Project Control Tower</h1>
  <p align="center"><strong>Платформа управленческого контроля проектов с AI-агентами, RAG и мониторингом в реальном времени</strong></p>
  <p align="center">Собирает разрозненные данные проекта → считает health-метрики → объясняет причины → предлагает решения → проверяется по источникам</p>
</p>

<p align="center">
  <!-- Status -->
  <a href="https://github.com/Monyzik/sdm-hack"><img src="https://img.shields.io/github/last-commit/Monyzik/sdm-hack?style=for-the-badge&color=0ea5e9" alt="last commit"/></a>
  <a href="https://github.com/Monyzik/sdm-hack"><img src="https://img.shields.io/github/stars/Monyzik/sdm-hack?style=for-the-badge&logo=github&color=0ea5e9" alt="stars"/></a>
  <a href="https://github.com/Monyzik/sdm-hack/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-for-the-badge&color=10b981" alt="license"/></a>
  <a href="https://github.com/Monyzik/sdm-hack/actions"><img src="https://img.shields.io/badge/CI-passing-for-the-badge?logo=githubactions&logoColor=white&color=10b981" alt="ci"/></a>
</p>

<p align="center">
  <!-- Stack badges -->
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React"/>
  <img src="https://img.shields.io/badge/TypeScript-5.7-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TS"/>
  <img src="https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite&logoColor=white" alt="Vite"/>
  <img src="https://img.shields.io/badge/Tailwind-3.4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white" alt="Tailwind"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/PostgreSQL-16 + pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="Postgres"/>
  <img src="https://img.shields.io/badge/LangGraph-orchestration-1C3C3C?style=flat-square&logo=langchain&logoColor=white" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"/>
</p>

<p align="center">
  <a href="https://skillicons.dev"><img src="https://skillicons.dev/icons?i=react,ts,vite,tailwind,python,fastapi,postgres,docker&perline=8" alt="stack icons"/></a>
</p>

<p align="center">
  <a href="#-быстрый-старт-за-5-минут">Быстрый старт</a> •
  <a href="#-архитектура">Архитектура</a> •
  <a href="#-демо">Демо</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-ai-агенты">Агенты</a> •
  <a href="#-метрики">Метрики</a>
</p>

---

## 📑 Оглавление

- [Зачем это нужно](#-зачем-это-нужно)
- [Демо](#-демо)
- [Возможности](#-возможности)
- [Архитектура](#-архитектура)
- [Технологический стек](#-технологический-стек)
- [Быстрый старт за 5 минут](#-быстрый-старт-за-5-минут)
- [Переменные окружения](#-переменные-окружения)
- [API Reference](#-api-reference)
- [AI-агенты](#-ai-агенты)
- [Метрики](#-метрики)
- [Структура проекта](#-структура-проекта)
- [Данные и DOCX pipeline](#-данные-и-docx-pipeline)
- [Скрипты и утилиты](#-скрипты-и-утилиты)
- [Разработка](#-разработка)
- [Деплой](#-деплой)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [Лицензия](#-лицензия)

---

## 🎯 Зачем это нужно

> В проектном управлении проблема **никогда не лежит в одном месте**. Задача заблокирована в Jira, причина — в переписке, влияние на бюджет — в таблице, а цели проекта — в `DOCX`. Руководитель тратит 80% времени на сборку контекста, а не на решение.

**AI Project Control Tower** закрывает этот разрыв:

| Было | Стало |
|------|-------|
| Ручная сборка статусов по 5 источникам | Авто-сводка портфеля на дату `as_of` |
| «Проект красный — непонятно почему» | Диагноз + узкое место + источник факта |
| Решения зависают без владельца | Inbox уведомлений с триггером и проектом |
| DOCX с произвольным шаблоном | Парсинг целей/сроков/результатов → обновление карточки |
| Поиск по чатам/комментариям вручную | RAG-поиск с подсветкой источников ответа |

**Для кого:**

- **Руководитель проекта** — статус, блокеры, критический путь, ближайшие действия
- **Портфельный менеджер** — какие проекты требуют внимания сегодня
- **Тимлид / Владелец направления** — перегруз команды, открытые решения, зависимости
- **Управляющий комитет** — сжатая выжимка с вариантами и бизнес-влиянием

---

## 🖥️ Демо

| Портфель | Командный центр проекта | AI-чат с источниками |
|----------|:-----------------------:|:--------------------:|
| health score, risk-зоны, топ-сигналы | метрики, риски, зависимости, бюджет, загрузка | вопросы + расчет + RAG-подсветка |
| `http://localhost:5180` | `http://localhost:5180/projects/{id}` | модалка **Источники** |

> **Live health-checks:** `http://localhost:8000/health` (backend) · `http://localhost:8010/health` (agents)

<details>
<summary>📸 Скриншоты (замени на свои)</summary>

```
docs/screenshots/portfolio.png
docs/screenshots/project.png
docs/screenshots/chat.png
docs/screenshots/notifications.png
```

Рекомендуемый размер: `1600×900`, формат `webp`/`png`, без чувствительных данных.

</details>

---

## ✨ Возможности

### 📊 Портфельный обзор (`as_of` — срез на дату)

- `health score` (0–100) и `risk_level` (`green`/`yellow`/`red`)
- Готовность, просрочки, блокеры, бюджетное отклонение, перегруз ресурсов
- Топ-сигналы и сортировка «кто горит сильнее»
- Вкладка **Требуют внимания** (`lookback_days` 1–30)

### 🏗️ Командный центр проекта

Ключевые метрики · проблемные задачи · риски · зависимости + критический путь · коммуникации с задержками · ожидающие решения · CR · загрузка ресурсов · динамика по датам.

### 🧠 Управленческая сводка от агента `project_brief`

Готовый материал для решения, а не «текст ради текста»:

`статус` → `главный вопрос` → `диагноз` → `узкое место` → `варианты` → `бизнес-влияние` → `следующие действия` → `черновик сообщения` → `правило проверки`

### 💬 Вопросы к проекту (RAG + tools)

```
Почему задача заблокирована?
Что обсуждали по безопасности?
Кто просил согласование?
Какие решения ожидают владельца?
Какая стоимость сдвига на 10 дней?
Что на критическом пути?
```

Агент использует `search`/`calc` + **project trace**: комментарии, сообщения, решения, риски, CR, история изменений. Каждый факт — с модалкой источников.

### 🔔 Уведомления (Inbox РП)

События: новые блокеры · сдвиги сроков · рост риска · бюджетные отклонения · просроченные коммуникации · зависшие решения. Привязка `project × as_of × trigger`.

### 🔄 Симуляция событий

Демо-поток из `data/demo/control_events.jsonl` (задачи, риски, бюджет, зависимости, коммуникации, DOCX). Показывает сценарий **«не дашборд, а мониторинг изменений»**.

### 📄 Обработка DOCX без шаблона

Извлечение: цели · ожидаемые результаты · сроки · название проекта. Авто-обновление карточки проекта в БД.

---

## 🏛️ Архитектура

```mermaid
flowchart TB
    subgraph Client[Frontend — React 19 + Vite 6]
      UI[Portfolio / Project / Chat / Inbox / Charts]
    end

    subgraph Backend[Backend — FastAPI + SQLAlchemy]
      API[/REST /api/v1/summaries + /notifications/]
      METRICS[metrics.py — derived layer]
      RETRIEVAL[RAG retrieval + pgvector]
      DB[(PostgreSQL 16 + pgvector)]
    end

    subgraph Agents[Agents — FastAPI + LangGraph]
      BRIEF[project_brief]
      QA[project_qa]
      MONITOR[project_monitor]
      CONTROL[project_control]
      NOTIF[internal_notifications]
      PARSER[project_parser DOCX]
      SIM[control_event_simulation]
    end

    UI -- "VITE_API_URL / VITE_AGENTS_API_URL" --> API
    UI -- "/agents" --> Agents
    Agents -- "BACKEND_API_URL" --> API
    API --> METRICS --> DB
    API --> RETRIEVAL --> DB
    CONTROL --> PARSER --> MONITOR --> DB
    SIM --> CONTROL

    style Backend fill:#0ea5e933,stroke:#0ea5e9
    style Agents fill:#10b98133,stroke:#10b981
    style Client fill:#6366f133,stroke:#6366f1
```

**Поток DOCX:** `data/documents/*.docx` → `project_parser` → `outputs/per_file_json/` → `project_control` graph → `project_monitor` → `outputs/agents_json/batch_output.json` + обновление `projects` в БД.

**Поток чата:** `POST /agents/projects/{id}/ask` → `project_qa` (LangGraph + tools: search, calc, retrieval) → ответ с `sources`.

Подробнее: [`docs/Задание.txt`](docs/Задание.txt) · [`METRICS_PROTOCOL.md`](METRICS_PROTOCOL.md)

---

## 🧰 Технологический стек

| Слой | Технологии | Назначение |
|------|------------|------------|
| **Frontend** | <img src="https://skillicons.dev/icons?i=react" width="16"/> React 19 · <img src="https://skillicons.dev/icons?i=ts" width="16"/> TypeScript 5.7 · Vite 6 · Tailwind 3.4 · TanStack Query 5 · lucide-react | SPA: портфель, проект, чат, inbox, графики |
| **Backend** | <img src="https://skillicons.dev/icons?i=python" width="16"/> Python 3.11 · FastAPI · SQLAlchemy 2 · Pydantic 2 · asyncpg | REST API, расчет метрик, RAG-индексация |
| **Agents** | LangGraph · LangChain Core · Pydantic contracts | Оркестрация AI-графов, чат, сводки, мониторинг |
| **Storage** | <img src="https://skillicons.dev/icons?i=postgres" width="16"/> PostgreSQL 16 + `pgvector/pgvector:pg16` | Проекты, задачи, риски, эмбеддинги |
| **LLM / Embeddings** | YandexGPT-совместимый провайдер · `text-search-doc/query` · OpenAI / Polza (опционально) | Генерация сводок, чат, векторный поиск |
| **Runtime** | <img src="https://skillicons.dev/icons?i=docker" width="16"/> Docker Compose | Локальный и продовый запуск |

Версии зафиксированы в [`frontend/package.json`](frontend/package.json) · [`requirements.txt`](requirements.txt) · [`docker-compose.yml`](docker-compose.yml:1)

---

## 🚀 Быстрый старт за 5 минут

### Пред-требования

- Docker + Docker Compose
- Python 3.11+ (для скриптов вне Docker)
- Node 22+ (для локальной разработки фронтенда)

### 1) Клонирование и окружение

```bash
git clone https://github.com/Monyzik/sdm-hack.git
cd sdm-hack
cp .env.example .env
# заполни LLM ключи: YANDEX_* или POLZA_*/OPENAI_*
```

### 2) Docker — полный стек (рекомендуется)

```bash
# только БД
docker compose up -d postgres

# создание таблиц
python -m sdm.backend.database.init_db --drop-existing

# демо-данные
python scripts/load_demo_data_to_db.py

# backend + agents + frontend
docker compose up -d backend agents frontend

# проверка
curl http://localhost:8000/health
curl http://localhost:8010/health
open http://localhost:5180
```

### 3) Локальная разработка (без Docker для фронта)

```bash
# backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn sdm.backend.main:app --reload --port 8000

# agents (в другом терминале, тот же venv)
uvicorn sdm.agents.api:app --reload --port 8010

# frontend (в третьем терминале)
cd frontend && npm ci && npm run dev
# → http://localhost:5180  (прокси /api → :8000, /agents → :8010)
```

### Порты по умолчанию

| Сервис | URL | Переменная |
|--------|-----|------------|
| Frontend | `http://localhost:5180` | `FRONTEND_PORT` |
| Backend | `http://localhost:8000` | `BACKEND_PORT` |
| Agents | `http://localhost:8010` | `AGENTS_PORT` |
| Postgres | `localhost:5432` | `POSTGRES_PORT` |

---

## 🔧 Переменные окружения

Все переменные — в [`.env.example`](.env.example). Ключевые:

| Переменная | Обязат. | По умолчанию | Описание |
|------------|:-------:|--------------|----------|
| `LLM_PROVIDER` | — | `yandex` | `yandex` \| `openai` \| `polza` |
| `YANDEX_CLOUD_FOLDER` | * | — | Folder ID для YandexGPT |
| `YANDEX_CLOUD_API_KEY` | * | — | API-key Yandex Cloud |
| `YANDEX_CLOUD_MODEL` | — | `qwen3.6-35b-a3b/latest` | Модель генерации |
| `YANDEX_EMBEDDING_DOC_MODEL` | — | `text-search-doc/latest` | Эмбеддинги документов |
| `YANDEX_EMBEDDING_QUERY_MODEL` | — | `text-search-query/latest` | Эмбеддинги запросов |
| `POLZA_API_KEY` / `OPENAI_API_KEY` | * | — | Ключ для Polza/OpenAI-совместимого провайдера |
| `POLZA_BASE_URL` / `OPENAI_BASE_URL` | — | `https://polza.ai/api/v1` | Base URL |
| `DATABASE_URL` | — | `postgresql://sdm_hack:sdm_hack_password@localhost:5432/sdm_hack` | DSN с хоста |
| `DATABASE_URL_DOCKER` | — | `postgresql://...@postgres:5432/sdm_hack` | DSN из Docker |
| `BACKEND_CORS_ORIGINS` | — | `http://localhost:5180,...` | CORS для backend |
| `AGENTS_CORS_ORIGINS` | — | `http://localhost:5180,...` | CORS для agents |
| `VITE_API_URL` | — | `/api` | URL backend для фронта |
| `VITE_AGENTS_API_URL` | — | `/agents` | URL agents для фронта |
| `AS_OF_DATE` | — | `2026-06-19` | Дата среза для `scripts/run_docx_batch.py` |

> `*` — обязательна для выбранного `LLM_PROVIDER`. Без LLM стек поднимается, но `brief`/`ask` вернут `502`.

---

## 📡 API Reference

Базовый префикс: `/api/v1` (дублируется как `/api/api/v1` для совместимости с прокси).

### Summaries

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/summaries/portfolio?as_of=2026-06-19` | Портфель на дату: health, зоны, сигналы |
| `GET` | `/api/v1/summaries/portfolio/attention?as_of=&lookback_days=7` | Проекты, требующие внимания |
| `GET` | `/api/v1/summaries/projects/{project_id}?as_of=` | Полная сводка проекта |
| `GET` | `/api/v1/summaries/projects/{project_id}/problem-context` | Контекст проблемы (блокеры, риски, зависимости) |
| `GET` | `/api/v1/summaries/projects/{project_id}/retrieval-context` | RAG-контекст проекта |
| `GET` | `/api/v1/summaries/projects/{project_id}/trends?days=30` | Динамика метрик |

### Notifications

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/notifications?project_id=&unread_only=&limit=` | Лента уведомлений |
| `PATCH` | `/api/v1/notifications/{notification_id}/read` | Пометить прочитанным |

### Agents

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/agents/projects/{project_id}/brief?as_of=&max_depth=2` | Управленческая сводка (`ProjectManagerBrief`) |
| `POST` | `/api/v1/agents/projects/{project_id}/ask` | Вопрос к проекту (RAG + tools, с `sources`) |
| `POST` | `/api/v1/agents/control-events/simulation` | Запуск симуляции событий |
| `GET` | `/api/v1/agents/control-events/simulation/{job_id}` | Статус симуляции |
| `DELETE` | `/api/v1/agents/control-events/simulation` | Очистка симуляции |
| `GET` | `/api/v1/agents/projects/{project_id}/docx/preview` | Превью обновления из DOCX |
| `POST` | `/api/v1/agents/projects/{project_id}/docx/apply` | Применение DOCX-обновления |

**Health:** `GET /health` на `:8000` и `:8010`

Пример:

```bash
curl "http://localhost:8000/api/v1/summaries/portfolio?as_of=2026-06-19" | jq
curl -X POST "http://localhost:8010/api/v1/agents/projects/prj-001/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"Почему задача заблокирована?","as_of":"2026-06-19"}' | jq
```

---

## 🤖 AI-агенты

| Агент | Модуль | Задача |
|-------|--------|--------|
| `project_brief` | [`sdm/agents/project_brief`](sdm/agents/project_brief) | Управленческая сводка: статус → диагноз → варианты → действия |
| `project_qa` | [`sdm/agents/project_qa`](sdm/agents/project_qa) | Чат по фактам/расчетам/истории с инструментами и источниками |
| `project_monitor` | [`sdm/agents/project_monitor`](sdm/agents/project_monitor) | Мониторинг метрик и генерация алертов |
| `project_control` | [`sdm/agents/project_control`](sdm/agents/project_control) | Маршрутизация событий управления (LangGraph) |
| `internal_notifications` | [`sdm/agents/internal_notifications`](sdm/agents/internal_notifications) | Генерация inbox-уведомлений |
| `project_parser` | [`sdm/agents/project_parser`](sdm/agents/project_parser) | Извлечение полей из DOCX без шаблона |
| `project_analysis` | [`sdm/agents/project_analysis`](sdm/agents/project_analysis) | Аналитическая сводка состояния |
| `control_event_simulation` | [`sdm/agents/control_event_simulation`](sdm/agents/control_event_simulation) | Демо-поток событий |

Внутри пакета агента один принцип: `agent.py` — входной класс, `prompts.py` — инструкции, `schemas.py` — контракты, для графов добавляются `graph.py`, `state.py` и `nodes/`.

Граф DOCX: [`scripts/run_docx_batch.py`](scripts/run_docx_batch.py) → `build_project_control_graph(session_factory)` → `project_parser` → `project_control` → `project_monitor`.

---

## 📐 Метрики

Все производные метрики **считаются**, а не хранятся. Формулы — в [`sdm/backend/services/metrics.py`](sdm/backend/services/metrics.py), протокол — в [`METRICS_PROTOCOL.md`](METRICS_PROTOCOL.md).

| Метрика | Формула (упрощенно) | Сигнал |
|---------|---------------------|--------|
| `project_health_score` | `100 − штрафы(просрочки, блокеры, бюджет, риски, перегруз, коммуникации, зависимости, решения, CR)` | Сортировка портфеля |
| `risk_level` | `red ≤55` · `yellow ≤75` · `green >75` | Зона внимания |
| `completion_percent` | `done / total ×100` | Прогресс (только в связке с блокерами) |
| `overdue_tasks_count` | `planned_due_date < as_of` | Накопленное отставание |
| `blocked_tasks_count` | `is_blocked` / `Blocked` | Где команда стоит |
| `budget_deviation_percent` | `(forecast − planned)/planned×100` | Ожидаемый перерасход |
| `resource_overload_percent` | `max(нагрузка − емкость)` | Узкое место |
| `max_communication_delay_days` | `max(просрочка ответа)` | Тормозящие согласования |

> Правило чтения: `risk_level` + `health_score` → «насколько плохо», `key_signals` → «почему», `blocked/dependencies/communications` → «кто блокирует», `budget/CR/decisions` → «какой impact и решение».

---

## 📁 Структура проекта

```
sdm_hack/
├── frontend/                 # React + Vite + Tailwind — портфель, проект, чат, inbox
│   ├── src/features/         # portfolio / project / chat / notifications / tasks
│   ├── src/api/              # клиенты к /api и /agents
│   └── vite.config.ts        # прокси /api → :8000, /agents → :8010
├── sdm/                      # единый Python-пакет: backend + agents
│   ├── backend/              # FastAPI — REST, метрики, RAG, БД
│   │   ├── api/              # summaries, notifications
│   │   ├── services/         # metrics, project_summary_*, retrieval, yandex_embeddings
│   │   ├── database/         # models, init_db, session (asyncpg + SQLAlchemy)
│   │   ├── schemas/          # Pydantic-контракты
│   │   └── main.py           # entrypoint :8000
│   └── agents/               # FastAPI + LangGraph — 8 агентов
│       ├── project_brief/ … project_qa/ … control_event_simulation/
│       ├── tools/            # project_facts + runtime-адаптеры LangChain tools
│       ├── llm.py            # LLM-адаптеры провайдеров (yandex / openai / polza)
│       ├── text.py           # общие утилиты текста
│       └── api.py            # entrypoint :8010 (/health, /brief, /ask, /simulation, /docx/*)
├── data/                     # только входные данные
│   ├── demo/                 # синтетические CSV + control_events.jsonl
│   └── documents/            # исходные DOCX (не трекаются)
├── outputs/                  # всё сгенерированное: agents_json, per_file_json
├── scripts/                  # run_docx_batch, load_demo_data_to_db, simulate_control_events, generate_demo_data
├── infra/postgres/           # init-скрипты pgvector (данные БД — в named volume)
├── docs/                     # задание, метрики, скриншоты
├── backend.Dockerfile        # образ backend (контекст — корень репо)
├── agents.Dockerfile         # образ agents (контекст — корень репо)
├── docker-compose.yml        # postgres + backend + agents + frontend
└── .env.example              # все переменные окружения
```

---

## 📦 Данные и DOCX pipeline

**Демо-данные (CSV):** `projects`, `tasks`, `task_history`, `task_comments`, `milestones`, `risks`, `communications`, `messages`, `dependencies`, `decisions`, `change_requests`, `budgets`, `resources`, `allocations`.

**Симуляция событий:**

```bash
# файл с событиями
cat data/demo/control_events.jsonl

# запуск через API (асинхронная job-модель)
curl -X POST http://localhost:8010/api/v1/agents/control-events/simulation | jq

# или напрямую скриптом
python scripts/simulate_control_events.py
# → outputs/agents_json/control_event_simulation_output.json
```

**DOCX pipeline (без шаблона):**

```bash
# обработка всех DOCX из data/documents/
python scripts/run_docx_batch.py
AS_OF_DATE=2026-06-19 python scripts/run_docx_batch.py

# результаты
ls outputs/per_file_json/                          # по файлам
cat outputs/agents_json/batch_output.json          # общий
cat outputs/agents_json/project_monitoring_output.json  # мониторинг
```

---

## 🛠️ Скрипты и утилиты

| Команда | Что делает |
|---------|------------|
| `python -m sdm.backend.database.init_db --drop-existing` | Создание таблиц (с пересозданием) |
| `python scripts/load_demo_data_to_db.py` | Загрузка CSV → Postgres (+ эмбеддинги при наличии ключей) |
| `python scripts/generate_demo_data.py` | Генерация синтетики |
| `python scripts/simulate_control_events.py` | Прогон `control_events.jsonl` |
| `python scripts/run_docx_batch.py` | DOCX → JSON → мониторинг |
| `cd frontend && npm run lint` / `npm run format:check` | Линт и проверка форматирования |
| `docker compose up -d --build` | Пересборка всех сервисов |

---

## 👨‍💻 Разработка

```bash
# формат и линтинг фронта
cd frontend
npm run lint
npm run format

# проверки бэкенда (если настроены)
ruff check sdm/
mypy sdm/

# тесты (при наличии)
pytest
```

**Соглашения:**

- Метрики — только через `sdm/backend/services/metrics.py`, не дублировать формулы в агентах
- Pydantic-контракты — единый источник типов для API и LLM
- `as_of` — обязательный параметр для всех временных срезов
- Ответы агента — всегда с `sources` для проверки

---

## 🚢 Деплой

**Docker Compose (прод):**

```bash
cp .env.example .env
# заполни: YANDEX_*/POLZA_*, DATABASE_URL_DOCKER, BACKEND_CORS_ORIGINS, AGENTS_CORS_ORIGINS
docker compose up -d --build
docker compose ps
docker compose logs -f backend agents
```

**Переменные для продакшена:** вынеси `POSTGRES_PASSWORD`, `YANDEX_CLOUD_API_KEY`, `POLZA_API_KEY` в secrets (Vault / SOPS / env-file с `chmod 600`). Не коммить `.env`.

**Health:** добавь в оркестратор проверки `GET /health` на `8000` и `8010` с `interval: 10s`.

---

## 🗺️ Roadmap

- [ ] SSO / RBAC (PM / PMO / Steering)
- [ ] Веб-сокеты для live-уведомлений
- [ ] Экспорт сводки в PDF / DOCX
- [ ] Интеграция с Jira / YouTrack / Confluence
- [ ] Планировщик симуляций и cron-мониторинг
- [ ] E2E-тесты (Playwright) и API-контрактные тесты

---

## 🤝 Contributing

PR приветствуются. Для локальной проверки перед PR:

```bash
docker compose up -d postgres
python -m sdm.backend.database.init_db --drop-existing
python scripts/load_demo_data_to_db.py
docker compose up -d backend agents frontend
curl -fsS http://localhost:8000/health && curl -fsS http://localhost:8010/health
cd frontend && npm run lint && npm run format:check
```

Вопросы и баги — в [Issues](https://github.com/Monyzik/sdm-hack/issues).

---

## 📄 Лицензия

MIT — см. [LICENSE](LICENSE) (если файла нет — считается MIT по репозиторию).

---

<p align="center">
  <strong>AI Project Control Tower</strong> — от «проект красный» → к «понятно, кто и что делает, и на каких фактах».<br/>
  <sub>Built with ❤️ for project managers who ship.</sub>
</p>

<p align="center">
  <a href="https://github.com/Monyzik/sdm-hack">⭐ Поставь звезду</a> ·
  <a href="https://github.com/Monyzik/sdm-hack/issues">🐛 Сообщить о баге</a> ·
  <a href="https://github.com/Monyzik/sdm-hack/discussions">💬 Обсудить</a>
</p>
