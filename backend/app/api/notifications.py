from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

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
def get_notifications(
    project_id: str | None = Query(default=None),
    severity: str | None = Query(default=None, pattern="^(info|warning|critical)$"),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> NotificationList:
    notifications = list_notifications(
        session,
        project_id=project_id,
        severity=severity,
        unread_only=unread_only,
        limit=limit,
    )
    return NotificationList(
        total=count_notifications(
            session,
            project_id=project_id,
            severity=severity,
            unread_only=unread_only,
        ),
        unread_count=count_notifications(
            session,
            project_id=project_id,
            severity=severity,
            unread_only=True,
        ),
        items=[notification_to_item(notification) for notification in notifications],
    )


@router.patch("/{notification_id}/read", response_model=NotificationItem)
def read_notification(
    notification_id: str,
    session: Session = Depends(get_session),
) -> NotificationItem:
    notification = mark_notification_read(session, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    session.commit()
    return notification_to_item(notification)


def notification_to_item(notification: Notification) -> NotificationItem:
    project_name = notification.project.name if notification.project else None
    return NotificationItem(
        id=notification.id,
        project_id=notification.project_id,
        project_name=project_name,
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
