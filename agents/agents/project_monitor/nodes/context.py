from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sdm.backend.services.data_classes import ProjectSummarySource
from sdm.backend.services.project_summary_repository import ProjectSummaryRepository

from ..state import ProjectMonitorData, state_value


def project_context_from_source(source: ProjectSummarySource) -> dict[str, Any]:
    budget = source.budget
    return {
        "project": {
            "id": source.project.id,
            "name": source.project.name,
            "lifecycle_status": source.project.lifecycle_status,
            "priority": source.project.priority,
            "start_date": source.project.start_date,
            "planned_end_date": source.project.planned_end_date,
            "business_goal": source.project.business_goal,
            "expected_result": source.project.expected_result,
        },
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "planned_due_date": task.planned_due_date,
                "actual_end_date": task.actual_end_date,
                "estimated_hours": task.estimated_hours,
                "spent_hours": task.spent_hours,
                "is_blocked": task.is_blocked,
                "blocker_reason": task.blocker_reason,
                "assignee_name": task.assignee_name,
            }
            for task in source.tasks
        ],
        "milestones": [
            {
                "id": milestone.id,
                "name": milestone.name,
                "status": milestone.status,
                "planned_end_date": milestone.planned_end_date,
                "actual_end_date": milestone.actual_end_date,
                "responsible_team": milestone.responsible_team,
            }
            for milestone in source.milestones
        ],
        "risks": [
            {
                "id": risk.id,
                "risk_type": risk.risk_type,
                "description": risk.description,
                "probability": risk.probability,
                "impact": risk.impact,
                "status": risk.status,
                "owner_name": risk.owner_name,
                "mitigation_plan": risk.mitigation_plan,
            }
            for risk in source.risks
        ],
        "communications": [
            {
                "id": communication.id,
                "topic": communication.topic,
                "status": communication.status,
                "importance": communication.importance,
                "expected_response_date": communication.expected_response_date,
                "from_team": communication.from_team,
                "to_team": communication.to_team,
            }
            for communication in source.communications
        ],
        "dependencies": [
            {
                "id": dependency.id,
                "dependency_type": dependency.dependency_type,
                "depends_on": dependency.depends_on,
                "owner_team": dependency.owner_team,
                "expected_date": dependency.expected_date,
                "status": dependency.status,
                "criticality": dependency.criticality,
            }
            for dependency in source.dependencies
        ],
        "decisions": [
            {
                "id": decision.id,
                "decision_type": decision.decision_type,
                "description": decision.description,
                "decision_owner": decision.decision_owner,
                "status": decision.status,
                "decision_date": decision.decision_date,
            }
            for decision in source.decisions
        ],
        "change_requests": [
            {
                "id": change_request.id,
                "request_date": change_request.request_date,
                "requested_by": change_request.requested_by,
                "change_type": change_request.change_type,
                "description": change_request.description,
                "requested_budget_delta": change_request.requested_budget_delta,
                "requested_timeline_delta_days": change_request.requested_timeline_delta_days,
                "status": change_request.status,
            }
            for change_request in source.change_requests
        ],
        "budget": None
        if budget is None
        else {
            "planned_budget": budget.planned_budget,
            "actual_spent": budget.actual_spent,
            "expected_economic_effect": budget.expected_economic_effect,
            "cost_of_delay_per_day": budget.cost_of_delay_per_day,
            "currency": budget.currency,
        },
    }


def load_project_context_node(session_factory: async_sessionmaker[AsyncSession]) -> Any:
    async def load_project_context(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        project_id = state_value(state, "project_id")

        async with session_factory() as session:
            source = await ProjectSummaryRepository(session).get_project_source(project_id)

        return project_context_from_source(source)

    return load_project_context
