from __future__ import annotations

from typing import Any

from sdm.agents.project_analysis import ProjectAnalystAgent

from ..state import ProjectMonitorData, state_value


def analyze_project_node(agent: ProjectAnalystAgent) -> Any:
    async def analyze_project(state: ProjectMonitorData | dict[str, Any]) -> dict[str, Any]:
        analysis = await agent.analyze(
            project=state_value(state, "project", {}),
            metrics=state_value(state, "metrics", {}),
            alerts=state_value(state, "alerts", []),
        )
        return {"analysis": analysis.model_dump(mode="json")}

    return analyze_project
