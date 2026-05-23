from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from agents.internal_notification_agent import ProjectInternalNotificationAgent
from agents.project_analysis_agent import ProjectAnalystAgent
from agents.parser_agent import ProjectData, ProjectParser
from agents.project_monitor_graph import run_project_monitor
from backend.app.database.project_import import update_project_from_schema
from backend.app.database.session import create_engine_from_env, create_session_factory


DocxEventType = Literal["docx_added", "docx_changed"]


class ProjectControlData(BaseModel):
    event_type: DocxEventType
    file_path: str
    project_id: str | None = None
    parsed_project: dict[str, Any] | None = None
    monitoring: dict[str, Any] | None = None


def state_value(state: ProjectControlData | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, ProjectControlData):
        return getattr(state, key)
    return state.get(key, default)


def parse_docx_node(parser: ProjectParser) -> Any:
    def parse_docx(state: ProjectControlData | dict[str, Any]) -> dict[str, Any]:
        file_path = Path(state_value(state, "file_path"))
        project_data = parser.parse(file_path)

        return {
            "parsed_project": project_data.model_dump(mode="json"),
        }

    return parse_docx


def update_project_node(session_factory: sessionmaker) -> Any:
    def update_project(state: ProjectControlData | dict[str, Any]) -> dict[str, Any]:
        parsed_project = state_value(state, "parsed_project")
        if parsed_project is None:
            raise ValueError("Нет результата парсинга DOCX для записи в projects")

        file_path = Path(state_value(state, "file_path"))
        project_data = ProjectData.model_validate(parsed_project)

        with session_factory() as session:
            project = update_project_from_schema(session, project_data, file_path)
            project_id = project.id
            session.commit()

        return {
            "project_id": project_id,
        }

    return update_project


def monitor_project_node(
    session_factory: sessionmaker,
    analyst: ProjectAnalystAgent | None = None,
    notification_agent: ProjectInternalNotificationAgent | None = None,
) -> Any:
    def monitor_project(state: ProjectControlData | dict[str, Any]) -> dict[str, Any]:
        project_id = state_value(state, "project_id")
        if not project_id:
            raise ValueError("Нет project_id для запуска мониторинга")

        monitoring_result = run_project_monitor(
            project_id,
            session_factory=session_factory,
            analyst=analyst,
            notification_agent=notification_agent,
        )

        return {
            "monitoring": {
                "project": monitoring_result["project"],
                "metrics": monitoring_result["metrics"],
                "alerts": monitoring_result["alerts"],
                "analysis": monitoring_result["analysis"],
                "notification_draft": monitoring_result["notification_draft"],
            },
        }

    return monitor_project


def build_project_control_graph(
    session_factory: sessionmaker | None = None,
    parser: ProjectParser | None = None,
    analyst: ProjectAnalystAgent | None = None,
    notification_agent: ProjectInternalNotificationAgent | None = None,
):
    if session_factory is None:
        engine = create_engine_from_env()
        session_factory = create_session_factory(engine)
    if parser is None:
        parser = ProjectParser()

    graph = StateGraph(ProjectControlData)
    graph.add_node("parse_docx", parse_docx_node(parser))
    graph.add_node("update_project", update_project_node(session_factory))
    graph.add_node(
        "monitor_project",
        monitor_project_node(session_factory, analyst, notification_agent),
    )

    graph.add_edge(START, "parse_docx")
    graph.add_edge("parse_docx", "update_project")
    graph.add_edge("update_project", "monitor_project")
    graph.add_edge("monitor_project", END)

    return graph.compile()


def run_project_control_event(
    file_path: str | Path,
    event_type: DocxEventType = "docx_changed",
    session_factory: sessionmaker | None = None,
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
        file_path=str(Path(file_path)),
    )
    return graph.invoke(initial_state.model_dump())
