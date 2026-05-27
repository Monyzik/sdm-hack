from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.domain.project_document import ProjectData
from agents.agents.project_parser import ProjectParser
from sdm.backend.database.project_import import update_project_from_schema_async

from ..state import ProjectControlData, state_value


def parse_docx_node(parser: ProjectParser | None = None) -> Any:
    parser_instance = parser

    async def parse_docx(state: ProjectControlData | dict[str, Any]) -> dict[str, Any]:
        nonlocal parser_instance

        raw_file_path = state_value(state, "file_path")
        if not raw_file_path:
            raise ValueError("Нет file_path для парсинга DOCX")

        if parser_instance is None:
            parser_instance = ProjectParser()

        project_data = await parser_instance.parse(Path(raw_file_path))
        return {"parsed_project": project_data.model_dump(mode="json")}

    return parse_docx


def update_project_node(session_factory: async_sessionmaker[AsyncSession]) -> Any:
    async def update_project(state: ProjectControlData | dict[str, Any]) -> dict[str, Any]:
        parsed_project = state_value(state, "parsed_project")
        if parsed_project is None:
            raise ValueError("Нет результата парсинга DOCX для записи в projects")

        raw_file_path = state_value(state, "file_path")
        if not raw_file_path:
            raise ValueError("Нет file_path для записи DOCX-схемы в projects")

        project_data = ProjectData.model_validate(parsed_project)
        async with session_factory() as session:
            project = await update_project_from_schema_async(session, project_data, Path(raw_file_path))
            project_id = project.id
            await session.commit()

        return {"project_id": project_id}

    return update_project
