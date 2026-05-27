from __future__ import annotations

from typing import Any

from ..constants import DOCX_EVENTS, MONITORING_EVENTS
from ..state import ProjectControlData, state_value


def route_event(state: ProjectControlData | dict[str, Any]) -> str:
    event_type = state_value(state, "event_type")

    if event_type in DOCX_EVENTS:
        if not state_value(state, "file_path"):
            raise ValueError("Для DOCX-события нужен file_path")
        return "docx"

    if event_type in MONITORING_EVENTS:
        if not state_value(state, "project_id"):
            raise ValueError("Для события мониторинга нужен project_id")
        return "monitor"

    raise ValueError(f"Неизвестный тип события: {event_type}")
