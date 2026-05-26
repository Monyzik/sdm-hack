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
    ProjectTrendPoint,
    ProjectTrends,
    ResourceCostSignal,
    TaskCommentFact,
    TaskDependencyGraphEdge,
    TaskDependencyEdgeFact,
    TaskHistoryFact,
)
from backend.app.services.metrics import (
    build_portfolio_signals,
    calculate_portfolio_health_score,
    calculate_project_metrics,
    infer_as_of_date,
    normalize_priority,
    normalize_status,
    project_metrics_fact_payload,
    project_summary_payload,
)
from backend.app.services.data_classes import ProjectSummarySource
from backend.app.services.protocols import ProjectSummaryReader


OPEN_COMMUNICATION_STATUSES = {"pending", "delayed", "escalated"}
OPEN_CHANGE_REQUEST_STATUSES = {"pending", "under_review", "proposed"}
OPEN_DECISION_STATUSES = {"pending", "under_review"}
PRIORITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class ProjectSummaryService:
    def __init__(self, repository: ProjectSummaryReader) -> None:
        self._repository = repository

    async def build_project_summary(self, project_id: str, as_of: date | None = None) -> ProjectSummary:
        source = await self._repository.get_project_source(project_id)
        return _build_project_summary_from_source(source, as_of=as_of)

    async def build_project_trends(
        self,
        project_id: str,
        as_of: date | None = None,
        points: int = 8,
    ) -> ProjectTrends:
        source = await self._repository.get_project_source(project_id)
        end_date = as_of or infer_as_of_date(source)
        trend_dates = _trend_dates(source.project.start_date, end_date, points)

        return ProjectTrends(
            project_id=source.project.id,
            project_name=source.project.name,
            points=[
                _project_trend_point(source=source, as_of=trend_date)
                for trend_date in trend_dates
            ],
        )

    async def build_project_problem_context(
        self,
        project_id: str,
        as_of: date | None = None,
        max_depth: int = 2,
    ) -> ProjectProblemContext:
        source = await self._repository.get_project_source(project_id)
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
            or normalize_priority(dependency.criticality) in {"critical", "high"}
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
            metrics=ProjectMetricsFact(**project_metrics_fact_payload(metrics)),
            budget=metrics.budget,
            problem_tasks=[_problem_task_fact(task, metrics.as_of_date) for task in problem_tasks],
            task_dependency_edges=dependency_edges,
            linked_risks=linked_risks[:20],
            linked_communications=linked_communications[:20],
            linked_project_dependencies=linked_project_dependencies[:20],
            pending_decisions=metrics.pending_decisions[:20],
            open_change_requests=metrics.open_change_requests[:20],
            project_resources=_build_project_resources(source),
            task_dependency_graph=_build_task_dependency_graph(source),
            overloaded_resources=metrics.overloaded_resources[:20],
            recent_task_history=recent_task_history,
            recent_task_comments=recent_task_comments,
        )

    async def build_portfolio_summary(self, as_of: date | None = None) -> PortfolioSummary:
        sources = await self._project_sources()
        project_summaries = [
            _build_project_summary_from_source(source, as_of=as_of)
            for source in sources
        ]
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

    async def build_portfolio_attention(
        self,
        as_of: date | None = None,
        lookback_days: int = 7,
    ) -> PortfolioAttentionSummary:
        sources = await self._project_sources()
        as_of_date = as_of or max(
            (infer_as_of_date(source) for source in sources),
            default=date.today(),
        )
        lookback_days = min(max(lookback_days, 1), 30)
        window_start = as_of_date - timedelta(days=lookback_days)
        window_start_at = datetime.combine(window_start, time.min)
        window_end_at = datetime.combine(as_of_date, time.max)

        project_summaries = {
            source.project.id: _build_project_summary_from_source(source, as_of=as_of_date)
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
                if item.field_changed == "status" and normalize_status(item.new_value) == "blocked":
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
                    title="Нужно решение по коммуникациям",
                    description=item.summary,
                    recommended_action="Назначить ответственного за ответ и срок следующего контакта.",
                    evidence_ids=[item.id, item.communication_id],
                )

            for item in source.change_requests:
                if not (window_start <= item.request_date <= as_of_date):
                    continue
                if normalize_status(item.status) not in OPEN_CHANGE_REQUEST_STATUSES:
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
                    title="Открыт запрос на изменение",
                    description=item.description,
                    recommended_action="Принять или отклонить изменение, потому что оно меняет срок, бюджет или scope.",
                    evidence_ids=[item.id],
                )

            for item in source.communications:
                if normalize_status(item.status) not in OPEN_COMMUNICATION_STATUSES:
                    continue
                if not (window_start <= item.expected_response_date < as_of_date):
                    continue
                delay_days = max(0, (as_of_date - item.expected_response_date).days)
                severity = "critical" if delay_days >= 7 or normalize_priority(item.importance) == "critical" else "warning"
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
                if normalize_status(item.status) not in OPEN_DECISION_STATUSES:
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

    async def _project_sources(self) -> list[ProjectSummarySource]:
        sources: list[ProjectSummarySource] = []
        for project in await self._repository.list_projects():
            sources.append(await self._repository.get_project_source(project.id))
        return sources


