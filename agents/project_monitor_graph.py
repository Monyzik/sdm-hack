from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy.orm import sessionmaker

from agents.internal_notification_agent import ProjectInternalNotificationAgent
from agents.project_analysis_agent import ProjectAnalystAgent
from backend.app.database.session import create_engine_from_env, create_session_factory
from backend.app.services.metrics import ProjectMetrics, calculate_project_metrics
from backend.app.services.project_summary_repository import (
    ProjectSummaryRepository,
    ProjectSummarySource,
)


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
    change_requests: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    analysis: dict[str, Any] | None = None
    notification_draft: dict[str, Any] | None = None


def state_value(state: ProjectMonitorData | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, ProjectMonitorData):
        return getattr(state, key)
    return state.get(key, default)


def coerce_as_of(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported as_of value: {value!r}")


def project_context_from_source(source: ProjectSummarySource) -> dict[str, Any]:
    budget = source.budget
    return {
        "project": {
            "id": source.project.id,
            "name": source.project.name,
            "owner_name": source.project.owner_name,
            "status": source.project.status,
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
                "impact_scope": change_request.impact_scope,
                "impact_budget": change_request.impact_budget,
                "impact_days": change_request.impact_days,
                "status": change_request.status,
            }
            for change_request in source.change_requests
        ],
        "budget": None
        if budget is None
        else {
            "planned_budget": budget.planned_budget,
            "actual_spent": budget.actual_spent,
            "forecast_total_spent": budget.forecast_total_spent,
            "expected_economic_effect": budget.expected_economic_effect,
            "cost_of_delay_per_day": budget.cost_of_delay_per_day,
            "currency": budget.currency,
        },
    }


