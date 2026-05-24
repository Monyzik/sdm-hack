from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Iterable

from backend.app.database.models import Task, TaskDependency
from backend.app.schemas.project_summary import (
    PortfolioAttentionProject,
    PortfolioAttentionSignal,
    PortfolioAttentionSummary,
    PortfolioProjectSummary,
    PortfolioSummary,
    ProblemTaskFact,
    ProjectFact,
    ProjectMetricsFact,
    ProjectProblemContext,
    ProjectSummary,
    TaskCommentFact,
    TaskDependencyEdgeFact,
    TaskHistoryFact,
)
from backend.app.services.metrics import (
    build_portfolio_signals,
    calculate_portfolio_health_score,
    calculate_project_metrics,
    infer_as_of_date,
)
from backend.app.services.project_summary_repository import ProjectSummaryRepository, ProjectSummarySource


OPEN_COMMUNICATION_STATUSES = {"pending", "delayed", "escalated"}
OPEN_CHANGE_REQUEST_STATUSES = {"pending", "under_review", "proposed"}
OPEN_DECISION_STATUSES = {"pending", "under_review"}
PRIORITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class ProjectSummaryService:
    def __init__(self, repository: ProjectSummaryRepository) -> None:
        self._repository = repository

    def build_project_summary(self, project_id: str, as_of: date | None = None) -> ProjectSummary:
        source = self._repository.get_project_source(project_id)
        metrics = calculate_project_metrics(source, as_of=as_of)

        return ProjectSummary(
            project_id=source.project.id,
            project_name=source.project.name,
            lifecycle_status=source.project.lifecycle_status,
            priority=source.project.priority,
            as_of_date=metrics.as_of_date,
            completion_percent=metrics.completion_percent,
            total_tasks_count=metrics.total_tasks_count,
            completed_tasks_count=metrics.completed_tasks_count,
            overdue_tasks_count=metrics.overdue_tasks_count,
            delayed_milestones_count=metrics.delayed_milestones_count,
            blocked_tasks_count=metrics.blocked_tasks_count,
            high_risk_count=metrics.high_risk_count,
            dependency_risk_count=metrics.dependency_risk_count,
            pending_decision_count=metrics.pending_decision_count,
            open_change_request_count=metrics.open_change_request_count,
            dependency_sla_breach_count=metrics.dependency_sla_breach_count,
            budget=metrics.budget,
            milestone_slip_days=metrics.milestone_slip_days,
            critical_path_delay_days=metrics.critical_path_delay_days,
            blocked_age_days=metrics.blocked_age_days,
            decision_age_days=metrics.decision_age_days,
            net_change_request_impact_days=metrics.net_change_request_impact_days,
            net_change_request_impact_budget=metrics.net_change_request_impact_budget,
            scope_churn_rate=metrics.scope_churn_rate,
            burn_rate_percent=metrics.burn_rate_percent,
            schedule_variance_percent=metrics.schedule_variance_percent,
            stale_tasks_count=metrics.stale_tasks_count,
            max_status_age_days=metrics.max_status_age_days,
            estimate_overrun_percent=metrics.estimate_overrun_percent,
            workload_imbalance_index=metrics.workload_imbalance_index,
            key_person_dependency_percent=metrics.key_person_dependency_percent,
            critical_task_silence_days=metrics.critical_task_silence_days,
            communication_silence_days=metrics.communication_silence_days,
            data_freshness_days=metrics.data_freshness_days,
            cost_of_delay_exposure=metrics.cost_of_delay_exposure,
            risk_trend=metrics.risk_trend,
            resource_overload_percent=metrics.resource_overload_percent,
            max_communication_delay_days=metrics.max_communication_delay_days,
            project_health_score=metrics.project_health_score,
            risk_level=metrics.risk_level,
            executive_summary=metrics.executive_summary,
            key_signals=metrics.key_signals,
            blocked_tasks=metrics.blocked_tasks[:7],
            overdue_tasks=metrics.overdue_tasks[:7],
            delayed_milestones=metrics.delayed_milestones[:7],
            top_risks=metrics.top_risks[:7],
            delayed_communications=metrics.delayed_communications[:7],
            overloaded_resources=metrics.overloaded_resources[:7],
            risky_dependencies=metrics.risky_dependencies[:7],
            pending_decisions=metrics.pending_decisions[:7],
            open_change_requests=metrics.open_change_requests[:7],
            owner_action_load=metrics.owner_action_load[:7],
        )

    def build_project_problem_context(
        self,
        project_id: str,
        as_of: date | None = None,
        max_depth: int = 2,
    ) -> ProjectProblemContext:
        source = self._repository.get_project_source(project_id)
        metrics = calculate_project_metrics(source, as_of=as_of)
        max_depth = min(max(max_depth, 1), 4)

        tasks_by_id = {task.id: task for task in source.tasks}
        problem_task_ids = {
            signal.id for signal in [*metrics.blocked_tasks, *metrics.overdue_tasks]
        }
        problem_tasks = _sort_problem_tasks(
            task for task_id, task in tasks_by_id.items() if task_id in problem_task_ids
        )

        dependency_edges = _build_task_dependency_edges(
            source=source,
            root_task_ids=[task.id for task in problem_tasks],
            max_depth=max_depth,
        )
        context_task_ids = {task.id for task in problem_tasks}
        for edge in dependency_edges:
            context_task_ids.add(edge.task_id)
            context_task_ids.add(edge.depends_on_task_id)

        linked_risks = [
            risk for risk in metrics.top_risks
            if risk.linked_task_id in context_task_ids or risk.score >= 15
        ]
        linked_communications = [
            communication for communication in metrics.delayed_communications
            if communication.linked_task_id in context_task_ids or communication.delay_days > 0
        ]
        linked_project_dependencies = [
            dependency for dependency in metrics.risky_dependencies
            if dependency.linked_task_id in context_task_ids
            or dependency.criticality.casefold() in {"critical", "high"}
        ]
        recent_task_history = [
            TaskHistoryFact(
                id=item.id,
                task_id=item.task_id,
                changed_at=item.changed_at,
                field_changed=item.field_changed,
                old_value=item.old_value,
                new_value=item.new_value,
                changed_by=item.changed_by,
                source_system=item.source_system,
            )
            for item in source.task_history
            if item.task_id in context_task_ids
        ][:20]
        recent_task_comments = [
            TaskCommentFact(
                id=item.id,
                task_id=item.task_id,
                author_id=item.author_id,
                author_name=item.author_name,
                created_at=item.created_at,
                channel=item.channel,
                text=item.text,
                mentions_count=item.mentions_count,
                source_system=item.source_system,
            )
            for item in source.task_comments
            if item.task_id in context_task_ids
        ][:20]

        return ProjectProblemContext(
            project=ProjectFact(
                id=source.project.id,
                name=source.project.name,
                lifecycle_status=source.project.lifecycle_status,
                priority=source.project.priority,
                start_date=source.project.start_date,
                planned_end_date=source.project.planned_end_date,
                business_goal=source.project.business_goal,
                expected_result=source.project.expected_result,
                business_value=source.project.business_value,
            ),
            as_of_date=metrics.as_of_date,
            metrics=ProjectMetricsFact(
                completion_percent=metrics.completion_percent,
                total_tasks_count=metrics.total_tasks_count,
                completed_tasks_count=metrics.completed_tasks_count,
                overdue_tasks_count=metrics.overdue_tasks_count,
                delayed_milestones_count=metrics.delayed_milestones_count,
                blocked_tasks_count=metrics.blocked_tasks_count,
                high_risk_count=metrics.high_risk_count,
                dependency_risk_count=metrics.dependency_risk_count,
                pending_decision_count=metrics.pending_decision_count,
                open_change_request_count=metrics.open_change_request_count,
                dependency_sla_breach_count=metrics.dependency_sla_breach_count,
                budget_deviation_percent=metrics.budget.budget_deviation_percent if metrics.budget else None,
                milestone_slip_days=metrics.milestone_slip_days,
                critical_path_delay_days=metrics.critical_path_delay_days,
                blocked_age_days=metrics.blocked_age_days,
                decision_age_days=metrics.decision_age_days,
                net_change_request_impact_days=metrics.net_change_request_impact_days,
                net_change_request_impact_budget=metrics.net_change_request_impact_budget,
                scope_churn_rate=metrics.scope_churn_rate,
                burn_rate_percent=metrics.burn_rate_percent,
                schedule_variance_percent=metrics.schedule_variance_percent,
                stale_tasks_count=metrics.stale_tasks_count,
                max_status_age_days=metrics.max_status_age_days,
                estimate_overrun_percent=metrics.estimate_overrun_percent,
                workload_imbalance_index=metrics.workload_imbalance_index,
                key_person_dependency_percent=metrics.key_person_dependency_percent,
                critical_task_silence_days=metrics.critical_task_silence_days,
                communication_silence_days=metrics.communication_silence_days,
                data_freshness_days=metrics.data_freshness_days,
                cost_of_delay_exposure=metrics.cost_of_delay_exposure,
                risk_trend=metrics.risk_trend,
                resource_overload_percent=metrics.resource_overload_percent,
                max_communication_delay_days=metrics.max_communication_delay_days,
                project_health_score=metrics.project_health_score,
                risk_level=metrics.risk_level,
            ),
            budget=metrics.budget,
            problem_tasks=[_problem_task_fact(task, metrics.as_of_date) for task in problem_tasks],
            task_dependency_edges=dependency_edges,
            linked_risks=linked_risks[:20],
            linked_communications=linked_communications[:20],
            linked_project_dependencies=linked_project_dependencies[:20],
            pending_decisions=metrics.pending_decisions[:20],
            open_change_requests=metrics.open_change_requests[:20],
            overloaded_resources=metrics.overloaded_resources[:20],
            recent_task_history=recent_task_history,
            recent_task_comments=recent_task_comments,
        )

    def build_portfolio_summary(self, as_of: date | None = None) -> PortfolioSummary:
        project_ids = [project.id for project in self._repository.list_projects()]
        project_summaries = [self.build_project_summary(project_id, as_of=as_of) for project_id in project_ids]
        portfolio_as_of = max((summary.as_of_date for summary in project_summaries), default=date.today())

        compact_projects = [
            PortfolioProjectSummary(
                project_id=summary.project_id,
                project_name=summary.project_name,
                lifecycle_status=summary.lifecycle_status,
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

        return PortfolioSummary(
            as_of_date=portfolio_as_of,
            projects_count=len(project_summaries),
            red_projects_count=red_count,
            yellow_projects_count=yellow_count,
            green_projects_count=green_count,
            portfolio_health_score=calculate_portfolio_health_score(project_summaries),
            top_portfolio_signals=build_portfolio_signals(project_summaries),
            projects=compact_projects,
        )

    def build_portfolio_attention(
        self,
        as_of: date | None = None,
        lookback_days: int = 7,
    ) -> PortfolioAttentionSummary:
        sources = [
            self._repository.get_project_source(project.id)
            for project in self._repository.list_projects()
        ]
        as_of_date = as_of or max(
            (infer_as_of_date(source) for source in sources),
            default=date.today(),
        )
        lookback_days = min(max(lookback_days, 1), 30)
        window_start = as_of_date - timedelta(days=lookback_days)
        window_start_at = datetime.combine(window_start, time.min)
        window_end_at = datetime.combine(as_of_date, time.max)

        project_summaries = {
            source.project.id: self.build_project_summary(source.project.id, as_of=as_of_date)
            for source in sources
        }
        signals: list[PortfolioAttentionSignal] = []

        for source in sources:
            tasks_by_id = {task.id: task for task in source.tasks}

            def add_signal(
                *,
                signal_id: str,
                occurred_at: datetime,
                signal_type: str,
                severity: str,
                title: str,
                description: str,
                recommended_action: str,
                evidence_ids: list[str],
            ) -> None:
                signals.append(
                    PortfolioAttentionSignal(
                        id=signal_id,
                        project_id=source.project.id,
                        project_name=source.project.name,
                        occurred_at=occurred_at,
                        signal_type=signal_type,
                        severity=severity,
                        title=title,
                        description=description,
                        recommended_action=recommended_action,
                        evidence_ids=evidence_ids,
                    )
                )

            for item in source.task_history:
                if not (window_start_at <= item.changed_at <= window_end_at):
                    continue

                task = tasks_by_id.get(item.task_id)
                task_title = task.title if task else item.task_id
                if item.field_changed == "status" and item.new_value.casefold() == "blocked":
                    add_signal(
                        signal_id=f"attention-{item.id}",
                        occurred_at=item.changed_at,
                        signal_type="task_blocked",
                        severity="critical",
                        title="Новая блокировка задачи",
                        description=f"Задача «{task_title}» перешла в блокировку.",
                        recommended_action="Проверить владельца блокера и срок ответа.",
                        evidence_ids=[item.id, item.task_id],
                    )
                elif item.field_changed == "planned_due_date":
                    add_signal(
                        signal_id=f"attention-{item.id}",
                        occurred_at=item.changed_at,
                        signal_type="due_date_changed",
                        severity="warning",
                        title="Сдвинулся срок задачи",
                        description=f"По задаче «{task_title}» изменился плановый срок.",
                        recommended_action="Проверить влияние на ближайшую веху и зависимые команды.",
                        evidence_ids=[item.id, item.task_id],
                    )
                elif item.field_changed in {"estimated_hours", "spent_hours"}:
                    add_signal(
                        signal_id=f"attention-{item.id}",
                        occurred_at=item.changed_at,
                        signal_type="effort_changed",
                        severity="warning",
                        title="Изменилась трудоемкость",
                        description=f"По задаче «{task_title}» изменились часы исполнения.",
                        recommended_action="Сверить рост трудоемкости с ресурсным планом и бюджетным прогнозом.",
                        evidence_ids=[item.id, item.task_id],
                    )

            for item in source.communication_messages:
                if not (window_start_at <= item.message_time <= window_end_at) or not item.is_escalation:
                    continue
                add_signal(
                    signal_id=f"attention-{item.id}",
                    occurred_at=item.message_time,
                    signal_type="communication_escalated",
                    severity="critical",
                    title="Появилась эскалация в коммуникациях",
                    description=item.summary,
                    recommended_action="Назначить ответственного за закрытие эскалации и срок следующего ответа.",
                    evidence_ids=[item.id, item.communication_id],
                )

            for item in source.change_requests:
                if not (window_start <= item.request_date <= as_of_date):
                    continue
                if item.status.casefold() not in OPEN_CHANGE_REQUEST_STATUSES:
                    continue
                severity = (
                    "critical"
                    if abs(item.requested_budget_delta) >= 4_000_000
                    or abs(item.requested_timeline_delta_days) >= 7
                    else "warning"
                )
                add_signal(
                    signal_id=f"attention-{item.id}",
                    occurred_at=_date_to_datetime(item.request_date),
                    signal_type="change_request_opened",
                    severity=severity,
                    title="Открыт change request",
                    description=item.description,
                    recommended_action="Принять или отклонить изменение, потому что оно меняет срок, бюджет или scope.",
                    evidence_ids=[item.id],
                )

            for item in source.communications:
                if item.status.casefold() not in OPEN_COMMUNICATION_STATUSES:
                    continue
                if not (window_start <= item.expected_response_date < as_of_date):
                    continue
                delay_days = max(0, (as_of_date - item.expected_response_date).days)
                severity = "critical" if delay_days >= 7 or item.importance.casefold() == "critical" else "warning"
                add_signal(
                    signal_id=f"attention-{item.id}",
                    occurred_at=_date_to_datetime(item.expected_response_date),
                    signal_type="communication_overdue",
                    severity=severity,
                    title="Просрочен ответ по коммуникации",
                    description=f"{item.from_team} ожидает ответ от {item.to_team}: {item.topic}.",
                    recommended_action="Зафиксировать срок ответа или поднять вопрос владельцу зависимости.",
                    evidence_ids=[item.id],
                )

            for item in source.decisions:
                if item.status.casefold() not in OPEN_DECISION_STATUSES:
                    continue
                if not (window_start <= item.decision_date <= as_of_date):
                    continue
                add_signal(
                    signal_id=f"attention-{item.id}",
                    occurred_at=_date_to_datetime(item.decision_date),
                    signal_type="decision_pending",
                    severity="warning",
                    title="Зависло управленческое решение",
                    description=item.description,
                    recommended_action="Вынести решение руководителю проектов.",
                    evidence_ids=[item.id],
                )

        signals = sorted(
            signals,
            key=lambda item: (_severity_weight(item.severity), item.occurred_at, item.project_id),
            reverse=True,
        )
        signals_by_project: defaultdict[str, list[PortfolioAttentionSignal]] = defaultdict(list)
        for signal in signals:
            signals_by_project[signal.project_id].append(signal)

        projects_to_watch: list[PortfolioAttentionProject] = []
        for project_id, project_signals in signals_by_project.items():
            summary = project_summaries[project_id]
            top_signal = project_signals[0]
            projects_to_watch.append(
                PortfolioAttentionProject(
                    project_id=summary.project_id,
                    project_name=summary.project_name,
                    risk_level=summary.risk_level,
                    project_health_score=summary.project_health_score,
                    urgent_signals_count=len(project_signals),
                    top_reason=top_signal.title,
                    next_action=top_signal.recommended_action,
                )
            )

        projects_to_watch = sorted(
            projects_to_watch,
            key=lambda item: (
                max(_severity_weight(signal.severity) for signal in signals_by_project[item.project_id]),
                item.urgent_signals_count,
                -item.project_health_score,
            ),
            reverse=True,
        )

        return PortfolioAttentionSummary(
            as_of_date=as_of_date,
            lookback_days=lookback_days,
            total_signals_count=len(signals),
            critical_signals_count=sum(1 for signal in signals if signal.severity == "critical"),
            projects_to_watch=projects_to_watch,
            signals=signals[:20],
        )


def _problem_task_fact(task: Task, as_of: date) -> ProblemTaskFact:
    problem_flags: list[str] = []
    if task.is_blocked or task.status.casefold() == "blocked":
        problem_flags.append("blocked")
    if task.actual_end_date is None and task.status.casefold() not in {"done", "closed", "resolved"} and task.planned_due_date < as_of:
        problem_flags.append("overdue")

    return ProblemTaskFact(
        id=task.id,
        external_id=task.external_id,
        title=task.title,
        assignee_id=task.assignee_id,
        assignee_name=task.assignee_name,
        status=task.status,
        priority=task.priority,
        planned_due_date=task.planned_due_date,
        actual_end_date=task.actual_end_date,
        estimated_hours=task.estimated_hours,
        spent_hours=task.spent_hours,
        is_blocked=task.is_blocked or task.status.casefold() == "blocked",
        blocker_reason=task.blocker_reason or None,
        overdue_days=max(0, (as_of - task.planned_due_date).days),
        problem_flags=problem_flags,
    )


def _build_task_dependency_edges(
    *,
    source: ProjectSummarySource,
    root_task_ids: list[str],
    max_depth: int,
) -> list[TaskDependencyEdgeFact]:
    tasks_by_id = {task.id: task for task in source.tasks}
    upstream_by_task_id: defaultdict[str, list[TaskDependency]] = defaultdict(list)
    downstream_by_task_id: defaultdict[str, list[TaskDependency]] = defaultdict(list)

    for dependency in source.task_dependencies:
        upstream_by_task_id[dependency.task_id].append(dependency)
        downstream_by_task_id[dependency.depends_on_task_id].append(dependency)

    edge_facts: list[TaskDependencyEdgeFact] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(root_task_id: str, direction: str, depth: int, dependency: TaskDependency) -> None:
        key = (root_task_id, direction, dependency.id)
        if key in seen_edges:
            return
        seen_edges.add(key)
        task = tasks_by_id.get(dependency.task_id)
        depends_on_task = tasks_by_id.get(dependency.depends_on_task_id)
        edge_facts.append(
            TaskDependencyEdgeFact(
                id=dependency.id,
                root_task_id=root_task_id,
                direction=direction,
                depth=depth,
                task_id=dependency.task_id,
                task_title=task.title if task else dependency.task_id,
                depends_on_task_id=dependency.depends_on_task_id,
                depends_on_task_title=depends_on_task.title if depends_on_task else dependency.depends_on_task_id,
                dependency_type=dependency.dependency_type,
                is_critical_path=dependency.is_critical_path,
                lag_days=dependency.lag_days,
                reason=dependency.reason,
            )
        )

    def walk_upstream(root_task_id: str, current_task_id: str, depth: int) -> None:
        if depth > max_depth:
            return
        for dependency in upstream_by_task_id.get(current_task_id, []):
            add_edge(root_task_id, "upstream", depth, dependency)
            walk_upstream(root_task_id, dependency.depends_on_task_id, depth + 1)

    def walk_downstream(root_task_id: str, current_task_id: str, depth: int) -> None:
        if depth > max_depth:
            return
        for dependency in downstream_by_task_id.get(current_task_id, []):
            add_edge(root_task_id, "downstream", depth, dependency)
            walk_downstream(root_task_id, dependency.task_id, depth + 1)

    for root_task_id in root_task_ids:
        walk_upstream(root_task_id, root_task_id, 1)
        walk_downstream(root_task_id, root_task_id, 1)

    return sorted(
        edge_facts,
        key=lambda item: (
            item.root_task_id,
            item.direction,
            item.depth,
            item.is_critical_path,
            item.id,
        ),
        reverse=True,
    )


def _sort_problem_tasks(tasks: Iterable[Task]) -> list[Task]:
    return sorted(
        tasks,
        key=lambda task: (
            PRIORITY_WEIGHT.get(task.priority, 0),
            -task.planned_due_date.toordinal(),
            task.id,
        ),
        reverse=True,
    )


def _date_to_datetime(value: date) -> datetime:
    return datetime.combine(value, time(hour=12))


def _severity_weight(severity: str) -> int:
    return {"critical": 3, "warning": 2, "info": 1}.get(severity, 0)
