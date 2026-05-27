from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sdm.backend.database.models import (
    Budget,
    BudgetLineItem,
    ChangeRequest,
    Communication,
    CommunicationMessage,
    Decision,
    Milestone,
    Project,
    ProjectDependency,
    Resource,
    ResourceAllocation,
    Risk,
    Task,
    TaskComment,
    TaskDependency,
    TaskHistory,
)
from sdm.backend.schemas.project_summary import (
    BudgetSummary,
    ChangeRequestSignal,
    CommunicationSignal,
    DecisionSignal,
    DependencySignal,
    MilestoneSignal,
    OwnerActionLoadSignal,
    ResourceLoadSignal,
    RiskSignal,
    TaskSignal,
)


@dataclass(frozen=True)
class ProjectSummarySource:
    project: Project
    tasks: list[Task]
    task_history: list[TaskHistory]
    task_comments: list[TaskComment]
    milestones: list[Milestone]
    budget: Budget | None
    budget_line_items: list[BudgetLineItem]
    risks: list[Risk]
    communications: list[Communication]
    communication_messages: list[CommunicationMessage]
    project_allocations: list[ResourceAllocation]
    related_allocations: list[ResourceAllocation]
    resources_by_id: dict[str, Resource]
    task_dependencies: list[TaskDependency]
    dependencies: list[ProjectDependency]
    decisions: list[Decision]
    change_requests: list[ChangeRequest]


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
    dependency_sla_breach_count: int
    budget: BudgetSummary | None
    milestone_slip_days: int
    critical_path_delay_days: int
    blocked_age_days: int
    decision_age_days: int
    net_change_request_impact_days: int
    net_change_request_impact_budget: int
    scope_churn_rate: float
    burn_rate_percent: float
    schedule_variance_percent: float
    stale_tasks_count: int
    max_status_age_days: int
    estimate_overrun_percent: float
    workload_imbalance_index: float
    key_person_dependency_percent: float
    critical_task_silence_days: int
    communication_silence_days: int
    data_freshness_days: int
    cost_of_delay_exposure: int
    risk_trend: str
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
    owner_action_load: list[OwnerActionLoadSignal]
    key_signals: list[str]
    executive_summary: str
