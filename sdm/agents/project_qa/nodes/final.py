from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from sdm.agents.llm import LLMAdapter
from sdm.agents.prompt_utils import prompt_data
from sdm.agents.streaming import streamed_stage

from ..answer import render_verified_answer
from ..evidence.models import AnswerVerification
from ..evidence.validation import evidence_catalog
from ..messages import _messages_to_openai
from ..prompts import QA_SYSTEM_PROMPT, SOURCE_ANSWER_PROMPT
from ..schemas import (
    ProjectQuestionAnswer,
    ProjectQuestionLLMAnswer,
    grounded_answer_model,
)
from ..state import ProjectQuestionState


def finalize_answer_node(*, llm: LLMAdapter, temperature: float, verify_claims: bool = True):
    async def finalize_answer(state: ProjectQuestionState) -> ProjectQuestionState:
        with streamed_stage("finalize_answer"):
            if state.get("request_intent", "project_question") == "project_question":
                results = [m for m in state.get("messages", []) if isinstance(m, ToolMessage)]
                if not results and not state.get("used_tools"):
                    raise ValueError(
                        "Q&A-агент не получил результатов инструментов по проектному вопросу."
                    )
                if not state.get("tool_sources"):
                    state = {**state, "evidence_unavailable": True}
                if verify_claims or state.get("evidence_unavailable"):
                    answer = render_verified_answer(state)
                else:
                    response = await llm.parse_pydantic(
                        response_model=grounded_answer_model(state["tool_sources"]),
                        system_prompt=SOURCE_ANSWER_PROMPT,
                        user_prompt=prompt_data(
                            "answer_input",
                            {
                                "question": state["question"],
                                "project_id": state["project_id"],
                                "as_of": state["as_of"],
                                "conversation_context": state.get("conversation_context", ""),
                                "evidence_sources": evidence_catalog(state["tool_sources"]),
                                "used_tools": state.get("used_tools", []),
                            },
                        ),
                        temperature=temperature,
                        stream=state.get("stream_response", False),
                    )
                    answer = ProjectQuestionAnswer(
                        **response.model_dump(),
                        verification=AnswerVerification(
                            status="not_checked",
                            checked_claims=0,
                            supported_claims=0,
                            recovery_rounds=0,
                        ),
                    )
            else:
                answer = await llm.parse_pydantic(
                    response_model=ProjectQuestionLLMAnswer,
                    system_prompt=QA_SYSTEM_PROMPT,
                    user_prompt=(
                        "Ответь коротко на приветствие или объясни, что помогаешь с выбранным "
                        "проектом. Не добавляй проектные факты. evidence_ids, used_tools и "
                        "suggested_questions должны быть пустыми.\n\n"
                        + prompt_data(
                            "conversation",
                            _messages_to_openai(
                                [
                                    message
                                    for message in state.get("messages", [])
                                    if not isinstance(message, SystemMessage)
                                ]
                            ),
                        )
                    ),
                    temperature=temperature,
                    stream=state.get("stream_response", False),
                )
            content = answer.model_dump_json()
            return {"messages": [AIMessage(content=content)], "final_content": content}

    return finalize_answer
