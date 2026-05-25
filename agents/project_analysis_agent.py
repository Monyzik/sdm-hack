from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.yandex_client import get_yandex_client, get_yandex_model_uri

HealthStatus = Literal["green", "yellow", "red"]
ActionUrgency = Literal["today", "this_week", "later"]


class ProjectAction(BaseModel):
    action: str = Field(description="Конкретное действие для тимлида или РП")
    reason: str = Field(description="Почему это действие важно")
    owner_hint: str | None = Field(None, description="Кто должен быть вовлечен")
    urgency: ActionUrgency = Field(description="Срочность действия")


class ProjectAnalysis(BaseModel):
    health_status: HealthStatus = Field(description="Общее состояние проекта")
    summary: str = Field(description="Короткая управленческая сводка")
    key_findings: list[str] = Field(description="Главные выводы из метрик")
    root_causes: list[str] = Field(description="Вероятные причины проблем")
    recommended_actions: list[ProjectAction] = Field(description="Рекомендованные действия")
    questions_for_teamlead: list[str] = Field(description="Что стоит уточнить у тимлида")
    escalation_needed: bool = Field(description="Нужна ли эскалация выше тимлида")
    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность анализа")


class ProjectAnalystAgent:
    """LLM-агент для управленческого анализа проекта по рассчитанным метрикам."""

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

    def analyze(
            self,
            *,
            project: dict[str, Any],
            metrics: dict[str, Any],
            alerts: list[dict[str, Any]],
    ) -> ProjectAnalysis:
        response_text = self._ask_llm(project=project, metrics=metrics, alerts=alerts)
        result_dict = self._parse_json(response_text)
        return ProjectAnalysis.model_validate(result_dict)

    def _ask_llm(
            self,
            *,
            project: dict[str, Any],
            metrics: dict[str, Any],
            alerts: list[dict[str, Any]],
    ) -> str:
        schema = json.dumps(ProjectAnalysis.model_json_schema(), ensure_ascii=False, indent=2)
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

        prompt = f"""
Проанализируй состояние проекта для цифрового руководителя проекта.

Входные данные:
{context[: self.max_context_chars]}

Верни только JSON-объект, который соответствует этой JSON Schema:
{schema}

Правила анализа:
1. Используй только факты из project, metrics и alerts. Не выдумывай задачи, людей, даты и бюджеты.
2. Метрики уже рассчитаны детерминированным кодом, не пересчитывай их.
3. key_findings должны ссылаться на конкретные проблемы из metrics/alerts.
4. recommended_actions должны быть практичными действиями для тимлида или РП.
5. Если критичных алертов нет, не придумывай кризис: дай аккуратный green/yellow статус.
6. escalation_needed ставь true только если есть критичные блокеры, критичные зависимости, сильная просрочка или явный бюджетный риск.
7. confidence отражает полноту входных данных и согласованность выводов.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты опытный цифровой руководитель проекта. "
                        "Ты объясняешь состояние проекта по метрикам, "
                        "не фантазируешь и отвечаешь только валидным JSON без markdown."
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
