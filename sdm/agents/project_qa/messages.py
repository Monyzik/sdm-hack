"""Преобразование сообщений и начальная история вызовов инструментов."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

PRELOADED_ID_PREFIX = "preloaded:"


def preloaded_message_id(tool_name: str) -> str:
    return f"{PRELOADED_ID_PREFIX}{tool_name}"


def bootstrap_tool_arguments(question: str) -> dict[str, Any]:
    """Аргументы трёх обязательных инструментов перед первым ответом.

    Их используют загрузка контекста (nodes/context.py) и чистка истории
    (nodes/tool_call.py): повторный вызов с теми же аргументами заменяет
    соответствующее preloaded-сообщение.
    """
    return {
        "get_project_summary": {},
        "get_problem_context": {},
        "search_project_evidence": {"query": question},
    }


def _messages_to_openai(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    return [_message_to_openai(message) for message in messages]


def _message_to_openai(message: BaseMessage) -> dict[str, Any]:
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": _message_content(message.content)}

    if isinstance(message, HumanMessage):
        return {"role": "user", "content": _message_content(message.content)}

    if isinstance(message, AIMessage):
        payload: dict[str, Any] = {
            "role": "assistant",
            "content": _message_content(message.content),
        }
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": tool_call["id"],
                    "type": "function",
                    "function": {
                        "name": tool_call["name"],
                        "arguments": json.dumps(tool_call["args"], ensure_ascii=False),
                    },
                }
                for tool_call in message.tool_calls
            ]
        reasoning = message.additional_kwargs.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning:
            payload["reasoning_content"] = reasoning
        return payload

    if isinstance(message, ToolMessage):
        payload = {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": _message_content(message.content),
        }
        if message.name:
            payload["name"] = message.name
        return payload

    role = getattr(message, "type", "user")
    return {
        "role": "assistant" if role == "ai" else role,
        "content": _message_content(message.content),
    }


def _ai_message_from_openai(message: Any) -> AIMessage:
    tool_calls = []
    for tool_call in message.tool_calls or []:
        tool_calls.append(
            {
                "id": tool_call.id,
                "name": tool_call.function.name,
                "args": _parse_tool_arguments(tool_call.function.arguments),
            }
        )
    reasoning = getattr(message, "reasoning_content", None)
    additional_kwargs = (
        {"reasoning_content": reasoning} if isinstance(reasoning, str) and reasoning else {}
    )
    return AIMessage(
        content=message.content or "",
        tool_calls=tool_calls,
        additional_kwargs=additional_kwargs,
    )


def _message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not isinstance(raw_arguments, str):
        raise ValueError("Tool-call arguments must be a JSON object.")
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as error:
        raise ValueError("Tool-call arguments contain invalid JSON.") from error
    if not isinstance(parsed, dict):
        raise ValueError("Tool-call arguments must be a JSON object.")
    return parsed
