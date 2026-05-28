from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import Field

from ..base import NoArgs, ToolArgsModel, make_tool
from ..formatting import _compact_items
from .executor import ProjectFactToolExecutor
from .formatting import (
    RESOURCE_COST_FIELDS,
    _compact_budget_result,
)


class CalculateDelayCostArgs(ToolArgsModel):
    delay_days: int = Field(
        ge=0,
        le=365,
        description="Число дней сдвига. При учёте ресурсов применяется дневная ставка из пятидневной рабочей недели.",
    )
    include_resource_burn: bool = Field(
        default=True,
        description="Добавлять расход ресурсов по текущей загрузке; оценка, а не новая смета.",
    )


def build_get_budget(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def get_budget() -> dict[str, Any]:
        return _compact_budget_result(await tool_executor.budget())

    return make_tool(
        name="get_budget",
        description="Получить бюджет проекта и влияние открытых запросов на изменение.",
        args_schema=NoArgs,
        func=get_budget,
    )


def build_get_resource_rates(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    async def get_resource_rates() -> dict[str, Any]:
        context = await tool_executor.problem_context()
        resources = context.get("project_resources")
        items = _compact_items(resources, RESOURCE_COST_FIELDS, limit=20)
        count = len(resources) if isinstance(resources, list) else None
        return {
            "count": count,
            "returned_count": len(items),
            "truncated": count is not None and count > len(items),
            "scope": "project_resources",
            "items": items,
        }

    return make_tool(
        name="get_resource_rates",
        description="Получить ставки и стоимость ресурсов, выделенных проекту. До 20 записей; count — доступно, returned_count — выдано, truncated — обрезка.",
        args_schema=NoArgs,
        func=get_resource_rates,
    )


def build_calculate_delay_cost(tool_executor: ProjectFactToolExecutor) -> BaseTool:
    return make_tool(
        name="calculate_delay_cost",
        description=(
            "Посчитать стоимость сдвига срока на заданное число дней. "
            "Возвращает стоимость задержки по бюджету и, опционально, стоимость ресурсо-дней. При неизвестных ставках возвращает null и missing_data; отсутствие данных не означает нулевую стоимость."
        ),
        args_schema=CalculateDelayCostArgs,
        func=tool_executor.calculate_delay_cost,
    )
