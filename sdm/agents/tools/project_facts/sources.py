from __future__ import annotations

import json
from typing import Any

from sdm.agents.text import limit_text

SOURCE_ID_FIELDS = (
    "id",
    "resource_id",
    "source_id",
    "entity_id",
    "task_id",
    "linked_task_id",
    "external_id",
)
SOURCE_TITLE_FIELDS = (
    "title",
    "full_name",
    "name",
    "description",
    "topic",
    "task_title",
    "depends_on",
    "risk_type",
    "item_name",
)
SOURCE_TEXT_FIELDS = (
    "text",
    "description",
    "blocker_reason",
    "reason",
    "body",
    "business_goal",
    "expected_result",
    "business_value",
)
TOP_LEVEL_SOURCE_TOOLS = {
    "calculate_delay_cost": "Расчет стоимости сдвига",
    "get_budget": "Бюджет проекта",
}
STRUCTURAL_SECTIONS = {"project", "metrics", "budget", "budget_metrics"}
PUBLIC_SOURCE_FIELDS = ("id", "tool", "source_type", "title", "reference", "excerpt", "data")


def collect_tool_sources(
    tool_name: str,
    result: dict[str, Any],
    *,
    max_sources: int = 40,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []

    def walk(value: Any, path: tuple[str, ...]) -> None:
        if len(sources) >= max_sources:
            return
        if isinstance(value, list):
            for item in value[:max_sources]:
                walk(item, path)
            return
        if not isinstance(value, dict):
            return

        if _is_source_dict(tool_name, value, path):
            sources.append(_source_from_dict(tool_name, value, path, len(sources)))

        for key, nested_value in value.items():
            if isinstance(nested_value, (dict, list)):
                walk(nested_value, (*path, str(key)))

    walk(result, ())
    return _unique_sources(sources)


def select_answer_sources(
    records: list[dict[str, Any]],
    evidence_ids: list[str],
    *,
    max_sources: int = 14,
) -> list[dict[str, Any]]:
    if not records:
        return []

    targets = {_normalize_id(value) for value in evidence_ids if value}
    matched: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []

    for record in records:
        match_keys = {_normalize_id(value) for value in record.get("_match_keys", []) if value}
        if targets and targets.intersection(match_keys):
            matched.append(record)
        else:
            fallback.append(record)

    selected = [*matched, *fallback][:max_sources]
    return [{key: record[key] for key in PUBLIC_SOURCE_FIELDS if key in record} for record in selected]


def _is_source_dict(tool_name: str, value: dict[str, Any], path: tuple[str, ...]) -> bool:
    if not path and tool_name in TOP_LEVEL_SOURCE_TOOLS:
        return True
    if path and path[-1] in STRUCTURAL_SECTIONS:
        return True
    return any(field in value and value[field] not in (None, "") for field in (*SOURCE_ID_FIELDS, *SOURCE_TITLE_FIELDS))


def _source_from_dict(
    tool_name: str,
    value: dict[str, Any],
    path: tuple[str, ...],
    index: int,
) -> dict[str, Any]:
    source_type = _source_type(value, path)
    reference = _reference(value)
    match_keys = _match_keys(value)
    title = _title(value, source_type)
    excerpt = _excerpt(value)
    source_id = _safe_source_id(tool_name, source_type, reference or title or str(index), index)

    return {
        "id": source_id,
        "tool": tool_name,
        "source_type": source_type,
        "title": title,
        "reference": reference,
        "excerpt": excerpt,
        "data": _compact_data(value),
        "_match_keys": match_keys,
    }


def _source_type(value: dict[str, Any], path: tuple[str, ...]) -> str:
    for field in ("source_table", "entity_type"):
        raw_value = value.get(field)
        if raw_value:
            return str(raw_value)
    return path[-1] if path else "tool_result"


def _reference(value: dict[str, Any]) -> str | None:
    for field in SOURCE_ID_FIELDS:
        raw_value = value.get(field)
        if raw_value not in (None, ""):
            return str(raw_value)
    metadata = value.get("metadata")
    if isinstance(metadata, dict) and metadata.get("external_id"):
        return str(metadata["external_id"])
    return None


def _match_keys(value: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for field in SOURCE_ID_FIELDS:
        raw_value = value.get(field)
        if raw_value not in (None, ""):
            keys.append(str(raw_value))
    metadata = value.get("metadata")
    if isinstance(metadata, dict):
        for field in SOURCE_ID_FIELDS:
            raw_value = metadata.get(field)
            if raw_value not in (None, ""):
                keys.append(str(raw_value))
    return keys


def _title(value: dict[str, Any], source_type: str) -> str:
    for field in SOURCE_TITLE_FIELDS:
        raw_value = value.get(field)
        if raw_value not in (None, ""):
            return limit_text(str(raw_value), 120)
    return source_type.replace("_", " ")


def _excerpt(value: dict[str, Any]) -> str | None:
    for field in SOURCE_TEXT_FIELDS:
        raw_value = value.get(field)
        if raw_value not in (None, ""):
            return limit_text(str(raw_value), 520)
    return None


def _compact_data(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key.startswith("_") or item is None:
            continue
        result[key] = _compact_value(item)
    return result


def _compact_value(value: Any) -> Any:
    if isinstance(value, str):
        return limit_text(value, 520)
    if isinstance(value, list):
        return [_compact_value(item) for item in value[:10]]
    if isinstance(value, dict):
        return {str(key): _compact_value(item) for key, item in list(value.items())[:20] if item is not None}
    return value


def _safe_source_id(tool_name: str, source_type: str, reference: str, index: int) -> str:
    raw_value = f"{tool_name}:{source_type}:{reference}:{index}"
    return limit_text(raw_value.replace(" ", "_"), 180)


def _unique_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        key = json.dumps(
            {
                "tool": source.get("tool"),
                "source_type": source.get("source_type"),
                "reference": source.get("reference"),
                "data": source.get("data"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(source)
    return result


def _normalize_id(value: str) -> str:
    return str(value).strip().casefold()
