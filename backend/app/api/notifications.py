from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.models import Notification
from backend.app.dependencies import get_session
from backend.app.schemas.notifications import NotificationItem, NotificationList
from backend.app.services.notifications import (
    count_notifications,
    list_notifications,
    mark_notification_read,
)


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
async def get_notifications(
    project_id: str | None = Query(default=None),
    severity: str | None = Query(default=None, pattern="^(info|warning|critical)$"),
    as_of_date: date | None = Query(default=None),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> NotificationList:
    notifications = await list_notifications(
        session,
        project_id=project_id,
        severity=severity,
        as_of_date=as_of_date,
        unread_only=unread_only,
        limit=limit,
    )
    return NotificationList(
        total=await count_notifications(
            session,
            project_id=project_id,
            severity=severity,
            as_of_date=as_of_date,
            unread_only=unread_only,
        ),
        unread_count=await count_notifications(
            session,
            project_id=project_id,
            severity=severity,
            as_of_date=as_of_date,
            unread_only=True,
        ),
        items=[notification_to_item(notification) for notification in notifications],
    )


@router.patch("/{notification_id}/read", response_model=NotificationItem)
async def read_notification(
    notification_id: str,
    session: AsyncSession = Depends(get_session),
) -> NotificationItem:
    notification = await mark_notification_read(session, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    await session.commit()
    return notification_to_item(notification)


def notification_to_item(notification: Notification) -> NotificationItem:
    project_name = notification.project.name if notification.project else None
    return NotificationItem(
        id=notification.id,
        project_id=notification.project_id,
        project_name=project_name,
        as_of_date=parse_notification_as_of_date(notification),
        trigger_event_type=parse_notification_trigger_event_type(notification),
        trigger_event_label=parse_notification_trigger_event_label(notification),
        created_at=notification.created_at,
        updated_at=notification.updated_at,
        source=notification.source,
        target_role=notification.target_role,
        recipient_hint=notification.recipient_hint,
        severity=notification.severity,
        title=notification.title,
        body=notification.body,
        reason=notification.reason,
        action_items=notification.action_items,
        requires_acknowledgement=notification.requires_acknowledgement,
        deduplication_key=notification.deduplication_key,
        is_read=notification.is_read,
        read_at=notification.read_at,
    )


def parse_notification_as_of_date(notification: Notification) -> date | None:
    raw_as_of_date = notification.payload.get("as_of_date")
    if not raw_as_of_date:
        return None
    try:
        return date.fromisoformat(str(raw_as_of_date))
    except ValueError:
        return None


def parse_notification_trigger_event_type(notification: Notification) -> str | None:
    value = notification.payload.get("trigger_event_type")
    if isinstance(value, str) and value.strip():
        return value.strip()

    trigger_event = notification.payload.get("trigger_event")
    if isinstance(trigger_event, dict):
        raw_type = trigger_event.get("type") or trigger_event.get("event_type")
        if raw_type:
            return str(raw_type).strip() or None
    return None


def parse_notification_trigger_event_label(notification: Notification) -> str | None:
    value = notification.payload.get("trigger_event_label")
    if isinstance(value, str) and value.strip():
        return value.strip()

    trigger_event = notification.payload.get("trigger_event")
    if isinstance(trigger_event, dict):
        raw_label = trigger_event.get("label")
        if raw_label:
            return str(raw_label).strip() or None
    return parse_notification_trigger_event_type(notification)
