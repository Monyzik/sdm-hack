from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from sdm.backend.services.data_classes import ProjectSummarySource


@dataclass(frozen=True)
class EvidenceCandidate:
    project_id: str
    source_table: str
    source_id: str
    entity_type: str
    entity_id: str
    title: str
    text: str
    occurred_at: datetime | None = None
    linked_task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def build_project_evidence(
    source: ProjectSummarySource,
    *,
    as_of: date | None,
) -> list[EvidenceCandidate]:
    """Build snapshot evidence plus events observed by ``as_of``.

    Undated snapshot entities (including tasks and dependencies) are current state,
    not reconstructed historical state: their creation/status history is incomplete.
    Planned deadlines are never observation timestamps. Communication aggregates
    updated after the cutoff are omitted; their individually dated messages remain
    available without claiming to reconstruct the earlier aggregate status.
    """
    tasks_by_id = {task.id: task for task in source.tasks}
    communications_by_id = {
        communication.id: communication for communication in source.communications
    }
    milestones_by_id = {milestone.id: milestone for milestone in source.milestones}

    candidates: list[EvidenceCandidate] = [
        EvidenceCandidate(
            project_id=source.project.id,
            source_table="projects",
            source_id=source.project.id,
            entity_type="project",
            entity_id=source.project.id,
            title=source.project.name,
            text=" ".join(
                [
                    source.project.business_goal,
                    source.project.expected_result,
                    source.project.business_value,
                ]
            ),
            metadata={
                "priority": source.project.priority,
                "lifecycle_status": source.project.lifecycle_status,
            },
        )
    ]

    for task in source.tasks:
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="tasks",
                source_id=task.id,
                entity_type="task",
                entity_id=task.id,
                title=f"{task.external_id}: {task.title}",
                text=task.blocker_reason or task.title,
                linked_task_id=task.id,
                metadata={
                    "external_id": task.external_id,
                    "status": task.status,
                    "priority": task.priority,
                    "assignee_name": task.assignee_name,
                    "planned_due_date": task.planned_due_date.isoformat(),
                },
            )
        )

    for comment in source.task_comments:
        if not _is_observed(comment.created_at, as_of):
            continue
        task = tasks_by_id.get(comment.task_id)
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="task_comments",
                source_id=comment.id,
                entity_type="task_comment",
                entity_id=comment.task_id,
                title=f"Комментарий по {task.external_id if task else comment.task_id}",
                text=comment.text,
                occurred_at=comment.created_at,
                linked_task_id=comment.task_id,
                metadata={
                    "author_name": comment.author_name,
                    "channel": comment.channel,
                    "task_title": task.title if task else None,
                    "source_system": comment.source_system,
                },
            )
        )

    for history_item in source.task_history:
        if not _is_observed(history_item.changed_at, as_of):
            continue
        task = tasks_by_id.get(history_item.task_id)
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="task_history",
                source_id=history_item.id,
                entity_type="task_history",
                entity_id=history_item.task_id,
                title=f"Изменение {history_item.field_changed} по {task.external_id if task else history_item.task_id}",
                text=f"{history_item.field_changed}: {history_item.old_value} -> {history_item.new_value}",
                occurred_at=history_item.changed_at,
                linked_task_id=history_item.task_id,
                metadata={
                    "task_title": task.title if task else None,
                    "changed_by": history_item.changed_by,
                    "source_system": history_item.source_system,
                },
            )
        )

    for risk in source.risks:
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="risks",
                source_id=risk.id,
                entity_type="risk",
                entity_id=risk.id,
                title=f"{risk.risk_type}: {risk.status}",
                text=f"{risk.description} План снижения риска: {risk.mitigation_plan}",
                linked_task_id=risk.linked_task_id,
                metadata={
                    "owner_name": risk.owner_name,
                    "score": risk.probability * risk.impact,
                    "probability": risk.probability,
                    "impact": risk.impact,
                },
            )
        )

    for communication in source.communications:
        if not _is_observed(communication.last_message_date, as_of):
            continue
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="communications",
                source_id=communication.id,
                entity_type="communication",
                entity_id=communication.id,
                title=communication.topic,
                text=(
                    f"{communication.from_team} -> {communication.to_team}. "
                    f"Статус: {communication.status}. Канал: {communication.channel}."
                ),
                occurred_at=_date_to_datetime(communication.last_message_date),
                linked_task_id=communication.linked_task_id,
                metadata={
                    "from_team": communication.from_team,
                    "to_team": communication.to_team,
                    "importance": communication.importance,
                    "expected_response_date": communication.expected_response_date.isoformat(),
                },
            )
        )

    for message in source.communication_messages:
        if not _is_observed(message.message_time, as_of):
            continue
        communication = communications_by_id.get(message.communication_id)
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="communication_messages",
                source_id=message.id,
                entity_type="communication_message",
                entity_id=message.communication_id,
                title=communication.topic if communication else message.communication_id,
                text=message.summary,
                occurred_at=message.message_time,
                linked_task_id=message.linked_task_id,
                metadata={
                    "sender_team": message.sender_team,
                    "recipient_team": message.recipient_team,
                    "channel": message.channel,
                    "message_type": message.message_type,
                    "status": message.status,
                    "is_escalation": message.is_escalation,
                },
            )
        )

    for dependency in source.task_dependencies:
        task = tasks_by_id.get(dependency.task_id)
        depends_on_task = tasks_by_id.get(dependency.depends_on_task_id)
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="task_dependencies",
                source_id=dependency.id,
                entity_type="task_dependency",
                entity_id=dependency.id,
                title=f"{dependency.task_id} зависит от {dependency.depends_on_task_id}",
                text=dependency.reason,
                linked_task_id=dependency.task_id,
                metadata={
                    "task_title": task.title if task else None,
                    "depends_on_task_title": depends_on_task.title if depends_on_task else None,
                    "dependency_type": dependency.dependency_type,
                    "is_critical_path": dependency.is_critical_path,
                    "lag_days": dependency.lag_days,
                },
            )
        )

    for dependency in source.dependencies:
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="dependencies",
                source_id=dependency.id,
                entity_type="project_dependency",
                entity_id=dependency.id,
                title=dependency.depends_on,
                text=(
                    f"{dependency.dependency_type}, владелец {dependency.owner_team}, "
                    f"статус {dependency.status}, критичность {dependency.criticality}."
                ),
                linked_task_id=dependency.linked_task_id,
                metadata={
                    "owner_team": dependency.owner_team,
                    "expected_date": dependency.expected_date.isoformat(),
                    "status": dependency.status,
                    "criticality": dependency.criticality,
                },
            )
        )

    for decision in source.decisions:
        if not _is_observed(decision.decision_date, as_of):
            continue
        milestone = milestones_by_id.get(decision.linked_milestone_id or "")
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="decisions",
                source_id=decision.id,
                entity_type="decision",
                entity_id=decision.id,
                title=decision.decision_type,
                text=decision.description,
                occurred_at=_date_to_datetime(decision.decision_date),
                metadata={
                    "decision_owner": decision.decision_owner,
                    "status": decision.status,
                    "linked_milestone": milestone.name
                    if milestone
                    else decision.linked_milestone_id,
                },
            )
        )

    for request in source.change_requests:
        if not _is_observed(request.request_date, as_of):
            continue
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="change_requests",
                source_id=request.id,
                entity_type="change_request",
                entity_id=request.id,
                title=request.change_type,
                text=request.description,
                occurred_at=_date_to_datetime(request.request_date),
                metadata={
                    "requested_by": request.requested_by,
                    "requested_budget_delta": request.requested_budget_delta,
                    "requested_timeline_delta_days": request.requested_timeline_delta_days,
                    "status": request.status,
                },
            )
        )

    for item in source.budget_line_items:
        candidates.append(
            EvidenceCandidate(
                project_id=source.project.id,
                source_table="budget_line_items",
                source_id=item.id,
                entity_type="budget_line_item",
                entity_id=item.id,
                title=item.item_name,
                text=f"{item.category}: {item.item_name}, команда-владелец {item.owner_team}.",
                metadata={
                    "planned_amount": item.planned_amount,
                    "actual_amount": item.actual_amount,
                    "owner_team": item.owner_team,
                },
            )
        )

    return candidates


def evidence_embedding_text(candidate: EvidenceCandidate) -> str:
    metadata = " ".join(str(value) for value in candidate.metadata.values() if value is not None)
    return " ".join(
        [
            candidate.source_table,
            candidate.source_id,
            candidate.entity_type,
            candidate.entity_id,
            candidate.linked_task_id or "",
            candidate.title,
            candidate.text,
            metadata,
        ]
    )


def _is_observed(value: date | datetime, as_of: date | None) -> bool:
    if as_of is None:
        return True
    observed_date = value.date() if isinstance(value, datetime) else value
    return observed_date <= as_of


def _date_to_datetime(value: date) -> datetime:
    return datetime.combine(value, time(hour=12))
