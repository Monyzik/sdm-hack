from __future__ import annotations

from typing import Any

from agents.core.text import unique

from ..message_utils import _state_value, _tool_names_from_messages
from ..runtime import ToolNode
from ..state import ProjectQuestionState


def run_tools_node(tools: list[Any]) -> Any:
    tool_node = ToolNode(tools)

    async def run_tools(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        used_tools = list(_state_value(state, "used_tools", []))
        result = await tool_node.ainvoke(state)
        tool_messages = _state_value(result, "messages", [])
        used_tools.extend(_tool_names_from_messages(tool_messages))

        return {
            "messages": tool_messages,
            "used_tools": unique(used_tools),
            "tool_rounds": int(_state_value(state, "tool_rounds", 0) or 0) + 1,
        }

    return run_tools


def route_after_tools(max_tool_rounds: int) -> Any:
    def route(state: ProjectQuestionState | dict[str, Any]) -> str:
        if int(_state_value(state, "tool_rounds", 0) or 0) >= max_tool_rounds:
            return "finalize"
        return "model"

    return route
