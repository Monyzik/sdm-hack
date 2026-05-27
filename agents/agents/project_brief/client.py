from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx


async def fetch_project_problem_context(
    project_id: str,
    as_of: str,
    max_depth: int,
    api_base_url: str,
) -> dict[str, Any]:
    query = urlencode({"as_of": as_of, "max_depth": max_depth})
    url = f"{api_base_url}/api/v1/summaries/projects/{project_id}/problem-context?{query}"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()
