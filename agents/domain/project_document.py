from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Goal(BaseModel):
    """Цель проекта."""

    goal: str = Field(description="Текст цели")
    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность (0-1)")


class Result(BaseModel):
    """Результат проекта."""

    result: str = Field(description="Текст результата")
    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность (0-1)")
    measurable: bool = Field(description="Измеримый результат")


class Timeline(BaseModel):
    """Сроки проекта."""

    start_date: Optional[date] = Field(None, description="Дата начала")
    end_date: Optional[date] = Field(None, description="Дата окончания")
    duration: Optional[str] = Field(None, description="Длительность")
    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность")


class ProjectData(BaseModel):
    """Основная модель с целями, сроками и результатами."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_name": "Разработка системы кредитного скоринга",
                "goals": [
                    {
                        "goal": "Разработать модель кредитного скоринга",
                        "confidence": 0.95,
                    }
                ],
                "results": [
                    {
                        "result": "Обученная модель с ROC-AUC >= 0.75",
                        "confidence": 0.9,
                        "measurable": True,
                    }
                ],
                "timeline": {
                    "start_date": "2026-03-01",
                    "end_date": "2026-05-31",
                    "confidence": 0.95,
                },
            }
        }
    )

    project_name: str = Field(description="Название проекта")
    goals: List[Goal] = Field(default_factory=list, description="Цели проекта")
    results: List[Result] = Field(default_factory=list, description="Результаты проекта")
    timeline: Optional[Timeline] = Field(None, description="Сроки проекта")

