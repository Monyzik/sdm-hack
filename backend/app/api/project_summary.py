from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.dependencies import get_session
from backend.app.schemas.project_summary import (
    PortfolioAttentionSummary,
    PortfolioSummary,
    ProjectProblemContext,
    ProjectSummary,
)
from backend.app.services.project_summary_repository import ProjectSummaryRepository
from backend.app.services.project_summary_service import ProjectSummaryService


router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.get("/portfolio", response_model=PortfolioSummary)
def get_portfolio_summary(
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
) -> PortfolioSummary:
    service = _summary_service(session)
    return service.build_portfolio_summary(as_of=as_of)


@router.get("/portfolio/attention", response_model=PortfolioAttentionSummary)
def get_portfolio_attention(
    as_of: date | None = Query(default=None),
    lookback_days: int = Query(default=7, ge=1, le=30),
    session: Session = Depends(get_session),
) -> PortfolioAttentionSummary:
    service = _summary_service(session)
    return service.build_portfolio_attention(as_of=as_of, lookback_days=lookback_days)


@router.get("/projects/{project_id}", response_model=ProjectSummary)
def get_project_summary(
    project_id: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
) -> ProjectSummary:
    service = _summary_service(session)
    try:
        return service.build_project_summary(project_id, as_of=as_of)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/problem-context", response_model=ProjectProblemContext)
def get_project_problem_context(
    project_id: str,
    as_of: date | None = Query(default=None),
    max_depth: int = Query(default=2, ge=1, le=4),
    session: Session = Depends(get_session),
) -> ProjectProblemContext:
    service = _summary_service(session)
    try:
        return service.build_project_problem_context(project_id, as_of=as_of, max_depth=max_depth)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _summary_service(session: Session) -> ProjectSummaryService:
    repository = ProjectSummaryRepository(session)
    return ProjectSummaryService(repository)
