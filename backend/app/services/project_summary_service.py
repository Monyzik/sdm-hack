from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

from backend.app.database.models import (
    Budget,
    ChangeRequest,
    Communication,
    Decision,
    ProjectDependency,
    ResourceAllocation,
    Risk,
    Task,
)
from backend.app.schemas.project_summary import (
    BudgetSummary,
    ChangeRequestSignal,
    CommunicationSignal,
    DecisionSignal,
    DependencySignal,
    PortfolioProjectSummary,
    PortfolioSummary,
    ProjectSummary,
    ResourceLoadSignal,
    RiskSignal,
    TaskSignal,
)
from backend.app.services.project_summary_repository import ProjectSummaryRepository, ProjectSummarySource


DONE_TASK_STATUSES = {"done", "closed", "resolved"}
BLOCKED_TASK_STATUSES = {"blocked"}
OPEN_COMMUNICATION_STATUSES = {"pending", "delayed", "escalated"}
OPEN_DEPENDENCY_STATUSES = {"pending", "delayed", "blocked"}
OPEN_DECISION_STATUSES = {"pending", "under_review"}
OPEN_CHANGE_REQUEST_STATUSES = {"pending", "under_review", "proposed"}
RISK_OPEN_STATUSES = {"active", "escalated", "mitigating", "open"}
PRIORITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
CRITICALITY_WEIGHT = {"critical": 3, "high": 2, "medium": 1, "low": 0}


