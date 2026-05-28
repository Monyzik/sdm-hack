from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import Field

from ..base import NoArgs, ToolArgsModel, make_tool
from .executor import ProjectFactToolExecutor
from .formatting import (
    _compact_problem_context,
    _compact_project_summary,
)


class ProblemContextArgs(ToolArgsModel):
    max_depth: int | None = Field(
        default=None,
        ge=1,
        le=4,
        description="Глубина обхода связей проблемных задач; по умолчанию глубина текущего запроса.",
    )


def build_get_project_summary(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def get_project_summary() -> dict[str, Any]:
        return _compact_project_summary(await tool_executor.project_summary())

    return make_tool(
        name="get_project_summary",
        description="Получить агрегированные метрики и состояние проекта, сигналы и ограниченные подборки основных сущностей; это не полный список сущностей. collections содержит размеры доступных и выданных списков.",
        args_schema=NoArgs,
        func=get_project_summary,
    )


def build_get_problem_context(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def get_problem_context(max_depth: int | None = None) -> dict[str, Any]:
        return _compact_problem_context(await tool_executor.problem_context(max_depth=max_depth))

    return make_tool(
        name="get_problem_context",
        description=(
            "Получить контекст фактов: проблемные задачи, граф зависимостей, риски, "
            "коммуникации, решения, бюджет и ресурсы. Связанный контекст ограничен max_depth (1–4); коллекции обрезаются, их размеры указаны в collections."
        ),
        args_schema=ProblemContextArgs,
        func=get_problem_context,
    )
