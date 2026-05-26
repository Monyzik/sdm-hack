from __future__ import annotations

from typing import Any, TypeVar, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.models import (
    Budget,
    BudgetLineItem,
    ChangeRequest,
    Communication,
    CommunicationMessage,
    Decision,
    Milestone,
    Project,
    ProjectDependency,
    Resource,
    ResourceAllocation,
    Risk,
    Task,
    TaskComment,
    TaskDependency,
    TaskHistory,
)
from backend.app.services.data_classes import ProjectSummarySource


_ModelT = TypeVar("_ModelT")


class ProjectSummaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_projects(self) -> list[Project]:
        result = await self._session.scalars(
            select(Project).order_by(Project.priority.asc(), Project.id.asc())
        )
        return list(result.all())

    async def get_project_source(self, project_id: str) -> ProjectSummarySource:
        project = await self._session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        tasks = await self._project_items(Task, project_id, Task.planned_due_date, Task.id)
        task_history = await self._project_items(
            TaskHistory,
            project_id,
            TaskHistory.changed_at.desc(),
            TaskHistory.id,
        )
        task_comments = await self._project_items(
            TaskComment,
            project_id,
            TaskComment.created_at.desc(),
            TaskComment.id,
        )
        milestones = await self._project_items(
            Milestone,
            project_id,
            Milestone.planned_start_date,
            Milestone.id,
        )
        budget = await self._session.scalar(select(Budget).where(Budget.project_id == project_id))
        budget_line_items = await self._project_items(
            BudgetLineItem,
            project_id,
            BudgetLineItem.category,
            BudgetLineItem.id,
        )
        risks = await self._project_items(
            Risk,
            project_id,
            Risk.probability.desc(),
            Risk.impact.desc(),
            Risk.id,
        )
        communications = await self._project_items(
            Communication,
            project_id,
            Communication.expected_response_date,
            Communication.id,
        )
        communication_messages = await self._project_items(
            CommunicationMessage,
            project_id,
            CommunicationMessage.message_time.desc(),
            CommunicationMessage.id,
        )
        project_allocations = await self._project_items(
            ResourceAllocation,
            project_id,
            ResourceAllocation.resource_id,
            ResourceAllocation.id,
        )
        task_dependencies = await self._project_items(
            TaskDependency,
            project_id,
            TaskDependency.is_critical_path.desc(),
            TaskDependency.id,
        )
        dependencies = await self._project_items(
            ProjectDependency,
            project_id,
            ProjectDependency.expected_date,
            ProjectDependency.id,
        )
        decisions = await self._project_items(
            Decision,
            project_id,
            Decision.decision_date.desc(),
            Decision.id,
        )
        change_requests = await self._project_items(
            ChangeRequest,
            project_id,
            ChangeRequest.request_date.desc(),
            ChangeRequest.id,
        )
        related_allocations, resources_by_id = await self._load_related_resources(project_allocations)

        return ProjectSummarySource(
            project=project,
            tasks=tasks,
            task_history=task_history,
            task_comments=task_comments,
            milestones=milestones,
            budget=budget,
            budget_line_items=budget_line_items,
            risks=risks,
            communications=communications,
            communication_messages=communication_messages,
            project_allocations=project_allocations,
            related_allocations=related_allocations,
            resources_by_id=resources_by_id,
            task_dependencies=task_dependencies,
            dependencies=dependencies,
            decisions=decisions,
            change_requests=change_requests,
        )

    async def _project_items(
        self,
        model: type[_ModelT],
        project_id: str,
        *order_by: Any,
    ) -> list[_ModelT]:
        statement = select(model).where(model.project_id == project_id).order_by(*order_by)
        return cast(list[_ModelT], await self._scalars(statement))

    async def _load_related_resources(
        self,
        project_allocations: list[ResourceAllocation],
    ) -> tuple[list[ResourceAllocation], dict[str, Resource]]:
        resource_ids = {allocation.resource_id for allocation in project_allocations}
        if not resource_ids:
            return [], {}

        related_allocations = await self._scalars(
            select(ResourceAllocation)
            .where(ResourceAllocation.resource_id.in_(resource_ids))
            .order_by(ResourceAllocation.resource_id, ResourceAllocation.project_id)
        )
        resources = await self._scalars(
            select(Resource)
            .where(Resource.id.in_(resource_ids))
            .order_by(Resource.id)
        )
        return related_allocations, {resource.id: resource for resource in resources}

    async def _scalars(self, statement: Any) -> list[Any]:
        result = await self._session.scalars(statement)
        return list(result.all())
