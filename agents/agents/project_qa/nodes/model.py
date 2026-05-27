from __future__ import annotations

from typing import Any

from agents.infrastructure.llm import LLMAdapter

from ..message_utils import _ai_message_from_openai, _last_message, _messages_to_openai, _state_value
from ..state import ProjectQuestionState


def call_model_node(*, llm: LLMAdapter, tools: list[dict[str, Any]], temperature: float) -> Any:
    async def call_model(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        needs_project_tools = _state_value(state, "needs_project_tools", True)
        used_tools = _state_value(state, "used_tools", [])
        response = await llm.chat_completion(
            messages=_messages_to_openai(_state_value(state, "messages", [])),
            tools=tools,
            tool_choice="required" if needs_project_tools and not used_tools else "auto",
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        message = response.choices[0].message
        ai_message = _ai_message_from_openai(message)
        return {
            "messages": [ai_message],
            "final_content": None if ai_message.tool_calls else (message.content or "{}"),
        }

    return call_model


def route_after_model(state: ProjectQuestionState | dict[str, Any]) -> str:
    last_message = _last_message(_state_value(state, "messages", []))
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "finalize"
