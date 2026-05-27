from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_AS_OF = "2026-06-19"


class ProjectConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=800)


class ProjectQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    as_of: date | None = None
    max_depth: int = Field(default=2, ge=1, le=4)
    conversation_context: list[ProjectConversationMessage] = Field(default_factory=list, max_length=8)


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


class RequestRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["small_talk", "project_question", "out_of_scope"] = "project_question"
    needs_project_tools: bool = True
    reason: str = ""
