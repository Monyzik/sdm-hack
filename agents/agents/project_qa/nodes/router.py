from __future__ import annotations

from typing import Any

from agents.infrastructure.llm import LLMAdapter

from ..message_utils import _state_value
from ..prompts import REQUEST_ROUTER_PROMPT
from ..schemas import RequestRoute
from ..state import ProjectQuestionState


def route_request_node(*, llm: LLMAdapter) -> Any:
    async def route_request(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        route = await llm.parse_pydantic(
            response_model=RequestRoute,
            system_prompt=REQUEST_ROUTER_PROMPT,
            user_prompt=(
                f"project_id={_state_value(state, 'project_id')}, "
                f"as_of={_state_value(state, 'as_of')}\n"
                f"{_state_value(state, 'conversation_context', '')}"
                f"Сообщение пользователя: {_state_value(state, 'question')}"
            ),
            temperature=0,
        )

        intent = route.intent
        if intent not in {"small_talk", "project_question", "out_of_scope"}:
            intent = "project_question"
        needs_project_tools = intent == "project_question" and bool(route.needs_project_tools)

        return {
            "request_intent": intent,
            "needs_project_tools": needs_project_tools,
        }

    return route_request


def route_after_request_router(state: ProjectQuestionState | dict[str, Any]) -> str:
    if _state_value(state, "needs_project_tools", True):
        return "model"
    return "finalize"
