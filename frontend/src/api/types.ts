/**
 * TypeScript-типы API.
 *
 * Они один-в-один повторяют Pydantic-контракты backend
 * (`backend/app/schemas/project_summary.py`). Это слой только для чтения —
 * фронтенд не меняет контракты, а лишь типизирует то, что приходит.
 *
 * Даты передаются как ISO-строки (`YYYY-MM-DD`), поэтому здесь они имеют тип
 * `string`; форматирование выполняется в `lib/format.ts`.
 */

export type RiskLevel = "green" | "yellow" | "red";

export interface TaskSignal {
  id: string;
  external_id: string;
  title: string;
  status: string;
  priority: string;
  planned_due_date: string;
  overdue_days: number;
  assignee_name: string;
  blocker_reason: string | null;
}

export interface BudgetSummary {
  planned_budget: number;
  actual_spent: number;
  forecast_total_spent: number;
  expected_economic_effect: number;
  cost_of_delay_per_day: number;
  currency: string;
  budget_deviation_percent: number;
  roi_percent: number;
  risk_adjusted_roi_percent: number;
}

export interface RiskSignal {
  id: string;
  risk_type: string;
  description: string;
  probability: number;
  impact: number;
  score: number;
  status: string;
  owner_name: string;
  linked_task_id: string | null;
}

export interface CommunicationSignal {
  id: string;
  from_team: string;
  to_team: string;
  topic: string;
  status: string;
  importance: string;
  expected_response_date: string;
  delay_days: number;
  linked_task_id: string | null;
}

export interface ResourceLoadSignal {
  resource_id: string;
  full_name: string;
  role: string;
  team: string;
  available_hours_per_week: number;
  project_actual_hours_per_week: number;
  total_actual_hours_per_week: number;
  total_allocation_percent: number;
  overload_percent: number;
}

export interface DependencySignal {
  id: string;
  dependency_type: string;
  depends_on: string;
  owner_team: string;
  expected_date: string;
  status: string;
  criticality: string;
  linked_task_id: string | null;
  delay_days: number;
}

export interface DecisionSignal {
  id: string;
  decision_type: string;
  description: string;
  decision_owner: string;
  status: string;
  decision_date: string;
}

export interface ChangeRequestSignal {
  id: string;
  change_type: string;
  requested_by: string;
  status: string;
  impact_budget: number;
  impact_days: number;
  description: string;
}

export interface ProjectSummary {
  project_id: string;
  project_name: string;
  owner_name: string;
  status: string;
  priority: string;
  as_of_date: string;

  completion_percent: number;
  total_tasks_count: number;
  completed_tasks_count: number;
  overdue_tasks_count: number;
  blocked_tasks_count: number;
  high_risk_count: number;
  dependency_risk_count: number;
  pending_decision_count: number;
  open_change_request_count: number;

  budget: BudgetSummary | null;
  resource_overload_percent: number;
  max_communication_delay_days: number;
  project_health_score: number;
  risk_level: RiskLevel;

  executive_summary: string;
  key_signals: string[];
  blocked_tasks: TaskSignal[];
  overdue_tasks: TaskSignal[];
  top_risks: RiskSignal[];
  delayed_communications: CommunicationSignal[];
  overloaded_resources: ResourceLoadSignal[];
  risky_dependencies: DependencySignal[];
  pending_decisions: DecisionSignal[];
  open_change_requests: ChangeRequestSignal[];
}

export interface PortfolioProjectSummary {
  project_id: string;
  project_name: string;
  owner_name: string;
  status: string;
  priority: string;
  project_health_score: number;
  risk_level: RiskLevel;
  completion_percent: number;
  overdue_tasks_count: number;
  blocked_tasks_count: number;
  high_risk_count: number;
  budget_deviation_percent: number | null;
  resource_overload_percent: number;
  top_signals: string[];
}

export interface PortfolioSummary {
  as_of_date: string;
  projects_count: number;
  red_projects_count: number;
  yellow_projects_count: number;
  green_projects_count: number;
  portfolio_health_score: number;
  top_portfolio_signals: string[];
  projects: PortfolioProjectSummary[];
}
