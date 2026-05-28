from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from sdm.agents.text import unique
from sdm.agents.tools.sources import MAX_EVIDENCE_SOURCES

from .evidence.models import AnswerVerification, VerifiedClaim

DEFAULT_AS_OF = "2026-06-19"
PROJECT_DATA_UNAVAILABLE_ANSWER = (
    "Не удалось получить подтверждённые данные проекта. Повторите запрос позже."
)


class ProjectConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=800)


class ProjectQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    as_of: date | None = None
    max_depth: int = Field(default=2, ge=1, le=4)
    verify_claims: bool = Field(
        default=True,
        strict=True,
        description="Проверять подтверждение утверждений источниками перед публикацией ответа.",
    )
    conversation_context: list[ProjectConversationMessage] = Field(
        default_factory=list, max_length=8
    )


class ProjectEvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool: str
    source_type: str
    title: str
    reference: str | None = None
    excerpt: str | None = None
    data: dict[str, object] = Field(default_factory=dict)


class ProjectQuestionLLMAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    evidence_ids: list[str] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class ProjectQuestionAnswer(ProjectQuestionLLMAnswer):
    evidence_sources: list[ProjectEvidenceSource] = Field(default_factory=list)
    claims: list[VerifiedClaim] = Field(default_factory=list)
    verification: AnswerVerification | None = None


def grounded_answer_model(
    tool_sources: list[dict[str, Any]],
) -> type[ProjectQuestionLLMAnswer]:
    """Создаёт схему ответа со ссылками только на полученные источники."""
    allowed_ids = unique(
        [
            str(value).strip()
            for source in tool_sources
            for value in [source.get("id"), *source.get("_match_keys", [])]
            if value and str(value).strip()
        ]
    )
    if not allowed_ids:
        raise ValueError("Нет подтверждённых источников для проектного ответа.")

    evidence_id_type = Literal.__getitem__(tuple(allowed_ids))
    return create_model(
        "GroundedProjectQuestionLLMAnswer",
        __base__=ProjectQuestionLLMAnswer,
        evidence_ids=(
            list[evidence_id_type],
            Field(min_length=1, max_length=min(MAX_EVIDENCE_SOURCES, len(allowed_ids))),
        ),
    )


class RequestRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["small_talk", "project_question", "out_of_scope"] = "project_question"
    reason: str = ""
