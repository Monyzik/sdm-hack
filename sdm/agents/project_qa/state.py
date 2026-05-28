from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from .evidence.models import AnswerDraft, EvidenceReview


class ProjectQuestionState(TypedDict, total=False):
    project_id: str
    question: str
    as_of: str
    max_depth: int
    conversation_context: str
    request_intent: Literal["small_talk", "project_question", "out_of_scope"]
    messages: Annotated[list[BaseMessage], add_messages]
    used_tools: list[str]
    tool_sources: list[dict[str, Any]]
    tool_rounds: int
    final_content: str | None
    stream_response: bool
    verify_claims: bool
    request_deadline: float
    answer_draft: AnswerDraft
    evidence_review: EvidenceReview | None
    evidence_unavailable: bool
    verification_failed: bool
    recovery_rounds: int
