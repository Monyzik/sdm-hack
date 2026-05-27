from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NotificationSeverity = Literal["info", "warning", "critical"]
NotificationTargetRole = Literal["teamlead", "project_manager", "portfolio_manager"]


class InternalNotificationDraft(BaseModel):
    should_create: bool = Field(description="Нужно ли создавать уведомление в сервисе")
    project_id: str = Field(description="Идентификатор проекта")
    as_of_date: str | None = Field(None, description="Дата среза метрик в формате YYYY-MM-DD")
    trigger_event_type: str | None = Field(None, description="Тип события, после которого создано уведомление")
    trigger_event_label: str | None = Field(None, description="Человекочитаемое описание события")
    target_role: NotificationTargetRole = Field(description="Роль получателя уведомления")
    recipient_hint: str | None = Field(None, description="Подсказка по получателю из данных проекта")
    severity: NotificationSeverity = Field(description="Важность внутреннего уведомления")
    title: str = Field(description="Короткий заголовок для центра уведомлений")
    body: str = Field(description="Текст внутреннего push-уведомления")
    reason: str = Field(description="Почему уведомление нужно создать или не создавать")
    action_items: list[str] = Field(description="Короткие действия для получателя")
    requires_acknowledgement: bool = Field(description="Нужно ли подтверждение прочтения")
    deduplication_key: str = Field(description="Ключ для будущего подавления дублей")
