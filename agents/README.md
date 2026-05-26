# Архитектура `agents`

Слой `agents` разделен по ответственности, чтобы новые агенты не складывались в корень пакета.

```text
agents/
  api/                 HTTP API сервиса агентов
  domain/              чистые Pydantic-модели без LLM и I/O
  use_cases/           пользовательские сценарии: brief, Q&A
  workflows/           LangGraph orchestration: control, monitor
  services/            прикладные агенты и парсер документов
  infrastructure/      внешние адаптеры: LLM-провайдеры
  cli/                 локальные консольные запуски
```

Правило зависимостей:

```text
api -> use_cases/workflows -> services -> infrastructure
use_cases/workflows/services -> domain
```

`backend` не импортирует агентские сервисы напрямую: ему передается структурный объект проекта через backend-протокол.
Скрипты импортируют публичные сценарии из `agents.workflows`, `agents.use_cases` и `agents.services`.
Корень пакета не должен содержать новые агентские модули.
