from __future__ import annotations

import asyncio
import logging
from typing import Any

from openai import APIError

from sdm.agents.llm import LLMAdapter
from sdm.agents.prompt_utils import prompt_data
from sdm.agents.streaming import emit_stream_event, streamed_stage, suppress_reasoning_stream

from ..evidence.models import ClaimReview, ClaimSupport, EvidenceReview
from ..evidence.validation import invalid_quote_indices, validate_review, verification_evidence
from ..prompts import CLAIM_SUPPORT_PROMPT, VERIFY_ANSWER_PROMPT
from ..recovery import MAX_RECOVERY_ROUNDS, previous_evidence_calls, recovery_calls
from ..state import ProjectQuestionState

logger = logging.getLogger(__name__)


def verify_answer_node(*, llm: LLMAdapter):
    async def verify_answer(state: ProjectQuestionState) -> ProjectQuestionState:
        if state.get("evidence_unavailable"):
            return {}
        with streamed_stage("verify_answer"), suppress_reasoning_stream():
            draft = state["answer_draft"]
            sources = state.get("tool_sources", [])
            evidence = verification_evidence(draft, sources)
            try:
                invalid = invalid_quote_indices(draft, sources)
                isolated_reviews = await _check_claims(
                    llm, state, evidence["claim_evidence"], invalid
                )
                review = await llm.parse_pydantic(
                    response_model=EvidenceReview,
                    system_prompt=VERIFY_ANSWER_PROMPT,
                    user_prompt=prompt_data(
                        "verification_input",
                        {
                            "question": state["question"],
                            "project_id": state["project_id"],
                            "as_of": state["as_of"],
                            "conversation_context": state.get("conversation_context", ""),
                            "draft": draft.model_dump(),
                            **evidence,
                            "isolated_citation_reviews": [
                                item.model_dump() for item in isolated_reviews
                            ],
                            "invalid_quote_indices": sorted(invalid),
                            "previous_evidence_calls": previous_evidence_calls(state),
                            "recovery_available": state.get("recovery_rounds", 0)
                            < MAX_RECOVERY_ROUNDS,
                        },
                    ),
                    temperature=0,
                    stream=state.get("stream_response", False),
                )
                review = validate_review(review, draft, sources)
                # Общая проверка может отклонить утверждение, но не может
                # отменить отказ отдельной проверки его цитат.
                vetoes = {
                    item.claim_index: item
                    for item in isolated_reviews
                    if item.verdict != "supported"
                }
                review = review.model_copy(
                    update={
                        "claims": [vetoes.get(item.claim_index, item) for item in review.claims]
                    }
                )
            except (ValueError, APIError, TimeoutError) as error:
                # При сбое не публикуем черновик или подробности ошибки сервиса.
                logger.warning("Evidence verification failed: %s", type(error).__name__)
                emit_stream_event(
                    "verification_failed", message="Не удалось проверить подтверждения."
                )
                return {"verification_failed": True}
            updated = {**state, "evidence_review": review, "verification_failed": False}
            emit_stream_event(
                "evidence_review",
                round=state.get("recovery_rounds", 0) + 1,
                claims_total=len(draft.claims),
                supported=sum(claim.verdict == "supported" for claim in review.claims),
                unsupported=sum(claim.verdict == "unsupported" for claim in review.claims),
                contradicted=sum(claim.verdict == "contradicted" for claim in review.claims),
                missing_aspects=review.missing_aspects,
                recovery_available=bool(recovery_calls(updated)),
            )
            if (
                draft.claims
                and all(claim.verdict == "supported" for claim in review.claims)
                and review.missing_aspects
                and not state.get("recovery_rounds", 0)
            ):
                emit_stream_event("recovery_skipped", reason="answer_supported")
            return {"evidence_review": review, "verification_failed": False}

    return verify_answer


async def _check_claims(
    llm: LLMAdapter,
    state: ProjectQuestionState,
    claim_evidence: list[dict[str, Any]],
    invalid: set[int],
) -> list[ClaimReview]:
    """Проверяет каждое утверждение только по его цитатам, не больше двух одновременно."""
    semaphore = asyncio.Semaphore(2)

    async def check(item: dict[str, Any]) -> ClaimReview:
        index = item["claim_index"]
        if index in invalid:
            return ClaimReview(claim_index=index, verdict="unsupported")
        async with semaphore:
            support = await llm.parse_pydantic(
                response_model=ClaimSupport,
                system_prompt=CLAIM_SUPPORT_PROMPT,
                user_prompt=prompt_data(
                    "isolated_claim",
                    {
                        "project_id": state["project_id"],
                        "as_of": state["as_of"],
                        "claim": state["answer_draft"].claims[index].model_dump(),
                        "sources": item["sources"],
                    },
                ),
                temperature=0,
                stream=state.get("stream_response", False),
            )
            return ClaimReview(claim_index=index, verdict=support.verdict)

    # TaskGroup отменяет соседние запросы при ошибке или отмене.
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(check(item)) for item in claim_evidence]
    except* (ValueError, APIError, TimeoutError):
        raise ValueError("An isolated citation check could not be completed") from None
    return [task.result() for task in tasks]
