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

export interface ProblemTaskFact {
  id: string;
  external_id: string;
  title: string;
  assignee_id: string;
  assignee_name: string;
  status: string;
  priority: string;
  planned_due_date: string;
  actual_end_date: string | null;
  estimated_hours: number;
  spent_hours: number;
  is_blocked: boolean;
  blocker_reason: string | null;
  overdue_days: number;
  problem_flags: string[];
}

export interface MilestoneSignal {
  id: string;
  name: string;
  status: string;
  planned_end_date: string;
  delay_days: number;
  responsible_team: string;
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
  requested_budget_delta: number;
  requested_timeline_delta_days: number;
  description: string;
}

export interface OwnerActionLoadSignal {
  owner_name: string;
  owner_type: string;
  action_count: number;
  blocked_tasks_count: number;
  overdue_tasks_count: number;
  dependency_count: number;
  decision_count: number;
  change_request_count: number;
  communication_count: number;
}

export interface TaskDependencyGraphEdge {
  id: string;
  task_id: string;
  task_title: string;
  depends_on_task_id: string;
  depends_on_task_title: string;
  dependency_type: string;
  is_critical_path: boolean;
  lag_days: number;
  reason: string;
}

export interface ProjectProblemContext {
  as_of_date: string;
  problem_tasks: ProblemTaskFact[];
  task_dependency_graph: TaskDependencyGraphEdge[];
}

export interface ProjectSummary {
  project_id: string;
  project_name: string;
  lifecycle_status: string;
  priority: string;
  as_of_date: string;

  completion_percent: number;
  total_tasks_count: number;
  completed_tasks_count: number;
  overdue_tasks_count: number;
  delayed_milestones_count: number;
  blocked_tasks_count: number;
  high_risk_count: number;
  dependency_risk_count: number;
  pending_decision_count: number;
  open_change_request_count: number;
  dependency_sla_breach_count: number;

  budget: BudgetSummary | null;
  milestone_slip_days: number;
  critical_path_delay_days: number;
  blocked_age_days: number;
  decision_age_days: number;
  net_change_request_impact_days: number;
  net_change_request_impact_budget: number;
  scope_churn_rate: number;
  burn_rate_percent: number;
  schedule_variance_percent: number;
  stale_tasks_count: number;
  max_status_age_days: number;
  estimate_overrun_percent: number;
  workload_imbalance_index: number;
  key_person_dependency_percent: number;
  critical_task_silence_days: number;
  communication_silence_days: number;
  data_freshness_days: number;
  cost_of_delay_exposure: number;
  risk_trend: string;
  resource_overload_percent: number;
  max_communication_delay_days: number;
  project_health_score: number;
  risk_level: RiskLevel;

  executive_summary: string;
  key_signals: string[];
  blocked_tasks: TaskSignal[];
  overdue_tasks: TaskSignal[];
  delayed_milestones: MilestoneSignal[];
  top_risks: RiskSignal[];
  delayed_communications: CommunicationSignal[];
  overloaded_resources: ResourceLoadSignal[];
  risky_dependencies: DependencySignal[];
  pending_decisions: DecisionSignal[];
  open_change_requests: ChangeRequestSignal[];
  owner_action_load: OwnerActionLoadSignal[];
}

export interface ProjectTrendPoint {
  as_of_date: string;
  completion_percent: number;
  completed_tasks_count: number;
  high_risk_count: number;
  risk_pressure_score: number;
  dependency_sla_breach_count: number;
  resource_overload_percent: number;
}

export interface ProjectTrends {
  project_id: string;
  project_name: string;
  points: ProjectTrendPoint[];
}

