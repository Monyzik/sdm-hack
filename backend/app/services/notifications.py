from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.app.database.models import Notification


def upsert_notification_from_draft(
    session: Session,
    *,
    project_id: str,
    draft: Mapping[str, Any] | None,
    source: str = "monitoring_graph",
) -> Notification | None:
    if not draft or not bool(draft.get("should_create")):
        return None

    deduplication_key = _string_value(draft.get("deduplication_key"))
    if not deduplication_key:
        severity = _string_value(draft.get("severity"))
        title = _string_value(draft.get("title"))
        deduplication_key = f"{project_id}:{severity}:{title}"

    notification = session.scalar(
        select(Notification).where(
            Notification.project_id == project_id,
            Notification.deduplication_key == deduplication_key,
        )
    )

    if notification is None:
        notification = Notification(
            id=_notification_id(),
            project_id=project_id,
            created_at=datetime.utcnow(),
            is_read=False,
            read_at=None,
        )
        session.add(notification)

    payload = dict(draft)
    payload["project_id"] = project_id

    notification.updated_at = datetime.utcnow()
    notification.source = source
    notification.target_role = _string_value(draft.get("target_role"))
    notification.recipient_hint = _optional_string_value(draft.get("recipient_hint"))
    notification.severity = _string_value(draft.get("severity"))
    notification.title = _string_value(draft.get("title"))
    notification.body = _string_value(draft.get("body"))
    notification.reason = _string_value(draft.get("reason"))
    notification.action_items = _string_list(draft.get("action_items"))
    notification.requires_acknowledgement = bool(draft.get("requires_acknowledgement"))
    notification.deduplication_key = deduplication_key
    notification.payload = payload

    session.flush()
    return notification


def list_notifications(
    session: Session,
    *,
    project_id: str | None = None,
    severity: str | None = None,
    unread_only: bool = False,
    limit: int = 100,
) -> list[Notification]:
    conditions = _notification_conditions(
        project_id=project_id,
        severity=severity,
        unread_only=unread_only,
    )
    statement = (
        select(Notification)
        .options(joinedload(Notification.project))
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(statement))


def mark_notification_read(session: Session, notification_id: str) -> Notification | None:
    notification = session.scalar(
        select(Notification)
        .options(joinedload(Notification.project))
        .where(Notification.id == notification_id)
    )
    if notification is None:
        return None

    if not notification.is_read:
        now = datetime.utcnow()
        notification.is_read = True
        notification.read_at = now
        notification.updated_at = now

    session.flush()
    return notification


def count_notifications(
    session: Session,
    *,
    project_id: str | None = None,
    severity: str | None = None,
    unread_only: bool = False,
) -> int:
    conditions = _notification_conditions(
        project_id=project_id,
        severity=severity,
        unread_only=unread_only,
    )
    statement = select(func.count()).select_from(Notification).where(*conditions)
    return int(session.scalar(statement) or 0)


def _notification_conditions(
    *,
    project_id: str | None,
    severity: str | None,
    unread_only: bool,
) -> list[Any]:
    conditions: list[Any] = []
    if project_id:
        conditions.append(Notification.project_id == project_id)
    if severity:
        conditions.append(Notification.severity == severity)
    if unread_only:
        conditions.append(Notification.is_read.is_(False))
    return conditions


def _notification_id() -> str:
    return f"N{uuid4().hex[:15]}"


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_string_value(value: Any) -> str | None:
    string_value = _string_value(value)
    return string_value or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_string_value(item) for item in value if _string_value(item)]
