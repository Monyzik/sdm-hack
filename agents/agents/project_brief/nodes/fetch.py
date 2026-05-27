from __future__ import annotations

from datetime import date
from typing import Any

from ..client import fetch_project_problem_context
from ..state import ProjectBriefData, state_value


def fetch_problem_context_node(backend_api_url: str) -> Any:
    async def fetch_problem_context(state: ProjectBriefData | dict[str, Any]) -> dict[str, Any]:
        as_of = state_value(state, "as_of")
        as_of_value = as_of.isoformat() if isinstance(as_of, date) else str(as_of or "2026-06-19")
        problem_context = await fetch_project_problem_context(
            project_id=state_value(state, "project_id"),
            as_of=as_of_value,
            max_depth=state_value(state, "max_depth", 2),
            api_base_url=backend_api_url,
        )
        return {"problem_context": problem_context}

    return fetch_problem_context
