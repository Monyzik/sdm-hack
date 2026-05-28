from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import Field

from ..base import NoArgs, ToolArgsModel, make_tool
from ..formatting import _compact_items, _compact_search_result
from .executor import ProjectFactToolExecutor
from .formatting import (
    DEPENDENCY_FIELDS,
    TASK_FIELDS,
    TASK_GRAPH_FIELDS,
)


class CriticalTasksArgs(ToolArgsModel):
    limit: int | None = Field(
        default=None, ge=1, le=20, description="Максимум возвращаемых записей; по умолчанию 10."
    )


class SearchTasksArgs(ToolArgsModel):
    query: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Подстрока в ID или текстовых полях, без учёта регистра.",
    )
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Точное исходное значение из фактов, без перевода и без учёта регистра.",
    )
    priority: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Точное исходное значение из фактов, без перевода и без учёта регистра.",
    )
    assignee: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Подстрока в имени исполнителя, без учёта регистра.",
    )
    limit: int | None = Field(
        default=None, ge=1, le=20, description="Максимум возвращаемых записей; по умолчанию 10."
    )


class SearchDependenciesArgs(ToolArgsModel):
    query: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Подстрока в ID или текстовых полях, без учёта регистра.",
    )
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Точное исходное значение из фактов, без перевода и без учёта регистра.",
    )
    criticality: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Точное исходное значение из фактов, без перевода и без учёта регистра.",
    )
    limit: int | None = Field(
        default=None, ge=1, le=20, description="Максимум возвращаемых записей; по умолчанию 10."
    )


def build_get_critical_tasks(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def get_critical_tasks(limit: int | None = None) -> dict[str, Any]:
        result = await tool_executor.critical_tasks({"limit": limit})
        return _compact_search_result(result, TASK_FIELDS)

    return make_tool(
        name="get_critical_tasks",
        description=(
            "Получить задачи, которые сильнее всего мешают проекту: заблокированные, просроченные и задачи с проблемными признаками. Эвристическая сортировка по блокировкам, приоритету и просрочке; не гарантирует полный критический путь. Поиск в снимке проблем, не по всем сущностям. count — совпадения в снимке, returned_count — выдано; truncated — обрезка."
        ),
        args_schema=CriticalTasksArgs,
        func=get_critical_tasks,
    )


def build_search_tasks(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def search_tasks(
        query: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_tasks(
            {
                "query": query,
                "status": status,
                "priority": priority,
                "assignee": assignee,
                "limit": limit,
            }
        )
        return _compact_search_result(result, TASK_FIELDS)

    return make_tool(
        name="search_tasks",
        description="Найти проблемные, заблокированные и просроченные задачи по тексту, статусу, приоритету или исполнителю. Поиск в снимке проблем, не по всем сущностям. count — совпадения в снимке, returned_count — выдано; truncated — обрезка.",
        args_schema=SearchTasksArgs,
        func=search_tasks,
    )


def build_search_dependencies(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def search_dependencies(
        query: str | None = None,
        status: str | None = None,
        criticality: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_dependencies(
            {
                "query": query,
                "status": status,
                "criticality": criticality,
                "limit": limit,
            }
        )
        return _compact_search_result(result, DEPENDENCY_FIELDS)

    return make_tool(
        name="search_dependencies",
        description="Найти связанные с проблемными задачами и рисковые зависимости по тексту, статусу или критичности. Поиск в снимке проблем, не по всем сущностям. count — совпадения в снимке, returned_count — выдано; truncated — обрезка.",
        args_schema=SearchDependenciesArgs,
        func=search_dependencies,
    )


def build_get_task_dependency_graph(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def get_task_dependency_graph() -> dict[str, Any]:
        context = await tool_executor.problem_context()
        graph = context.get("task_dependency_graph")
        items = _compact_items(graph, TASK_GRAPH_FIELDS, limit=60)
        count = len(graph) if isinstance(graph, list) else None
        return {
            "count": count,
            "returned_count": len(items),
            "truncated": count is not None and count > len(items),
            "scope": "project_task_dependencies",
            "items": items,
        }

    return make_tool(
        name="get_task_dependency_graph",
        description="Получить связи задач проекта и отметки критического пути. До 60 рёбер; count — доступно, returned_count — выдано, truncated — обрезка.",
        args_schema=NoArgs,
        func=get_task_dependency_graph,
    )
