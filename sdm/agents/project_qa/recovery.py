"""Выбор дополнительного поиска с ограничением числа раундов и вызовов."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage

from .evidence.models import EvidenceReview
from .messages import bootstrap_tool_arguments
from .state import ProjectQuestionState

MAX_RECOVERY_ROUNDS = 1
MAX_RECOVERY_CALLS = 3


def previous_evidence_calls(state: ProjectQuestionState) -> list[dict[str, Any]]:
    calls = [
        {"name": call["name"], "args": call["args"]}
        for message in state.get("messages", [])
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call["name"] in {"search_project_evidence", "get_evidence_context"}
    ]
    if "search_project_evidence" in state.get("used_tools", []) and state.get("question"):
        calls.insert(
            0,
            {
                "name": "search_project_evidence",
                "args": bootstrap_tool_arguments(state["question"])["search_project_evidence"],
            },
        )
    return calls


def _call_key(call: dict[str, Any]) -> str:
    args = call["args"]
    if call["name"] == "search_project_evidence":
        # Другой лимит результатов не делает тот же вопрос новым.
        args = {
            "query": " ".join(str(args.get("query", "")).split()),
            "entity_id": args.get("entity_id") or None,
        }
    elif call["name"] == "get_evidence_context":
        args = {"evidence_id": args.get("evidence_id"), "neighbors": args.get("neighbors", 1)}
    return json.dumps(
        {"name": call["name"], "args": args}, sort_keys=True, ensure_ascii=False
    ).casefold()


def recovery_calls(state: ProjectQuestionState) -> list[dict[str, Any]]:
    if state.get("verification_failed") or state.get("recovery_rounds", 0) >= MAX_RECOVERY_ROUNDS:
        return []
    review: EvidenceReview | None = state.get("evidence_review")
    if review is None or state.get("evidence_unavailable"):
        return []
    draft = state["answer_draft"]
    rejected = [claim for claim in review.claims if claim.verdict != "supported"]
    # Пробелы полноты сами по себе не требуют переписывать подтверждённый ответ.
    if not (rejected or not draft.claims):
        return []
    sources = {source["id"]: source for source in state.get("tool_sources", [])}
    candidates = []
    for source_id in review.context_source_ids:
        source = sources.get(source_id, {})
        # Читаем контекст только для найденных документов.
        # Сервис повторно проверяет принадлежность документа проекту.
        if source.get("tool") in {"search_project_evidence", "get_evidence_context"}:
            evidence_id = source.get("data", {}).get("id")
            if evidence_id:
                candidates.append(
                    {
                        "name": "get_evidence_context",
                        "args": {"evidence_id": str(evidence_id), "neighbors": 1},
                    }
                )
    for search in review.searches:
        args = {"query": search.query.strip()}
        if search.entity_id:
            args["entity_id"] = search.entity_id
        if args["query"]:
            candidates.append({"name": "search_project_evidence", "args": args})
    # Если проверка нашла пробелы без плана поиска, ищем по этим пробелам.
    # Эти формулировки используются только как запросы.
    fallback_queries = list(review.missing_aspects)
    if not fallback_queries:
        fallback_queries = [draft.claims[item.claim_index].text for item in rejected]
    if not candidates:
        for query in fallback_queries:
            if query.strip():
                candidates.append(
                    {"name": "search_project_evidence", "args": {"query": query[:500]}}
                )
    seen = {_call_key(call) for call in previous_evidence_calls(state)}
    selected = []
    for call in candidates:
        key = _call_key(call)
        if key not in seen:
            selected.append(call)
            seen.add(key)
        if len(selected) == MAX_RECOVERY_CALLS:
            break
    return selected
