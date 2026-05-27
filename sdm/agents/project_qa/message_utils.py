from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from sdm.agents.text import humanize_agent_text, unique

from .runtime import AIMessage, HumanMessage, SystemMessage, ToolMessage
from .schemas import ProjectQuestionAnswer, ProjectQuestionLLMAnswer
from .state import ProjectQuestionState

def _state_value(state: ProjectQuestionState | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _messages_to_openai(messages: list[Any]) -> list[dict[str, Any]]:
    return [_message_to_openai(message) for message in messages]


def _message_to_openai(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return message

    if SystemMessage is not None and isinstance(message, SystemMessage):
        return {"role": "system", "content": _message_content(message.content)}

    if HumanMessage is not None and isinstance(message, HumanMessage):
        return {"role": "user", "content": _message_content(message.content)}

    if AIMessage is not None and isinstance(message, AIMessage):
        payload: dict[str, Any] = {"role": "assistant", "content": _message_content(message.content)}
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": str(tool_call.get("id")),
                    "type": "function",
                    "function": {
                        "name": str(tool_call.get("name")),
                        "arguments": json.dumps(tool_call.get("args") or {}, ensure_ascii=False),
                    },
                }
                for tool_call in message.tool_calls
            ]
        return payload

    if ToolMessage is not None and isinstance(message, ToolMessage):
        payload = {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": _message_content(message.content),
        }
        if message.name:
            payload["name"] = message.name
        return payload

    role = getattr(message, "type", "user")
    return {"role": "assistant" if role == "ai" else role, "content": _message_content(message.content)}


def _ai_message_from_openai(message: Any) -> Any:
    tool_calls = []
    for tool_call in message.tool_calls or []:
        tool_calls.append(
            {
                "id": str(tool_call.id),
                "name": str(tool_call.function.name),
                "args": _parse_tool_arguments(tool_call.function.arguments),
            }
        )
    return AIMessage(content=message.content or "", tool_calls=tool_calls)


def _last_message(messages: list[Any]) -> Any | None:
    return messages[-1] if messages else None


def _tool_names_from_messages(messages: list[Any]) -> list[str]:
    names: list[str] = []
    for message in messages:
        name = getattr(message, "name", None)
        if name:
            names.append(str(name))
    return names


def _message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(str(raw_arguments))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_agent_answer(
    content: str,
    used_tools: list[Any],
    *,
    needs_project_tools: bool = True,
) -> ProjectQuestionAnswer:
    actual_tools = unique(used_tools)
    if needs_project_tools and not actual_tools:
        raise ValueError("Q&A-агент ответил по проектному вопросу без вызова инструментов.")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        text = content.strip()
        if not text:
            raise ValueError("Модель вернула пустой ответ для Q&A.") from error
        return ProjectQuestionAnswer(answer=text, used_tools=actual_tools)
    try:
        llm_answer = ProjectQuestionLLMAnswer.model_validate(payload)
        answer = ProjectQuestionAnswer.model_validate(llm_answer.model_dump())
    except ValidationError as error:
        raise ValueError("Модель вернула JSON не по контракту ProjectQuestionAnswer.") from error

    answer.answer = humanize_agent_text(answer.answer)
    answer.used_tools = actual_tools
    answer.evidence_ids = unique(answer.evidence_ids)[:20]
    answer.suggested_questions = unique(
        [humanize_agent_text(question) for question in answer.suggested_questions]
    )[:4]
    return answer
