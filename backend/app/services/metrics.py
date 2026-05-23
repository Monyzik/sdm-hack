from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Protocol

from backend.app.database.models import (
    Budget,
    Milestone,
    Task,
)
from backend.app.schemas.project_summary import (
    BudgetSummary,
    ChangeRequestSignal,
    CommunicationSignal,
    DecisionSignal,
    DependencySignal,
    MilestoneSignal,
    ProjectSummary,
    ResourceLoadSignal,
    RiskSignal,
    TaskSignal,
)
from backend.app.services.project_summary_repository import ProjectSummarySource


DONE_TASK_STATUSES = {"done", "closed", "resolved", "completed"}
DONE_MILESTONE_STATUSES = {"done", "closed", "completed"}
BLOCKED_TASK_STATUSES = {"blocked"}
OPEN_COMMUNICATION_STATUSES = {"pending", "delayed", "escalated"}
OPEN_DEPENDENCY_STATUSES = {"pending", "delayed", "blocked"}
OPEN_DECISION_STATUSES = {"pending", "under_review"}
OPEN_CHANGE_REQUEST_STATUSES = {"pending", "under_review", "proposed"}
RISK_OPEN_STATUSES = {"active", "escalated", "mitigating", "open"}
PRIORITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
CRITICALITY_WEIGHT = {"critical": 3, "high": 2, "medium": 1, "low": 0}


@dataclass(frozen=True)
class ProjectMetricContext:
    source: ProjectSummarySource
    as_of: date


@dataclass(frozen=True)
class ProjectMetrics:
    as_of_date: date
    total_tasks_count: int
    completed_tasks_count: int
    completion_percent: float
    blocked_tasks_count: int
    overdue_tasks_count: int
    delayed_milestones_count: int
    high_risk_count: int
    dependency_risk_count: int
    pending_decision_count: int
    open_change_request_count: int
    budget: BudgetSummary | None
    resource_overload_percent: float
    max_communication_delay_days: int
    project_health_score: int
    risk_level: str
    blocked_tasks: list[TaskSignal]
    overdue_tasks: list[TaskSignal]
    delayed_milestones: list[MilestoneSignal]
    top_risks: list[RiskSignal]
    delayed_communications: list[CommunicationSignal]
    overloaded_resources: list[ResourceLoadSignal]
    risky_dependencies: list[DependencySignal]
    pending_decisions: list[DecisionSignal]
    open_change_requests: list[ChangeRequestSignal]
    key_signals: list[str]
    executive_summary: str


class MetricCalculator(Protocol):
    def __call__(self, context: ProjectMetricContext) -> object:
        ...


class ProjectMetric(Protocol):
    key: str
    title: str
    source_tables: tuple[str, ...]

    def calculate(self, context: ProjectMetricContext) -> object:
        ...


@dataclass(frozen=True)
class FunctionMetric:
    key: str
    title: str
    source_tables: tuple[str, ...]
    calculator: MetricCalculator
    description: str
    owner_action: str

    def calculate(self, context: ProjectMetricContext) -> object:
        return self.calculator(context)


