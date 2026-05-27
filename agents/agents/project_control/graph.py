from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.agents.internal_notifications import ProjectInternalNotificationAgent
from agents.agents.project_analysis import ProjectAnalystAgent
from agents.agents.project_parser import ProjectParser
from sdm.backend.database.session import create_async_engine_from_env, create_async_session_factory

from .nodes import monitor_project_node, parse_docx_node, route_event, update_project_node
from .state import ProjectControlData, ProjectEventType


def build_project_control_graph(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    parser: ProjectParser | None = None,
    analyst: ProjectAnalystAgent | None = None,
    notification_agent: ProjectInternalNotificationAgent | None = None,
):
    if session_factory is None:
        engine = create_async_engine_from_env()
        session_factory = create_async_session_factory(engine)

    graph = StateGraph(ProjectControlData)
    graph.add_node("route_event", lambda state: {})
    graph.add_node("parse_docx", parse_docx_node(parser))
    graph.add_node("update_project", update_project_node(session_factory))
    graph.add_node(
        "monitor_project",
        monitor_project_node(session_factory, analyst, notification_agent),
    )

    graph.add_edge(START, "route_event")
    graph.add_conditional_edges(
        "route_event",
        route_event,
        {
            "docx": "parse_docx",
            "monitor": "monitor_project",
        },
    )
    graph.add_edge("parse_docx", "update_project")
    graph.add_edge("update_project", "monitor_project")
    graph.add_edge("monitor_project", END)

    return graph.compile()


async def run_project_control_event(
    file_path: str | Path | None = None,
    event_type: ProjectEventType = "docx_changed",
    project_id: str | None = None,
    as_of: date | str | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    analyst: ProjectAnalystAgent | None = None,
    notification_agent: ProjectInternalNotificationAgent | None = None,
) -> dict[str, Any]:
    graph = build_project_control_graph(
        session_factory=session_factory,
        analyst=analyst,
        notification_agent=notification_agent,
    )
    initial_state = ProjectControlData(
        event_type=event_type,
        file_path=None if file_path is None else str(Path(file_path)),
        project_id=project_id,
        as_of=as_of,
    )
    return await graph.ainvoke(initial_state.model_dump())
