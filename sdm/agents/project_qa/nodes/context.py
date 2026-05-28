from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import BaseTool

from sdm.agents.prompt_utils import prompt_data
from sdm.agents.streaming import streamed_stage

from ..messages import bootstrap_tool_arguments, preloaded_message_id
from ..state import ProjectQuestionState
from .tool_call import _tool_sources_from_messages


def request_project_context(
    tools: dict[str, BaseTool],
) -> Callable[[ProjectQuestionState], Awaitable[ProjectQuestionState]]:
    """Загружает обязательный контекст до первого обращения модели к инструментам.

    Вызовы сохраняют проверку аргументов и события инструментов. Модель получает
    сообщения с постоянными id, чтобы повторный вызов мог заменить старый результат.
    """

    async def load_context(state: ProjectQuestionState) -> ProjectQuestionState:
        with streamed_stage("request_project_context"):
            arguments = bootstrap_tool_arguments(state["question"])
            # Ошибки аргументов возвращаются в ToolMessage.
            # Сбой сервиса прерывает запуск, как и при обычном вызове ToolNode.
            results = await asyncio.gather(
                *(
                    tools[name].ainvoke(
                        {"name": name, "args": args, "id": f"context_{name}", "type": "tool_call"}
                    )
                    for name, args in arguments.items()
                )
            )
            messages = [
                _preloaded_message(result, arguments[str(result.name)]) for result in results
            ]
        return {
            "messages": messages,
            "used_tools": [str(result.name) for result in results],
            "tool_sources": _tool_sources_from_messages(list(results)),
            "tool_rounds": 1,
        }

    return load_context


def _preloaded_message(result: ToolMessage, arguments: dict) -> HumanMessage:
    payload: dict = {"tool": result.name, "args": arguments}
    if result.status == "error":
        payload["error"] = str(result.content)
    else:
        payload["result"] = result.artifact if result.artifact is not None else result.content
    return HumanMessage(
        id=preloaded_message_id(str(result.name)),
        content=prompt_data("preloaded_tool_result", payload),
    )