def calculate_project_metrics(source: ProjectSummarySource, as_of: date | None = None) -> ProjectMetrics:
    as_of_date = as_of or infer_as_of_date(source)
    context = ProjectMetricContext(source=source, as_of=as_of_date)

    total_tasks_count = calculate_total_tasks_count(context)
    completed_tasks = calculate_completed_tasks(context)
    blocked_tasks = calculate_blocked_tasks(context)
    overdue_tasks = calculate_overdue_tasks(context)
    delayed_milestones = calculate_delayed_milestones(context)
    completion_percent = calculate_completion_percent(
        context,
        completed_tasks_count=len(completed_tasks),
        total_tasks_count=total_tasks_count,
    )

    risk_signals = calculate_risk_signals(context)
    high_risk_signals = calculate_high_risk_signals(context, risk_signals=risk_signals)
    budget_summary = calculate_budget_summary(context, high_risks=high_risk_signals)
    delayed_communications = calculate_delayed_communications(context)
    overloaded_resources = calculate_overloaded_resources(context)
    resource_overload_percent = calculate_resource_overload_percent(
        context,
        overloaded_resources=overloaded_resources,
    )
    max_communication_delay_days = calculate_max_communication_delay_days(
        context,
        delayed_communications=delayed_communications,
    )
    risky_dependencies = calculate_risky_dependencies(context)
    pending_decisions = calculate_pending_decisions(context)
    open_change_requests = calculate_open_change_requests(context)

    health_score = calculate_project_health_score(
        context,
        total_tasks_count=total_tasks_count,
        overdue_tasks_count=len(overdue_tasks),
        blocked_tasks_count=len(blocked_tasks),
        delayed_milestones_count=len(delayed_milestones),
        high_risk_count=len(high_risk_signals),
        budget_deviation_percent=budget_summary.budget_deviation_percent if budget_summary else 0.0,
        resource_overload_percent=resource_overload_percent,
        max_communication_delay_days=max_communication_delay_days,
        dependency_risk_count=len(risky_dependencies),
        pending_decision_count=len(pending_decisions),
        open_change_request_count=len(open_change_requests),
    )
    risk_level = calculate_risk_level(context, health_score=health_score)

    blocked_task_signals = [_task_signal(task, as_of_date) for task in _sort_tasks(blocked_tasks)]
    overdue_task_signals = [_task_signal(task, as_of_date) for task in _sort_tasks(overdue_tasks)]
    key_signals = build_key_signals(
        blocked_tasks=blocked_task_signals,
        overdue_tasks=overdue_task_signals,
        delayed_milestones=delayed_milestones,
        high_risks=high_risk_signals,
        budget=budget_summary,
        delayed_communications=delayed_communications,
        overloaded_resources=overloaded_resources,
        risky_dependencies=risky_dependencies,
        pending_decisions=pending_decisions,
        open_change_requests=open_change_requests,
    )

    return ProjectMetrics(
        as_of_date=as_of_date,
        total_tasks_count=total_tasks_count,
        completed_tasks_count=len(completed_tasks),
        completion_percent=completion_percent,
        blocked_tasks_count=len(blocked_tasks),
        overdue_tasks_count=len(overdue_tasks),
        delayed_milestones_count=len(delayed_milestones),
        high_risk_count=len(high_risk_signals),
        dependency_risk_count=len(risky_dependencies),
        pending_decision_count=len(pending_decisions),
        open_change_request_count=len(open_change_requests),
        budget=budget_summary,
        resource_overload_percent=resource_overload_percent,
        max_communication_delay_days=max_communication_delay_days,
        project_health_score=health_score,
        risk_level=risk_level,
        blocked_tasks=blocked_task_signals,
        overdue_tasks=overdue_task_signals,
        delayed_milestones=delayed_milestones,
        top_risks=high_risk_signals,
        delayed_communications=delayed_communications,
        overloaded_resources=overloaded_resources,
        risky_dependencies=risky_dependencies,
        pending_decisions=pending_decisions,
        open_change_requests=open_change_requests,
        key_signals=key_signals,
        executive_summary=build_executive_summary(
            project_name=source.project.name,
            risk_level=risk_level,
            health_score=health_score,
            completion_percent=completion_percent,
            key_signals=key_signals,
        ),
    )


def infer_as_of_date(source: ProjectSummarySource) -> date:
    activity_dates: list[date] = []
    activity_dates.extend(item.changed_at.date() for item in source.task_history)
    activity_dates.extend(item.created_at.date() for item in source.task_comments)
    activity_dates.extend(item.message_time.date() for item in source.communication_messages)
    activity_dates.extend(item.last_message_date for item in source.communications)
    activity_dates.extend(item.decision_date for item in source.decisions)
    activity_dates.extend(item.request_date for item in source.change_requests)
    activity_dates.extend(item.actual_end_date for item in source.milestones if item.actual_end_date is not None)
    return max(activity_dates, default=date.today())


def calculate_total_tasks_count(context: ProjectMetricContext) -> int:
    return len(context.source.tasks)


def calculate_completed_tasks(context: ProjectMetricContext) -> list[Task]:
    return [task for task in context.source.tasks if _is_done_task(task)]


def calculate_completed_tasks_count(context: ProjectMetricContext) -> int:
    return len(calculate_completed_tasks(context))