export interface PortfolioProjectSummary {
  project_id: string;
  project_name: string;
  lifecycle_status: string;
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

export interface PortfolioAttentionProject {
  project_id: string;
  project_name: string;
  risk_level: RiskLevel;
  project_health_score: number;
  urgent_signals_count: number;
  top_reason: string;
  next_action: string;
}

export type PortfolioAttentionSeverity = "critical" | "warning" | "info";

export interface PortfolioAttentionSignal {
  id: string;
  project_id: string;
  project_name: string;
  occurred_at: string;
  signal_type: string;
  severity: PortfolioAttentionSeverity;
  title: string;
  description: string;
  recommended_action: string;
  evidence_ids: string[];
}

export interface PortfolioAttentionSummary {
  as_of_date: string;
  lookback_days: number;
  total_signals_count: number;
  critical_signals_count: number;
  projects_to_watch: PortfolioAttentionProject[];
  signals: PortfolioAttentionSignal[];
}

export type NotificationSeverity = "info" | "warning" | "critical";

export interface InternalNotification {
  id: string;
  project_id: string;
  project_name: string | null;
  as_of_date: string | null;
  trigger_event_type: string | null;
  trigger_event_label: string | null;
  created_at: string;
  updated_at: string;
  source: string;
  target_role: string;
  recipient_hint: string | null;
  severity: NotificationSeverity;
  title: string;
  body: string;
  reason: string;
  action_items: string[];
  requires_acknowledgement: boolean;
  deduplication_key: string;
  is_read: boolean;
  read_at: string | null;
}

export interface NotificationList {
  total: number;
  unread_count: number;
  items: InternalNotification[];
}

export type SimulationStageStatus = "pending" | "running" | "success" | "error";
export type SimulationJobStatus = "queued" | "running" | "completed" | "failed";

export interface SimulationStage {
  id: string;
  label: string;
  detail: string | null;
  status: SimulationStageStatus;
  timestamp: string;
}

export interface SimulationEventResult {
  event_type: string;
  event_label: string;
  project_id: string | null;
  notification_id: string | null;
  error: string | null;
}

export interface SimulationJob {
  job_id: string;
  status: SimulationJobStatus;
  total_events: number;
  processed_events: number;
  failed_events: number;
  stages: SimulationStage[];
  results: SimulationEventResult[];
  output_file: string | null;
  error: string | null;
}

export interface SimulationClearResult {
  deleted_notifications: number;
  output_file_removed: boolean;
}

export interface ProjectDocxEditableUpdate {
  project_name: string;
  start_date: string | null;
  planned_end_date: string | null;
  business_goal: string;
  expected_result: string;
}

export interface ProjectDocxFieldChange {
  field: keyof ProjectDocxEditableUpdate;
  label: string;
  current_value: string | null;
  proposed_value: string | null;
  changed: boolean;
}

export interface ParsedProjectGoal {
  goal: string;
  confidence: number;
}

export interface ParsedProjectResult {
  result: string;
  confidence: number;
  measurable: boolean;
}

export interface ParsedProjectTimeline {
  start_date: string | null;
  end_date: string | null;
  duration: string | null;
  confidence: number;
}

export interface ParsedProjectData {
  project_name: string;
  goals: ParsedProjectGoal[];
  results: ParsedProjectResult[];
  timeline: ParsedProjectTimeline | null;
}

export interface ProjectDocxPreview {
  project_id: string;
  file_name: string;
  parsed_project: ParsedProjectData;
  editable_update: ProjectDocxEditableUpdate;
  changes: ProjectDocxFieldChange[];
}

export interface ProjectDocxApplyResult {
  project_id: string;
  updated_project: ProjectDocxEditableUpdate;
  changes: ProjectDocxFieldChange[];
}

export type AgentBriefStatus = "в норме" | "под наблюдением" | "критично";

export interface DecisionOption {
  option: string;
  when_to_choose: string;
  tradeoff: string;
}

export interface BusinessImpact {
  delay_days: number | null;
  cost_of_delay: number | null;
  budget_delta: number | null;
  impact_summary: string;
}

export interface AgentActionItem {
  action: string;
  owner_hint: string;
  deadline: string;
  success_signal: string;
}

export interface DraftMessage {
  recipient_hint: string;
  subject: string;
  body: string;
}

export interface FollowUpCheck {
  check_after: string;
  success_condition: string;
  escalation_condition: string;
}

export interface ProjectManagerBrief {
  status: AgentBriefStatus;
  headline: string;
  management_question: string;
  diagnosis: string;
  bottleneck: string;
  critical_path: string[];
  recommended_move: string;
  decision_options: DecisionOption[];
  business_impact: BusinessImpact;
  next_actions: AgentActionItem[];
  draft_message: DraftMessage;
  follow_up_check: FollowUpCheck;
  watchouts: string[];
  evidence_ids: string[];
  missing_data: string[];
}

export interface ProjectQuestionAnswer {
  answer: string;
  evidence_ids: string[];
  evidence_sources: ProjectEvidenceSource[];
  used_tools: string[];
  suggested_questions: string[];
}

export interface ProjectEvidenceSource {
  id: string;
  tool: string;
  source_type: string;
  title: string;
  reference: string | null;
  excerpt: string | null;
  data: Record<string, unknown>;
}

export interface ProjectChatContextMessage {
  role: "user" | "assistant";
  content: string;
}
