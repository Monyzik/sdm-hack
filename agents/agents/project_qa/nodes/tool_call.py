from __future__ import annotations

import ast
import json
from typing import Any

from agents.core.text import unique
from agents.tools.project_facts.sources import collect_tool_sources

from ..message_utils import _state_value, _tool_names_from_messages
from ..runtime import ToolNode
from ..state import ProjectQuestionState


def run_tools_node(tools: list[Any]) -> Any:
    tool_node = ToolNode(tools)

    async def run_tools(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        used_tools = list(_state_value(state, "used_tools", []))
        tool_sources = list(_state_value(state, "tool_sources", []))
        result = await tool_node.ainvoke(state)
        tool_messages = _state_value(result, "messages", [])
        used_tools.extend(_tool_names_from_messages(tool_messages))
        tool_sources.extend(_tool_sources_from_messages(tool_messages))

        return {
            "messages": tool_messages,
            "used_tools": unique(used_tools),
            "tool_sources": tool_sources,
            "tool_rounds": int(_state_value(state, "tool_rounds", 0) or 0) + 1,
        }

    return run_tools


def route_after_tools(max_tool_rounds: int) -> Any:
    def route(state: ProjectQuestionState | dict[str, Any]) -> str:
        if int(_state_value(state, "tool_rounds", 0) or 0) >= max_tool_rounds:
            return "finalize"
        return "model"

    return route


def _tool_sources_from_messages(messages: list[Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for message in messages:
        tool_name = getattr(message, "name", None)
        if not tool_name:
            continue
        result = _parse_tool_result(getattr(message, "content", None))
        if result is None:
            continue
        sources.extend(collect_tool_sources(str(tool_name), result))
    return sources


def _parse_tool_result(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return content
    if isinstance(content, list):
        return {"items": content}
    if not isinstance(content, str):
        return None

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(content)
        except (SyntaxError, ValueError):
            return {"text": content} if content.strip() else None

    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return {"items": parsed}
    return {"value": parsed}