def calculate_completion_percent(
    context: ProjectMetricContext,
    *,
    completed_tasks_count: int | None = None,
    total_tasks_count: int | None = None,
) -> float:
    completed = calculate_completed_tasks_count(context) if completed_tasks_count is None else completed_tasks_count
    total = calculate_total_tasks_count(context) if total_tasks_count is None else total_tasks_count
    return _percent(completed, total)


def calculate_blocked_tasks(context: ProjectMetricContext) -> list[Task]:
    return [task for task in context.source.tasks if _is_blocked_task(task)]


def calculate_blocked_tasks_count(context: ProjectMetricContext) -> int:
    return len(calculate_blocked_tasks(context))


def calculate_overdue_tasks(context: ProjectMetricContext) -> list[Task]:
    return [task for task in context.source.tasks if _is_overdue_task(task, context.as_of)]


def calculate_overdue_tasks_count(context: ProjectMetricContext) -> int:
    return len(calculate_overdue_tasks(context))


def calculate_delayed_milestones(context: ProjectMetricContext) -> list[MilestoneSignal]:
    signals = [
        _milestone_signal(milestone, context.as_of)
        for milestone in context.source.milestones
        if _is_delayed_milestone(milestone, context.as_of)
    ]
    return sorted(signals, key=lambda item: (item.delay_days, item.id), reverse=True)


def calculate_delayed_milestones_count(context: ProjectMetricContext) -> int:
    return len(calculate_delayed_milestones(context))


def calculate_risk_signals(context: ProjectMetricContext) -> list[RiskSignal]:
    signals = [
        RiskSignal(
            id=risk.id,
            risk_type=risk.risk_type,
            description=risk.description,
            probability=risk.probability,
            impact=risk.impact,
            score=risk.probability * risk.impact,
            status=risk.status,
            owner_name=risk.owner_name,
            linked_task_id=risk.linked_task_id,
        )
        for risk in context.source.risks
    ]
    return sorted(signals, key=lambda item: (item.score, _status_weight(item.status), item.id), reverse=True)


def calculate_high_risk_signals(
    context: ProjectMetricContext,
    *,
    risk_signals: list[RiskSignal] | None = None,
) -> list[RiskSignal]:
    signals = calculate_risk_signals(context) if risk_signals is None else risk_signals
    return [
        risk
        for risk in signals
        if risk.score >= 15 and risk.status.casefold() in RISK_OPEN_STATUSES
    ]


def calculate_high_risk_count(context: ProjectMetricContext) -> int:
    return len(calculate_high_risk_signals(context))


def calculate_budget_summary(
    context: ProjectMetricContext,
    *,
    high_risks: list[RiskSignal] | None = None,
) -> BudgetSummary | None:
    budget = context.source.budget
    if budget is None:
        return None

    risk_signals = calculate_high_risk_signals(context) if high_risks is None else high_risks
    return _budget_summary(budget, risk_signals)


def calculate_budget_deviation_percent(context: ProjectMetricContext) -> float:
    budget = calculate_budget_summary(context)
    return budget.budget_deviation_percent if budget else 0.0


def calculate_roi_percent(context: ProjectMetricContext) -> float:
    budget = calculate_budget_summary(context)
    return budget.roi_percent if budget else 0.0


def calculate_risk_adjusted_roi_percent(context: ProjectMetricContext) -> float:
    budget = calculate_budget_summary(context)
    return budget.risk_adjusted_roi_percent if budget else 0.0


def calculate_delayed_communications(context: ProjectMetricContext) -> list[CommunicationSignal]:
    signals: list[CommunicationSignal] = []
    for communication in context.source.communications:
        status = communication.status.casefold()
        delay_days = max(0, (context.as_of - communication.expected_response_date).days)
        if status not in OPEN_COMMUNICATION_STATUSES or delay_days == 0:
            continue
        signals.append(
            CommunicationSignal(
                id=communication.id,
                from_team=communication.from_team,
                to_team=communication.to_team,
                topic=communication.topic,
                status=communication.status,
                importance=communication.importance,
                expected_response_date=communication.expected_response_date,
                delay_days=delay_days,
                linked_task_id=communication.linked_task_id,
            )
        )
    return sorted(
        signals,
        key=lambda item: (item.delay_days, PRIORITY_WEIGHT.get(item.importance, 0), item.id),
        reverse=True,
    )


