from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.dependencies import get_session
from backend.app.schemas.project_summary import PortfolioSummary, ProjectSummary
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


def _summary_service(session: Session) -> ProjectSummaryService:
    repository = ProjectSummaryRepository(session)
    return ProjectSummaryService(repository)

