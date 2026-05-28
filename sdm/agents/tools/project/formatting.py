from __future__ import annotations

from typing import Any

from sdm.backend.schemas.project_summary import ProjectMetricsFact, ProjectSummary

from ..formatting import (
    _compact_items,
    _compact_list,
    _compact_value,
    _pick,
    _with_collection_metadata,
)

SUMMARY_NESTED_FIELDS = {
    "budget",
    "key_signals",
    "blocked_tasks",
    "overdue_tasks",
    "delayed_milestones",
    "top_risks",
    "delayed_communications",
    "overloaded_resources",
    "risky_dependencies",
    "pending_decisions",
    "open_change_requests",
    "owner_action_load",
}
SUMMARY_FIELDS = tuple(
    field for field in ProjectSummary.model_fields if field not in SUMMARY_NESTED_FIELDS
)
PROJECT_FIELDS = (
    "id",
    "name",
    "owner_name",
    "status",
    "priority",
    "start_date",
    "planned_end_date",
    "business_goal",
    "expected_result",
    "business_value",
)
METRIC_FIELDS = tuple(ProjectMetricsFact.model_fields)
BUDGET_FIELDS = (
    "planned_budget",
    "actual_spent",
    "forecast_total_spent",
    "expected_economic_effect",
    "cost_of_delay_per_day",
    "currency",
    "budget_deviation_percent",
    "roi_percent",
    "risk_adjusted_roi_percent",
)
TASK_FIELDS = (
    "id",
    "external_id",
    "title",
    "assignee_name",
    "status",
    "priority",
    "planned_due_date",
    "actual_end_date",
    "estimated_hours",
    "spent_hours",
    "is_blocked",
    "blocker_reason",
    "overdue_days",
    "problem_flags",
)
TASK_EDGE_FIELDS = (
    "id",
    "root_task_id",
    "direction",
    "depth",
    "task_id",
    "task_title",
    "depends_on_task_id",
    "depends_on_task_title",
    "dependency_type",
    "is_critical_path",
    "lag_days",
    "reason",
)
RISK_FIELDS = (
    "id",
    "risk_type",
    "description",
    "probability",
    "impact",
    "score",
    "status",
    "owner_name",
    "linked_task_id",
)
COMMUNICATION_FIELDS = (
    "id",
    "from_team",
    "to_team",
    "topic",
    "status",
    "importance",
    "expected_response_date",
    "delay_days",
    "linked_task_id",
)
DEPENDENCY_FIELDS = (
    "id",
    "dependency_type",
    "depends_on",
    "owner_team",
    "expected_date",
    "status",
    "criticality",
    "linked_task_id",
    "delay_days",
)
DECISION_FIELDS = (
    "id",
    "decision_type",
    "description",
    "decision_owner",
    "status",
    "decision_date",
)
CHANGE_REQUEST_FIELDS = (
    "id",
    "change_type",
    "requested_by",
    "status",
    "impact_budget",
    "impact_days",
    "description",
)
RESOURCE_FIELDS = (
    "resource_id",
    "full_name",
    "role",
    "team",
    "hour_rate",
    "available_hours_per_week",
    "project_actual_hours_per_week",
    "total_actual_hours_per_week",
    "total_allocation_percent",
    "overload_percent",
)
RESOURCE_COST_FIELDS = (
    "resource_id",
    "full_name",
    "role",
    "team",
    "seniority",
    "hour_rate",
    "available_hours_per_week",
    "project_planned_hours_per_week",
    "project_actual_hours_per_week",
    "weekly_project_cost",
    "daily_project_cost",
)
TASK_GRAPH_FIELDS = (
    "id",
    "task_id",
    "task_title",
    "depends_on_task_id",
    "depends_on_task_title",
    "dependency_type",
    "is_critical_path",
    "lag_days",
    "reason",
)
HISTORY_FIELDS = (
    "id",
    "task_id",
    "changed_at",
    "field_changed",
    "old_value",
    "new_value",
    "changed_by",
)
COMMENT_FIELDS = ("id", "task_id", "author_name", "created_at", "channel", "text", "mentions_count")


