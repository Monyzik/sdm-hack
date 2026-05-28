from typing import Any


def _compact_search_result(result: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    items = _compact_items(result.get("items", []), fields, limit=20)
    count = result.get("count", len(items))
    return {
        "count": count,
        "returned_count": len(items),
        "truncated": count > len(items),
        "scope": result.get("scope", "problem_snapshot"),
        "items": items,
    }


def _compact_items(items: Any, fields: tuple[str, ...], *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [_pick(item, fields) for item in items[:limit] if isinstance(item, dict)]


def _pick(item: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    result: dict[str, Any] = {}
    for field in fields:
        if field not in item or item[field] is None:
            continue
        # Ссылки и фильтры используют исходные идентификаторы и значения статусов.
        if field == "id" or field.endswith("_id") or field in {"status", "priority", "criticality"}:
            result[field] = item[field]
        else:
            result[field] = _compact_value(item[field])
    return result


def _compact_list(items: Any, *, limit: int) -> list[Any]:
    if not isinstance(items, list):
        return []
    return [_compact_value(item) for item in items[:limit]]


def _compact_value(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= 260 else value[:257] + "..."
    if isinstance(value, list):
        return [_compact_value(item) for item in value[:12]]
    if isinstance(value, dict):
        return {key: _compact_value(item) for key, item in value.items() if item is not None}
    return value


def _with_collection_metadata(
    compacted: dict[str, Any], original: dict[str, Any], *, scope: str
) -> dict[str, Any]:
    """Показывает размеры исходных списков и выданных фрагментов."""
    collections = {}
    for field, items in compacted.items():
        if not isinstance(items, list):
            continue
        source_items = original.get(field)
        collections[field] = {
            "count": len(source_items) if isinstance(source_items, list) else None,
            "returned_count": len(items),
            "truncated": len(source_items) > len(items)
            if isinstance(source_items, list)
            else False,
        }
    return {**compacted, "scope": scope, "collections": collections}
