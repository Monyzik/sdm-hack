from __future__ import annotations

from typing import Any

from agents.core.text import humanize_agent_text

LLM_PROBLEM_TASK_LIMIT = 35
LLM_DEPENDENCY_EDGE_LIMIT = 60
LLM_LINKED_FACT_LIMIT = 12
LLM_RECENT_EVENT_LIMIT = 8

HUMAN_VALUE_LABELS = {
    "active": "активен",
    "approved": "согласовано",
    "blocked": "заблокировано",
    "closed": "закрыто",
    "completed": "завершено",
    "critical": "критичный",
    "delayed": "задержано",
    "done": "готово",
    "escalated": "требует решения",
    "green": "зелёная зона",
    "high": "высокий",
    "in_progress": "в работе",
    "low": "низкий",
    "medium": "средний",
    "mitigating": "снижается",
    "open": "открыто",
    "pending": "ожидает решения",
    "proposed": "предложено",
    "red": "красная зона",
    "resolved": "решено",
    "under_review": "на рассмотрении",
    "warning": "важно",
    "yellow": "жёлтая зона",
}


def compact_problem_context_for_llm(problem_context: dict[str, Any]) -> dict[str, Any]:
    problem_tasks = _list_value(problem_context.get("problem_tasks"))
    dependency_edges = _list_value(problem_context.get("task_dependency_edges"))
    linked_risks = _list_value(problem_context.get("linked_risks"))
    linked_communications = _list_value(problem_context.get("linked_communications"))
    linked_project_dependencies = _list_value(problem_context.get("linked_project_dependencies"))
    pending_decisions = _list_value(problem_context.get("pending_decisions"))
    open_change_requests = _list_value(problem_context.get("open_change_requests"))
    project_resources = _list_value(problem_context.get("project_resources"))
    task_dependency_graph = _list_value(problem_context.get("task_dependency_graph"))
    overloaded_resources = _list_value(problem_context.get("overloaded_resources"))
    recent_task_history = _list_value(problem_context.get("recent_task_history"))
    recent_task_comments = _list_value(problem_context.get("recent_task_comments"))

    compact_context = {
        "project": problem_context.get("project"),
        "as_of_date": problem_context.get("as_of_date"),
        "metrics": problem_context.get("metrics"),
        "budget": problem_context.get("budget"),
        "context_note": (
            "Списки ниже ограничены для LLM. Полные количества находятся в metrics; "
            "используй списки как evidence/sample, а не как полный объем проблем."
        ),
        "aggregates": _build_problem_aggregates(problem_tasks, dependency_edges),
        "omitted_counts": {
            "problem_tasks": max(0, len(problem_tasks) - LLM_PROBLEM_TASK_LIMIT),
            "task_dependency_edges": max(0, len(dependency_edges) - LLM_DEPENDENCY_EDGE_LIMIT),
            "linked_risks": max(0, len(linked_risks) - LLM_LINKED_FACT_LIMIT),
            "linked_communications": max(0, len(linked_communications) - LLM_LINKED_FACT_LIMIT),
            "linked_project_dependencies": max(0, len(linked_project_dependencies) - LLM_LINKED_FACT_LIMIT),
            "pending_decisions": max(0, len(pending_decisions) - LLM_LINKED_FACT_LIMIT),
            "open_change_requests": max(0, len(open_change_requests) - LLM_LINKED_FACT_LIMIT),
            "project_resources": max(0, len(project_resources) - LLM_LINKED_FACT_LIMIT),
            "task_dependency_graph": max(0, len(task_dependency_graph) - LLM_DEPENDENCY_EDGE_LIMIT),
            "overloaded_resources": max(0, len(overloaded_resources) - LLM_LINKED_FACT_LIMIT),
            "recent_task_history": max(0, len(recent_task_history) - LLM_RECENT_EVENT_LIMIT),
            "recent_task_comments": max(0, len(recent_task_comments) - LLM_RECENT_EVENT_LIMIT),
        },
        "problem_tasks": problem_tasks[:LLM_PROBLEM_TASK_LIMIT],
        "task_dependency_edges": dependency_edges[:LLM_DEPENDENCY_EDGE_LIMIT],
        "linked_risks": linked_risks[:LLM_LINKED_FACT_LIMIT],
        "linked_communications": linked_communications[:LLM_LINKED_FACT_LIMIT],
        "linked_project_dependencies": linked_project_dependencies[:LLM_LINKED_FACT_LIMIT],
        "pending_decisions": pending_decisions[:LLM_LINKED_FACT_LIMIT],
        "open_change_requests": open_change_requests[:LLM_LINKED_FACT_LIMIT],
        "project_resources": project_resources[:LLM_LINKED_FACT_LIMIT],
        "task_dependency_graph": task_dependency_graph[:LLM_DEPENDENCY_EDGE_LIMIT],
        "overloaded_resources": overloaded_resources[:LLM_LINKED_FACT_LIMIT],
        "recent_task_history": recent_task_history[:LLM_RECENT_EVENT_LIMIT],
        "recent_task_comments": recent_task_comments[:LLM_RECENT_EVENT_LIMIT],
    }
    return _humanize_context_values(compact_context)


def _build_problem_aggregates(
    problem_tasks: list[dict[str, Any]],
    dependency_edges: list[dict[str, Any]],
) -> dict[str, Any]:
    overdue_days = [
        _int_value(task.get("overdue_days"))
        for task in problem_tasks
        if _int_value(task.get("overdue_days")) > 0
    ]
    planned_due_dates = [
        str(task.get("planned_due_date"))
        for task in problem_tasks
        if task.get("planned_due_date")
    ]
    return {
        "problem_tasks_total_in_context": len(problem_tasks),
        "problem_flags": _top_flag_counts(problem_tasks),
        "tasks_by_status": _top_counts(problem_tasks, "status"),
        "tasks_by_priority": _top_counts(problem_tasks, "priority"),
        "tasks_by_assignee": _top_counts(problem_tasks, "assignee_name"),
        "max_overdue_days_in_context": max(overdue_days, default=0),
        "earliest_planned_due_date_in_context": min(planned_due_dates, default=None),
        "dependency_edges_total_in_context": len(dependency_edges),
        "critical_dependency_edges_in_context": sum(
            1 for edge in dependency_edges if bool(edge.get("is_critical_path"))
        ),
        "dependency_edges_by_direction": _top_counts(dependency_edges, "direction"),
    }


def _list_value(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _top_counts(items: list[dict[str, Any]], key: str, limit: int = 10) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in items:
        raw_value = item.get(key)
        label = str(raw_value).strip() if raw_value is not None else ""
        if not label:
            label = "unknown"
        counts[label] = counts.get(label, 0) + 1
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _top_flag_counts(problem_tasks: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for task in problem_tasks:
        flags = task.get("problem_flags")
        if not isinstance(flags, list):
            continue
        for flag in flags:
            label = str(flag).strip()
            if label:
                counts[label] = counts.get(label, 0) + 1
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _humanize_context_values(value: Any) -> Any:
    if isinstance(value, str):
        normalized = value.strip().casefold()
        return HUMAN_VALUE_LABELS.get(normalized, humanize_agent_text(value))
    if isinstance(value, list):
        return [_humanize_context_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _humanize_context_values(item) for key, item in value.items()}
    return value
