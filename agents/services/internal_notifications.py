from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.infrastructure.llm import get_llm_adapter

NotificationSeverity = Literal["info", "warning", "critical"]
NotificationTargetRole = Literal["teamlead", "project_manager", "portfolio_manager"]


class InternalNotificationDraft(BaseModel):
    should_create: bool = Field(description="Нужно ли создавать уведомление в сервисе")
    project_id: str = Field(description="Идентификатор проекта")
    as_of_date: str | None = Field(None, description="Дата среза метрик в формате YYYY-MM-DD")
    trigger_event_type: str | None = Field(None, description="Тип события, после которого создано уведомление")
    trigger_event_label: str | None = Field(None, description="Человекочитаемое описание события")
    target_role: NotificationTargetRole = Field(description="Роль получателя уведомления")
    recipient_hint: str | None = Field(None, description="Подсказка по получателю из данных проекта")
    severity: NotificationSeverity = Field(description="Важность внутреннего уведомления")
    title: str = Field(description="Короткий заголовок для центра уведомлений")
    body: str = Field(description="Текст внутреннего push-уведомления")
    reason: str = Field(description="Почему уведомление нужно создать или не создавать")
    action_items: list[str] = Field(description="Короткие действия для получателя")
    requires_acknowledgement: bool = Field(description="Нужно ли подтверждение прочтения")
    deduplication_key: str = Field(description="Ключ для будущего подавления дублей")


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

        prompt = f"""
Подготовь черновик внутреннего push-уведомления для сервиса цифрового руководителя проекта.

Входные данные:
{context[: self.max_context_chars]}

Верни ответ по строгому Pydantic-контракту InternalNotificationDraft.

Правила:
1. Это внутреннее уведомление в нашем сервисе, не email и не мессенджер.
2. Не отправляй ничего сам. Нужно только решить, создавать ли уведомление, и подготовить текст.
3. should_create=true ставь, если есть critical alerts, analysis.health_status red/yellow, нужно решение выше уровня тимлида или есть конкретные действия для тимлида.
4. should_create=false ставь, если проект green, критичных алертов нет и нет действий, требующих внимания.
5. target_role обычно teamlead. Если нужно решение выше уровня тимлида, можно выбрать project_manager или portfolio_manager.
6. recipient_hint бери из владельца конкретного действия, блокера, решения или зависимости; если его нет, указывай руководителя проектов.
7. title должен быть коротким, body должен быть конкретным и пригодным для push внутри продукта.
8. action_items должны быть краткими действиями из analysis.recommended_actions.
9. requires_acknowledgement=true ставь для critical severity и ситуаций, где нужно решение руководителя.
10. deduplication_key сделай стабильным: project_id + главная метрика или health_status.
11. Если metrics.as_of_date есть во входных данных, верни его в as_of_date.
12. Используй только факты из входных данных, не выдумывай людей, даты и причины.
"""

        return await self.llm.parse_pydantic(
            response_model=InternalNotificationDraft,
            system_prompt=(
                "Ты агент подготовки внутренних уведомлений для сервиса "
                "управления проектами. Отвечай только структурой InternalNotificationDraft."
            ),
            user_prompt=prompt,
            temperature=self.temperature,
        )


def json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
