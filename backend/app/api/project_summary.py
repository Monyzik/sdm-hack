from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_session
from backend.app.schemas.project_summary import (
    PortfolioAttentionSummary,
    PortfolioSummary,
    ProjectProblemContext,
    ProjectRetrievalContext,
    ProjectRetrievalIndexResult,
    ProjectSummary,
    ProjectTrends,
)
from backend.app.services.data_classes import ProjectSummarySource
from backend.app.services.project_summary_repository import ProjectSummaryRepository
from backend.app.services.project_summary_service import ProjectSummaryService
from backend.app.services.retrieval import reindex_project_rag, search_project_rag
from backend.app.services.yandex_embeddings import YandexEmbeddingClient, get_yandex_embedding_client


router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.get("/portfolio", response_model=PortfolioSummary)
async def get_portfolio_summary(
    as_of: date | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> PortfolioSummary:
    service = _summary_service(session)
    return await service.build_portfolio_summary(as_of=as_of)


@router.get("/portfolio/attention", response_model=PortfolioAttentionSummary)
async def get_portfolio_attention(
    as_of: date | None = Query(default=None),
    lookback_days: int = Query(default=7, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
) -> PortfolioAttentionSummary:
    service = _summary_service(session)
    return await service.build_portfolio_attention(as_of=as_of, lookback_days=lookback_days)


@router.get("/projects/{project_id}", response_model=ProjectSummary)
async def get_project_summary(
    project_id: str,
    as_of: date | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProjectSummary:
    service = _summary_service(session)
    try:
        return await service.build_project_summary(project_id, as_of=as_of)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/trends", response_model=ProjectTrends)
async def get_project_trends(
    project_id: str,
    as_of: date | None = Query(default=None),
    points: int = Query(default=8, ge=2, le=12),
    session: AsyncSession = Depends(get_session),
) -> ProjectTrends:
    service = _summary_service(session)
    try:
        return await service.build_project_trends(project_id, as_of=as_of, points=points)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/problem-context", response_model=ProjectProblemContext)
async def get_project_problem_context(
    project_id: str,
    as_of: date | None = Query(default=None),
    max_depth: int = Query(default=2, ge=1, le=4),
    session: AsyncSession = Depends(get_session),
) -> ProjectProblemContext:
    service = _summary_service(session)
    try:
        return await service.build_project_problem_context(project_id, as_of=as_of, max_depth=max_depth)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/retrieval-context", response_model=ProjectRetrievalContext)
async def get_project_retrieval_context(
    project_id: str,
    query: str = Query(..., min_length=1, max_length=500),
    as_of: date | None = Query(default=None),
    limit: int = Query(default=8, ge=1, le=20),
    entity_id: str | None = Query(default=None, min_length=1, max_length=64),
    session: AsyncSession = Depends(get_session),
) -> ProjectRetrievalContext:
    source = await _project_source_or_404(session, project_id)
    embedding_client = _embedding_client_or_503()
    try:
        return await search_project_rag(
            session,
            source,
            query=query,
            embedding_client=embedding_client,
            as_of=as_of,
            limit=limit,
            entity_id=entity_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Не удалось выполнить pgvector-поиск. Проверь, что PostgreSQL запущен с расширением vector.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/projects/{project_id}/retrieval-index", response_model=ProjectRetrievalIndexResult)
async def reindex_project_retrieval(
    project_id: str,
    as_of: date | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProjectRetrievalIndexResult:
    source = await _project_source_or_404(session, project_id)
    embedding_client = _embedding_client_or_503()
    try:
        return await reindex_project_rag(
            session,
            source,
            embedding_client=embedding_client,
            as_of=as_of,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Не удалось построить RAG-индекс. Проверь, что PostgreSQL запущен с расширением vector.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _summary_service(session: AsyncSession) -> ProjectSummaryService:
    repository = ProjectSummaryRepository(session)
    return ProjectSummaryService(repository)


async def _project_source_or_404(session: AsyncSession, project_id: str) -> ProjectSummarySource:
    repository = ProjectSummaryRepository(session)
    try:
        return await repository.get_project_source(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _embedding_client_or_503() -> YandexEmbeddingClient:
    try:
        return get_yandex_embedding_client()
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Не настроен сервис эмбеддингов Yandex: {exc}",
        ) from exc
