from __future__ import annotations

import json
from typing import Any

from agents.infrastructure.llm import get_llm_adapter

from .prompts import NOTIFICATION_SYSTEM_PROMPT, build_notification_prompt
from .schemas import InternalNotificationDraft
from .utils import json_default


class ProjectInternalNotificationAgent:
    """Агент для черновика внутреннего уведомления по результатам мониторинга."""

    def __init__(
        self,
        *,
        temperature: float = 0.2,
        max_context_chars: int = 12000,
    ) -> None:
        self.llm = get_llm_adapter()
        self.temperature = temperature
        self.max_context_chars = max_context_chars

    async def draft(
        self,
        *,
        project: dict[str, Any],
        metrics: dict[str, Any],
        alerts: list[dict[str, Any]],
        analysis: dict[str, Any],
    ) -> InternalNotificationDraft:
        return await self._ask_llm(
            project=project,
            metrics=metrics,
            alerts=alerts,
            analysis=analysis,
        )

    async def _ask_llm(
        self,
        *,
        project: dict[str, Any],
        metrics: dict[str, Any],
        alerts: list[dict[str, Any]],
        analysis: dict[str, Any],
    ) -> InternalNotificationDraft:
        context = json.dumps(
            {
                "project": project,
                "metrics": metrics,
                "alerts": alerts,
                "analysis": analysis,
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        )

        return await self.llm.parse_pydantic(
            response_model=InternalNotificationDraft,
            system_prompt=NOTIFICATION_SYSTEM_PROMPT,
            user_prompt=build_notification_prompt(context[: self.max_context_chars]),
            temperature=self.temperature,
        )
