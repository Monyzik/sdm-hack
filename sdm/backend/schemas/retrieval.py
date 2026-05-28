from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RankingMode = Literal["dense", "bm25", "hybrid"]


class RetrievalScores(BaseModel):
    """Ranks refer to candidate lists; scores are not answer confidence."""

    dense_rank: int | None = Field(default=None, ge=1)
    dense_score: float | None = None
    bm25_rank: int | None = Field(default=None, ge=1)
    bm25_score: float | None = None
    fusion_score: float | None = None
    rerank_rank: int | None = Field(default=None, ge=1)


class ProjectEvidenceChunk(BaseModel):
    id: str
    project_id: str
    source_table: str
    source_id: str
    entity_type: str
    entity_id: str
    title: str
    text: str
    occurred_at: datetime | None = None
    linked_task_id: str | None = None
    score: float = Field(description="Score of the selected ranking mode, not a probability.")
    retrieval: RetrievalScores
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectRetrievalContext(BaseModel):
    project_id: str
    query: str
    as_of_date: date | None
    ranking: RankingMode
    candidate_limit: int
    candidate_counts: dict[str, int]
    fusion_rank_constant: int | None = None
    rerank_applied: bool = False
    reranker_model: str | None = None
    rerank_fallback: str | None = None
    count: int
    items: list[ProjectEvidenceChunk]


class ProjectRetrievalIndexResult(BaseModel):
    project_id: str
    chunks_indexed: int
    embedding_model: str
    embedding_dimensions: int
