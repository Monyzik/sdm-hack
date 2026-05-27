from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas.project_summary import (
    ProjectEvidenceChunk,
    ProjectRetrievalContext,
    ProjectRetrievalIndexResult,
)
from backend.app.services.data_classes import ProjectSummarySource
from backend.app.services.yandex_embeddings import YandexEmbeddingClient


DEFAULT_LIMIT = 8
MAX_LIMIT = 20
EMBEDDING_DIMENSIONS = 256
RAG_TABLE_NAME = "project_rag_chunks"
TOKEN_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+")


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


async def ensure_project_rag_schema(session: AsyncSession) -> None:
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    await session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {RAG_TABLE_NAME} (
                id TEXT PRIMARY KEY,
                project_id VARCHAR(16) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                source_table VARCHAR(64) NOT NULL,
                source_id VARCHAR(64) NOT NULL,
                entity_type VARCHAR(64) NOT NULL,
                entity_id VARCHAR(64) NOT NULL,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                occurred_at TIMESTAMP NULL,
                linked_task_id VARCHAR(64) NULL,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                embedding vector({EMBEDDING_DIMENSIONS}) NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT now(),
                UNIQUE (project_id, source_table, source_id)
            )
            """
        )
    )
    await session.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_{RAG_TABLE_NAME}_project_id "
            f"ON {RAG_TABLE_NAME} (project_id)"
        )
    )


async def reindex_project_rag(
    session: AsyncSession,
    source: ProjectSummarySource,
    *,
    embedding_client: YandexEmbeddingClient,
    as_of: date | None = None,
) -> ProjectRetrievalIndexResult:
    await ensure_project_rag_schema(session)
    candidates = _project_evidence_candidates(source, as_of=as_of)
    dimensions = 0

    await session.execute(
        text(f"DELETE FROM {RAG_TABLE_NAME} WHERE project_id = :project_id"),
        {"project_id": source.project.id},
    )
    for candidate in candidates:
        embedding = await embedding_client.embed_document(_candidate_text(candidate))
        dimensions = len(embedding)
        await session.execute(
            text(
                f"""
                INSERT INTO {RAG_TABLE_NAME} (
                    id,
                    project_id,
                    source_table,
                    source_id,
                    entity_type,
                    entity_id,
                    title,
                    text,
                    occurred_at,
                    linked_task_id,
                    metadata,
                    embedding,
                    updated_at
                )
                VALUES (
                    :id,
                    :project_id,
                    :source_table,
                    :source_id,
                    :entity_type,
                    :entity_id,
                    :title,
                    :text,
                    :occurred_at,
                    :linked_task_id,
                    CAST(:metadata AS jsonb),
                    CAST(:embedding AS vector),
                    now()
                )
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    text = EXCLUDED.text,
                    occurred_at = EXCLUDED.occurred_at,
                    linked_task_id = EXCLUDED.linked_task_id,
                    metadata = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding,
                    updated_at = now()
                """
            ),
            {
                "id": _chunk_id(candidate),
                "project_id": candidate.project_id,
                "source_table": candidate.source_table,
                "source_id": candidate.source_id,
                "entity_type": candidate.entity_type,
                "entity_id": candidate.entity_id,
                "title": candidate.title,
                "text": candidate.text,
                "occurred_at": candidate.occurred_at,
                "linked_task_id": candidate.linked_task_id,
                "metadata": _json_metadata(candidate.metadata),
                "embedding": _vector_literal(embedding),
            },
        )
    await session.commit()
    return ProjectRetrievalIndexResult(
        project_id=source.project.id,
        chunks_indexed=len(candidates),
        embedding_model=embedding_client.doc_model,
        embedding_dimensions=dimensions,
    )


async def search_project_rag(
    session: AsyncSession,
    source: ProjectSummarySource,
    *,
    query: str,
    embedding_client: YandexEmbeddingClient,
    as_of: date | None = None,
    limit: int = DEFAULT_LIMIT,
    entity_id: str | None = None,
) -> ProjectRetrievalContext:
    await ensure_project_rag_schema(session)
    query = " ".join(query.split())
    bounded_limit = max(1, min(MAX_LIMIT, limit))
    candidate_limit = min(60, max(bounded_limit * 5, 20))
    if await _indexed_chunks_count(session, source.project.id) == 0:
        await reindex_project_rag(
            session,
            source,
            embedding_client=embedding_client,
            as_of=None,
        )
    query_embedding = await embedding_client.embed_query(query)
    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                    id,
                    project_id,
                    source_table,
                    source_id,
                    entity_type,
                    entity_id,
                    title,
                    text,
                    occurred_at,
                    linked_task_id,
                    metadata,
                    1 - (embedding <=> CAST(:embedding AS vector)) AS score
                FROM {RAG_TABLE_NAME}
                WHERE project_id = :project_id
                  AND (
                    CAST(:as_of_date AS date) IS NULL
                    OR occurred_at IS NULL
                    OR occurred_at::date <= CAST(:as_of_date AS date)
                  )
                  AND (
                    CAST(:entity_id AS text) IS NULL
                    OR source_id = CAST(:entity_id AS text)
                    OR entity_id = CAST(:entity_id AS text)
                    OR linked_task_id = CAST(:entity_id AS text)
                    OR metadata::text ILIKE :entity_pattern
                  )
                ORDER BY embedding <=> CAST(:embedding AS vector), occurred_at DESC NULLS LAST, source_id
                LIMIT :candidate_limit
                """
            ),
            {
                "project_id": source.project.id,
                "embedding": _vector_literal(query_embedding),
                "as_of_date": as_of,
                "entity_id": entity_id,
                "entity_pattern": f"%{entity_id}%" if entity_id else None,
                "candidate_limit": candidate_limit,
            },
        )
    ).mappings().all()
    ranked_rows = sorted(
        rows,
        key=lambda row: (
            float(row["score"] or 0.0) + _lexical_boost(row, query=query, entity_id=entity_id),
            row["occurred_at"] or datetime.min,
            str(row["source_id"]),
        ),
        reverse=True,
    )[:bounded_limit]

    return ProjectRetrievalContext(
        project_id=source.project.id,
        query=query,
        as_of_date=as_of,
        count=len(ranked_rows),
        items=[
            ProjectEvidenceChunk(
                id=str(row["id"]),
                project_id=str(row["project_id"]),
                source_table=str(row["source_table"]),
                source_id=str(row["source_id"]),
                entity_type=str(row["entity_type"]),
                entity_id=str(row["entity_id"]),
                title=str(row["title"]),
                text=str(row["text"]),
                occurred_at=row["occurred_at"],
                linked_task_id=row["linked_task_id"],
                score=round(
                    float(row["score"] or 0.0)
                    + _lexical_boost(row, query=query, entity_id=entity_id),
                    6,
                ),
                metadata=dict(row["metadata"] or {}),
            )
            for row in ranked_rows
        ],
    )

