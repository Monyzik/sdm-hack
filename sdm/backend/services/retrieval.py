from __future__ import annotations

import asyncio
import json
from datetime import date
from collections.abc import Mapping
from typing import Any, get_args

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sdm.backend.schemas.retrieval import (
    ProjectEvidenceChunk,
    ProjectRetrievalContext,
    ProjectRetrievalIndexResult,
    RankingMode,
    RetrievalScores,
)
from sdm.backend.services.data_classes import ProjectSummarySource
from sdm.backend.services.document_evidence import load_document_evidence
from sdm.backend.services.embeddings import EmbeddingClient, validate_embedding
from sdm.backend.services.project_evidence import (
    EvidenceCandidate,
    build_project_evidence,
    evidence_embedding_text,
)

from sdm.backend.services.ranking import (
    RankedCandidate,
    bm25_search,
    reciprocal_rank_fusion,
)

DEFAULT_LIMIT = 8
MAX_LIMIT = 20
EMBEDDING_BATCH_SIZE = 3
RAG_TABLE_NAME = "project_rag_chunks_v2"
FUSION_RANK_CONSTANT = 60


async def ensure_project_rag_schema(session: AsyncSession) -> None:
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    await session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {RAG_TABLE_NAME} (
                id TEXT NOT NULL,
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
                embedding_profile TEXT NOT NULL,
                embedding_dimensions INTEGER NOT NULL,
                embedding vector NOT NULL,
                CHECK (vector_dims(embedding) = embedding_dimensions),
                PRIMARY KEY (id, embedding_profile),
                updated_at TIMESTAMP NOT NULL DEFAULT now(),
                UNIQUE (project_id, source_table, source_id, embedding_profile)
            )
            """
        )
    )
    await session.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_{RAG_TABLE_NAME}_project_id "
            f"ON {RAG_TABLE_NAME} (project_id, embedding_profile)"
        )
    )


async def reindex_project_rag(
    session: AsyncSession,
    source: ProjectSummarySource,
    *,
    embedding_client: EmbeddingClient,
    as_of: date | None = None,
) -> ProjectRetrievalIndexResult:
    # Always build the complete index. as_of is a search filter, never a partial
    # replacement that could hide later evidence from future requests.
    candidates = build_project_evidence(source, as_of=None)
    candidates.extend(await asyncio.to_thread(load_document_evidence, source.project.id))
    rows = []
    for offset in range(0, len(candidates), EMBEDDING_BATCH_SIZE):
        batch = candidates[offset : offset + EMBEDDING_BATCH_SIZE]
        # Bound provider concurrency and wait for the entire batch before
        # propagating an error. No partial batch ever changes the live index.
        embeddings = await asyncio.gather(
            *(embedding_client.embed_document(evidence_embedding_text(item)) for item in batch),
            return_exceptions=True,
        )
        for candidate, embedding in zip(batch, embeddings, strict=True):
            if isinstance(embedding, BaseException):
                raise embedding
            rows.append(
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
                    "embedding": _vector_literal(embedding, embedding_client.dimensions),
                    "embedding_profile": embedding_client.index_identity,
                    "embedding_dimensions": embedding_client.dimensions,
                }
            )
    try:
        await ensure_project_rag_schema(session)
        # Serialize replacements of one project's profile, including an empty index.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": f"{RAG_TABLE_NAME}:{source.project.id}:{embedding_client.index_identity}"},
        )
        await session.execute(
            text(
                f"DELETE FROM {RAG_TABLE_NAME} WHERE project_id = :project_id AND embedding_profile = :profile"
            ),
            {"project_id": source.project.id, "profile": embedding_client.index_identity},
        )
        if rows:
            await session.execute(
                text(f"""
                INSERT INTO {RAG_TABLE_NAME} (
                    id, project_id, source_table, source_id, entity_type, entity_id,
                    title, text, occurred_at, linked_task_id, metadata,
                    embedding, embedding_profile, embedding_dimensions
                ) VALUES (
                    :id, :project_id, :source_table, :source_id, :entity_type, :entity_id,
                    :title, :text, :occurred_at, :linked_task_id, CAST(:metadata AS jsonb),
                    CAST(:embedding AS vector), :embedding_profile, :embedding_dimensions
                )
            """),
                rows,
            )
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    return ProjectRetrievalIndexResult(
        project_id=source.project.id,
        chunks_indexed=len(candidates),
        embedding_model=embedding_client.doc_model,
        embedding_dimensions=embedding_client.dimensions,
    )


async def search_project_rag(
    session: AsyncSession,
    source: ProjectSummarySource,
    *,
    query: str,
    embedding_client: EmbeddingClient,
    as_of: date | None = None,
    limit: int = DEFAULT_LIMIT,
    entity_id: str | None = None,
    ranking: RankingMode = "hybrid",
) -> ProjectRetrievalContext:
    query = " ".join(query.split())
    if not query:
        raise ValueError("Поисковый запрос не должен быть пустым.")
    if ranking not in get_args(RankingMode):
        raise ValueError("Неизвестный режим ранжирования.")
    bounded_limit = max(1, min(MAX_LIMIT, limit))
    candidate_limit = min(60, max(bounded_limit * 5, 20))
    await ensure_project_rag_schema(session)
    if await _indexed_chunks_count(session, source.project.id, embedding_client) == 0:
        await reindex_project_rag(session, source, embedding_client=embedding_client)

    # BM25 needs no query embedding when the shared evidence index is already built.
    query_embedding = await embedding_client.embed_query(query) if ranking != "bm25" else None
    rows = await _load_search_candidates(
        session,
        project_id=source.project.id,
        embedding_client=embedding_client,
        query_embedding=query_embedding,
        as_of=as_of,
        entity_id=entity_id,
        ranking=ranking,
        candidate_limit=candidate_limit,
    )
    by_id = {str(row["id"]): row for row in rows}
    rankings: dict[str, list[RankedCandidate]] = {}
    if ranking != "bm25":
        rankings["dense"] = sorted(
            (
                RankedCandidate(str(row["id"]), float(row["score"]))
                for row in rows
                if row["score"] is not None
            ),
            key=lambda item: (-item.score, item.id),
        )
    if ranking != "dense":
        # All eligible text participates, including chunks outside the dense pool.
        # Rebuilding this small in-memory index avoids stale cache after reindexing.
        rankings["bm25"] = bm25_search(
            query,
            [(str(row["id"]), _lexical_document(row)) for row in rows],
            limit=candidate_limit,
        )

    if ranking == "hybrid":
        selected = reciprocal_rank_fusion(
            rankings, limit=bounded_limit, rank_constant=FUSION_RANK_CONSTANT
        )
        scores = {
            item.id: RetrievalScores(
                dense_rank=item.ranks.get("dense"),
                dense_score=item.scores.get("dense"),
                bm25_rank=item.ranks.get("bm25"),
                bm25_score=item.scores.get("bm25"),
                fusion_score=item.score,
            )
            for item in selected
        }
    else:
        selected = rankings[ranking][:bounded_limit]
        scores = {
            item.id: RetrievalScores(**{f"{ranking}_rank": rank, f"{ranking}_score": item.score})
            for rank, item in enumerate(selected, start=1)
        }
    return ProjectRetrievalContext(
        project_id=source.project.id,
        query=query,
        as_of_date=as_of,
        ranking=ranking,
        candidate_limit=candidate_limit,
        candidate_counts={name: len(items) for name, items in rankings.items()},
        fusion_rank_constant=FUSION_RANK_CONSTANT if ranking == "hybrid" else None,
        count=len(selected),
        items=[
            ProjectEvidenceChunk(
                **{key: value for key, value in by_id[item.id].items() if key != "score"},
                score=item.score,
                retrieval=scores[item.id],
            )
            for item in selected
        ],
    )


async def get_evidence_context(
    session: AsyncSession,
    *,
    project_id: str,
    evidence_id: str,
    embedding_client: EmbeddingClient,
    as_of: date | None = None,
    neighbors: int = 1,
) -> dict[str, Any]:
    """Read indexed text only, within the same snapshot scope as retrieval.

    No schema writes, reindexing, filesystem reads or embedding calls. Source IDs
    are accepted only when unambiguous inside the eligible project/profile.
    """
    if not evidence_id or len(evidence_id) > 256:
        raise ValueError("Require an exact evidence ID (1–256 characters).")
    if not 0 <= neighbors <= 2:
        raise ValueError("neighbors must be between 0 and 2")
    result = await session.execute(text(f"""
        WITH eligible AS MATERIALIZED (
            SELECT * FROM {RAG_TABLE_NAME}
            WHERE project_id = :project_id
              AND embedding_profile = :embedding_profile
              AND embedding_dimensions = :embedding_dimensions
              AND vector_dims(embedding) = :embedding_dimensions
              AND (CAST(:as_of_date AS date) IS NULL OR occurred_at IS NULL
                   OR occurred_at::date <= CAST(:as_of_date AS date))
        ), anchors AS (
            SELECT * FROM eligible WHERE id = :evidence_id OR source_id = :evidence_id
        ), anchor AS (
            SELECT * FROM anchors WHERE (SELECT count(*) FROM anchors) = 1
        ), document_chunks AS (
            SELECT e.*, row_number() OVER (
                ORDER BY substring(e.source_id FROM :chunk_ordinal_pattern)::numeric, e.id
            ) AS ordinal
            FROM eligible e JOIN anchor a
              ON e.source_table = 'documents' AND a.source_table = 'documents'
             AND e.metadata ->> 'document_id' = a.metadata ->> 'document_id'
             AND e.metadata ->> 'version' = a.metadata ->> 'version'
             AND coalesce(a.metadata ->> 'document_id', '') <> ''
             AND coalesce(a.metadata ->> 'version', '') <> ''
            WHERE e.source_id ~ :chunk_id_pattern
        ), selected AS (
            SELECT id, 0::bigint AS relative_position FROM anchor
            UNION ALL
            SELECT d.id, d.ordinal - center.ordinal
            FROM document_chunks d JOIN document_chunks center
              ON center.id = (SELECT id FROM anchor)
            WHERE d.id <> center.id
              AND abs(d.ordinal - center.ordinal) <= :neighbors
        )
        SELECT e.id, e.project_id, e.source_table, e.source_id, e.entity_type, e.entity_id,
               e.title, left(e.text, 6000) AS text, length(e.text) AS text_length,
               length(e.text) > 6000 AS text_truncated, e.occurred_at,
               e.linked_task_id, e.metadata, s.relative_position
        FROM selected s JOIN eligible e ON e.id = s.id
        ORDER BY s.relative_position LIMIT 5
    """), {
        "project_id": project_id,
        "evidence_id": evidence_id,
        "embedding_profile": embedding_client.index_identity,
        "embedding_dimensions": embedding_client.dimensions,
        "as_of_date": as_of,
        "neighbors": neighbors,
        "chunk_ordinal_pattern": ":c([0-9]+)$",
        "chunk_id_pattern": ":c[0-9]+$",
    })
    items = [dict(row) for row in result.mappings().all()]
    # Datetimes must survive both JSON content and the structured source artifact.
    for item in items:
        if item.get("occurred_at") is not None:
            item["occurred_at"] = item["occurred_at"].isoformat()
    return {
        "status": "found" if items else "not_found",
        "requested_evidence_id": evidence_id,
        "as_of_date": as_of.isoformat() if as_of else None,
        "count": len(items),
        "neighbors": neighbors,
        "max_chars_per_chunk": 6000,
        "truncated": any(item["text_truncated"] for item in items),
        "items": items,
    }


async def _load_search_candidates(
    session: AsyncSession,
    *,
    project_id: str,
    embedding_client: EmbeddingClient,
    query_embedding: list[float] | None,
    as_of: date | None,
    entity_id: str | None,
    ranking: RankingMode,
    candidate_limit: int,
) -> list[Mapping[str, Any]]:
    # Both branches read one PostgreSQL snapshot and the same prefiltered corpus.
    # MATERIALIZED keeps dimension/profile guards ahead of vector distance.
    scope = f"""
        WITH matching_chunks AS MATERIALIZED (
            SELECT * FROM {RAG_TABLE_NAME}
            WHERE project_id = :project_id
              AND embedding_profile = :embedding_profile
              AND embedding_dimensions = :embedding_dimensions
              AND vector_dims(embedding) = :embedding_dimensions
              AND (CAST(:as_of_date AS date) IS NULL OR occurred_at IS NULL
                   OR occurred_at::date <= CAST(:as_of_date AS date))
              AND (CAST(:entity_id AS text) IS NULL
                   OR source_id = CAST(:entity_id AS text)
                   OR entity_id = CAST(:entity_id AS text)
                   OR linked_task_id = CAST(:entity_id AS text)
                   OR metadata ->> 'external_id' = CAST(:entity_id AS text)
                   OR metadata ->> 'document_id' = CAST(:entity_id AS text))
        )
    """
    params = {
        "project_id": project_id,
        "embedding_profile": embedding_client.index_identity,
        "embedding_dimensions": embedding_client.dimensions,
        "as_of_date": as_of,
        "entity_id": entity_id,
    }
    join, score = "", "NULL AS score"
    if query_embedding is not None:
        scope += """, dense_candidates AS (
            SELECT id, 1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM matching_chunks
            ORDER BY embedding <=> CAST(:embedding AS vector), id
            LIMIT :candidate_limit
        )
        """
        params["embedding"] = _vector_literal(query_embedding, embedding_client.dimensions)
        params["candidate_limit"] = candidate_limit
        # Hybrid keeps every eligible document for independent BM25 scoring.
        join_type = "LEFT JOIN" if ranking == "hybrid" else "JOIN"
        join = f"{join_type} dense_candidates d ON d.id = m.id"
        score = "d.score"
    statement = text(f"""
        {scope}
        SELECT m.id, m.project_id, m.source_table, m.source_id, m.entity_type,
               m.entity_id, m.title, m.text, m.occurred_at, m.linked_task_id,
               m.metadata, {score}
        FROM matching_chunks m {join}
        ORDER BY m.id
    """)
    result = await session.execute(statement, params)
    return list(result.mappings().all())


def _lexical_document(row: Mapping[str, Any]) -> str:
    """Search meaningful text and exact identifiers once, without field boosts."""
    metadata = row["metadata"] or {}
    fields = ("title", "text", "source_id", "entity_id", "linked_task_id")
    values = [str(row[field]) for field in fields if row[field]]
    values.extend(str(metadata[key]) for key in ("external_id", "document_id") if metadata.get(key))
    return "\n".join(dict.fromkeys(values))


def _chunk_id(candidate: EvidenceCandidate) -> str:
    return f"{candidate.project_id}:{candidate.source_table}:{candidate.source_id}"


def _json_metadata(metadata: dict[str, Any]) -> str:
    return json.dumps(
        {key: value for key, value in metadata.items() if value is not None}, ensure_ascii=False
    )


async def _indexed_chunks_count(
    session: AsyncSession, project_id: str, embedding_client: EmbeddingClient
) -> int:
    value = await session.scalar(
        text(f"""SELECT count(*) FROM {RAG_TABLE_NAME}
             WHERE project_id = :project_id AND embedding_profile = :profile
               AND embedding_dimensions = :dimensions AND vector_dims(embedding) = :dimensions"""),
        {
            "project_id": project_id,
            "profile": embedding_client.index_identity,
            "dimensions": embedding_client.dimensions,
        },
    )
    return int(value or 0)


def _vector_literal(values: list[float], dimensions: int) -> str:
    vector = validate_embedding(values, dimensions)
    return "[" + ",".join(format(value, ".9g") for value in vector) + "]"
