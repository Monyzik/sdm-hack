from __future__ import annotations

from datetime import date

from backend.app.schemas.project_summary import (
    PortfolioProjectSummary,
    PortfolioSummary,
    ProjectSummary,
)
from backend.app.services.metrics import (
    build_portfolio_signals,
    calculate_portfolio_health_score,
    calculate_project_metrics,
)
from backend.app.services.project_summary_repository import ProjectSummaryRepository


class ProjectSummaryService:
    def __init__(self, repository: ProjectSummaryRepository) -> None:
        self._repository = repository

    def build_project_summary(self, project_id: str, as_of: date | None = None) -> ProjectSummary:
        source = self._repository.get_project_source(project_id)
        metrics = calculate_project_metrics(source, as_of=as_of)

        return ProjectSummary(
            project_id=source.project.id,
            project_name=source.project.name,
            owner_name=source.project.owner_name,
            status=source.project.status,
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
            budget=metrics.budget,
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