def calculate_max_communication_delay_days(
    context: ProjectMetricContext,
    *,
    delayed_communications: list[CommunicationSignal] | None = None,
) -> int:
    signals = calculate_delayed_communications(context) if delayed_communications is None else delayed_communications
    return max((signal.delay_days for signal in signals), default=0)


def calculate_overloaded_resources(context: ProjectMetricContext) -> list[ResourceLoadSignal]:
    return calculate_resource_load_signals(context, threshold_percent=100)


def calculate_resource_load_signals(
    context: ProjectMetricContext,
    threshold_percent: int,
) -> list[ResourceLoadSignal]:
    project_actual_by_resource: defaultdict[str, int] = defaultdict(int)
    total_actual_by_resource: defaultdict[str, int] = defaultdict(int)

    for allocation in context.source.project_allocations:
        project_actual_by_resource[allocation.resource_id] += allocation.actual_hours_per_week
    for allocation in context.source.related_allocations:
        total_actual_by_resource[allocation.resource_id] += allocation.actual_hours_per_week

    signals: list[ResourceLoadSignal] = []
    for resource_id, project_hours in project_actual_by_resource.items():
        resource = context.source.resources_by_id.get(resource_id)
        if resource is None or resource.available_hours_per_week <= 0:
            continue
        total_hours = total_actual_by_resource[resource_id]
        total_allocation_percent = round(total_hours / resource.available_hours_per_week * 100, 1)
        overload_percent = round(max(0.0, total_allocation_percent - threshold_percent), 1)
        if total_allocation_percent <= threshold_percent:
            continue
        signals.append(
            ResourceLoadSignal(
                resource_id=resource.id,
                full_name=resource.full_name,
                role=resource.role,
                team=resource.team,
                available_hours_per_week=resource.available_hours_per_week,
                project_actual_hours_per_week=project_hours,
                total_actual_hours_per_week=total_hours,
                total_allocation_percent=total_allocation_percent,
                overload_percent=overload_percent,
            )
        )

    return sorted(signals, key=lambda item: (item.overload_percent, item.resource_id), reverse=True)


def calculate_resource_overload_percent(
    context: ProjectMetricContext,
    *,
    overloaded_resources: list[ResourceLoadSignal] | None = None,
) -> float:
    signals = calculate_overloaded_resources(context) if overloaded_resources is None else overloaded_resources
    return round(max((signal.overload_percent for signal in signals), default=0.0), 1)


def calculate_risky_dependencies(context: ProjectMetricContext) -> list[DependencySignal]:
    signals: list[DependencySignal] = []
    for dependency in context.source.dependencies:
        status = dependency.status.casefold()
        criticality = dependency.criticality.casefold()
        delay_days = max(0, (context.as_of - dependency.expected_date).days)
        is_risky = status in OPEN_DEPENDENCY_STATUSES and (
            criticality in {"critical", "high"} or delay_days > 0
        )
        if not is_risky:
            continue
        signals.append(
            DependencySignal(
                id=dependency.id,
                dependency_type=dependency.dependency_type,
                depends_on=dependency.depends_on,
                owner_team=dependency.owner_team,
                expected_date=dependency.expected_date,
                status=dependency.status,
                criticality=dependency.criticality,
                linked_task_id=dependency.linked_task_id,
                delay_days=delay_days,
            )
        )
    return sorted(
        signals,
        key=lambda item: (CRITICALITY_WEIGHT.get(item.criticality, 0), item.delay_days, item.id),
        reverse=True,
    )


def calculate_dependency_risk_count(context: ProjectMetricContext) -> int:
    return len(calculate_risky_dependencies(context))


def calculate_pending_decisions(context: ProjectMetricContext) -> list[DecisionSignal]:
    signals = [
        DecisionSignal(
            id=decision.id,
            decision_type=decision.decision_type,
            description=decision.description,
            decision_owner=decision.decision_owner,
            status=decision.status,
            decision_date=decision.decision_date,
        )
        for decision in context.source.decisions
        if decision.status.casefold() in OPEN_DECISION_STATUSES
    ]
    return sorted(signals, key=lambda item: (item.decision_date, item.id), reverse=True)


def calculate_pending_decision_count(context: ProjectMetricContext) -> int:
    return len(calculate_pending_decisions(context))


