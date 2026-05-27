from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.agents.internal_notifications import ProjectInternalNotificationAgent
from sdm.backend.services.notifications import upsert_notification_from_draft

from ..state import ProjectMonitorData, state_value


def draft_notification_node(agent: ProjectInternalNotificationAgent) -> Any:
    async def draft_notification(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        metrics = state_value(state, "metrics", {})
        notification_draft = await agent.draft(
            project=state_value(state, "project", {}),
            metrics=metrics,
            alerts=state_value(state, "alerts", []),
            analysis=state_value(state, "analysis", {}),
        )
        draft = notification_draft.model_dump(mode="json")
        if metrics.get("as_of_date"):
            draft["as_of_date"] = str(metrics["as_of_date"])
        trigger_event = state_value(state, "trigger_event")
        if trigger_event:
            draft["trigger_event"] = trigger_event
            draft["trigger_event_type"] = trigger_event.get("type")
            draft["trigger_event_label"] = trigger_event.get("label")
        return {"notification_draft": draft}

    return draft_notification


def persist_notification_node(session_factory: async_sessionmaker[AsyncSession]) -> Any:
    async def persist_notification(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        project_id = state_value(state, "project_id")
        notification_draft = state_value(state, "notification_draft")
        if not project_id or not notification_draft:
            return {"notification_id": None}

        async with session_factory() as session:
            notification = await upsert_notification_from_draft(
                session,
                project_id=project_id,
                draft=notification_draft,
            )
            notification_id = None if notification is None else notification.id
            await session.commit()

        return {"notification_id": notification_id}

    return persist_notification