def _build_project_summary_from_source(source: ProjectSummarySource, as_of: date | None = None) -> ProjectSummary:
    metrics = calculate_project_metrics(source, as_of=as_of)

    return ProjectSummary(
        project_id=source.project.id,
        project_name=source.project.name,
        lifecycle_status=source.project.lifecycle_status,
        priority=source.project.priority,
        **project_summary_payload(metrics),
    )


def _problem_task_fact(task: Task, as_of: date) -> ProblemTaskFact:
    problem_flags: list[str] = []
    if task.is_blocked or normalize_status(task.status) == "blocked":
        problem_flags.append("blocked")
    if task.actual_end_date is None and normalize_status(task.status) not in {"done", "closed", "resolved"} and task.planned_due_date < as_of:
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
        is_blocked=task.is_blocked or normalize_status(task.status) == "blocked",
        blocker_reason=task.blocker_reason or None,
        overdue_days=max(0, (as_of - task.planned_due_date).days),
        problem_flags=problem_flags,
    )


def _build_project_resources(source: ProjectSummarySource) -> list[ResourceCostSignal]:
    planned_by_resource: defaultdict[str, int] = defaultdict(int)
    actual_by_resource: defaultdict[str, int] = defaultdict(int)
    for allocation in source.project_allocations:
        planned_by_resource[allocation.resource_id] += allocation.planned_hours_per_week
        actual_by_resource[allocation.resource_id] += allocation.actual_hours_per_week

    result: list[ResourceCostSignal] = []
    for resource_id in sorted(planned_by_resource):
        resource = source.resources_by_id.get(resource_id)
        if resource is None:
            continue
        weekly_cost = actual_by_resource[resource_id] * resource.hour_rate
        result.append(
            ResourceCostSignal(
                resource_id=resource.id,
                full_name=resource.full_name,
                role=resource.role,
                team=resource.team,
                seniority=resource.seniority,
                hour_rate=resource.hour_rate,
                available_hours_per_week=resource.available_hours_per_week,
                project_planned_hours_per_week=planned_by_resource[resource_id],
                project_actual_hours_per_week=actual_by_resource[resource_id],
                weekly_project_cost=weekly_cost,
                daily_project_cost=round(weekly_cost / 5),
            )
        )
    return result


