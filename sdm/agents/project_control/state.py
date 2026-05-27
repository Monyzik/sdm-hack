from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

DocxEventType = Literal["docx_added", "docx_changed"]
MonitoringEventType = Literal[
    "task_changed",
    "risk_changed",
    "budget_changed",
    "dependency_changed",
    "communication_changed",
    "manual_monitoring_requested",
]
ProjectEventType = DocxEventType | MonitoringEventType


class ProjectControlData(BaseModel):
    event_type: ProjectEventType
    file_path: str | None = None
    project_id: str | None = None
    as_of: date | None = None
    parsed_project: dict[str, Any] | None = None
    monitoring: dict[str, Any] | None = None


def state_value(state: ProjectControlData | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, ProjectControlData):
        return getattr(state, key)
    return state.get(key, default)
