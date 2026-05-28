from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from sdm.agents.llm import LLMAdapter
from sdm.agents.prompt_utils import prompt_data
from sdm.agents.streaming import streamed_stage

from ..messages import _ai_message_from_openai, _messages_to_openai
from ..state import ProjectQuestionState


def call_model_node(
    *, llm: LLMAdapter, tools: list[dict[str, Any]], temperature: float
) -> Callable[[ProjectQuestionState], Awaitable[ProjectQuestionState]]:
    async def call_model(state: ProjectQuestionState) -> ProjectQuestionState:
        with streamed_stage("select_tools"):
            messages = _messages_to_openai(state.get("messages", []))
            if state.get("tool_sources"):
                messages.append(
                    {
                        "role": "user",
                        "content": prompt_data(
                            "available_evidence_sources",
                            [
                                {key: source.get(key) for key in ("id", "reference", "title")}
                                for source in state["tool_sources"]
                            ],
                        ),
                    }
                )
            response = await llm.chat_completion(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
                stream=state.get("stream_response", False),
            )
            ai_message = _ai_message_from_openai(response.choices[0].message)
        return {"messages": [ai_message], "final_content": None}

    return call_model


def route_after_model(state: ProjectQuestionState) -> Literal["tools", "finalize"]:
    messages = state.get("messages", [])
    if messages and getattr(messages[-1], "tool_calls", None):
        return "tools"
    return "finalize"