def _build_task_dependency_graph(source: ProjectSummarySource) -> list[TaskDependencyGraphEdge]:
    tasks_by_id = {task.id: task for task in source.tasks}
    result: list[TaskDependencyGraphEdge] = []
    for dependency in source.task_dependencies:
        task = tasks_by_id.get(dependency.task_id)
        depends_on_task = tasks_by_id.get(dependency.depends_on_task_id)
        if task is None or depends_on_task is None:
            continue
        result.append(
            TaskDependencyGraphEdge(
                id=dependency.id,
                task_id=dependency.task_id,
                task_title=task.title,
                depends_on_task_id=dependency.depends_on_task_id,
                depends_on_task_title=depends_on_task.title,
                dependency_type=dependency.dependency_type,
                is_critical_path=dependency.is_critical_path,
                lag_days=dependency.lag_days,
                reason=dependency.reason,
            )
        )
    return result


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
            PRIORITY_WEIGHT.get(normalize_priority(task.priority), 0),
            -task.planned_due_date.toordinal(),
            task.id,
        ),
        reverse=True,
    )


def _trend_dates(start_date: date, end_date: date, points: int) -> list[date]:
    points = min(max(points, 2), 12)
    if start_date >= end_date:
        return [end_date]

    total_days = max(1, (end_date - start_date).days)
    dates: list[date] = []
    for index in range(points):
        offset = round(total_days * index / (points - 1))
        trend_date = start_date + timedelta(days=offset)
        if not dates or dates[-1] != trend_date:
            dates.append(trend_date)
    if dates[-1] != end_date:
        dates[-1] = end_date
    return dates


def _project_trend_point(source: ProjectSummarySource, as_of: date) -> ProjectTrendPoint:
    total_tasks_count = len(source.tasks)
    completed_tasks_count = sum(
        1
        for task in source.tasks
        if task.actual_end_date is not None and task.actual_end_date <= as_of
    )
    high_risk_score_sum = sum(
        risk.probability * risk.impact
        for risk in source.risks
        if risk.probability * risk.impact >= 15
        and risk.status.casefold() in {"active", "escalated", "mitigating", "open"}
    )
    high_risk_count = sum(
        1
        for risk in source.risks
        if risk.probability * risk.impact >= 15
        and risk.status.casefold() in {"active", "escalated", "mitigating", "open"}
    )
    dependency_sla_breach_count = sum(
        1
        for dependency in source.dependencies
        if dependency.status.casefold() in {"pending", "delayed", "blocked"}
        and dependency.expected_date < as_of
    )
    overdue_problem_count = sum(
        1
        for task in source.tasks
        if task.actual_end_date is None and task.planned_due_date < as_of
    )
    resource_overload_percent = _trend_resource_overload_percent(source)
    risk_pressure_score = min(
        100,
        round(
            high_risk_score_sum * 1.4
            + dependency_sla_breach_count * 8
            + overdue_problem_count * 1.5
            + resource_overload_percent * 0.25
        ),
    )
    return ProjectTrendPoint(
        as_of_date=as_of,
        completion_percent=round(
            (completed_tasks_count / total_tasks_count * 100) if total_tasks_count else 0,
            1,
        ),
        completed_tasks_count=completed_tasks_count,
        high_risk_count=high_risk_count,
        risk_pressure_score=risk_pressure_score,
        dependency_sla_breach_count=dependency_sla_breach_count,
        resource_overload_percent=resource_overload_percent,
    )


def _trend_resource_overload_percent(source: ProjectSummarySource) -> float:
    resources_by_id = source.resources_by_id
    actual_hours_by_resource: dict[str, int] = defaultdict(int)
    for allocation in source.related_allocations:
        actual_hours_by_resource[allocation.resource_id] += allocation.actual_hours_per_week

    overloaded = 0
    total = 0
    for resource_id, actual_hours in actual_hours_by_resource.items():
        resource = resources_by_id.get(resource_id)
        if resource is None:
            continue
        total += 1
        if actual_hours > resource.available_hours_per_week:
            overloaded += 1
    return round((overloaded / total * 100) if total else 0, 1)


def _date_to_datetime(value: date) -> datetime:
    return datetime.combine(value, time(hour=12))


def _severity_weight(severity: str) -> int:
    return {"critical": 3, "warning": 2, "info": 1}.get(severity, 0)
