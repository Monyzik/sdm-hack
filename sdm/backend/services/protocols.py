from __future__ import annotations

from typing import Protocol

from sdm.backend.database.models import Project
from sdm.backend.services.data_classes import ProjectSummarySource


class ProjectSummaryReader(Protocol):
    async def list_projects(self) -> list[Project]:
        ...

    async def get_project_source(self, project_id: str) -> ProjectSummarySource:
        ...
