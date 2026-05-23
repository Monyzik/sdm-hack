from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    business_goal: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    business_value: Mapped[str] = mapped_column(Text, nullable=False)

    tasks: Mapped[list[Task]] = relationship(back_populates="project")
    task_history: Mapped[list[TaskHistory]] = relationship(back_populates="project")
    task_comments: Mapped[list[TaskComment]] = relationship(back_populates="project")
    milestones: Mapped[list[Milestone]] = relationship(back_populates="project")
    budget: Mapped[Budget | None] = relationship(back_populates="project")
    risks: Mapped[list[Risk]] = relationship(back_populates="project")
    communications: Mapped[list[Communication]] = relationship(back_populates="project")
    resource_allocations: Mapped[list[ResourceAllocation]] = relationship(back_populates="project")
    task_dependencies: Mapped[list[TaskDependency]] = relationship(back_populates="project")
    budget_line_items: Mapped[list[BudgetLineItem]] = relationship(back_populates="project")
    communication_messages: Mapped[list[CommunicationMessage]] = relationship(back_populates="project")
    dependencies: Mapped[list[ProjectDependency]] = relationship(back_populates="project")
    decisions: Mapped[list[Decision]] = relationship(back_populates="project")
    change_requests: Mapped[list[ChangeRequest]] = relationship(back_populates="project")


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(128), nullable=False)
    team: Mapped[str] = mapped_column(String(128), nullable=False)
    available_hours_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    hour_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    seniority: Mapped[str] = mapped_column(String(64), nullable=False)

    tasks: Mapped[list[Task]] = relationship(back_populates="assignee")
    allocations: Mapped[list[ResourceAllocation]] = relationship(back_populates="resource")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    assignee_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), nullable=False, index=True)
    assignee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    planned_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_end_date: Mapped[date | None] = mapped_column(Date)
    estimated_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    spent_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    blocker_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    project: Mapped[Project] = relationship(back_populates="tasks")
    assignee: Mapped[Resource] = relationship(back_populates="tasks")
    history: Mapped[list[TaskHistory]] = relationship(back_populates="task")
    comments: Mapped[list[TaskComment]] = relationship(back_populates="task")


class TaskHistory(Base):
    __tablename__ = "task_history"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    field_changed: Mapped[str] = mapped_column(String(128), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, nullable=False)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(ForeignKey("resources.id"), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)

    project: Mapped[Project] = relationship(back_populates="task_history")
    task: Mapped[Task] = relationship(back_populates="history")


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), nullable=False, index=True)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    mentions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)

    project: Mapped[Project] = relationship(back_populates="task_comments")
    task: Mapped[Task] = relationship(back_populates="comments")


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    actual_end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    responsible_team: Mapped[str] = mapped_column(String(128), nullable=False)

    project: Mapped[Project] = relationship(back_populates="milestones")
    decisions: Mapped[list[Decision]] = relationship(back_populates="linked_milestone")


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, unique=True)
    planned_budget: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actual_spent: Mapped[int] = mapped_column(BigInteger, nullable=False)
    forecast_total_spent: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_economic_effect: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_of_delay_per_day: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    project: Mapped[Project] = relationship(back_populates="budget")
    line_items: Mapped[list[BudgetLineItem]] = relationship(back_populates="budget")


class BudgetLineItem(Base):
    __tablename__ = "budget_line_items"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    budget_id: Mapped[str] = mapped_column(ForeignKey("budgets.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    planned_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actual_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    forecast_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_team: Mapped[str] = mapped_column(String(128), nullable=False)

    project: Mapped[Project] = relationship(back_populates="budget_line_items")
    budget: Mapped[Budget] = relationship(back_populates="line_items")


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    risk_type: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    probability: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mitigation_plan: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    linked_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)

    project: Mapped[Project] = relationship(back_populates="risks")


class Communication(Base):
    __tablename__ = "communications"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    from_team: Mapped[str] = mapped_column(String(128), nullable=False)
    to_team: Mapped[str] = mapped_column(String(128), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    last_message_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_response_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    importance: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)

    project: Mapped[Project] = relationship(back_populates="communications")
    messages: Mapped[list[CommunicationMessage]] = relationship(back_populates="communication")


class CommunicationMessage(Base):
    __tablename__ = "communication_messages"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    communication_id: Mapped[str] = mapped_column(ForeignKey("communications.id"), nullable=False, index=True)
    message_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sender_team: Mapped[str] = mapped_column(String(128), nullable=False)
    recipient_team: Mapped[str] = mapped_column(String(128), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    message_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    linked_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    is_escalation: Mapped[bool] = mapped_column(Boolean, nullable=False)

    project: Mapped[Project] = relationship(back_populates="communication_messages")
    communication: Mapped[Communication] = relationship(back_populates="messages")


class ResourceAllocation(Base):
    __tablename__ = "resource_allocations"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    planned_hours_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_hours_per_week: Mapped[int] = mapped_column(Integer, nullable=False)

    resource: Mapped[Resource] = relationship(back_populates="allocations")
    project: Mapped[Project] = relationship(back_populates="resource_allocations")


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    depends_on_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    dependency_type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_critical_path: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lag_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    project: Mapped[Project] = relationship(back_populates="task_dependencies")


class ProjectDependency(Base):
    __tablename__ = "dependencies"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    dependency_type: Mapped[str] = mapped_column(String(64), nullable=False)
    depends_on: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_team: Mapped[str] = mapped_column(String(128), nullable=False)
    expected_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    criticality: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)

    project: Mapped[Project] = relationship(back_populates="dependencies")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    decision_date: Mapped[date] = mapped_column(Date, nullable=False)
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    decision_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    linked_milestone_id: Mapped[str | None] = mapped_column(ForeignKey("milestones.id"), index=True)

    project: Mapped[Project] = relationship(back_populates="decisions")
    linked_milestone: Mapped[Milestone | None] = relationship(back_populates="decisions")


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    impact_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    impact_budget: Mapped[int] = mapped_column(BigInteger, nullable=False)
    impact_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)

    project: Mapped[Project] = relationship(back_populates="change_requests")