def _compact_project_summary(summary: dict[str, Any]) -> dict[str, Any]:
    compacted = {
        **_pick(summary, SUMMARY_FIELDS),
        "key_signals": _compact_list(summary.get("key_signals", []), limit=8),
        "budget": _pick(summary.get("budget"), BUDGET_FIELDS),
        "blocked_tasks": _compact_items(summary.get("blocked_tasks", []), TASK_FIELDS, limit=6),
        "overdue_tasks": _compact_items(summary.get("overdue_tasks", []), TASK_FIELDS, limit=6),
        "delayed_milestones": _compact_items(
            summary.get("delayed_milestones", []),
            ("id", "name", "status", "planned_end_date", "delay_days", "responsible_team"),
            limit=6,
        ),
        "top_risks": _compact_items(summary.get("top_risks", []), RISK_FIELDS, limit=6),
        "delayed_communications": _compact_items(
            summary.get("delayed_communications", []),
            COMMUNICATION_FIELDS,
            limit=6,
        ),
        "overloaded_resources": _compact_items(
            summary.get("overloaded_resources", []),
            RESOURCE_FIELDS,
            limit=6,
        ),
        "risky_dependencies": _compact_items(
            summary.get("risky_dependencies", []),
            DEPENDENCY_FIELDS,
            limit=6,
        ),
        "pending_decisions": _compact_items(
            summary.get("pending_decisions", []), DECISION_FIELDS, limit=6
        ),
        "open_change_requests": _compact_items(
            summary.get("open_change_requests", []),
            CHANGE_REQUEST_FIELDS,
            limit=6,
        ),
    }

    return _with_collection_metadata(compacted, summary, scope="project_summary")


def _compact_problem_context(context: dict[str, Any]) -> dict[str, Any]:
    compacted = {
        "project": _pick(context.get("project"), PROJECT_FIELDS),
        "as_of_date": context.get("as_of_date"),
        "metrics": _pick(context.get("metrics"), METRIC_FIELDS),
        "budget": _pick(context.get("budget"), BUDGET_FIELDS),
        "problem_tasks": _compact_items(context.get("problem_tasks", []), TASK_FIELDS, limit=8),
        "task_dependency_edges": _compact_items(
            context.get("task_dependency_edges", []),
            TASK_EDGE_FIELDS,
            limit=12,
        ),
        "linked_risks": _compact_items(context.get("linked_risks", []), RISK_FIELDS, limit=8),
        "linked_communications": _compact_items(
            context.get("linked_communications", []),
            COMMUNICATION_FIELDS,
            limit=8,
        ),
        "linked_project_dependencies": _compact_items(
            context.get("linked_project_dependencies", []),
            DEPENDENCY_FIELDS,
            limit=8,
        ),
        "pending_decisions": _compact_items(
            context.get("pending_decisions", []), DECISION_FIELDS, limit=8
        ),
        "open_change_requests": _compact_items(
            context.get("open_change_requests", []),
            CHANGE_REQUEST_FIELDS,
            limit=8,
        ),
        "project_resources": _compact_items(
            context.get("project_resources", []),
            RESOURCE_COST_FIELDS,
            limit=12,
        ),
        "task_dependency_graph": _compact_items(
            context.get("task_dependency_graph", []),
            TASK_GRAPH_FIELDS,
            limit=30,
        ),
        "overloaded_resources": _compact_items(
            context.get("overloaded_resources", []),
            RESOURCE_FIELDS,
            limit=8,
        ),
        "recent_task_history": _compact_items(
            context.get("recent_task_history", []), HISTORY_FIELDS, limit=6
        ),
        "recent_task_comments": _compact_items(
            context.get("recent_task_comments", []), COMMENT_FIELDS, limit=6
        ),
    }

    return _with_collection_metadata(compacted, context, scope="problem_context")


def _compact_budget_result(result: dict[str, Any]) -> dict[str, Any]:
    compacted = {
        "budget": _pick(result.get("budget"), BUDGET_FIELDS),
        "budget_metrics": _compact_value(result.get("budget_metrics", {})),
        "open_change_requests": _compact_items(
            result.get("open_change_requests", []),
            CHANGE_REQUEST_FIELDS,
            limit=8,
        ),
    }

    return _with_collection_metadata(compacted, result, scope="project_budget")
