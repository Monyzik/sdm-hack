from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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
    escalation_needed: bool = Field(description="Нужно ли решение выше уровня тимлида")
    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность анализа")