def calculate_open_change_requests(context: ProjectMetricContext) -> list[ChangeRequestSignal]:
    signals = [
        ChangeRequestSignal(
            id=change_request.id,
            change_type=change_request.change_type,
            requested_by=change_request.requested_by,
            status=change_request.status,
            impact_budget=change_request.impact_budget,
            impact_days=change_request.impact_days,
            description=change_request.description,
        )
        for change_request in context.source.change_requests
        if change_request.status.casefold() in OPEN_CHANGE_REQUEST_STATUSES
    ]
    return sorted(
        signals,
        key=lambda item: (abs(item.impact_days), abs(item.impact_budget), item.id),
        reverse=True,
    )


def calculate_open_change_request_count(context: ProjectMetricContext) -> int:
    return len(calculate_open_change_requests(context))


def calculate_project_health_score(
    context: ProjectMetricContext,
    *,
    total_tasks_count: int | None = None,
    overdue_tasks_count: int | None = None,
    blocked_tasks_count: int | None = None,
    delayed_milestones_count: int | None = None,
    high_risk_count: int | None = None,
    budget_deviation_percent: float | None = None,
    resource_overload_percent: float | None = None,
    max_communication_delay_days: int | None = None,
    dependency_risk_count: int | None = None,
    pending_decision_count: int | None = None,
    open_change_request_count: int | None = None,
) -> int:
    total_tasks = calculate_total_tasks_count(context) if total_tasks_count is None else total_tasks_count
    overdue_count = calculate_overdue_tasks_count(context) if overdue_tasks_count is None else overdue_tasks_count
    blocked_count = calculate_blocked_tasks_count(context) if blocked_tasks_count is None else blocked_tasks_count
    delayed_milestone_count = (
        calculate_delayed_milestones_count(context)
        if delayed_milestones_count is None
        else delayed_milestones_count
    )
    risk_count = calculate_high_risk_count(context) if high_risk_count is None else high_risk_count
    budget_deviation = (
        calculate_budget_deviation_percent(context)
        if budget_deviation_percent is None
        else budget_deviation_percent
    )
    resource_overload = (
        calculate_resource_overload_percent(context)
        if resource_overload_percent is None
        else resource_overload_percent
    )
    communication_delay = (
        calculate_max_communication_delay_days(context)
        if max_communication_delay_days is None
        else max_communication_delay_days
    )
    dependency_count = (
        calculate_dependency_risk_count(context)
        if dependency_risk_count is None
        else dependency_risk_count
    )
    decision_count = (
        calculate_pending_decision_count(context)
        if pending_decision_count is None
        else pending_decision_count
    )
    change_request_count = (
        calculate_open_change_request_count(context)
        if open_change_request_count is None
        else open_change_request_count
    )

    overdue_ratio = overdue_count / max(total_tasks, 1)
    blocked_ratio = blocked_count / max(total_tasks, 1)
    penalty = 0.0
    penalty += min(14.0, overdue_ratio * 70)
    penalty += min(18.0, blocked_ratio * 110)
    penalty += min(8.0, delayed_milestone_count * 4.0)
    penalty += min(12.0, max(0.0, budget_deviation) * 0.4)
    penalty += min(14.0, risk_count * 3.5)
    penalty += min(9.0, resource_overload * 0.22)
    penalty += min(7.0, communication_delay * 1.2)
    penalty += min(7.0, dependency_count * 2.5)
    penalty += min(4.0, decision_count * 2.0)
    penalty += min(3.0, change_request_count * 1.5)
    return max(0, min(100, round(100 - penalty)))


def calculate_risk_level(
    context: ProjectMetricContext,
    *,
    health_score: int | None = None,
) -> str:
    score = calculate_project_health_score(context) if health_score is None else health_score
    if score <= 55:
        return "red"
    if score <= 75:
        return "yellow"
    return "green"


def calculate_portfolio_health_score(summaries: list[ProjectSummary]) -> int:
    if not summaries:
        return 100
    return round(sum(summary.project_health_score for summary in summaries) / len(summaries))


