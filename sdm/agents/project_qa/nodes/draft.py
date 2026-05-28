from __future__ import annotations

import asyncio
import logging
from time import monotonic

from langchain_core.messages import ToolMessage
from openai import APIError

from sdm.agents.budget import RECOVERY_DRAFT_TIMEOUT_SECONDS, VERIFICATION_RESERVE_SECONDS
from sdm.agents.llm import IncompleteOutputError, LLMAdapter
from sdm.agents.prompt_utils import prompt_data
from sdm.agents.streaming import emit_stream_event, streamed_stage, suppress_reasoning_stream

from ..evidence.validation import evidence_catalog, grounded_draft_model
from ..prompts import DRAFT_ANSWER_PROMPT
from ..state import ProjectQuestionState

logger = logging.getLogger(__name__)


def draft_answer_node(*, llm: LLMAdapter, temperature: float):
    async def draft_answer(state: ProjectQuestionState) -> ProjectQuestionState:
        with streamed_stage("draft_answer"), suppress_reasoning_stream():
            results = [m for m in state.get("messages", []) if isinstance(m, ToolMessage)]
            if not results and not state.get("used_tools"):
                raise ValueError(
                    "Q&A-агент не получил результатов инструментов по проектному вопросу."
                )
            sources = evidence_catalog(state.get("tool_sources", []))
            if not sources:
                return {"evidence_unavailable": True}
            previous_review = state.get("evidence_review")
            previous_draft = state.get("answer_draft")
            recovering = bool(state.get("recovery_rounds", 0))
            timeout = None
            if recovering:
                timeout = RECOVERY_DRAFT_TIMEOUT_SECONDS
                if "request_deadline" in state:
                    timeout = min(
                        timeout,
                        max(
                            0.0,
                            state["request_deadline"] - monotonic() - VERIFICATION_RESERVE_SECONDS,
                        ),
                    )
            user_prompt = prompt_data(
                "draft_input",
                {
                    "question": state["question"],
                    "project_id": state["project_id"],
                    "as_of": state["as_of"],
                    "conversation_context": state.get("conversation_context", ""),
                    "evidence_sources": sources,
                    "previous_draft": previous_draft.model_dump()
                    if previous_review is not None and previous_draft is not None
                    else None,
                    "previous_review": previous_review.model_dump() if previous_review else None,
                },
            )
            try:
                if timeout == 0:
                    raise TimeoutError("Оставшееся время нужно для проверки источников.")
                async with asyncio.timeout(timeout):
                    draft = await llm.parse_pydantic(
                        response_model=grounded_draft_model(state["tool_sources"]),
                        system_prompt=DRAFT_ANSWER_PROMPT,
                        user_prompt=user_prompt,
                        temperature=temperature,
                        stream=state.get("stream_response", False),
                    )
            except (ValueError, APIError, TimeoutError) as error:
                if (
                    not recovering
                    or previous_draft is None
                    or previous_review is None
                    or state.get("verification_failed")
                ):
                    raise
                reason = "invalid_output"
                if isinstance(error, IncompleteOutputError) and error.reason == "length":
                    reason = "length"
                elif isinstance(error, TimeoutError):
                    reason = "timeout"
                elif isinstance(error, APIError):
                    reason = "provider_error"
                logger.warning("Recovery draft failed: %s", type(error).__name__)
                emit_stream_event("draft_reused", reason=reason)
                draft = previous_draft
            # Старый review нельзя применять к новому черновику или обновлённым источникам.
            return {"answer_draft": draft, "evidence_review": None, "evidence_unavailable": False}

    return draft_answer
