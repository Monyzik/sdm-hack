from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

from sdm.agents.project_qa.messages import (
    PRELOADED_ID_PREFIX,
    bootstrap_tool_arguments,
    preloaded_message_id,
)
from sdm.agents.project_qa.state import ProjectQuestionState
from sdm.agents.streaming import streamed_stage
from sdm.agents.text import unique
from sdm.agents.tools.sources import collect_tool_sources

# Повторный успешный вызов этих инструментов заменяет все более ранние копии:
# каждый из них возвращает снимок целиком, а не выборку по аргументам.
SNAPSHOT_TOOLS = frozenset(
    {
        "get_project_summary",
        "get_problem_context",
        "get_budget",
        "get_resource_rates",
        "get_task_dependency_graph",
    }
)


def _recovery_tool_error(error: Exception) -> str:
    logging.getLogger(__name__).warning("Recovery tool failed: %s", type(error).__name__)
    return "Не удалось получить дополнительные источники. Результат не является доказательством."


def run_tools_node(
    tools: list[BaseTool],
    *,
    stage: str = "run_tools",
    tolerate_errors: bool = False,
) -> Callable[[ProjectQuestionState, RunnableConfig], Awaitable[ProjectQuestionState]]:
    tool_node = (
        ToolNode(tools, handle_tool_errors=_recovery_tool_error)
        if tolerate_errors
        else ToolNode(tools)
    )

    async def run_tools(
        state: ProjectQuestionState, config: RunnableConfig
    ) -> ProjectQuestionState:
        with streamed_stage(stage):
            used_tools = list(state.get("used_tools", []))
            tool_sources = list(state.get("tool_sources", []))
            result = await tool_node.ainvoke(state, config=config)
            executed = list(result.get("messages", []))
            for message in executed:
                if message.id is None:
                    # Стабильный адрес для RemoveMessage при последующем supersede.
                    message.id = message.tool_call_id
            used_tools.extend(str(message.name) for message in executed if message.name)
            history = list(state.get("messages", []))
            args_by_call = _serialized_arguments(history)
            kept, dropped_call_ids = _dedupe_within_round(executed, args_by_call)
            supersede_messages = _supersede_updates(
                history, kept, dropped_call_ids, state.get("question", ""), args_by_call
            )
            tool_sources.extend(_tool_sources_from_messages(kept))

        return {
            "messages": [*supersede_messages, *kept],
            "used_tools": unique(used_tools),
            "tool_sources": tool_sources,
            "tool_rounds": state.get("tool_rounds", 0) + 1,
        }

    return run_tools


def route_after_tools(
    max_tool_rounds: int,
) -> Callable[[ProjectQuestionState], Literal["model", "finalize"]]:
    def route(state: ProjectQuestionState) -> Literal["model", "finalize"]:
        if state.get("tool_rounds", 0) >= max_tool_rounds:
            return "finalize"
        return "model"

    return route


def _serialized_arguments(history: list[BaseMessage]) -> dict[str, str]:
    """Один раз приводит аргументы вызовов к строкам для сравнения повторов."""
    return {
        str(call.get("id")): json.dumps(
            call["args"], ensure_ascii=False, sort_keys=True, default=str
        )
        for message in history
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if isinstance(call.get("args"), dict)
    }


def _dedupe_within_round(
    executed: list[ToolMessage], args_by_call: dict[str, str]
) -> tuple[list[ToolMessage], set[str]]:
    """Оставляет последний успешный результат одинаковых вызовов внутри раунда."""
    groups: dict[tuple[str, str], list[ToolMessage]] = {}
    keeper_ids: set[str] = set()
    for message in executed:
        args = args_by_call.get(message.tool_call_id)
        if not message.name or args is None:
            keeper_ids.add(message.tool_call_id)
            continue
        groups.setdefault((str(message.name), args), []).append(message)
    for messages in groups.values():
        chosen = next((m for m in reversed(messages) if m.status != "error"), messages[-1])
        keeper_ids.add(chosen.tool_call_id)
    kept = [message for message in executed if message.tool_call_id in keeper_ids]
    dropped = {
        message.tool_call_id for message in executed if message.tool_call_id not in keeper_ids
    }
    return kept, dropped


def _supersede_updates(
    history: list[BaseMessage],
    kept: list[ToolMessage],
    dropped_call_ids: set[str],
    question: str,
    args_by_call: dict[str, str],
) -> list[BaseMessage]:
    """Удаляет старые результаты, которые заменены успешными повторными вызовами.

    Вместе с ToolMessage удаляет соответствующий вызов из AIMessage.
    Так в истории сохраняются пары вызовов и ответов.
    """
    earlier_tools = [
        message
        for message in history
        if isinstance(message, ToolMessage) and message.id is not None
    ]
    preloaded_ids = {
        message.id
        for message in history
        if isinstance(message, HumanMessage)
        and message.id
        and message.id.startswith(PRELOADED_ID_PREFIX)
    }

    superseded_call_ids = set(dropped_call_ids)
    removed_ids: set[str] = set()

    def _mark_preloaded(name: str) -> None:
        preloaded_id = preloaded_message_id(name)
        if preloaded_id in preloaded_ids:
            removed_ids.add(preloaded_id)

    bootstrap_query_key = json.dumps(
        bootstrap_tool_arguments(question)["search_project_evidence"],
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    for message in kept:
        if message.status == "error":
            continue
        name = str(message.name)
        key = args_by_call.get(message.tool_call_id)
        if name in SNAPSHOT_TOOLS:
            for target in earlier_tools:
                if target.name == name and target.tool_call_id != message.tool_call_id:
                    superseded_call_ids.add(target.tool_call_id)
                    removed_ids.add(target.id)
            _mark_preloaded(name)
        elif key is not None:
            for target in earlier_tools:
                if (
                    target.name == name
                    and target.tool_call_id != message.tool_call_id
                    and args_by_call.get(target.tool_call_id) == key
                ):
                    superseded_call_ids.add(target.tool_call_id)
                    removed_ids.add(target.id)
            if name == "search_project_evidence" and key == bootstrap_query_key:
                _mark_preloaded(name)

    if not superseded_call_ids and not removed_ids:
        return []

    updates: list[BaseMessage] = [RemoveMessage(id=value) for value in sorted(removed_ids)]
    for message in history:
        if not isinstance(message, AIMessage) or not message.tool_calls:
            continue
        if not any(str(call.get("id")) in superseded_call_ids for call in message.tool_calls):
            continue
        if not message.id:
            # Без постоянного id оставляем пару сообщений.
            continue
        remaining = [
            call for call in message.tool_calls if str(call.get("id")) not in superseded_call_ids
        ]
        if remaining or message.content:
            updates.append(
                AIMessage(
                    id=message.id,
                    content=message.content,
                    tool_calls=remaining,
                    additional_kwargs=dict(message.additional_kwargs or {}),
                )
            )
        else:
            updates.append(RemoveMessage(id=message.id))
    return updates


def _tool_sources_from_messages(messages: list[ToolMessage]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for message in messages:
        tool_name = message.name
        if message.status == "error" or not tool_name:
            continue
        result = _parse_tool_result(
            message.artifact if message.artifact is not None else message.content
        )
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
        return {"text": content} if content.strip() else None

    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return {"items": parsed}
    return {"value": parsed}