def load_project_context_node(session_factory: sessionmaker) -> Any:
    def load_project_context(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        project_id = state_value(state, "project_id")

        with session_factory() as session:
            source = ProjectSummaryRepository(session).get_project_source(project_id)

        return project_context_from_source(source)

    return load_project_context


def calculate_metrics_node(session_factory: sessionmaker) -> Any:
    def calculate_metrics(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        project_id = state_value(state, "project_id")
        as_of = coerce_as_of(state_value(state, "as_of"))

        with session_factory() as session:
            source = ProjectSummaryRepository(session).get_project_source(project_id)
            project_metrics = calculate_project_metrics(source, as_of=as_of)

        return {
            "as_of": project_metrics.as_of_date,
            "metrics": project_monitor_metrics(project_metrics),
        }

    return calculate_metrics


def project_monitor_metrics(metrics: ProjectMetrics) -> dict[str, Any]:
    overdue_communications = [
        communication
        for communication in metrics.delayed_communications
        if communication.delay_days > 0
    ]
    budget_deviation_pct = None
    if metrics.budget is not None:
        budget_deviation_pct = round(metrics.budget.budget_deviation_percent / 100, 4)

    return {
        "as_of_date": metrics.as_of_date,
        "completion_percent": metrics.completion_percent,
        "total_tasks_count": metrics.total_tasks_count,
        "completed_tasks_count": metrics.completed_tasks_count,
        "overdue_tasks_count": metrics.overdue_tasks_count,
        "blocked_tasks_count": metrics.blocked_tasks_count,
        "delayed_milestones_count": metrics.delayed_milestones_count,
        "high_risk_count": metrics.high_risk_count,
        "dependency_risk_count": metrics.dependency_risk_count,
        "pending_decision_count": metrics.pending_decision_count,
        "open_change_request_count": metrics.open_change_request_count,
        "dependency_sla_breach_count": metrics.dependency_sla_breach_count,
        "budget_deviation_percent": None
        if metrics.budget is None
        else metrics.budget.budget_deviation_percent,
        "budget_deviation_pct": budget_deviation_pct,
        "roi_percent": None if metrics.budget is None else metrics.budget.roi_percent,
        "risk_adjusted_roi_percent": None
        if metrics.budget is None
        else metrics.budget.risk_adjusted_roi_percent,
        "milestone_slip_days": metrics.milestone_slip_days,
        "critical_path_delay_days": metrics.critical_path_delay_days,
        "blocked_age_days": metrics.blocked_age_days,
        "decision_age_days": metrics.decision_age_days,
        "net_change_request_impact_days": metrics.net_change_request_impact_days,
        "net_change_request_impact_budget": metrics.net_change_request_impact_budget,
        "scope_churn_rate": metrics.scope_churn_rate,
        "burn_rate_percent": metrics.burn_rate_percent,
        "schedule_variance_percent": metrics.schedule_variance_percent,
        "stale_tasks_count": metrics.stale_tasks_count,
        "max_status_age_days": metrics.max_status_age_days,
        "estimate_overrun_percent": metrics.estimate_overrun_percent,
        "workload_imbalance_index": metrics.workload_imbalance_index,
        "key_person_dependency_percent": metrics.key_person_dependency_percent,
        "critical_task_silence_days": metrics.critical_task_silence_days,
        "communication_silence_days": metrics.communication_silence_days,
        "data_freshness_days": metrics.data_freshness_days,
        "cost_of_delay_exposure": metrics.cost_of_delay_exposure,
        "risk_trend": metrics.risk_trend,
        "resource_overload_percent": metrics.resource_overload_percent,
        "max_communication_delay_days": metrics.max_communication_delay_days,
        "project_health_score": metrics.project_health_score,
        "risk_level": metrics.risk_level,
        "executive_summary": metrics.executive_summary,
        "key_signals": metrics.key_signals,
        "budget": None if metrics.budget is None else metrics.budget.model_dump(mode="json"),
        "overdue_tasks": metrics.overdue_tasks_count,
        "blocked_tasks": metrics.blocked_tasks_count,
        "delayed_milestones": metrics.delayed_milestones_count,
        "open_high_risks": metrics.high_risk_count,
        "overdue_communications": len(overdue_communications),
        "critical_dependencies": metrics.dependency_risk_count,
        "pending_decisions": metrics.pending_decision_count,
        "open_change_requests": metrics.open_change_request_count,
        "details": {
            "overdue_tasks": dump_signals(metrics.overdue_tasks),
            "blocked_tasks": dump_signals(metrics.blocked_tasks),
            "delayed_milestones": dump_signals(metrics.delayed_milestones),
            "open_high_risks": dump_signals(metrics.top_risks),
            "overdue_communications": dump_signals(overdue_communications),
            "critical_dependencies": dump_signals(metrics.risky_dependencies),
            "pending_decisions": dump_signals(metrics.pending_decisions),
            "open_change_requests": dump_signals(metrics.open_change_requests),
            "overloaded_resources": dump_signals(metrics.overloaded_resources),
            "owner_action_load": dump_signals(metrics.owner_action_load),
        },
    }


def dump_signals(signals: list[Any], limit: int = 5) -> list[dict[str, Any]]:
    return [
        signal.model_dump(mode="json") if hasattr(signal, "model_dump") else dict(signal)
        for signal in signals[:limit]
    ]


def metric_count(metrics: dict[str, Any], preferred_key: str, legacy_key: str | None = None) -> int:
    value = metrics.get(preferred_key)
    if value is None and legacy_key is not None:
        value = metrics.get(legacy_key)
    return int(value or 0)


def classify_alerts(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
    metrics = state_value(state, "metrics", {})
    alerts: list[dict[str, Any]] = []

    overdue_tasks = metric_count(metrics, "overdue_tasks_count", "overdue_tasks")
    blocked_tasks = metric_count(metrics, "blocked_tasks_count", "blocked_tasks")
    delayed_milestones = metric_count(metrics, "delayed_milestones_count", "delayed_milestones")
    high_risks = metric_count(metrics, "high_risk_count", "open_high_risks")
    overdue_communications = metric_count(metrics, "overdue_communications")
    critical_dependencies = metric_count(metrics, "dependency_risk_count", "critical_dependencies")
    pending_decisions = metric_count(metrics, "pending_decision_count", "pending_decisions")
    open_change_requests = metric_count(metrics, "open_change_request_count", "open_change_requests")
    critical_path_delay_days = metric_count(metrics, "critical_path_delay_days")
    dependency_sla_breach_count = metric_count(metrics, "dependency_sla_breach_count")
    cost_of_delay_exposure = metric_count(metrics, "cost_of_delay_exposure")
    stale_tasks_count = metric_count(metrics, "stale_tasks_count")

    if overdue_tasks > 0:
        alerts.append(
            {
                "level": "Critical",
                "metric": "overdue_tasks",
                "message": f"Есть просроченные задачи: {overdue_tasks}",
            }
        )
    if blocked_tasks > 0:
        alerts.append(
            {
                "level": "Critical",
                "metric": "blocked_tasks",
                "message": f"Есть заблокированные задачи: {blocked_tasks}",
            }
        )
    if delayed_milestones > 0:
        alerts.append(
            {
                "level": "Critical",
                "metric": "delayed_milestones",
                "message": f"Есть задержанные вехи: {delayed_milestones}",
            }
        )
    if high_risks > 0:
        alerts.append(
            {
                "level": "Warning",
                "metric": "open_high_risks",
                "message": f"Есть открытые высокие риски: {high_risks}",
            }
        )
    if overdue_communications > 0:
        alerts.append(
            {
                "level": "Warning",
                "metric": "overdue_communications",
                "message": f"Есть просроченные коммуникации: {overdue_communications}",
            }
        )
    if critical_dependencies > 0:
        alerts.append(
            {
                "level": "Critical",
                "metric": "critical_dependencies",
                "message": f"Есть критичные незакрытые зависимости: {critical_dependencies}",
            }
        )
    if pending_decisions > 0:
        alerts.append(
            {
                "level": "Warning",
                "metric": "pending_decisions",
                "message": f"Есть незакрытые решения: {pending_decisions}",
            }
        )
    if open_change_requests > 0:
        alerts.append(
            {
                "level": "Warning",
                "metric": "open_change_requests",
                "message": f"Есть открытые change requests: {open_change_requests}",
            }
        )
    if critical_path_delay_days > 0:
        alerts.append(
            {
                "level": "Critical",
                "metric": "critical_path_delay_days",
                "message": f"Critical path задержан на {critical_path_delay_days} дней",
            }
        )
    if dependency_sla_breach_count > 0:
        alerts.append(
            {
                "level": "Warning",
                "metric": "dependency_sla_breach_count",
                "message": f"Есть SLA breach по зависимостям: {dependency_sla_breach_count}",
            }
        )
    if cost_of_delay_exposure > 0:
        alerts.append(
            {
                "level": "Warning",
                "metric": "cost_of_delay_exposure",
                "message": f"Cost of delay exposure: {cost_of_delay_exposure}",
            }
        )
    if stale_tasks_count > 3:
        alerts.append(
            {
                "level": "Warning",
                "metric": "stale_tasks_count",
                "message": f"Есть зависшие задачи: {stale_tasks_count}",
            }
        )

    budget_deviation_pct = metrics.get("budget_deviation_pct")
    if budget_deviation_pct is not None and budget_deviation_pct > 0.1:
        alerts.append(
            {
                "level": "Warning",
                "metric": "budget_deviation_pct",
                "message": f"Прогнозный бюджет выше плана на {budget_deviation_pct:.1%}",
            }
        )

    return {"alerts": alerts}


def analyze_project_node(agent: ProjectAnalystAgent) -> Any:
    def analyze_project(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        analysis = agent.analyze(
            project=state_value(state, "project", {}),
            metrics=state_value(state, "metrics", {}),
            alerts=state_value(state, "alerts", []),
        )
        return {"analysis": analysis.model_dump(mode="json")}

    return analyze_project


def draft_notification_node(agent: ProjectInternalNotificationAgent) -> Any:
    def draft_notification(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        notification_draft = agent.draft(
            project=state_value(state, "project", {}),
            metrics=state_value(state, "metrics", {}),
            alerts=state_value(state, "alerts", []),
            analysis=state_value(state, "analysis", {}),
        )
        return {"notification_draft": notification_draft.model_dump(mode="json")}

    return draft_notification


def build_project_monitor_graph(
    session_factory: sessionmaker | None = None,
    analyst: ProjectAnalystAgent | None = None,
    notification_agent: ProjectInternalNotificationAgent | None = None,
):
    if session_factory is None:
        engine = create_engine_from_env()
        session_factory = create_session_factory(engine)
    if analyst is None:
        analyst = ProjectAnalystAgent()
    if notification_agent is None:
        notification_agent = ProjectInternalNotificationAgent()

    graph = StateGraph(ProjectMonitorData)
    graph.add_node("load_project_context", load_project_context_node(session_factory))
    graph.add_node("calculate_metrics", calculate_metrics_node(session_factory))
    graph.add_node("classify_alerts", classify_alerts)
    graph.add_node("analyze_project", analyze_project_node(analyst))
    graph.add_node("draft_notification", draft_notification_node(notification_agent))

    graph.add_edge(START, "load_project_context")
    graph.add_edge("load_project_context", "calculate_metrics")
    graph.add_edge("calculate_metrics", "classify_alerts")
    graph.add_edge("classify_alerts", "analyze_project")
    graph.add_edge("analyze_project", "draft_notification")
    graph.add_edge("draft_notification", END)

    return graph.compile()


def run_project_monitor(
    project_id: str,
    as_of: date | None = None,
    session_factory: sessionmaker | None = None,
    analyst: ProjectAnalystAgent | None = None,
    notification_agent: ProjectInternalNotificationAgent | None = None,
) -> dict[str, Any]:
    graph = build_project_monitor_graph(
        session_factory=session_factory,
        analyst=analyst,
        notification_agent=notification_agent,
    )
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
                "analysis": result["analysis"],
                "notification_draft": result["notification_draft"],
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        )
    )


if __name__ == "__main__":
    main()
