from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal

from sdm.agents.llm import LLMAdapter
from sdm.agents.prompt_utils import prompt_data
from sdm.agents.streaming import streamed_stage

from ..prompts import REQUEST_ROUTER_PROMPT
from ..schemas import RequestRoute
from ..state import ProjectQuestionState


def route_request_node(
    *, llm: LLMAdapter
) -> Callable[[ProjectQuestionState], Awaitable[ProjectQuestionState]]:
    async def route_request(state: ProjectQuestionState) -> ProjectQuestionState:
        with streamed_stage("route_request"):
            route = await llm.parse_pydantic(
                response_model=RequestRoute,
                system_prompt=REQUEST_ROUTER_PROMPT,
                user_prompt=prompt_data(
                    "request_to_classify",
                    {
                        "project_id": state["project_id"],
                        "as_of": state["as_of"],
                        "conversation_context": state.get("conversation_context", ""),
                        "question": state["question"],
                    },
                ),
                temperature=0,
                stream=state.get("stream_response", False),
            )

        return {
            "request_intent": route.intent,
        }

    return route_request


def route_after_request_router(state: ProjectQuestionState) -> Literal["context", "finalize"]:
    if state.get("request_intent", "project_question") == "project_question":
        return "context"
    return "finalize"
