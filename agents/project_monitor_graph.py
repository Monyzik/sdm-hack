from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.database.models import (
    Budget,
    Communication,
    Decision,
    Milestone,
    Project,
    ProjectDependency,
    Risk,
    Task,
)
from backend.database.session import create_engine_from_env, create_session_factory


DONE_STATUSES = {"done", "closed", "resolved", "approved", "completed"}


class ProjectMonitorData(BaseModel):
    project_id: str
    as_of: date | None = None
    project: dict[str, Any] = Field(default_factory=dict)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    communications: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    alerts: list[dict[str, Any]] = Field(default_factory=list)


def state_value(state: ProjectMonitorData | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, ProjectMonitorData):
        return getattr(state, key)
    return state.get(key, default)


def is_done(status: str) -> bool:
    return status.strip().lower() in DONE_STATUSES


def load_project_context_node(session_factory: sessionmaker) -> Any:
    def load_project_context(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        project_id = state_value(state, "project_id")

        with session_factory() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise ValueError(f"Проект {project_id} не найден")

            tasks = session.scalars(select(Task).where(Task.project_id == project_id)).all()
            milestones = session.scalars(select(Milestone).where(Milestone.project_id == project_id)).all()
            risks = session.scalars(select(Risk).where(Risk.project_id == project_id)).all()
            communications = session.scalars(
                select(Communication).where(Communication.project_id == project_id)
            ).all()
            dependencies = session.scalars(
                select(ProjectDependency).where(ProjectDependency.project_id == project_id)
            ).all()
            decisions = session.scalars(select(Decision).where(Decision.project_id == project_id)).all()
            budget = session.scalar(select(Budget).where(Budget.project_id == project_id))

        return {
            "project": {
                "id": project.id,
                "name": project.name,
                "owner_name": project.owner_name,
                "status": project.status,
                "priority": project.priority,
                "start_date": project.start_date,
                "planned_end_date": project.planned_end_date,
                "business_goal": project.business_goal,
                "expected_result": project.expected_result,
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
                for task in tasks
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
                for milestone in milestones
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
                for risk in risks
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
                for communication in communications
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
                for dependency in dependencies
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
                for decision in decisions
            ],
            "budget": None
            if budget is None
            else {
                "planned_budget": budget.planned_budget,
                "actual_spent": budget.actual_spent,
                "forecast_total_spent": budget.forecast_total_spent,
                "currency": budget.currency,
            },
        }

    return load_project_context


def calculate_metrics(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
    as_of = state_value(state, "as_of") or date.today()
    tasks = state_value(state, "tasks", [])
    milestones = state_value(state, "milestones", [])
    risks = state_value(state, "risks", [])
    communications = state_value(state, "communications", [])
    dependencies = state_value(state, "dependencies", [])
    decisions = state_value(state, "decisions", [])
    budget = state_value(state, "budget")

    overdue_tasks = [
        task
        for task in tasks
        if task["planned_due_date"] < as_of
        and not is_done(task["status"])
        and task["actual_end_date"] is None
    ]
    blocked_tasks = [task for task in tasks if task["is_blocked"]]
    delayed_milestones = [
        milestone
        for milestone in milestones
        if milestone["planned_end_date"] < as_of
        and milestone["actual_end_date"] is None
        and not is_done(milestone["status"])
    ]
    open_high_risks = [
        risk
        for risk in risks
        if not is_done(risk["status"]) and risk["probability"] * risk["impact"] >= 12
    ]
    overdue_communications = [
        communication
        for communication in communications
        if communication["expected_response_date"] < as_of
        and not is_done(communication["status"])
    ]
    critical_dependencies = [
        dependency
        for dependency in dependencies
        if dependency["criticality"].lower() == "high" and not is_done(dependency["status"])
    ]
    pending_decisions = [
        decision for decision in decisions if not is_done(decision["status"])
    ]

    budget_deviation_pct = None
    if budget and budget["planned_budget"]:
        budget_deviation_pct = (
            budget["forecast_total_spent"] - budget["planned_budget"]
        ) / budget["planned_budget"]

    metrics = {
        "overdue_tasks": len(overdue_tasks),
        "blocked_tasks": len(blocked_tasks),
        "delayed_milestones": len(delayed_milestones),
        "open_high_risks": len(open_high_risks),
        "overdue_communications": len(overdue_communications),
        "critical_dependencies": len(critical_dependencies),
        "pending_decisions": len(pending_decisions),
        "budget_deviation_pct": budget_deviation_pct,
        "details": {
            "overdue_tasks": overdue_tasks[:5],
            "blocked_tasks": blocked_tasks[:5],
            "delayed_milestones": delayed_milestones[:5],
            "open_high_risks": open_high_risks[:5],
            "overdue_communications": overdue_communications[:5],
            "critical_dependencies": critical_dependencies[:5],
            "pending_decisions": pending_decisions[:5],
        },
    }

    return {"as_of": as_of, "metrics": metrics}


def classify_alerts(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
    metrics = state_value(state, "metrics", {})
    alerts: list[dict[str, Any]] = []

    if metrics["overdue_tasks"] > 0:
        alerts.append(
            {
                "level": "Critical",
                "metric": "overdue_tasks",
                "message": f"Есть просроченные задачи: {metrics['overdue_tasks']}",
            }
        )
    if metrics["blocked_tasks"] > 0:
        alerts.append(
            {
                "level": "Critical",
                "metric": "blocked_tasks",
                "message": f"Есть заблокированные задачи: {metrics['blocked_tasks']}",
            }
        )
    if metrics["delayed_milestones"] > 0:
        alerts.append(
            {
                "level": "Critical",
                "metric": "delayed_milestones",
                "message": f"Есть задержанные вехи: {metrics['delayed_milestones']}",
            }
        )
    if metrics["open_high_risks"] > 0:
        alerts.append(
            {
                "level": "Warning",
                "metric": "open_high_risks",
                "message": f"Есть открытые высокие риски: {metrics['open_high_risks']}",
            }
        )
    if metrics["overdue_communications"] > 0:
        alerts.append(
            {
                "level": "Warning",
                "metric": "overdue_communications",
                "message": f"Есть просроченные коммуникации: {metrics['overdue_communications']}",
            }
        )
    if metrics["critical_dependencies"] > 0:
        alerts.append(
            {
                "level": "Critical",
                "metric": "critical_dependencies",
                "message": f"Есть критичные незакрытые зависимости: {metrics['critical_dependencies']}",
            }
        )
    if metrics["pending_decisions"] > 0:
        alerts.append(
            {
                "level": "Warning",
                "metric": "pending_decisions",
                "message": f"Есть незакрытые решения: {metrics['pending_decisions']}",
            }
        )

    budget_deviation_pct = metrics["budget_deviation_pct"]
    if budget_deviation_pct is not None and budget_deviation_pct > 0.1:
        alerts.append(
            {
                "level": "Warning",
                "metric": "budget_deviation_pct",
                "message": f"Прогнозный бюджет выше плана на {budget_deviation_pct:.1%}",
            }
        )

    return {"alerts": alerts}


def build_project_monitor_graph(session_factory: sessionmaker | None = None):
    if session_factory is None:
        engine = create_engine_from_env()
        session_factory = create_session_factory(engine)

    graph = StateGraph(ProjectMonitorData)
    graph.add_node("load_project_context", load_project_context_node(session_factory))
    graph.add_node("calculate_metrics", calculate_metrics)
    graph.add_node("classify_alerts", classify_alerts)

    graph.add_edge(START, "load_project_context")
    graph.add_edge("load_project_context", "calculate_metrics")
    graph.add_edge("calculate_metrics", "classify_alerts")
    graph.add_edge("classify_alerts", END)

    return graph.compile()


def run_project_monitor(
    project_id: str,
    as_of: date | None = None,
    session_factory: sessionmaker | None = None,
) -> dict[str, Any]:
    graph = build_project_monitor_graph(session_factory)
    initial_state = ProjectMonitorData(project_id=project_id)
    if as_of:
        initial_state.as_of = as_of
    return graph.invoke(initial_state.model_dump())


def json_default(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run project monitoring LangGraph workflow.")
    parser.add_argument("project_id", nargs="?", default="P001")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    result = run_project_monitor(args.project_id, as_of=as_of)
    print(
        json.dumps(
            {
                "project": result["project"],
                "metrics": result["metrics"],
                "alerts": result["alerts"],
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        )
    )


if __name__ == "__main__":
    main()
