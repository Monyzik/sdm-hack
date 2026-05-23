from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import (
    Budget,
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


@dataclass(frozen=True)
class ProjectSummarySource:
    project: Project
    tasks: list[Task]
    task_history: list[TaskHistory]
    task_comments: list[TaskComment]
    milestones: list[Milestone]
    budget: Budget | None
    risks: list[Risk]
    communications: list[Communication]
    communication_messages: list[CommunicationMessage]
    project_allocations: list[ResourceAllocation]
    related_allocations: list[ResourceAllocation]
    resources_by_id: dict[str, Resource]
    task_dependencies: list[TaskDependency]
    dependencies: list[ProjectDependency]
    decisions: list[Decision]
    change_requests: list[ChangeRequest]


class ProjectSummaryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_projects(self) -> list[Project]:
        return list(
            self._session.scalars(
                select(Project).order_by(Project.priority.asc(), Project.id.asc())
            ).all()
        )

    def get_project_source(self, project_id: str) -> ProjectSummarySource:
        project = self._session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        tasks = self._scalars(select(Task).where(Task.project_id == project_id).order_by(Task.planned_due_date, Task.id))
        task_history = self._scalars(
            select(TaskHistory)
            .where(TaskHistory.project_id == project_id)
            .order_by(TaskHistory.changed_at.desc(), TaskHistory.id)
        )
        task_comments = self._scalars(
            select(TaskComment)
            .where(TaskComment.project_id == project_id)
            .order_by(TaskComment.created_at.desc(), TaskComment.id)
        )
        milestones = self._scalars(
            select(Milestone)
            .where(Milestone.project_id == project_id)
            .order_by(Milestone.planned_start_date, Milestone.id)
        )
        budget = self._session.scalar(select(Budget).where(Budget.project_id == project_id))
        risks = self._scalars(
            select(Risk).where(Risk.project_id == project_id).order_by(Risk.probability.desc(), Risk.impact.desc(), Risk.id)
        )
        communications = self._scalars(
            select(Communication)
            .where(Communication.project_id == project_id)
            .order_by(Communication.expected_response_date, Communication.id)
        )
        communication_messages = self._scalars(
            select(CommunicationMessage)
            .where(CommunicationMessage.project_id == project_id)
            .order_by(CommunicationMessage.message_time.desc(), CommunicationMessage.id)
        )
        project_allocations = self._scalars(
            select(ResourceAllocation)
            .where(ResourceAllocation.project_id == project_id)
            .order_by(ResourceAllocation.resource_id, ResourceAllocation.id)
        )
        task_dependencies = self._scalars(
            select(TaskDependency)
            .where(TaskDependency.project_id == project_id)
            .order_by(TaskDependency.is_critical_path.desc(), TaskDependency.id)
        )
        dependencies = self._scalars(
            select(ProjectDependency)
            .where(ProjectDependency.project_id == project_id)
            .order_by(ProjectDependency.expected_date, ProjectDependency.id)
        )
        decisions = self._scalars(
            select(Decision)
            .where(Decision.project_id == project_id)
            .order_by(Decision.decision_date.desc(), Decision.id)
        )
        change_requests = self._scalars(
            select(ChangeRequest)
            .where(ChangeRequest.project_id == project_id)
            .order_by(ChangeRequest.request_date.desc(), ChangeRequest.id)
        )

        resource_ids = {allocation.resource_id for allocation in project_allocations}
        related_allocations: list[ResourceAllocation] = []
        resources_by_id: dict[str, Resource] = {}
        if resource_ids:
            related_allocations = self._scalars(
                select(ResourceAllocation)
                .where(ResourceAllocation.resource_id.in_(resource_ids))
                .order_by(ResourceAllocation.resource_id, ResourceAllocation.project_id)
            )
            resources = self._scalars(select(Resource).where(Resource.id.in_(resource_ids)).order_by(Resource.id))
            resources_by_id = {resource.id: resource for resource in resources}

        return ProjectSummarySource(
            project=project,
            tasks=tasks,
            task_history=task_history,
            task_comments=task_comments,
            milestones=milestones,
            budget=budget,
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

    def _scalars(self, statement: object) -> list:
        return list(self._session.scalars(statement).all())
