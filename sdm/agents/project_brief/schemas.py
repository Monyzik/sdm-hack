from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BusinessImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delay_days: int | None = Field(None, description="Оценка задержки в днях из входных метрик.")
    cost_of_delay: int | None = Field(None, description="Денежный exposure задержки из входных метрик.")
    budget_delta: int | None = Field(None, description="Отклонение или влияние на бюджет из входных данных.")
    impact_summary: str = Field(description="Короткое объяснение влияния на срок, деньги и результат проекта.")


class AgentActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(description="Конкретное действие, которое можно поручить.")
    owner_hint: str = Field(description="Кому адресовать действие по входным фактам.")
    deadline: str = Field(description="Срок реакции человеческим языком, без выдуманной даты.")
    success_signal: str = Field(description="Как понять, что действие сработало.")


class DraftMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_hint: str = Field(description="Кому отправить сообщение по входным фактам.")
    subject: str = Field(description="Короткая тема сообщения.")
    body: str = Field(description="Готовый черновик сообщения без технических id.")


class FollowUpCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_after: str = Field(description="Когда агент должен проверить изменения.")
    success_condition: str = Field(description="Какой факт во входных данных будет означать улучшение.")
    escalation_condition: str = Field(
        description="Что считать поводом вынести решение на комитет или зафиксировать отдельное поручение."
    )


class DecisionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option: str = Field(description="Короткое название управленческой опции.")
    when_to_choose: str = Field(description="Когда эту опцию стоит выбрать.")
    tradeoff: str = Field(description="Цена решения или риск компромисса.")


class ProjectManagerBrief(BaseModel):
    """Строгий контракт управленческой рекомендации для руководителя проекта."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["в норме", "под наблюдением", "критично"] = Field(
        description="Человеческая оценка состояния проекта."
    )
    headline: str = Field(description="Одна строка о главном управленческом выводе без технических id.")
    management_question: str = Field(
        description="Главный вопрос, который должен решить руководитель проектов или комитет."
    )
    diagnosis: str = Field(description="Короткая причинно-следственная диагностика, а не пересказ метрик.")
    bottleneck: str = Field(description="Одно главное узкое место, которое сильнее всего удерживает проект.")
    critical_path: list[str] = Field(
        min_length=2,
        max_length=3,
        description="Цепочка зависимостей, объясняющая почему проблема распространяется дальше.",
    )
    recommended_move: str = Field(description="Один лучший следующий управленческий ход с ожидаемым эффектом.")
    decision_options: list[DecisionOption] = Field(
        min_length=2,
        max_length=3,
        description="Реальные развилки решения с компромиссами.",
    )
    business_impact: BusinessImpact = Field(description="Перевод проблемы в срок, деньги и решение по проекту.")
    next_actions: list[AgentActionItem] = Field(
        min_length=1,
        max_length=3,
        description="Поручения, которые можно создать в системе по рекомендации агента.",
    )
    draft_message: DraftMessage = Field(
        description="Черновик управленческого сообщения владельцу блокера или решения."
    )
    follow_up_check: FollowUpCheck = Field(
        description="Правило последующей проверки, чтобы агент не заканчивался текстом."
    )
    watchouts: list[str] = Field(
        min_length=1,
        max_length=3,
        description="Что не стоит делать или что проверить перед решением.",
    )
    evidence_ids: list[str] = Field(
        max_length=20,
        description="ID источников из JSON проблемного контекста для трассировки. Не показывать в обычном тексте.",
    )
    missing_data: list[str] = Field(
        max_length=3,
        description="Каких данных не хватает. Вернуть пустой список, если данных достаточно.",
    )
