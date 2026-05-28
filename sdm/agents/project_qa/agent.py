from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import date
from time import monotonic
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph.state import CompiledStateGraph

from sdm.agents.budget import request_budget_seconds
from sdm.agents.llm import LLMAdapter, get_llm_adapter
from sdm.agents.prompt_utils import prompt_data
from sdm.agents.streaming import collect_stream_metrics
from sdm.agents.text import limit_text
from sdm.agents.tools.project.executor import ProjectFactToolExecutor
from sdm.agents.tools.registry import build_project_tools
from sdm.agents.tools.retrieval.executor import ProjectEvidenceExecutor
from sdm.agents.tools.sources import select_answer_sources

from .answer import _parse_agent_answer
from .graph import build_project_question_graph
from .prompts import QA_SYSTEM_PROMPT
from .schemas import (
    DEFAULT_AS_OF,
    ProjectConversationMessage,
    ProjectEvidenceSource,
    ProjectQuestionAnswer,
)
from .state import ProjectQuestionState


class ProjectQuestionAgent:
    """Отвечает на вопросы по проекту и проверяет факты через инструменты."""

    def __init__(
        self,
        *,
        temperature: float = 0.1,
        llm: LLMAdapter | None = None,
        max_tool_rounds: int = 3,
    ) -> None:
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1")
        self.llm = llm if llm is not None else get_llm_adapter()
        self.temperature = temperature
        self.max_tool_rounds = max_tool_rounds

    async def answer(
        self,
        *,
        project_id: str,
        question: str,
        as_of: date | None = None,
        max_depth: int = 2,
        conversation_context: list[ProjectConversationMessage] | None = None,
        verify_claims: bool = True,
    ) -> ProjectQuestionAnswer:
        state = _initial_state(
            project_id=project_id,
            question=question,
            as_of=as_of,
            max_depth=max_depth,
            conversation_context=conversation_context,
            stream_response=False,
            verify_claims=verify_claims,
        )
        graph = self._graph(state)
        async with asyncio.timeout(max(0.0, state["request_deadline"] - monotonic())):
            result = await graph.ainvoke(state)
        return _answer_from_state(result)

    async def answer_stream(
        self,
        *,
        project_id: str,
        question: str,
        as_of: date | None = None,
        max_depth: int = 2,
        conversation_context: list[ProjectConversationMessage] | None = None,
        verify_claims: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        state = _initial_state(
            project_id=project_id,
            question=question,
            as_of=as_of,
            max_depth=max_depth,
            conversation_context=conversation_context,
            stream_response=True,
            verify_claims=verify_claims,
        )
        yield {"event": "run_started", "data": {"run_id": uuid4().hex}}
        result: ProjectQuestionState | None = None
        with collect_stream_metrics() as metrics:
            graph = self._graph(state)
            try:
                async with asyncio.timeout(max(0.0, state["request_deadline"] - monotonic())):
                    async for chunk in graph.astream(
                        state,
                        stream_mode=["custom", "values"],
                        version="v2",
                    ):
                        if chunk["type"] == "custom":
                            event = chunk["data"]
                            if isinstance(event, dict) and {"event", "data"} <= event.keys():
                                yield event
                        elif chunk["type"] == "values":
                            result = chunk["data"]
            except TimeoutError:
                yield {
                    "event": "error",
                    "data": {
                        "message": "Превышен лимит времени на ответ агента. "
                        "Повторите запрос или упростите вопрос."
                    },
                }
                return
            if result is None:
                raise RuntimeError("Граф не вернул итоговое состояние.")
            answer = _answer_from_state(result)
            final_metrics = metrics.snapshot()
        yield {"event": "answer_delta", "data": {"text": answer.answer}}
        yield {"event": "usage", "data": final_metrics["usage"]}
        yield {
            "event": "final",
            "data": {
                "answer": answer.model_dump(mode="json"),
                "metrics": final_metrics,
            },
        }

    def _graph(self, state: ProjectQuestionState) -> CompiledStateGraph:
        fact_executor = ProjectFactToolExecutor(
            project_id=state["project_id"],
            as_of=state["as_of"],
            max_depth=state["max_depth"],
        )
        evidence_executor = ProjectEvidenceExecutor(
            project_id=state["project_id"],
            as_of=state["as_of"],
            llm=self.llm,
        )
        return build_project_question_graph(
            llm=self.llm,
            tools=build_project_tools(fact_executor, evidence_executor),
            temperature=self.temperature,
            max_tool_rounds=self.max_tool_rounds,
            verify_claims=state.get("verify_claims", True),
        )


def _initial_state(
    *,
    project_id: str,
    question: str,
    as_of: date | None,
    max_depth: int,
    conversation_context: list[ProjectConversationMessage] | None,
    stream_response: bool,
    verify_claims: bool = True,
) -> ProjectQuestionState:
    as_of_value = as_of.isoformat() if as_of else DEFAULT_AS_OF
    conversation_context_text = _format_conversation_context(conversation_context)
    messages = [
        SystemMessage(content=QA_SYSTEM_PROMPT),
        HumanMessage(
            content=prompt_data(
                "user_request",
                {
                    "project_id": project_id,
                    "as_of": as_of_value,
                    "conversation_context": conversation_context_text,
                    "question": question,
                },
            )
        ),
    ]
    return {
        "project_id": project_id,
        "question": question,
        "as_of": as_of_value,
        "max_depth": max_depth,
        "conversation_context": conversation_context_text,
        "messages": messages,
        "used_tools": [],
        "tool_sources": [],
        "tool_rounds": 0,
        "stream_response": stream_response,
        "verify_claims": verify_claims,
        "request_deadline": monotonic() + request_budget_seconds(),
    }


def _answer_from_state(result: ProjectQuestionState) -> ProjectQuestionAnswer:
    answer = _parse_agent_answer(
        result.get("final_content", "{}") or "{}",
        result.get("used_tools", []),
        needs_project_tools=result.get("request_intent", "project_question") == "project_question",
        tool_sources=result.get("tool_sources", []),
    )
    answer.evidence_sources = [
        ProjectEvidenceSource.model_validate(source)
        for source in select_answer_sources(
            list(reversed(result.get("tool_sources", []))), answer.evidence_ids
        )
    ]
    return answer


def _format_conversation_context(
    conversation_context: list[ProjectConversationMessage] | None,
) -> str:
    if not conversation_context:
        return ""

    lines: list[str] = []
    total_chars = 0
    for message in conversation_context[-8:]:
        content = limit_text(message.content, 800)
        if not content:
            continue
        role = "Пользователь" if message.role == "user" else "Агент"
        line = f"{role}: {content}"
        if total_chars + len(line) > 3000:
            break
        lines.append(line)
        total_chars += len(line)

    context = "\n".join(lines).strip()
    if not context:
        return ""
    return (
        "Короткий контекст предыдущих реплик. Используй его только для понимания уточнений, "
        "но факты по проекту всё равно проверяй через tools:\n"
        f"{context}\n\n"
    )
