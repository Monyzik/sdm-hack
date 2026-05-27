from __future__ import annotations

import os
from datetime import date
from typing import Any

from langgraph.graph import END, START, StateGraph

from .agent import ProjectBriefAgent
from .nodes import fetch_problem_context_node, generate_brief_node
from .schemas import ProjectManagerBrief
from .state import ProjectBriefData


def build_project_brief_graph(
    backend_api_url: str | None = None,
    agent: Any | None = None,
):
    backend_api_url = backend_api_url or os.getenv("BACKEND_API_URL", "http://backend:8000")
    if agent is None:
        agent = ProjectBriefAgent()

    graph = StateGraph(ProjectBriefData)
    graph.add_node("fetch_problem_context", fetch_problem_context_node(backend_api_url))
    graph.add_node("generate_brief", generate_brief_node(agent))
    graph.add_edge(START, "fetch_problem_context")
    graph.add_edge("fetch_problem_context", "generate_brief")
    graph.add_edge("generate_brief", END)
    return graph.compile()


async def run_project_brief(
    project_id: str,
    as_of: date | None = None,
    max_depth: int = 2,
    backend_api_url: str | None = None,
    agent: Any | None = None,
) -> ProjectManagerBrief:
    graph = build_project_brief_graph(backend_api_url=backend_api_url, agent=agent)
    initial_state = ProjectBriefData(project_id=project_id, as_of=as_of, max_depth=max_depth)
    result = await graph.ainvoke(initial_state.model_dump())
    return ProjectManagerBrief.model_validate(result["brief"])
