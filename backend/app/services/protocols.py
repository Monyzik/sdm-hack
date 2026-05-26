from __future__ import annotations

from typing import Protocol

from backend.app.database.models import Project
from backend.app.services.data_classes import ProjectSummarySource


class ProjectSummaryReader(Protocol):
    async def list_projects(self) -> list[Project]:
        ...

    async def get_project_source(self, project_id: str) -> ProjectSummarySource:
        ...