def build_key_signals(
    *,
    blocked_tasks: list[TaskSignal],
    overdue_tasks: list[TaskSignal],
    delayed_milestones: list[MilestoneSignal],
    high_risks: list[RiskSignal],
    budget: BudgetSummary | None,
    delayed_communications: list[CommunicationSignal],
    overloaded_resources: list[ResourceLoadSignal],
    risky_dependencies: list[DependencySignal],
    pending_decisions: list[DecisionSignal],
    open_change_requests: list[ChangeRequestSignal],
) -> list[str]:
    signals: list[str] = []
    if blocked_tasks:
        critical = [task for task in blocked_tasks if task.priority == "critical"]
        head = critical[0] if critical else blocked_tasks[0]
        signals.append(f"{len(blocked_tasks)} blocked задач, главный блокер: {head.title}")
    if overdue_tasks:
        max_delay = max(task.overdue_days for task in overdue_tasks)
        signals.append(f"{len(overdue_tasks)} просроченных задач, максимальная просрочка {max_delay} дней")
    if delayed_milestones:
        head = delayed_milestones[0]
        count = len(delayed_milestones)
        label = "задержанная веха" if count == 1 else "задержанных вех"
        signals.append(f"{count} {label}, ключевая: {head.name}")
    if high_risks:
        head = high_risks[0]
        signals.append(f"{len(high_risks)} высоких рисков, топ риск: {head.risk_type} score {head.score}")
    if budget and budget.budget_deviation_percent > 0:
        signals.append(
            f"Forecast бюджета выше плана на {budget.budget_deviation_percent}%, "
            f"risk-adjusted ROI {budget.risk_adjusted_roi_percent}%"
        )
    if overloaded_resources:
        head = overloaded_resources[0]
        signals.append(f"Перегруз ресурсов до {head.total_allocation_percent}%, ресурс: {head.full_name}")
    if delayed_communications:
        head = delayed_communications[0]
        signals.append(f"Задержка коммуникаций до {head.delay_days} дней, канал: {head.from_team} -> {head.to_team}")
    if risky_dependencies:
        head = risky_dependencies[0]
        signals.append(f"{len(risky_dependencies)} рискованных зависимостей, ключевая: {head.depends_on}")
    if pending_decisions:
        signals.append(f"{len(pending_decisions)} управленческих решений ждут владельца")
    if open_change_requests:
        total_days = sum(item.impact_days for item in open_change_requests)
        total_budget = sum(item.impact_budget for item in open_change_requests)
        signals.append(
            f"{len(open_change_requests)} открытых change requests, "
            f"impact {total_days} дней и {total_budget} бюджета"
        )
    return signals or ["Критичных отклонений не найдено"]


def build_executive_summary(
    *,
    project_name: str,
    risk_level: str,
    health_score: int,
    completion_percent: float,
    key_signals: list[str],
) -> str:
    top_reasons = "; ".join(key_signals[:3]).rstrip(".")
    return (
        f"{project_name}: зона {risk_level}, health score {health_score}/100, "
        f"готовность {completion_percent}%. Основные причины: {top_reasons}."
    )


def build_portfolio_signals(summaries: list[ProjectSummary]) -> list[str]:
    if not summaries:
        return ["В портфеле нет проектов"]

    signals: list[str] = []
    red_projects = [summary for summary in summaries if summary.risk_level == "red"]
    if red_projects:
        ids = ", ".join(summary.project_id for summary in sorted(red_projects, key=lambda item: item.project_id))
        signals.append(f"{len(red_projects)} проекта в красной зоне: {ids}")

    worst_budget = max(
        (summary for summary in summaries if summary.budget is not None),
        key=lambda item: item.budget.budget_deviation_percent if item.budget else 0,
        default=None,
    )
    if worst_budget and worst_budget.budget and worst_budget.budget.budget_deviation_percent > 0:
        signals.append(
            f"Максимальное отклонение бюджета у {worst_budget.project_id}: "
            f"{worst_budget.budget.budget_deviation_percent}%"
        )

    worst_resource = max(summaries, key=lambda item: item.resource_overload_percent)
    if worst_resource.resource_overload_percent > 0:
        signals.append(
            f"Максимальный перегруз ресурсов у {worst_resource.project_id}: "
            f"{worst_resource.resource_overload_percent}% сверх доступной емкости"
        )

    total_blocked = sum(summary.blocked_tasks_count for summary in summaries)
    if total_blocked:
        signals.append(f"Всего blocked задач в портфеле: {total_blocked}")

    return signals or ["Критичных портфельных отклонений не найдено"]