def _project_evidence_candidates(
    source: ProjectSummarySource,
    *,
    as_of: date | None,
) -> list[EvidenceCandidate]:
    tasks_by_id = {task.id: task for task in source.tasks}
    communications_by_id = {communication.id: communication for communication in source.communications}
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
                occurred_at=_date_to_datetime(task.planned_due_date),
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
                occurred_at=_date_to_datetime(dependency.expected_date),
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
                    "linked_milestone": milestone.name if milestone else decision.linked_milestone_id,
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


def _candidate_text(candidate: EvidenceCandidate) -> str:
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


def _lexical_boost(row: Any, *, query: str, entity_id: str | None) -> float:
    normalized_query = _normalize(query)
    normalized_title = _normalize(row["title"])
    normalized_text = _normalize(row["text"])
    metadata = dict(row["metadata"] or {})
    metadata_text = " ".join(str(value) for value in metadata.values() if value is not None)
    haystack = _normalize(
        " ".join(
            [
                str(row["source_table"]),
                str(row["source_id"]),
                str(row["entity_type"]),
                str(row["entity_id"]),
                str(row["linked_task_id"] or ""),
                str(row["title"]),
                str(row["text"]),
                metadata_text,
            ]
        )
    )
    boost = 0.0

    if normalized_title and normalized_title in normalized_query:
        boost += 2.0
    if len(normalized_text) >= 16 and normalized_text in normalized_query:
        boost += 1.0
    if normalized_query and normalized_query in haystack:
        boost += 0.8

    query_tokens = {
        token for token in TOKEN_PATTERN.findall(normalized_query) if len(token) >= 4
    }
    haystack_tokens = set(TOKEN_PATTERN.findall(haystack))
    if query_tokens and haystack_tokens:
        boost += min(0.8, 0.08 * len(query_tokens & haystack_tokens))

    if "заблок" in normalized_query and "заблок" in haystack:
        boost += 0.4
    if entity_id and _normalize(entity_id) in {
        _normalize(row["source_id"]),
        _normalize(row["entity_id"]),
        _normalize(row["linked_task_id"] or ""),
    }:
        boost += 2.0
    return boost


def _chunk_id(candidate: EvidenceCandidate) -> str:
    return f"{candidate.project_id}:{candidate.source_table}:{candidate.source_id}"


def _json_metadata(metadata: dict[str, Any]) -> str:
    return json.dumps({key: value for key, value in metadata.items() if value is not None}, ensure_ascii=False)


async def _indexed_chunks_count(session: AsyncSession, project_id: str) -> int:
    value = await session.scalar(
        text(f"SELECT count(*) FROM {RAG_TABLE_NAME} WHERE project_id = :project_id"),
        {"project_id": project_id},
    )
    return int(value or 0)


def _vector_literal(values: list[float]) -> str:
    if len(values) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Размерность вектора Yandex не совпадает: ожидалось {EMBEDDING_DIMENSIONS}, получено {len(values)}."
        )
    return "[" + ",".join(f"{value:.9f}" for value in values) + "]"


def _normalize(value: Any) -> str:
    return str(value or "").casefold().replace("ё", "е")


def _is_observed(value: date | datetime, as_of: date | None) -> bool:
    if as_of is None:
        return True
    observed_date = value.date() if isinstance(value, datetime) else value
    return observed_date <= as_of


def _date_to_datetime(value: date) -> datetime:
    return datetime.combine(value, time(hour=12))
