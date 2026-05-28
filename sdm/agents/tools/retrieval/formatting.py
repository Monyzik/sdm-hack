from typing import Any

from ..formatting import _compact_search_result

EVIDENCE_FIELDS = (
    "id",
    "source_table",
    "source_id",
    "entity_type",
    "entity_id",
    "title",
    "text",
    "occurred_at",
    "linked_task_id",
    "score",
    "retrieval",
    "metadata",
)


def _compact_retrieval_result(result: dict[str, Any]) -> dict[str, Any]:
    compacted = _compact_search_result({**result, "scope": "retrieval_matches"}, EVIDENCE_FIELDS)
    # Размер текста уже ограничен при индексации. Повторная обрезка может
    # удалить уточнение или отрицание, от которого зависит ответ.
    originals = [item for item in result.get("items", [])[:20] if isinstance(item, dict)]
    for item, original in zip(compacted["items"], originals, strict=True):
        if "text" in original:
            item["text"] = original["text"]
    compacted["query"] = result.get("query", "")
    compacted["ranking"] = result.get("ranking")
    compacted["candidate_counts"] = result.get("candidate_counts", {})
    compacted["rerank_applied"] = result.get("rerank_applied", False)
    compacted["reranker_model"] = result.get("reranker_model")
    if result.get("warning"):
        compacted["warning"] = result["warning"]
    return compacted