class ProjectSummaryService:
    def __init__(self, repository: ProjectSummaryRepository) -> None:
        self._repository = repository

    def build_project_summary(self, project_id: str, as_of: date | None = None) -> ProjectSummary:
        source = self._repository.get_project_source(project_id)
        as_of_date = as_of or self._infer_as_of_date(source)

        tasks = source.tasks
        total_tasks_count = len(tasks)
        completed_tasks = [task for task in tasks if _is_done_task(task)]
        blocked_tasks = [task for task in tasks if _is_blocked_task(task)]
        overdue_tasks = [task for task in tasks if _is_overdue_task(task, as_of_date)]
        completion_percent = _percent(len(completed_tasks), total_tasks_count)

        risk_signals = self._build_risk_signals(source.risks)
        high_risk_signals = [risk for risk in risk_signals if risk.score >= 15 and risk.status.casefold() in RISK_OPEN_STATUSES]

        budget_summary = self._build_budget_summary(source.budget, high_risk_signals)
        delayed_communications = self._build_communication_signals(source.communications, as_of_date)
        overloaded_resources = self._build_resource_load_signals(source, threshold_percent=100)
        risky_dependencies = self._build_dependency_signals(source.dependencies, as_of_date)
        pending_decisions = self._build_decision_signals(source.decisions)
        open_change_requests = self._build_change_request_signals(source.change_requests)

        resource_overload_percent = round(
            max((signal.overload_percent for signal in overloaded_resources), default=0.0),
            1,
        )
        max_communication_delay_days = max((signal.delay_days for signal in delayed_communications), default=0)
        dependency_risk_count = len(risky_dependencies)
        pending_decision_count = len(pending_decisions)
        open_change_request_count = len(open_change_requests)
        health_score = self._calculate_health_score(
            total_tasks_count=total_tasks_count,
            overdue_tasks_count=len(overdue_tasks),
            blocked_tasks_count=len(blocked_tasks),
            high_risk_count=len(high_risk_signals),
            budget_deviation_percent=budget_summary.budget_deviation_percent if budget_summary else 0.0,
            resource_overload_percent=resource_overload_percent,
            max_communication_delay_days=max_communication_delay_days,
            dependency_risk_count=dependency_risk_count,
            pending_decision_count=pending_decision_count,
            open_change_request_count=open_change_request_count,
        )
        risk_level = self._risk_level(health_score)

        all_blocked_task_signals = [_task_signal(task, as_of_date) for task in _sort_tasks(blocked_tasks)]
        all_overdue_task_signals = [_task_signal(task, as_of_date) for task in _sort_tasks(overdue_tasks)]
        key_signals = self._build_key_signals(
            blocked_tasks=all_blocked_task_signals,
            overdue_tasks=all_overdue_task_signals,
            high_risks=high_risk_signals,
            budget=budget_summary,
            delayed_communications=delayed_communications,
            overloaded_resources=overloaded_resources,
            risky_dependencies=risky_dependencies,
            pending_decisions=pending_decisions,
            open_change_requests=open_change_requests,
        )

        return ProjectSummary(
            project_id=source.project.id,
            project_name=source.project.name,
            owner_name=source.project.owner_name,
            status=source.project.status,
            priority=source.project.priority,
            as_of_date=as_of_date,
            completion_percent=completion_percent,
            total_tasks_count=total_tasks_count,
            completed_tasks_count=len(completed_tasks),
            overdue_tasks_count=len(overdue_tasks),
            blocked_tasks_count=len(blocked_tasks),
            high_risk_count=len(high_risk_signals),
            dependency_risk_count=dependency_risk_count,
            pending_decision_count=pending_decision_count,
            open_change_request_count=open_change_request_count,
            budget=budget_summary,
            resource_overload_percent=resource_overload_percent,
            max_communication_delay_days=max_communication_delay_days,
            project_health_score=health_score,
            risk_level=risk_level,
            executive_summary=self._build_executive_summary(
                project_name=source.project.name,
                risk_level=risk_level,
                health_score=health_score,
                completion_percent=completion_percent,
                key_signals=key_signals,
            ),
            key_signals=key_signals,
            blocked_tasks=all_blocked_task_signals[:7],
            overdue_tasks=all_overdue_task_signals[:7],
            top_risks=high_risk_signals[:7],
            delayed_communications=delayed_communications[:7],
            overloaded_resources=overloaded_resources[:7],
            risky_dependencies=risky_dependencies[:7],
            pending_decisions=pending_decisions[:7],
            open_change_requests=open_change_requests[:7],
        )

    def build_portfolio_summary(self, as_of: date | None = None) -> PortfolioSummary:
        project_ids = [project.id for project in self._repository.list_projects()]
        project_summaries = [self.build_project_summary(project_id, as_of=as_of) for project_id in project_ids]
        portfolio_as_of = max((summary.as_of_date for summary in project_summaries), default=date.today())

        compact_projects = [
            PortfolioProjectSummary(
                project_id=summary.project_id,
                project_name=summary.project_name,
                owner_name=summary.owner_name,
                status=summary.status,
                priority=summary.priority,
                project_health_score=summary.project_health_score,
                risk_level=summary.risk_level,
                completion_percent=summary.completion_percent,
                overdue_tasks_count=summary.overdue_tasks_count,
                blocked_tasks_count=summary.blocked_tasks_count,
                high_risk_count=summary.high_risk_count,
                budget_deviation_percent=summary.budget.budget_deviation_percent if summary.budget else None,
                resource_overload_percent=summary.resource_overload_percent,
                top_signals=summary.key_signals[:3],
            )
            for summary in sorted(project_summaries, key=lambda item: (item.project_health_score, item.project_id))
        ]

        red_count = sum(1 for summary in project_summaries if summary.risk_level == "red")
        yellow_count = sum(1 for summary in project_summaries if summary.risk_level == "yellow")
        green_count = sum(1 for summary in project_summaries if summary.risk_level == "green")
        portfolio_health_score = round(
            sum(summary.project_health_score for summary in project_summaries) / len(project_summaries)
        ) if project_summaries else 100

        return PortfolioSummary(
            as_of_date=portfolio_as_of,
            projects_count=len(project_summaries),
            red_projects_count=red_count,
            yellow_projects_count=yellow_count,
            green_projects_count=green_count,
            portfolio_health_score=portfolio_health_score,
            top_portfolio_signals=self._build_portfolio_signals(project_summaries),
            projects=compact_projects,
        )

    def _infer_as_of_date(self, source: ProjectSummarySource) -> date:
        activity_dates: list[date] = []
        activity_dates.extend(item.changed_at.date() for item in source.task_history)
        activity_dates.extend(item.created_at.date() for item in source.task_comments)
        activity_dates.extend(item.message_time.date() for item in source.communication_messages)
        activity_dates.extend(item.last_message_date for item in source.communications)
        activity_dates.extend(item.decision_date for item in source.decisions)
        activity_dates.extend(item.request_date for item in source.change_requests)
        activity_dates.extend(item.actual_end_date for item in source.milestones if item.actual_end_date is not None)
        return max(activity_dates, default=date.today())

    def _build_budget_summary(self, budget: Budget | None, high_risks: list[RiskSignal]) -> BudgetSummary | None:
        if budget is None:
            return None

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

    def _build_risk_signals(self, risks: Iterable[Risk]) -> list[RiskSignal]:
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
            for risk in risks
        ]
        return sorted(signals, key=lambda item: (item.score, _status_weight(item.status), item.id), reverse=True)

    def _build_communication_signals(
        self,
        communications: Iterable[Communication],
        as_of: date,
    ) -> list[CommunicationSignal]:
        signals: list[CommunicationSignal] = []
        for communication in communications:
            status = communication.status.casefold()
            delay_days = max(0, (as_of - communication.expected_response_date).days)
            if status not in OPEN_COMMUNICATION_STATUSES:
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

    def _build_resource_load_signals(
        self,
        source: ProjectSummarySource,
        threshold_percent: int,
    ) -> list[ResourceLoadSignal]:
        project_actual_by_resource: defaultdict[str, int] = defaultdict(int)
        total_actual_by_resource: defaultdict[str, int] = defaultdict(int)

        for allocation in source.project_allocations:
            project_actual_by_resource[allocation.resource_id] += allocation.actual_hours_per_week
        for allocation in source.related_allocations:
            total_actual_by_resource[allocation.resource_id] += allocation.actual_hours_per_week

        signals: list[ResourceLoadSignal] = []
        for resource_id, project_hours in project_actual_by_resource.items():
            resource = source.resources_by_id.get(resource_id)
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

    def _build_dependency_signals(
        self,
        dependencies: Iterable[ProjectDependency],
        as_of: date,
    ) -> list[DependencySignal]:
        signals: list[DependencySignal] = []
        for dependency in dependencies:
            status = dependency.status.casefold()
            criticality = dependency.criticality.casefold()
            delay_days = max(0, (as_of - dependency.expected_date).days)
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

    def _build_decision_signals(self, decisions: Iterable[Decision]) -> list[DecisionSignal]:
        signals = [
            DecisionSignal(
                id=decision.id,
                decision_type=decision.decision_type,
                description=decision.description,
                decision_owner=decision.decision_owner,
                status=decision.status,
                decision_date=decision.decision_date,
            )
            for decision in decisions
            if decision.status.casefold() in OPEN_DECISION_STATUSES
        ]
        return sorted(signals, key=lambda item: (item.decision_date, item.id), reverse=True)

    def _build_change_request_signals(self, change_requests: Iterable[ChangeRequest]) -> list[ChangeRequestSignal]:
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
            for change_request in change_requests
            if change_request.status.casefold() in OPEN_CHANGE_REQUEST_STATUSES
        ]
        return sorted(
            signals,
            key=lambda item: (abs(item.impact_days), abs(item.impact_budget), item.id),
            reverse=True,
        )

    def _calculate_health_score(
        self,
        *,
        total_tasks_count: int,
        overdue_tasks_count: int,
        blocked_tasks_count: int,
        high_risk_count: int,
        budget_deviation_percent: float,
        resource_overload_percent: float,
        max_communication_delay_days: int,
        dependency_risk_count: int,
        pending_decision_count: int,
        open_change_request_count: int,
    ) -> int:
        overdue_ratio = overdue_tasks_count / max(total_tasks_count, 1)
        blocked_ratio = blocked_tasks_count / max(total_tasks_count, 1)
        penalty = 0.0
        penalty += min(14.0, overdue_ratio * 70)
        penalty += min(18.0, blocked_ratio * 110)
        penalty += min(12.0, max(0.0, budget_deviation_percent) * 0.4)
        penalty += min(14.0, high_risk_count * 3.5)
        penalty += min(9.0, resource_overload_percent * 0.22)
        penalty += min(7.0, max_communication_delay_days * 1.2)
        penalty += min(7.0, dependency_risk_count * 2.5)
        penalty += min(4.0, pending_decision_count * 2.0)
        penalty += min(3.0, open_change_request_count * 1.5)
        return max(0, min(100, round(100 - penalty)))

    def _risk_level(self, health_score: int) -> str:
        if health_score <= 55:
            return "red"
        if health_score <= 75:
            return "yellow"
        return "green"

    def _build_key_signals(
        self,
        *,
        blocked_tasks: list[TaskSignal],
        overdue_tasks: list[TaskSignal],
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
            signals.append(
                f"{len(blocked_tasks)} blocked задач, главный блокер: {head.title}"
            )
        if overdue_tasks:
            max_delay = max(task.overdue_days for task in overdue_tasks)
            signals.append(f"{len(overdue_tasks)} просроченных задач, максимальная просрочка {max_delay} дней")
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
            signals.append(
                f"Перегруз ресурсов до {head.total_allocation_percent}%, ресурс: {head.full_name}"
            )
        if delayed_communications:
            head = delayed_communications[0]
            signals.append(
                f"Задержка коммуникаций до {head.delay_days} дней, канал: {head.from_team} -> {head.to_team}"
            )
        if risky_dependencies:
            head = risky_dependencies[0]
            signals.append(f"{len(risky_dependencies)} рискованных зависимостей, ключевая: {head.depends_on}")
        if pending_decisions:
            signals.append(f"{len(pending_decisions)} управленческих решений ждут владельца")
        if open_change_requests:
            total_days = sum(item.impact_days for item in open_change_requests)
            total_budget = sum(item.impact_budget for item in open_change_requests)
            signals.append(f"{len(open_change_requests)} открытых change requests, impact {total_days} дней и {total_budget} бюджета")
        return signals or ["Критичных отклонений не найдено"]

    def _build_executive_summary(
        self,
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

    def _build_portfolio_signals(self, summaries: list[ProjectSummary]) -> list[str]:
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


def _is_done_task(task: Task) -> bool:
    return task.status.casefold() in DONE_TASK_STATUSES


def _is_blocked_task(task: Task) -> bool:
    return task.is_blocked or task.status.casefold() in BLOCKED_TASK_STATUSES


def _is_overdue_task(task: Task, as_of: date) -> bool:
    return not _is_done_task(task) and task.planned_due_date < as_of


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
