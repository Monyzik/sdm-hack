from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import Field

from ..base import ToolArgsModel, make_tool
from ..formatting import _compact_search_result
from .executor import ProjectFactToolExecutor
from .formatting import RISK_FIELDS


class SearchRisksArgs(ToolArgsModel):
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
    min_score: int | None = Field(
        default=None,
        ge=0,
        le=25,
        description="Включительная нижняя граница балла риска (вероятность × влияние).",
    )
    limit: int | None = Field(
        default=None, ge=1, le=20, description="Максимум возвращаемых записей; по умолчанию 10."
    )


def build_search_risks(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def search_risks(
        query: str | None = None,
        status: str | None = None,
        min_score: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_risks(
            {
                "query": query,
                "status": status,
                "min_score": min_score,
                "limit": limit,
            }
        )
        return _compact_search_result(result, RISK_FIELDS)

    return make_tool(
        name="search_risks",
        description="Найти связанные и топовые риски проекта по тексту, статусу или минимальному баллу. Поиск в снимке проблем, не по всем сущностям. count — совпадения в снимке, returned_count — выдано; truncated — обрезка.",
        args_schema=SearchRisksArgs,
        func=search_risks,
    )
