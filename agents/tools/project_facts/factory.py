from __future__ import annotations

from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from agents.core.text import bounded_limit
from agents.tools.runtime import BaseTool, StructuredTool

from .schemas import (
    CalculateDelayCostArgs,
    CriticalTasksArgs,
    EvidenceSearchArgs,
    NoArgs,
    ProblemContextArgs,
    SearchCommunicationsArgs,
    SearchDecisionsArgs,
    SearchDependenciesArgs,
    SearchRisksArgs,
    SearchTasksArgs,
)

from .executor import ProjectFactToolExecutor
from .formatting import (
    CHANGE_REQUEST_FIELDS,
    COMMUNICATION_FIELDS,
    DECISION_FIELDS,
    DEPENDENCY_FIELDS,
    EVIDENCE_FIELDS,
    RESOURCE_COST_FIELDS,
    RISK_FIELDS,
    TASK_FIELDS,
    TASK_GRAPH_FIELDS,
    _compact_budget_result,
    _compact_items,
    _compact_problem_context,
    _compact_project_summary,
    _compact_retrieval_result,
    _compact_search_result,
)


def build_project_tools(tool_executor: "ProjectFactToolExecutor") -> list[BaseTool]:
    """Создает инструменты LangChain на время одного запроса."""

    async def get_project_summary() -> dict[str, Any]:
        return _compact_project_summary(await tool_executor.project_summary())

    async def get_problem_context(max_depth: int | None = None) -> dict[str, Any]:
        depth = bounded_limit(max_depth, default=tool_executor.max_depth, maximum=4)
        return _compact_problem_context(await tool_executor.problem_context(max_depth=depth))

    async def get_critical_tasks(limit: int | None = None) -> dict[str, Any]:
        result = await tool_executor.critical_tasks({"limit": limit})
        return _compact_search_result(result, TASK_FIELDS)

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

    async def search_project_evidence(
        query: str,
        entity_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_project_evidence(
            {
                "query": query,
                "entity_id": entity_id,
                "limit": limit,
            }
        )
        return _compact_retrieval_result(result)

    async def get_budget() -> dict[str, Any]:
        return _compact_budget_result(await tool_executor.budget())

    async def get_resource_rates() -> dict[str, Any]:
        context = await tool_executor.problem_context()
        resources = context.get("project_resources", [])
        return {
            "count": len(resources) if isinstance(resources, list) else 0,
            "items": _compact_items(resources, RESOURCE_COST_FIELDS, limit=20),
        }

    async def get_task_dependency_graph() -> dict[str, Any]:
        context = await tool_executor.problem_context()
        graph = context.get("task_dependency_graph", [])
        return {
            "count": len(graph) if isinstance(graph, list) else 0,
            "items": _compact_items(graph, TASK_GRAPH_FIELDS, limit=60),
        }

    async def calculate_delay_cost(delay_days: int, include_resource_burn: bool = True) -> dict[str, Any]:
        return await tool_executor.calculate_delay_cost(
            delay_days=delay_days,
            include_resource_burn=include_resource_burn,
        )

    def make_tool(
        *,
        name: str,
        description: str,
        args_schema: type[BaseModel],
        func: Callable[..., Awaitable[dict[str, Any]]],
    ) -> BaseTool:
        return StructuredTool.from_function(
            coroutine=func,
            name=name,
            description=description,
            args_schema=args_schema,
        )

    return [
        make_tool(
            name="get_project_summary",
            description="Получить детерминированный summary проекта: метрики, health, сигналы и топ-сущности.",
            args_schema=NoArgs,
            func=get_project_summary,
        ),
        make_tool(
            name="get_problem_context",
            description=(
                "Получить контекст фактов: проблемные задачи, граф зависимостей, риски, "
                "коммуникации, решения, бюджет и ресурсы."
            ),
            args_schema=ProblemContextArgs,
            func=get_problem_context,
        ),
        make_tool(
            name="get_critical_tasks",
            description=(
                "Получить задачи, которые сильнее всего мешают проекту: заблокированные, "
                "просроченные и задачи критического пути."
            ),
            args_schema=CriticalTasksArgs,
            func=get_critical_tasks,
        ),
        make_tool(
            name="search_tasks",
            description="Найти проблемные, заблокированные и просроченные задачи по тексту, статусу, приоритету или исполнителю.",
            args_schema=SearchTasksArgs,
            func=search_tasks,
        ),
        make_tool(
            name="search_risks",
            description="Найти связанные и топовые риски проекта по тексту, статусу или минимальному баллу.",
            args_schema=SearchRisksArgs,
            func=search_risks,
        ),
        make_tool(
            name="search_communications",
            description="Найти просроченные коммуникации и темы, требующие решения, по тексту, статусу или команде.",
            args_schema=SearchCommunicationsArgs,
            func=search_communications,
        ),
        make_tool(
            name="search_decisions",
            description="Найти ожидающие решения и открытые запросы на изменение.",
            args_schema=SearchDecisionsArgs,
            func=search_decisions,
        ),
        make_tool(
            name="search_dependencies",
            description="Найти проектные зависимости по тексту, статусу или критичности.",
            args_schema=SearchDependenciesArgs,
            func=search_dependencies,
        ),
        make_tool(
            name="search_project_evidence",
            description=(
                "RAG-поиск по текстовому следу проекта: комментарии задач, сообщения коммуникаций, "
                "риски, решения, запросы на изменение, причины зависимостей и историю изменений. "
                "Используй для вопросов о причинах, истории обсуждения и уже согласованных действиях."
            ),
            args_schema=EvidenceSearchArgs,
            func=search_project_evidence,
        ),
        make_tool(
            name="get_budget",
            description="Получить бюджет проекта и влияние открытых запросов на изменение.",
            args_schema=NoArgs,
            func=get_budget,
        ),
        make_tool(
            name="get_resource_rates",
            description="Получить ресурсы проекта, часовые ставки и недельную стоимость их работы на проекте.",
            args_schema=NoArgs,
            func=get_resource_rates,
        ),
        make_tool(
            name="get_task_dependency_graph",
            description="Получить граф зависимостей задач проекта: какая задача от какой зависит и что на критическом пути.",
            args_schema=NoArgs,
            func=get_task_dependency_graph,
        ),
        make_tool(
            name="calculate_delay_cost",
            description=(
                "Посчитать стоимость сдвига срока на заданное число дней. "
                "Возвращает стоимость задержки по бюджету и, опционально, стоимость ресурсо-дней."
            ),
            args_schema=CalculateDelayCostArgs,
            func=calculate_delay_cost,
        ),
    ]
