from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import Field

from ..base import ToolArgsModel, make_tool
from ..formatting import _compact_search_result
from .executor import ProjectFactToolExecutor
from .formatting import (
    CHANGE_REQUEST_FIELDS,
    COMMUNICATION_FIELDS,
    DECISION_FIELDS,
)


class SearchCommunicationsArgs(ToolArgsModel):
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
    team: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Подстрока в названии отправляющей или принимающей команды, без учёта регистра.",
    )
    limit: int | None = Field(
        default=None, ge=1, le=20, description="Максимум возвращаемых записей; по умолчанию 10."
    )


class SearchDecisionsArgs(ToolArgsModel):
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
    owner: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Подстрока в имени владельца решения или инициатора изменения, без учёта регистра.",
    )
    limit: int | None = Field(
        default=None, ge=1, le=20, description="Максимум возвращаемых записей; по умолчанию 10."
    )


def build_search_communications(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def search_communications(
        query: str | None = None,
        status: str | None = None,
        team: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_communications(
            {
                "query": query,
                "status": status,
                "team": team,
                "limit": limit,
            }
        )
        return _compact_search_result(result, COMMUNICATION_FIELDS)

    return make_tool(
        name="search_communications",
        description="Найти просроченные коммуникации и темы, требующие решения, по тексту, статусу или команде. Поиск в снимке проблем, не по всем сущностям. count — совпадения в снимке, returned_count — выдано; truncated — обрезка.",
        args_schema=SearchCommunicationsArgs,
        func=search_communications,
    )


def build_search_decisions(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def search_decisions(
        query: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_decisions(
            {
                "query": query,
                "status": status,
                "owner": owner,
                "limit": limit,
            }
        )
        return _compact_search_result(result, DECISION_FIELDS + CHANGE_REQUEST_FIELDS)

    return make_tool(
        name="search_decisions",
        description="Найти ожидающие решения и открытые запросы на изменение. Поиск в снимке проблем, не по всем сущностям. count — совпадения в снимке, returned_count — выдано; truncated — обрезка.",
        args_schema=SearchDecisionsArgs,
        func=search_decisions,
    )
