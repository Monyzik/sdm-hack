from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.services.data_classes import ProjectMetrics
from backend.app.services.metrics import calculate_project_metrics, project_metrics_fact_payload
from backend.app.services.project_summary_repository import ProjectSummaryRepository

from ..state import ProjectMonitorData, coerce_as_of, state_value


def calculate_metrics_node(session_factory: async_sessionmaker[AsyncSession]) -> Any:
    async def calculate_metrics(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        project_id = state_value(state, "project_id")
        as_of = coerce_as_of(state_value(state, "as_of"))

        async with session_factory() as session:
            source = await ProjectSummaryRepository(session).get_project_source(project_id)
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
    metric_payload = project_metrics_fact_payload(metrics)

    return {
        "as_of_date": metrics.as_of_date,
        **metric_payload,
        "budget_deviation_pct": budget_deviation_pct,
        "roi_percent": None if metrics.budget is None else metrics.budget.roi_percent,
        "risk_adjusted_roi_percent": None
        if metrics.budget is None
        else metrics.budget.risk_adjusted_roi_percent,
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
