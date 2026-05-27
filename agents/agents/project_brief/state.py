from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel


class ProjectBriefData(BaseModel):
    project_id: str
    as_of: date | None = None
    max_depth: int = 2
    problem_context: dict[str, Any] | None = None
    brief: dict[str, Any] | None = None


def state_value(state: ProjectBriefData | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, ProjectBriefData):
        return getattr(state, key)
    return state.get(key, default)
