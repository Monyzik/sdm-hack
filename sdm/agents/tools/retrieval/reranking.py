"""Модель упорядочивает готовую выборку поиска, схема проверяет перестановку."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Literal

from openai import APIError
from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from sdm.agents.llm import LLMAdapter
from sdm.agents.prompt_utils import UNTRUSTED_DATA_POLICY, prompt_data
from sdm.agents.streaming import emit_stream_event
from sdm.backend.schemas.retrieval import ProjectRetrievalContext

from .config import RerankSettings

MAX_RERANK_CANDIDATES = 20
RERANK_SYSTEM_PROMPT = (
    "Упорядочь все предоставленные источники по релевантности вопросу: от наиболее "
    "полезного к наименее полезному. Не отвечай на вопрос. Верни только ordered_ids "
    "через инструмент результата, каждый предоставленный id ровно один раз. "
    "Учитывай прямое подтверждение, отрицания, даты и различие между предложением "
    "и утвержденным решением. Не превращай отсутствие факта в подтверждение. "
    "Не добавляй объяснения и новые источники.\n\n" + UNTRUSTED_DATA_POLICY
)


def permutation_model(identifiers: list[str]) -> type[BaseModel]:
    if not identifiers or len(identifiers) > MAX_RERANK_CANDIDATES:
        raise ValueError("Reranking requires between 1 and 20 candidates")
    expected = set(identifiers)
    if len(expected) != len(identifiers):
        raise ValueError("Duplicate reranking candidate IDs")

    def validate_permutation(self):
        if len(set(self.ordered_ids)) != len(self.ordered_ids) or set(self.ordered_ids) != expected:
            raise ValueError("ordered_ids must be a full permutation of the candidate IDs")
        return self

    allowed = Literal.__getitem__(tuple(identifiers))
    return create_model(
        "EvidenceReranking",
        __config__=ConfigDict(extra="forbid"),
        __validators__={
            "validate_permutation": model_validator(mode="after")(validate_permutation)
        },
        ordered_ids=(
            list[allowed],
            Field(min_length=len(identifiers), max_length=len(identifiers)),
        ),
    )


async def rerank_evidence(
    context: ProjectRetrievalContext, *, top_k: int, llm: LLMAdapter
) -> ProjectRetrievalContext:
    if type(top_k) is not int or not 1 <= top_k <= MAX_RERANK_CANDIDATES:
        raise ValueError("top_k must be an integer between 1 and 20")
    if context.ranking != "hybrid":
        raise ValueError("LLM reranking requires hybrid candidates")
    if not context.items:
        return context.model_copy(
            update={"count": 0, "rerank_applied": False, "reranker_model": None}, deep=True
        )
    schema = permutation_model([item.id for item in context.items])
    started_at = perf_counter()
    emit_stream_event(
        "rerank_started", candidate_count=len(context.items), top_k=top_k, model=llm.model
    )
    response = await llm.parse_pydantic(
        response_model=schema,
        system_prompt=RERANK_SYSTEM_PROMPT,
        user_prompt=prompt_data(
            "reranking_candidates",
            {
                "question": context.query,
                "as_of": context.as_of_date,
                "candidates": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "text": item.text,
                        "occurred_at": item.occurred_at,
                    }
                    for item in context.items
                ],
            },
        ),
        temperature=0,
        stream=True,
    )
    by_id = {item.id: item for item in context.items}
    items = []
    for rank, identifier in enumerate(response.ordered_ids[:top_k], 1):
        item = by_id[identifier].model_copy(deep=True)
        item.retrieval = item.retrieval.model_copy(update={"rerank_rank": rank})
        items.append(item)
    result = context.model_copy(
        update={
            "items": items,
            "count": len(items),
            "rerank_applied": True,
            "reranker_model": llm.model,
        },
        deep=True,
    )
    emit_stream_event(
        "rerank_completed",
        model=llm.model,
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
        candidate_count=len(context.items),
        returned_count=len(items),
        ordered_ids=response.ordered_ids,
    )
    return result


async def rerank_with_fallback(
    context: ProjectRetrievalContext,
    *,
    top_k: int,
    llm: LLMAdapter,
    settings: RerankSettings,
) -> ProjectRetrievalContext:
    """При ожидаемых ошибках сохраняет порядок поиска для агента и оценки качества."""
    started_at = perf_counter()
    if settings.enabled and len(context.items) > 1:
        try:
            async with asyncio.timeout(settings.timeout_seconds):
                return await rerank_evidence(context, top_k=top_k, llm=llm)
        except (APIError, ValueError, RuntimeError, TimeoutError) as exc:
            emit_stream_event(
                "rerank_failed",
                model=llm.model,
                candidate_count=len(context.items),
                returned_count=min(top_k, len(context.items)),
                reason=type(exc).__name__,
                fallback="rrf",
                duration_ms=round((perf_counter() - started_at) * 1000, 1),
            )
            context = context.model_copy(update={"rerank_fallback": type(exc).__name__})
    return context.model_copy(
        update={"items": context.items[:top_k], "count": min(top_k, len(context.items))}
    )
