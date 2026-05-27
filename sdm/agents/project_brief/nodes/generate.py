from __future__ import annotations

from typing import Any

from ..state import ProjectBriefData, state_value


def generate_brief_node(agent: Any) -> Any:
    async def generate_brief(state: ProjectBriefData | dict[str, Any]) -> dict[str, Any]:
        problem_context = state_value(state, "problem_context")
        if problem_context is None:
            raise ValueError("Нет problem_context для генерации brief")

        brief = await agent.build(problem_context)
        return {"brief": brief.model_dump(mode="json")}

    return generate_brief
