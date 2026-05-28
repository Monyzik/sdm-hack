from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sdm.agents.db import get_shared_session_factory
from sdm.agents.text import bounded_limit, optional_int
from sdm.backend.services.project_summary_repository import ProjectSummaryRepository
from sdm.backend.services.project_summary_service import ProjectSummaryService

from .filters import _dedupe_items, _filter_items, _task_criticality_key, _tool_result


class ProjectFactToolExecutor:
    """Читает факты из базы и кеширует их на время одного запроса агента.

    Каждая операция открывает свою сессию. Блокировки по ключу кеша
    объединяют одинаковые чтения, сохраняя независимость разных глубин контекста.
    """

    def __init__(
        self,
        *,
        project_id: str,
        as_of: str,
        max_depth: int,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.project_id = project_id
        self.as_of = as_of
        self.max_depth = max_depth
        self._session_factory = (
            session_factory if session_factory is not None else get_shared_session_factory()
        )
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_locks: dict[str, asyncio.Lock] = {}

    async def project_summary(self) -> dict[str, Any]:
        return await self._fetch_cached(f"summary:{self.as_of}", self._load_project_summary)

    async def problem_context(self, max_depth: int | None = None) -> dict[str, Any]:
        depth = bounded_limit(max_depth, default=self.max_depth, maximum=4)
        return await self._fetch_cached(
            f"problem_context:{self.as_of}:{depth}", lambda: self._load_problem_context(depth)
        )

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
            },
            text_filters={"assignee_name": arguments.get("assignee")},
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
            items = [
                item
                for item in items
                if item.get("score") is not None and int(item["score"]) >= min_score
            ]
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

    async def budget(self) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
        budget = summary.get("budget") or {}
        return {
            "budget": summary.get("budget"),
            "budget_metrics": {
                "budget_deviation_percent": budget.get("budget_deviation_percent"),
                "roi_percent": budget.get("roi_percent"),
                "risk_adjusted_roi_percent": budget.get("risk_adjusted_roi_percent"),
                "net_change_request_impact_days": summary.get("net_change_request_impact_days"),
                "net_change_request_impact_budget": summary.get("net_change_request_impact_budget"),
                "cost_of_delay_exposure": summary.get("cost_of_delay_exposure"),
            },
            "open_change_requests": context.get("open_change_requests", []),
        }

    async def calculate_delay_cost(
        self, *, delay_days: int, include_resource_burn: bool = True
    ) -> dict[str, Any]:
        context = await self.problem_context()
        budget = context.get("budget") or {}
        missing_data: list[str] = []
        cost_of_delay_per_day = budget.get("cost_of_delay_per_day")
        if cost_of_delay_per_day is None:
            missing_data.append("budget.cost_of_delay_per_day")
        delay_cost = (
            delay_days * cost_of_delay_per_day if cost_of_delay_per_day is not None else None
        )

        daily_resource_cost = None
        if include_resource_burn:
            resources = context.get("project_resources")
            if not isinstance(resources, list):
                missing_data.append("project_resources")
            elif any(
                not isinstance(resource, dict) or resource.get("daily_project_cost") is None
                for resource in resources
            ):
                missing_data.append("project_resources.daily_project_cost")
            else:
                daily_resource_cost = sum(resource["daily_project_cost"] for resource in resources)
        resource_burn_cost = (
            delay_days * daily_resource_cost if daily_resource_cost is not None else None
        )
        total_cost = None
        if delay_cost is not None and (not include_resource_burn or resource_burn_cost is not None):
            total_cost = delay_cost + (resource_burn_cost if include_resource_burn else 0)
        return {
            "delay_days": delay_days,
            "cost_of_delay_per_day": cost_of_delay_per_day,
            "delay_opportunity_cost": delay_cost,
            "daily_resource_cost": daily_resource_cost if include_resource_burn else None,
            "resource_burn_cost": resource_burn_cost if include_resource_burn else None,
            "total_cost": total_cost,
            "missing_data": missing_data,
            "is_complete": not missing_data,
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

    async def _fetch_cached(
        self, key: str, loader: Callable[[], Awaitable[dict[str, Any]]]
    ) -> dict[str, Any]:
        lock = self._cache_locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key not in self._cache:
                self._cache[key] = await loader()
            return self._cache[key]

    async def _load_project_summary(self) -> dict[str, Any]:
        async with self._session_factory() as session:
            service = ProjectSummaryService(ProjectSummaryRepository(session))
            summary = await service.build_project_summary(
                self.project_id, as_of=_as_date(self.as_of)
            )
            return summary.model_dump(mode="json")

    async def _load_problem_context(self, max_depth: int) -> dict[str, Any]:
        async with self._session_factory() as session:
            service = ProjectSummaryService(ProjectSummaryRepository(session))
            context = await service.build_project_problem_context(
                self.project_id, as_of=_as_date(self.as_of), max_depth=max_depth
            )
            return context.model_dump(mode="json")


def _as_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
