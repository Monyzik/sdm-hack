from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from agents.core.text import bounded_limit, optional_int

from .filters import _dedupe_items, _filter_items, _task_criticality_key, _tool_result


class ProjectFactToolExecutor:
    """Исполнитель инструментов, который читает факты проекта из API бэкенда."""

    def __init__(self, *, backend_api_url: str, project_id: str, as_of: str, max_depth: int) -> None:
        self.backend_api_url = backend_api_url.rstrip("/")
        self.project_id = project_id
        self.as_of = as_of
        self.max_depth = max_depth
        self._summary: dict[str, Any] | None = None
        self._context: dict[str, Any] | None = None
        self._context_depth: int | None = None

    async def project_summary(self) -> dict[str, Any]:
        if self._summary is None:
            query = urlencode({"as_of": self.as_of})
            self._summary = await self._fetch_json(f"/api/v1/summaries/projects/{self.project_id}?{query}")
        return self._summary

    async def problem_context(self, max_depth: int | None = None) -> dict[str, Any]:
        depth = max_depth or self.max_depth
        if self._context is None or depth != self._context_depth:
            query = urlencode({"as_of": self.as_of, "max_depth": depth})
            self._context = await self._fetch_json(
                f"/api/v1/summaries/projects/{self.project_id}/problem-context?{query}"
            )
            self._context_depth = depth
        return self._context

    async def critical_tasks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
        items = _dedupe_items(
            [
                *context.get("problem_tasks", []),
                *summary.get("blocked_tasks", []),
                *summary.get("overdue_tasks", []),
            ]
        )
        items = sorted(items, key=_task_criticality_key, reverse=True)
        return _tool_result(items, arguments.get("limit"))

    async def search_tasks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
        items = _dedupe_items(
            [
                *context.get("problem_tasks", []),
                *summary.get("blocked_tasks", []),
                *summary.get("overdue_tasks", []),
            ]
        )
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("title", "blocker_reason", "assignee_name", "status", "priority"),
            exact_filters={
                "status": arguments.get("status"),
                "priority": arguments.get("priority"),
                "assignee_name": arguments.get("assignee"),
            },
        )
        return _tool_result(items, arguments.get("limit"))

    async def search_risks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
        items = _dedupe_items([*context.get("linked_risks", []), *summary.get("top_risks", [])])
        min_score = optional_int(arguments.get("min_score"))
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("risk_type", "description", "status", "owner_name"),
            exact_filters={"status": arguments.get("status")},
        )
        if min_score is not None:
            items = [item for item in items if int(item.get("score") or 0) >= min_score]
        return _tool_result(items, arguments.get("limit"))

    async def search_communications(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
        items = _dedupe_items(
            [
                *context.get("linked_communications", []),
                *summary.get("delayed_communications", []),
            ]
        )
        team = arguments.get("team")
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("topic", "from_team", "to_team", "status", "importance"),
            exact_filters={"status": arguments.get("status")},
        )
        if team:
            needle = str(team).casefold()
            items = [
                item
                for item in items
                if needle in str(item.get("from_team", "")).casefold()
                or needle in str(item.get("to_team", "")).casefold()
            ]
        return _tool_result(items, arguments.get("limit"))

    async def search_decisions(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
        items = _dedupe_items(
            [
                *context.get("pending_decisions", []),
                *summary.get("pending_decisions", []),
                *context.get("open_change_requests", []),
                *summary.get("open_change_requests", []),
            ]
        )
        owner = arguments.get("owner")
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("description", "decision_owner", "requested_by", "status", "change_type"),
            exact_filters={"status": arguments.get("status")},
        )
        if owner:
            needle = str(owner).casefold()
            items = [
                item
                for item in items
                if needle in str(item.get("decision_owner", "")).casefold()
                or needle in str(item.get("requested_by", "")).casefold()
            ]
        return _tool_result(items, arguments.get("limit"))

    async def search_dependencies(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
        items = _dedupe_items(
            [
                *context.get("linked_project_dependencies", []),
                *summary.get("risky_dependencies", []),
            ]
        )
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("depends_on", "owner_team", "status", "criticality", "dependency_type"),
            exact_filters={
                "status": arguments.get("status"),
                "criticality": arguments.get("criticality"),
            },
        )
        return _tool_result(items, arguments.get("limit"))

    async def search_project_evidence(self, arguments: dict[str, Any]) -> dict[str, Any]:
        limit_value = bounded_limit(arguments.get("limit"), default=8, maximum=20)
        query = urlencode(
            {
                "query": arguments.get("query") or "",
                "as_of": self.as_of,
                "limit": limit_value,
                **({"entity_id": arguments["entity_id"]} if arguments.get("entity_id") else {}),
            }
        )
        return await self._fetch_json(
            f"/api/v1/summaries/projects/{self.project_id}/retrieval-context?{query}"
        )

    async def budget(self) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
        return {
            "budget": summary.get("budget"),
            "budget_metrics": {
                "budget_deviation_percent": summary.get("budget", {}).get("budget_deviation_percent")
                if summary.get("budget")
                else None,
                "roi_percent": summary.get("budget", {}).get("roi_percent") if summary.get("budget") else None,
                "risk_adjusted_roi_percent": summary.get("budget", {}).get("risk_adjusted_roi_percent")
                if summary.get("budget")
                else None,
                "net_change_request_impact_days": summary.get("net_change_request_impact_days"),
                "net_change_request_impact_budget": summary.get("net_change_request_impact_budget"),
                "cost_of_delay_exposure": summary.get("cost_of_delay_exposure"),
            },
            "open_change_requests": context.get("open_change_requests", []),
        }

    async def calculate_delay_cost(self, *, delay_days: int, include_resource_burn: bool = True) -> dict[str, Any]:
        context = await self.problem_context()
        budget = context.get("budget") or {}
        resources = context.get("project_resources") or []
        cost_of_delay_per_day = int(budget.get("cost_of_delay_per_day") or 0)
        delay_cost = delay_days * cost_of_delay_per_day

        daily_resource_cost = 0
        if include_resource_burn and isinstance(resources, list):
            daily_resource_cost = sum(int(resource.get("daily_project_cost") or 0) for resource in resources)

        resource_burn_cost = delay_days * daily_resource_cost
        return {
            "delay_days": delay_days,
            "cost_of_delay_per_day": cost_of_delay_per_day,
            "delay_opportunity_cost": delay_cost,
            "daily_resource_cost": daily_resource_cost if include_resource_burn else None,
            "resource_burn_cost": resource_burn_cost if include_resource_burn else None,
            "total_cost": delay_cost + resource_burn_cost,
            "currency": budget.get("currency"),
            "formula": {
                "delay_opportunity_cost": "дни сдвига * цена задержки за день",
                "resource_burn_cost": "дни сдвига * сумма дневной стоимости ресурсов проекта",
            },
            "assumption": (
                "resource_burn_cost считает текущую дневную стоимость ресурсов проекта по фактическим часам в неделю / 5; "
                "это оценка текущего сдвига, а не новая смета после перепланирования."
            ),
        }

    async def _fetch_json(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.backend_api_url}{path}", headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
