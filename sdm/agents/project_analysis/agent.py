from __future__ import annotations

import json
from typing import Any

from sdm.agents.llm import get_llm_adapter

from .prompts import ANALYST_SYSTEM_PROMPT, build_analysis_prompt
from .schemas import ProjectAnalysis
from .utils import json_default


class ProjectAnalystAgent:
    """Агент для управленческого анализа проекта по рассчитанным метрикам."""

    def __init__(
        self,
        *,
        temperature: float = 0.2,
        max_context_chars: int = 12000,
    ) -> None:
        self.llm = get_llm_adapter()
        self.temperature = temperature
        self.max_context_chars = max_context_chars

    async def analyze(
        self,
        *,
        project: dict[str, Any],
        metrics: dict[str, Any],
        alerts: list[dict[str, Any]],
    ) -> ProjectAnalysis:
        return await self._ask_llm(project=project, metrics=metrics, alerts=alerts)

    async def _ask_llm(
        self,
        *,
        project: dict[str, Any],
        metrics: dict[str, Any],
        alerts: list[dict[str, Any]],
    ) -> ProjectAnalysis:
        context = json.dumps(
            {
                "project": project,
                "metrics": metrics,
                "alerts": alerts,
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        )

        return await self.llm.parse_pydantic(
            response_model=ProjectAnalysis,
            system_prompt=ANALYST_SYSTEM_PROMPT,
            user_prompt=build_analysis_prompt(context[: self.max_context_chars]),
            temperature=self.temperature,
        )
