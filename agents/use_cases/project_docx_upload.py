from __future__ import annotations

import asyncio
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from agents.workflows.project_control import run_project_control_event

DocxUploadEventType = Literal["docx_added", "docx_changed"]

MAX_DOCX_BYTES = 25 * 1024 * 1024
PROJECT_ID_RE = re.compile(r"^P(?P<number>\d+)$", re.IGNORECASE)


class ProjectKeyFields(BaseModel):
    project_name: str
    start_date: str | None = None
    planned_end_date: str | None = None
    business_goal: str
    expected_result: str


class ProjectDocxUploadResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    project_id: str
    original_file_name: str
    stored_file_name: str
    event_type: DocxUploadEventType
    updated_fields: ProjectKeyFields
    parsed_project: dict[str, Any]
    alerts_count: int
    notification_id: str | None = None


async def upload_project_docx(
    *,
    project_id: str,
    original_file_name: str,
    content: bytes,
    as_of: date | None = None,
) -> ProjectDocxUploadResult:
    if not original_file_name.lower().endswith(".docx"):
        raise ValueError("Можно загрузить только DOCX-файл.")
    if not content:
        raise ValueError("DOCX-файл пустой.")
    if len(content) > MAX_DOCX_BYTES:
        raise ValueError("DOCX-файл слишком большой. Максимум 25 МБ.")

    stored_file_path = _stored_docx_path(project_id)
    event_type: DocxUploadEventType = (
        "docx_changed" if stored_file_path.exists() else "docx_added"
    )
    stored_file_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(stored_file_path.write_bytes, content)

    result = await run_project_control_event(
        file_path=stored_file_path,
        event_type=event_type,
        as_of=as_of,
    )

    parsed_project = result.get("parsed_project") or {}
    monitoring = result.get("monitoring") or {}
    project = monitoring.get("project") or {}
    alerts = monitoring.get("alerts") or []

    return ProjectDocxUploadResult(
        project_id=str(result.get("project_id") or project_id.upper()),
        original_file_name=original_file_name,
        stored_file_name=stored_file_path.name,
        event_type=event_type,
        updated_fields=_key_fields(project=project, parsed_project=parsed_project),
        parsed_project=parsed_project,
        alerts_count=len(alerts) if isinstance(alerts, list) else 0,
        notification_id=monitoring.get("notification_id"),
    )


def _stored_docx_path(project_id: str) -> Path:
    match = PROJECT_ID_RE.fullmatch(project_id.strip())
    if not match:
        raise ValueError("project_id должен быть в формате P001.")

    project_number = int(match.group("number"))
    upload_dir = Path(os.getenv("PROJECT_DOCX_UPLOAD_DIR", "data/project_documents"))
    return upload_dir / f"project_summary_{project_number:03d}.docx"


def _key_fields(project: dict[str, Any], parsed_project: dict[str, Any]) -> ProjectKeyFields:
    timeline = (
        parsed_project.get("timeline")
        if isinstance(parsed_project.get("timeline"), dict)
        else {}
    )
    goals = (
        parsed_project.get("goals")
        if isinstance(parsed_project.get("goals"), list)
        else []
    )
    results = (
        parsed_project.get("results")
        if isinstance(parsed_project.get("results"), list)
        else []
    )

    return ProjectKeyFields(
        project_name=str(project.get("name") or parsed_project.get("project_name") or ""),
        start_date=_string_or_none(project.get("start_date") or timeline.get("start_date")),
        planned_end_date=_string_or_none(project.get("planned_end_date") or timeline.get("end_date")),
        business_goal=str(project.get("business_goal") or _joined_values(goals, "goal")),
        expected_result=str(project.get("expected_result") or _joined_values(results, "result")),
    )


def _joined_values(items: list[Any], key: str) -> str:
    values = [
        str(item.get(key))
        for item in items
        if isinstance(item, dict) and item.get(key)
    ]
    return "\n".join(values)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
