from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field

from agents.agents.project_parser import ProjectParser
from agents.domain.project_document import ProjectData
from backend.app.database.models import Project
from backend.app.database.session import (
    create_async_engine_from_env,
    create_async_session_factory,
)


MAX_DOCX_BYTES = 8 * 1024 * 1024


class ProjectDocxEditableUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str = Field(min_length=1, max_length=255)
    start_date: date | None = None
    planned_end_date: date | None = None
    business_goal: str = Field(default="", max_length=12000)
    expected_result: str = Field(default="", max_length=12000)


class ProjectDocxFieldChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    label: str
    current_value: str | None
    proposed_value: str | None
    changed: bool


class ProjectDocxPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    file_name: str
    parsed_project: ProjectData
    editable_update: ProjectDocxEditableUpdate
    changes: list[ProjectDocxFieldChange]


class ProjectDocxApplyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    updated_project: ProjectDocxEditableUpdate
    changes: list[ProjectDocxFieldChange]


async def preview_project_docx_update(
    *,
    project_id: str,
    file_name: str | None,
    content: bytes,
) -> ProjectDocxPreview:
    safe_file_name = _safe_docx_file_name(file_name)
    _validate_docx_content(content)

    engine = create_async_engine_from_env()
    try:
        session_factory = create_async_session_factory(engine)
        async with session_factory() as session:
            project = await session.get(Project, project_id)
            if project is None:
                raise ValueError(f"Проект {project_id} не найден.")

            parser = ProjectParser()
            parsed_project = await _parse_docx(parser, safe_file_name, content)
            editable_update = _editable_update_from_parsed(project, parsed_project)
            changes = _changes(project, editable_update)

            return ProjectDocxPreview(
                project_id=project_id,
                file_name=safe_file_name,
                parsed_project=parsed_project,
                editable_update=editable_update,
                changes=changes,
            )
    finally:
        await engine.dispose()


async def apply_project_docx_update(
    *,
    project_id: str,
    update: ProjectDocxEditableUpdate,
) -> ProjectDocxApplyResult:
    engine = create_async_engine_from_env()
    try:
        session_factory = create_async_session_factory(engine)
        async with session_factory() as session:
            project = await session.get(Project, project_id)
            if project is None:
                raise ValueError(f"Проект {project_id} не найден.")

            changes = _changes(project, update)
            project_name = update.project_name.strip()
            if not project_name:
                raise ValueError("Название проекта не может быть пустым.")
            if update.start_date is None or update.planned_end_date is None:
                raise ValueError("Заполните даты проекта.")

            project.name = project_name
            project.start_date = update.start_date
            project.planned_end_date = update.planned_end_date
            project.business_goal = update.business_goal.strip()
            project.expected_result = update.expected_result.strip()
            await session.commit()

            updated_project = _editable_update_from_project(project)
            return ProjectDocxApplyResult(
                project_id=project_id,
                updated_project=updated_project,
                changes=changes,
            )
    finally:
        await engine.dispose()


async def _parse_docx(
    parser: ProjectParser,
    file_name: str,
    content: bytes,
) -> ProjectData:
    with tempfile.TemporaryDirectory(prefix="sdm_docx_") as directory:
        file_path = Path(directory) / file_name
        file_path.write_bytes(content)
        return await parser.parse(file_path)


def _safe_docx_file_name(value: str | None) -> str:
    file_name = unquote(value or "").strip() or "project.docx"
    file_name = Path(file_name).name
    if not file_name.casefold().endswith(".docx"):
        raise ValueError("Можно загрузить только DOCX-файл.")
    return file_name


def _validate_docx_content(content: bytes) -> None:
    if not content:
        raise ValueError("DOCX-файл пустой.")
    if len(content) > MAX_DOCX_BYTES:
        raise ValueError("DOCX-файл слишком большой. Максимальный размер — 8 МБ.")


def _editable_update_from_parsed(
    project: Project,
    parsed_project: ProjectData,
) -> ProjectDocxEditableUpdate:
    timeline = parsed_project.timeline
    business_goal = "\n".join(goal.goal for goal in parsed_project.goals).strip()
    expected_result = "\n".join(result.result for result in parsed_project.results).strip()
    return ProjectDocxEditableUpdate(
        project_name=parsed_project.project_name.strip() or project.name,
        start_date=(
            timeline.start_date
            if timeline and timeline.start_date
            else project.start_date
        ),
        planned_end_date=(
            timeline.end_date
            if timeline and timeline.end_date
            else project.planned_end_date
        ),
        business_goal=business_goal or project.business_goal,
        expected_result=expected_result or project.expected_result,
    )


def _editable_update_from_project(project: Project) -> ProjectDocxEditableUpdate:
    return ProjectDocxEditableUpdate(
        project_name=project.name,
        start_date=project.start_date,
        planned_end_date=project.planned_end_date,
        business_goal=project.business_goal,
        expected_result=project.expected_result,
    )


def _changes(
    project: Project,
    update: ProjectDocxEditableUpdate,
) -> list[ProjectDocxFieldChange]:
    return [
        _change("project_name", "Название проекта", project.name, update.project_name),
        _change("start_date", "Дата начала", project.start_date, update.start_date),
        _change(
            "planned_end_date",
            "Плановая дата окончания",
            project.planned_end_date,
            update.planned_end_date,
        ),
        _change(
            "business_goal",
            "Цель проекта",
            project.business_goal,
            update.business_goal,
        ),
        _change(
            "expected_result",
            "Ожидаемый результат",
            project.expected_result,
            update.expected_result,
        ),
    ]


def _change(
    field: str,
    label: str,
    current_value: object,
    proposed_value: object,
) -> ProjectDocxFieldChange:
    current = _display_value(current_value)
    proposed = _display_value(proposed_value)
    return ProjectDocxFieldChange(
        field=field,
        label=label,
        current_value=current,
        proposed_value=proposed,
        changed=current != proposed,
    )


def _display_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()
