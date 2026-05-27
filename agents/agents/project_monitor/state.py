from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ProjectMonitorData(BaseModel):
    project_id: str
    as_of: date | None = None
    trigger_event: dict[str, Any] | None = None
    project: dict[str, Any] = Field(default_factory=dict)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    communications: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    change_requests: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    analysis: dict[str, Any] | None = None
    notification_draft: dict[str, Any] | None = None
    notification_id: str | None = None


def state_value(state: ProjectMonitorData | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, ProjectMonitorData):
        return getattr(state, key)
    return state.get(key, default)


def coerce_as_of(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported as_of value: {value!r}")
