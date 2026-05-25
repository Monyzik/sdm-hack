from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: str
    project_id: str
    project_name: str | None
    as_of_date: date | None
    trigger_event_type: str | None
    trigger_event_label: str | None
    created_at: datetime
    updated_at: datetime
    source: str
    target_role: str
    recipient_hint: str | None
    severity: str
    title: str
    body: str
    reason: str
    action_items: list[str]
    requires_acknowledgement: bool
    deduplication_key: str
    is_read: bool
    read_at: datetime | None


class NotificationList(BaseModel):
    total: int
    unread_count: int
    items: list[NotificationItem]
