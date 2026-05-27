# Архитектура `agents`

Код агентов собран в директории `agents/agents/<agent_name>/`. Внутри пакетов используется один принцип:
`agent.py` для входного класса, `prompts.py` для инструкций, `schemas.py` для контрактов, а для графов
добавляются `graph.py`, `state.py` и `nodes/`. По структуре сразу видно, где какая часть логики.

```text
agents/
  api/                 HTTP API сервиса агентов
  agents/              продуктовые агенты и графы
    control_event_simulation/
    internal_notifications/
    project_analysis/
    project_brief/
    project_control/
    project_monitor/
    project_parser/
    project_qa/
  domain/              чистые Pydantic-модели без LLM и I/O
  tools/               переиспользуемые инструменты агентов
    project_facts/     чтение project summary/problem context/RAG/budget
    runtime.py         адаптеры LangChain tools без зависимости от конкретного агента
  core/                общие утилиты без I/O и привязки к агентам
  infrastructure/      внешние адаптеры: LLM-провайдеры
```

Правило зависимостей:

```text
api -> agents/<agent_name> -> tools/core/domain/infrastructure
```

`backend` не импортирует агентские сервисы напрямую: ему передается структурный объект проекта через backend-протокол.
Скрипты и API импортируют публичные функции из пакетов `agents.agents.<agent_name>`.
Между API и агентом нет дополнительного слоя-обертки: все агентские входы лежат рядом
и называются по продуктовой роли.

Для крупного агента используем пакет, а не один файл:

```text
agents/<agent_name>/
  agent.py      публичный запуск и класс агента
  graph.py      сборка LangGraph
  state.py      состояние графа
  prompts.py    системные инструкции и skill-поведение
  schemas.py    Pydantic-контракты агента
  nodes/        узлы графа

tools/<tool_group>/
  schemas.py    Pydantic-контракты аргументов tools
  factory.py    LangChain/graph tool wrappers
  executor.py   I/O и вызовы backend/API
  formatting.py сжатие и нормализация tool outputs
```
