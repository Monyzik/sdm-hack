from __future__ import annotations

import json
from typing import Any

from agents.core.text import bounded_limit, optional_int

def _dedupe_items(items: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        item_key = item.get("id") or item.get("resource_id")
        key = str(item_key) if item_key else json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _filter_items(
    items: list[dict[str, Any]],
    *,
    query: Any,
    query_fields: tuple[str, ...],
    exact_filters: dict[str, Any],
) -> list[dict[str, Any]]:
    filtered = list(items)
    if query:
        needle = str(query).casefold()
        filtered = [
            item
            for item in filtered
            if any(needle in str(item.get(field, "")).casefold() for field in query_fields)
        ]

    for field, expected in exact_filters.items():
        if expected is None or expected == "":
            continue
        needle = str(expected).casefold()
        filtered = [item for item in filtered if needle in str(item.get(field, "")).casefold()]
    return filtered


def _task_criticality_key(item: dict[str, Any]) -> tuple[int, int, str]:
    status = str(item.get("status") or "").casefold()
    priority = str(item.get("priority") or "").casefold()
    blocker_reason = str(item.get("blocker_reason") or "").strip()
    problem_flags = item.get("problem_flags") if isinstance(item.get("problem_flags"), list) else []
    flags_text = " ".join(str(flag).casefold() for flag in problem_flags)
    overdue_days = max(0, optional_int(item.get("overdue_days")) or 0)

    score = overdue_days
    if item.get("is_blocked") or blocker_reason or "blocked" in status or "заблок" in status:
        score += 1000
    if "critical" in priority or "крит" in priority:
        score += 200
    if "critical" in flags_text or "крит" in flags_text:
        score += 100
    score += len(problem_flags) * 10
    return score, overdue_days, str(item.get("id") or "")


def _tool_result(items: list[dict[str, Any]], limit: Any) -> dict[str, Any]:
    limit_value = bounded_limit(limit, default=10)
    return {
        "count": len(items),
        "items": items[:limit_value],
    }
