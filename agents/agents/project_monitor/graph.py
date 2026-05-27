from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.agents.internal_notifications import ProjectInternalNotificationAgent
from agents.agents.project_analysis import ProjectAnalystAgent
from sdm.backend.database.session import create_async_engine_from_env, create_async_session_factory

from .nodes import (
    analyze_project_node,
    calculate_metrics_node,
    classify_alerts,
    draft_notification_node,
    load_project_context_node,
    persist_notification_node,
)
from .state import ProjectMonitorData


def build_project_monitor_graph(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    analyst: ProjectAnalystAgent | None = None,
    notification_agent: ProjectInternalNotificationAgent | None = None,
):
    if session_factory is None:
        engine = create_async_engine_from_env()
        session_factory = create_async_session_factory(engine)
    if analyst is None:
        analyst = ProjectAnalystAgent()
    if notification_agent is None:
        notification_agent = ProjectInternalNotificationAgent()

    graph = StateGraph(ProjectMonitorData)
    graph.add_node("load_project_context", load_project_context_node(session_factory))
    graph.add_node("calculate_metrics", calculate_metrics_node(session_factory))
    graph.add_node("classify_alerts", classify_alerts)
    graph.add_node("analyze_project", analyze_project_node(analyst))
    graph.add_node("draft_notification", draft_notification_node(notification_agent))
    graph.add_node("persist_notification", persist_notification_node(session_factory))

    graph.add_edge(START, "load_project_context")
    graph.add_edge("load_project_context", "calculate_metrics")
    graph.add_edge("calculate_metrics", "classify_alerts")
    graph.add_edge("classify_alerts", "analyze_project")
    graph.add_edge("analyze_project", "draft_notification")
    graph.add_edge("draft_notification", "persist_notification")
    graph.add_edge("persist_notification", END)

    return graph.compile()


async def run_project_monitor(
    project_id: str,
    as_of: date | str | None = None,
    trigger_event: dict[str, Any] | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    analyst: ProjectAnalystAgent | None = None,
    notification_agent: ProjectInternalNotificationAgent | None = None,
) -> dict[str, Any]:
    graph = build_project_monitor_graph(
        session_factory=session_factory,
        analyst=analyst,
        notification_agent=notification_agent,
    )
    initial_state = ProjectMonitorData(project_id=project_id)
    if as_of:
        initial_state.as_of = as_of
    if trigger_event:
        initial_state.trigger_event = trigger_event
    return await graph.ainvoke(initial_state.model_dump())


def json_default(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


async def async_main() -> None:
    parser = argparse.ArgumentParser(description="Запуск графа мониторинга проекта.")
    parser.add_argument("project_id", nargs="?", default="P001")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Дата в формате YYYY-MM-DD")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    result = await run_project_monitor(args.project_id, as_of=as_of)
    print(
        json.dumps(
            {
                "project": result["project"],
                "metrics": result["metrics"],
                "alerts": result["alerts"],
                "analysis": result["analysis"],
                "notification_draft": result["notification_draft"],
                "notification_id": result["notification_id"],
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        )
    )


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
