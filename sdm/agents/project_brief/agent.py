from __future__ import annotations

import json

from pydantic import ValidationError

from sdm.agents.llm import get_llm_adapter

from .cleaning import clean_brief
from .context import compact_problem_context_for_llm
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schemas import ProjectManagerBrief


class ProjectBriefAgent:
    """Агент, который строит управленческий brief по фактическому контексту."""

    def __init__(self, *, temperature: float = 0.2) -> None:
        self.llm = get_llm_adapter()
        self.temperature = temperature

    async def build(self, problem_context: dict) -> ProjectManagerBrief:
        first_error = ""
        try:
            return clean_brief(await self._ask_llm(problem_context), problem_context)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            first_error = str(exc)
            try:
                return clean_brief(
                    await self._ask_llm(problem_context, bad_response=first_error),
                    problem_context,
                )
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                raise RuntimeError(
                    "LLM вернула ответ не по JSON-контракту. "
                    f"Причина: {str(exc)[:700]}"
                ) from exc

    async def _ask_llm(
        self,
        problem_context: dict,
        bad_response: str | None = None,
    ) -> ProjectManagerBrief:
        llm_context = compact_problem_context_for_llm(problem_context)
        return await self.llm.parse_pydantic(
            response_model=ProjectManagerBrief,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(llm_context, bad_response),
            temperature=self.temperature,
        )
