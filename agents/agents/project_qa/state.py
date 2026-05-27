from __future__ import annotations

from typing import Annotated, Any, TypedDict

from .runtime import add_messages


class ProjectQuestionState(TypedDict, total=False):
    project_id: str
    question: str
    as_of: str
    max_depth: int
    conversation_context: str
    request_intent: str | None
    needs_project_tools: bool
    messages: Annotated[list[Any], add_messages]
    used_tools: list[str]
    tool_rounds: int
    final_content: str | None