def _budget_summary(budget: Budget, high_risks: list[RiskSignal]) -> BudgetSummary:
    budget_deviation_percent = _percent(
        budget.forecast_total_spent - budget.planned_budget,
        budget.planned_budget,
    )
    roi_percent = _percent(
        budget.expected_economic_effect - budget.forecast_total_spent,
        budget.forecast_total_spent,
    )
    risk_pressure = min(
        0.6,
        sum(risk.score for risk in high_risks) / (25 * max(len(high_risks), 1)) * 0.5,
    )
    risk_adjusted_effect = budget.expected_economic_effect * (1 - risk_pressure)
    risk_adjusted_roi_percent = _percent(
        risk_adjusted_effect - budget.forecast_total_spent,
        budget.forecast_total_spent,
    )

    return BudgetSummary(
        planned_budget=budget.planned_budget,
        actual_spent=budget.actual_spent,
        forecast_total_spent=budget.forecast_total_spent,
        expected_economic_effect=budget.expected_economic_effect,
        cost_of_delay_per_day=budget.cost_of_delay_per_day,
        currency=budget.currency,
        budget_deviation_percent=budget_deviation_percent,
        roi_percent=roi_percent,
        risk_adjusted_roi_percent=risk_adjusted_roi_percent,
    )


def _task_signal(task: Task, as_of: date) -> TaskSignal:
    return TaskSignal(
        id=task.id,
        external_id=task.external_id,
        title=task.title,
        status=task.status,
        priority=task.priority,
        planned_due_date=task.planned_due_date,
        overdue_days=max(0, (as_of - task.planned_due_date).days),
        assignee_name=task.assignee_name,
        blocker_reason=task.blocker_reason or None,
    )


def _milestone_signal(milestone: Milestone, as_of: date) -> MilestoneSignal:
    return MilestoneSignal(
        id=milestone.id,
        name=milestone.name,
        status=milestone.status,
        planned_end_date=milestone.planned_end_date,
        delay_days=max(0, (as_of - milestone.planned_end_date).days),
        responsible_team=milestone.responsible_team,
    )


def _is_done_task(task: Task) -> bool:
    return task.status.casefold() in DONE_TASK_STATUSES or task.actual_end_date is not None


def _is_blocked_task(task: Task) -> bool:
    return task.is_blocked or task.status.casefold() in BLOCKED_TASK_STATUSES


def _is_overdue_task(task: Task, as_of: date) -> bool:
    return not _is_done_task(task) and task.planned_due_date < as_of


def _is_delayed_milestone(milestone: Milestone, as_of: date) -> bool:
    return (
        milestone.planned_end_date < as_of
        and milestone.actual_end_date is None
        and milestone.status.casefold() not in DONE_MILESTONE_STATUSES
    )


def _sort_tasks(tasks: Iterable[Task]) -> list[Task]:
    return sorted(
        tasks,
        key=lambda task: (
            PRIORITY_WEIGHT.get(task.priority, 0),
            -task.planned_due_date.toordinal(),
            task.id,
        ),
        reverse=True,
    )


