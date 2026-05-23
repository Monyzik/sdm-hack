from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from agents.parser_agent import ProjectData
from backend.database.models import Project


def project_id_from_docx_path(file_path: Path) -> str:
    match = re.search(r"(\d+)$", file_path.stem)
    if not match:
        raise ValueError(f"Не удалось определить project_id из имени файла: {file_path.name}")
    return f"P{int(match.group(1)):03d}"


def update_project_from_schema(
    session: Session,
    project_data: ProjectData,
    file_path: Path,
) -> Project:
    project_id = project_id_from_docx_path(file_path)
    print(project_id)
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(
            f"Проект {project_id} не найден в таблице projects. "
            "Сначала загрузи базовые проекты из CSV."
        )

    timeline = project_data.timeline

    project.name = project_data.project_name
    if timeline and timeline.start_date:
        project.start_date = timeline.start_date
    if timeline and timeline.end_date:
        project.planned_end_date = timeline.end_date
    if project_data.goals:
        project.business_goal = "\n".join(goal.goal for goal in project_data.goals)
    if project_data.results:
        project.expected_result = "\n".join(result.result for result in project_data.results)

    return project
