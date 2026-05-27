from __future__ import annotations

import json
from typing import Any

from agents.infrastructure.llm import LLMAdapter

from ..message_utils import _messages_to_openai, _state_value
from ..prompts import QA_SYSTEM_PROMPT
from ..runtime import AIMessage, HumanMessage
from ..schemas import ProjectQuestionAnswer
from ..state import ProjectQuestionState


def finalize_answer_node(*, llm: LLMAdapter, temperature: float) -> Any:
    async def finalize_answer(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        if _state_value(state, "needs_project_tools", True):
            final_instruction = "Сформируй финальный JSON ProjectQuestionAnswer по уже полученным tool results."
        else:
            final_instruction = (
                "Сформируй финальный JSON ProjectQuestionAnswer без проектных фактов, "
                "evidence_ids и рекомендаций по проекту."
            )
        messages = [
            *_state_value(state, "messages", []),
            HumanMessage(content=final_instruction),
        ]
        final_prompt = (
            f"{final_instruction}\n\n"
            "История сообщений и результатов инструментов:\n"
            f"{json.dumps(_messages_to_openai(messages), ensure_ascii=False, default=str)}"
        )
        answer = await llm.parse_pydantic(
            response_model=ProjectQuestionAnswer,
            system_prompt=QA_SYSTEM_PROMPT,
            user_prompt=final_prompt,
            temperature=temperature,
        )
        content = answer.model_dump_json()
        return {
            "messages": [HumanMessage(content=final_instruction), AIMessage(content=content)],
            "final_content": content,
        }

    return finalize_answer