def _percent(value: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return round(value / denominator * 100, 1)


def _status_weight(status: str) -> int:
    status_value = status.casefold()
    if status_value == "escalated":
        return 3
    if status_value == "active":
        return 2
    if status_value == "mitigating":
        return 1
    return 0


PROJECT_METRIC_PROTOCOL = (
    FunctionMetric(
        key="completion_percent",
        title="Готовность проекта",
        source_tables=("tasks",),
        calculator=calculate_completion_percent,
        description="Доля завершенных задач от общего числа задач проекта.",
        owner_action="Сверять прогресс с ближайшими вехами и просрочками.",
    ),
    FunctionMetric(
        key="overdue_tasks_count",
        title="Просроченные задачи",
        source_tables=("tasks",),
        calculator=calculate_overdue_tasks_count,
        description="Количество незавершенных задач с плановой датой раньше даты среза.",
        owner_action="Выбрать задачи для recovery plan и weekly status.",
    ),
    FunctionMetric(
        key="delayed_milestones_count",
        title="Задержанные вехи",
        source_tables=("milestones",),
        calculator=calculate_delayed_milestones_count,
        description="Количество незавершенных вех с плановой датой завершения раньше даты среза.",
        owner_action="Проверить влияние на финальную дату проекта и обновить recovery plan.",
    ),
    FunctionMetric(
        key="blocked_tasks_count",
        title="Заблокированные задачи",
        source_tables=("tasks",),
        calculator=calculate_blocked_tasks_count,
        description="Количество задач в blocked-состоянии или с явным blocked-флагом.",
        owner_action="Найти владельца блокера и запустить эскалацию.",
    ),
    FunctionMetric(
        key="high_risk_count",
        title="Критичные риски",
        source_tables=("risks",),
        calculator=calculate_high_risk_count,
        description="Количество открытых рисков со score 15 и выше.",
        owner_action="Проверить mitigation plan и владельца риска.",
    ),
    FunctionMetric(
        key="budget_deviation_percent",
        title="Отклонение бюджета",
        source_tables=("budgets",),
        calculator=calculate_budget_deviation_percent,
        description="Отклонение forecast_total_spent от planned_budget в процентах.",
        owner_action="Подготовить решение по резерву, scope cut или reforecast.",
    ),
    FunctionMetric(
        key="roi_percent",
        title="ROI проекта",
        source_tables=("budgets",),
        calculator=calculate_roi_percent,
        description="Ожидаемый экономический эффект относительно forecast_total_spent.",
        owner_action="Проверить, сохраняет ли проект экономический смысл.",
    ),
    FunctionMetric(
        key="risk_adjusted_roi_percent",
        title="Risk-adjusted ROI",
        source_tables=("budgets", "risks"),
        calculator=calculate_risk_adjusted_roi_percent,
        description="ROI после дисконта эффекта на давление критичных рисков.",
        owner_action="Использовать для разговора с PMO и заказчиком при высоких рисках.",
    ),
    FunctionMetric(
        key="resource_overload_percent",
        title="Перегруз ресурсов",
        source_tables=("resources", "resource_allocations"),
        calculator=calculate_resource_overload_percent,
        description="Максимальный перегруз ресурса сверх доступной недельной емкости.",
        owner_action="Перераспределить capacity или снизить WIP.",
    ),
    FunctionMetric(
        key="max_communication_delay_days",
        title="Задержка коммуникаций",
        source_tables=("communications",),
        calculator=calculate_max_communication_delay_days,
        description="Максимальная просрочка ответа по открытым коммуникациям.",
        owner_action="Запустить follow-up или эскалацию в команду-владельца.",
    ),
    FunctionMetric(
        key="dependency_risk_count",
        title="Рискованные зависимости",
        source_tables=("dependencies",),
        calculator=calculate_dependency_risk_count,
        description="Количество critical/high зависимостей в открытых проблемных статусах.",
        owner_action="Согласовать дату, владельца и план снятия зависимости.",
    ),
    FunctionMetric(
        key="pending_decision_count",
        title="Ожидающие решения",
        source_tables=("decisions",),
        calculator=calculate_pending_decision_count,
        description="Количество управленческих решений, которые ждут владельца.",
        owner_action="Вынести решения на steering committee или к РП.",
    ),
    FunctionMetric(
        key="open_change_request_count",
        title="Открытые change requests",
        source_tables=("change_requests",),
        calculator=calculate_open_change_request_count,
        description="Количество CR, которые еще не согласованы окончательно.",
        owner_action="Оценить impact по бюджету, срокам и scope.",
    ),
    FunctionMetric(
        key="project_health_score",
        title="Health score проекта",
        source_tables=(
            "tasks",
            "milestones",
            "budgets",
            "risks",
            "communications",
            "resource_allocations",
            "dependencies",
            "decisions",
            "change_requests",
        ),
        calculator=calculate_project_health_score,
        description="Сводный score 0-100 после штрафов за ключевые отклонения.",
        owner_action="Использовать для сортировки инициатив и выбора зоны внимания.",
    ),
    FunctionMetric(
        key="risk_level",
        title="Зона риска",
        source_tables=(
            "tasks",
            "milestones",
            "budgets",
            "risks",
            "communications",
            "resource_allocations",
            "dependencies",
            "decisions",
            "change_requests",
        ),
        calculator=calculate_risk_level,
        description="Green/yellow/red зона проекта на основе health score.",
        owner_action="Определить формат контроля: штатный, внимание РП или эскалация.",
    ),
)
