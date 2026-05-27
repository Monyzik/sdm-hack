from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sdm.agents.internal_notifications import ProjectInternalNotificationAgent
from sdm.agents.project_analysis import ProjectAnalystAgent
from sdm.agents.project_monitor import run_project_monitor

from ..constants import EVENT_LABELS
from ..state import ProjectControlData, state_value


def build_trigger_event_context(state: ProjectControlData | dict[str, Any], project_id: str) -> dict[str, Any]:
    event_type = state_value(state, "event_type")
    raw_file_path = state_value(state, "file_path")
    trigger_event = {
        "type": event_type,
        "label": EVENT_LABELS.get(event_type, str(event_type)),
        "project_id": project_id,
    }
    if raw_file_path:
        file_path = Path(raw_file_path)
        trigger_event["file_path"] = str(file_path)
        trigger_event["file_name"] = file_path.name
        trigger_event["label"] = f"{trigger_event['label']}: {file_path.name}"
    return trigger_event


def monitor_project_node(
    session_factory: async_sessionmaker[AsyncSession],
    analyst: ProjectAnalystAgent | None = None,
    notification_agent: ProjectInternalNotificationAgent | None = None,
) -> Any:
    async def monitor_project(state: ProjectControlData | dict[str, Any]) -> dict[str, Any]:
        project_id = state_value(state, "project_id")
        if not project_id:
            raise ValueError("Нет project_id для запуска мониторинга")

        monitoring_result = await run_project_monitor(
            project_id,
            as_of=state_value(state, "as_of"),
            trigger_event=build_trigger_event_context(state, project_id),
            session_factory=session_factory,
            analyst=analyst,
            notification_agent=notification_agent,
        )

        return {
            "monitoring": {
                "project": monitoring_result["project"],
                "metrics": monitoring_result["metrics"],
                "alerts": monitoring_result["alerts"],
                "analysis": monitoring_result["analysis"],
                "notification_draft": monitoring_result["notification_draft"],
                "notification_id": monitoring_result["notification_id"],
            },
        }

    return monitor_project
