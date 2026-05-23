from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class TaskSignal(BaseModel):
    id: str
    external_id: str
    title: str
    status: str
    priority: str
    planned_due_date: date
    overdue_days: int
    assignee_name: str
    blocker_reason: str | None = None


class MilestoneSignal(BaseModel):
    id: str
    name: str
    status: str
    planned_end_date: date
    delay_days: int
    responsible_team: str


class BudgetSummary(BaseModel):
    planned_budget: int
    actual_spent: int
    forecast_total_spent: int
    expected_economic_effect: int
    cost_of_delay_per_day: int
    currency: str
    budget_deviation_percent: float
    roi_percent: float
    risk_adjusted_roi_percent: float


class RiskSignal(BaseModel):
    id: str
    risk_type: str
    description: str
    probability: int
    impact: int
    score: int
    status: str
    owner_name: str
    linked_task_id: str | None = None


class CommunicationSignal(BaseModel):
    id: str
    from_team: str
    to_team: str
    topic: str
    status: str
    importance: str
    expected_response_date: date
    delay_days: int
    linked_task_id: str | None = None


class ResourceLoadSignal(BaseModel):
    resource_id: str
    full_name: str
    role: str
    team: str
    available_hours_per_week: int
    project_actual_hours_per_week: int
    total_actual_hours_per_week: int
    total_allocation_percent: float
    overload_percent: float


class DependencySignal(BaseModel):
    id: str
    dependency_type: str
    depends_on: str
    owner_team: str
    expected_date: date
    status: str
    criticality: str
    linked_task_id: str | None = None
    delay_days: int


class DecisionSignal(BaseModel):
    id: str
    decision_type: str
    description: str
    decision_owner: str
    status: str
    decision_date: date


class ChangeRequestSignal(BaseModel):
    id: str
    change_type: str
    requested_by: str
    status: str
    impact_budget: int
    impact_days: int
    description: str


class OwnerActionLoadSignal(BaseModel):
    owner_name: str
    owner_type: str
    action_count: int
    blocked_tasks_count: int = 0
    overdue_tasks_count: int = 0
    dependency_count: int = 0
    decision_count: int = 0
    change_request_count: int = 0
    communication_count: int = 0


class ProjectSummary(BaseModel):
    project_id: str
    project_name: str
    owner_name: str
    status: str
    priority: str
    as_of_date: date

    completion_percent: float
    total_tasks_count: int
    completed_tasks_count: int
    overdue_tasks_count: int
    delayed_milestones_count: int
    blocked_tasks_count: int
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
    project_health_score: int = Field(ge=0, le=100)
    risk_level: str

    executive_summary: str
    key_signals: list[str]
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


class PortfolioProjectSummary(BaseModel):
    project_id: str
    project_name: str
    owner_name: str
    status: str
    priority: str
    project_health_score: int
    risk_level: str
    completion_percent: float
    overdue_tasks_count: int
    blocked_tasks_count: int
    high_risk_count: int
    budget_deviation_percent: float | None
    resource_overload_percent: float
    top_signals: list[str]


class PortfolioSummary(BaseModel):
    as_of_date: date
    projects_count: int
    red_projects_count: int
    yellow_projects_count: int
    green_projects_count: int
    portfolio_health_score: int
    top_portfolio_signals: list[str]
    projects: list[PortfolioProjectSummary]
