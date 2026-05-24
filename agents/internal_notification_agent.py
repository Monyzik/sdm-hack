from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.yandex_client import get_yandex_client, get_yandex_model_uri


NotificationSeverity = Literal["info", "warning", "critical"]
NotificationTargetRole = Literal["teamlead", "project_manager", "portfolio_manager"]


class InternalNotificationDraft(BaseModel):
    should_create: bool = Field(description="Нужно ли создавать уведомление в сервисе")
    project_id: str = Field(description="Идентификатор проекта")
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
    """LLM-агент для черновика внутреннего уведомления по результатам мониторинга."""

    def __init__(
        self,
        *,
        temperature: float = 0.2,
        max_context_chars: int = 12000,
    ) -> None:
        self.model = get_yandex_model_uri()
        self.client = get_yandex_client()
        self.temperature = temperature
        self.max_context_chars = max_context_chars

    def draft(
        self,
        *,
        project: dict[str, Any],
        metrics: dict[str, Any],
        alerts: list[dict[str, Any]],
        analysis: dict[str, Any],
    ) -> InternalNotificationDraft:
        response_text = self._ask_llm(
            project=project,
            metrics=metrics,
            alerts=alerts,
            analysis=analysis,
        )
        result_dict = self._parse_json(response_text)
        return InternalNotificationDraft.model_validate(result_dict)

    def _ask_llm(
        self,
        *,
        project: dict[str, Any],
        metrics: dict[str, Any],
        alerts: list[dict[str, Any]],
        analysis: dict[str, Any],
    ) -> str:
        schema = json.dumps(
            InternalNotificationDraft.model_json_schema(),
            ensure_ascii=False,
            indent=2,
        )
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

Верни только JSON-объект, который соответствует этой JSON Schema:
{schema}

Правила:
1. Это внутреннее уведомление в нашем сервисе, не email и не мессенджер.
2. Не отправляй ничего сам. Нужно только решить, создавать ли уведомление, и подготовить текст.
3. should_create=true ставь, если есть critical alerts, analysis.health_status red/yellow, escalation_needed=true или есть конкретные действия для тимлида.
4. should_create=false ставь, если проект green, критичных алертов нет и нет действий, требующих внимания.
5. target_role обычно teamlead. Если escalation_needed=true, можно выбрать project_manager или portfolio_manager.
6. recipient_hint бери из project.owner_name, если это похоже на владельца проекта.
7. title должен быть коротким, body должен быть конкретным и пригодным для push внутри продукта.
8. action_items должны быть краткими действиями из analysis.recommended_actions.
9. requires_acknowledgement=true ставь для critical severity и эскалаций.
10. deduplication_key сделай стабильным: project_id + главная метрика или health_status.
11. Используй только факты из входных данных, не выдумывай людей, даты и причины.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты агент подготовки внутренних уведомлений для сервиса "
                        "управления проектами. Отвечай только валидным JSON без markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content or "{}"

    @staticmethod
    def _parse_json(response_text: str) -> dict[str, Any]:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))


def json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
