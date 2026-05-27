from __future__ import annotations

from typing import Any

from ..state import ProjectMonitorData, state_value


def metric_count(metrics: dict[str, Any], preferred_key: str, fallback_key: str | None = None) -> int:
    value = metrics.get(preferred_key)
    if value is None and fallback_key is not None:
        value = metrics.get(fallback_key)
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
        alerts.append({"level": "Critical", "metric": "overdue_tasks", "message": f"Есть просроченные задачи: {overdue_tasks}"})
    if blocked_tasks > 0:
        alerts.append({"level": "Critical", "metric": "blocked_tasks", "message": f"Есть заблокированные задачи: {blocked_tasks}"})
    if delayed_milestones > 0:
        alerts.append({"level": "Critical", "metric": "delayed_milestones", "message": f"Есть задержанные вехи: {delayed_milestones}"})
    if high_risks > 0:
        alerts.append({"level": "Warning", "metric": "open_high_risks", "message": f"Есть открытые высокие риски: {high_risks}"})
    if overdue_communications > 0:
        alerts.append({"level": "Warning", "metric": "overdue_communications", "message": f"Есть просроченные коммуникации: {overdue_communications}"})
    if critical_dependencies > 0:
        alerts.append({"level": "Critical", "metric": "critical_dependencies", "message": f"Есть критичные незакрытые зависимости: {critical_dependencies}"})
    if pending_decisions > 0:
        alerts.append({"level": "Warning", "metric": "pending_decisions", "message": f"Есть незакрытые решения: {pending_decisions}"})
    if open_change_requests > 0:
        alerts.append({"level": "Warning", "metric": "open_change_requests", "message": f"Есть открытые запросы на изменение: {open_change_requests}"})
    if critical_path_delay_days > 0:
        alerts.append({"level": "Critical", "metric": "critical_path_delay_days", "message": f"Критический путь задержан на {critical_path_delay_days} дней"})
    if dependency_sla_breach_count > 0:
        alerts.append({"level": "Warning", "metric": "dependency_sla_breach_count", "message": f"Есть нарушение SLA по зависимостям: {dependency_sla_breach_count}"})
    if cost_of_delay_exposure > 0:
        alerts.append({"level": "Warning", "metric": "cost_of_delay_exposure", "message": f"Оценка стоимости задержки: {cost_of_delay_exposure}"})
    if stale_tasks_count > 3:
        alerts.append({"level": "Warning", "metric": "stale_tasks_count", "message": f"Есть зависшие задачи: {stale_tasks_count}"})

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
