from __future__ import annotations

from datetime import date
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
MonitoringEventType = Literal[
    "task_changed",
    "risk_changed",
    "budget_changed",
    "dependency_changed",
    "communication_changed",
    "manual_monitoring_requested",
]
ProjectEventType = DocxEventType | MonitoringEventType

DOCX_EVENTS = {"docx_added", "docx_changed"}
MONITORING_EVENTS = {
    "task_changed",
    "risk_changed",
    "budget_changed",
    "dependency_changed",
    "communication_changed",
    "manual_monitoring_requested",
}

EVENT_LABELS = {
    "docx_added": "Добавлен DOCX",
    "docx_changed": "Изменен DOCX",
    "task_changed": "Изменение задачи",
    "risk_changed": "Изменение риска",
    "budget_changed": "Изменение бюджета",
    "dependency_changed": "Изменение зависимости",
    "communication_changed": "Изменение коммуникации",
    "manual_monitoring_requested": "Ручной запуск мониторинга",
}


class ProjectControlData(BaseModel):
    event_type: ProjectEventType
    file_path: str | None = None
    project_id: str | None = None
    as_of: date | None = None
    parsed_project: dict[str, Any] | None = None
    monitoring: dict[str, Any] | None = None


def state_value(state: ProjectControlData | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, ProjectControlData):
        return getattr(state, key)
    return state.get(key, default)


def build_trigger_event_context(state: ProjectControlData | dict[str, Any], project_id: str) -> dict[str, Any]:
    event_type = state_value(state, "event_type")
    raw_file_path = state_value(state, "file_path")
    trigger_event = {
        "type": event_type,
        "label": EVENT_LABELS.get(event_type, str(event_type)),
        "project_id": project_id,
    }
    if raw_file_path:
        file_path = Path(raw_file_path)
        trigger_event["file_path"] = str(file_path)
        trigger_event["file_name"] = file_path.name
        trigger_event["label"] = f"{trigger_event['label']}: {file_path.name}"
    return trigger_event


def route_event(state: ProjectControlData | dict[str, Any]) -> str:
    event_type = state_value(state, "event_type")

    if event_type in DOCX_EVENTS:
        if not state_value(state, "file_path"):
            raise ValueError("Для DOCX-события нужен file_path")
        return "docx"

    if event_type in MONITORING_EVENTS:
        if not state_value(state, "project_id"):
            raise ValueError("Для события мониторинга нужен project_id")
        return "monitor"

    raise ValueError(f"Неизвестный тип события: {event_type}")


def parse_docx_node(parser: ProjectParser | None = None) -> Any:
    parser_instance = parser

    def parse_docx(state: ProjectControlData | dict[str, Any]) -> dict[str, Any]:
        nonlocal parser_instance

        raw_file_path = state_value(state, "file_path")
        if not raw_file_path:
            raise ValueError("Нет file_path для парсинга DOCX")

        if parser_instance is None:
            parser_instance = ProjectParser()

        file_path = Path(raw_file_path)
        project_data = parser_instance.parse(file_path)

        return {
            "parsed_project": project_data.model_dump(mode="json"),
        }

    return parse_docx


def update_project_node(session_factory: sessionmaker) -> Any:
    def update_project(state: ProjectControlData | dict[str, Any]) -> dict[str, Any]:
        parsed_project = state_value(state, "parsed_project")
        if parsed_project is None:
            raise ValueError("Нет результата парсинга DOCX для записи в projects")

        raw_file_path = state_value(state, "file_path")
        if not raw_file_path:
            raise ValueError("Нет file_path для записи DOCX-схемы в projects")

        file_path = Path(raw_file_path)
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

        as_of = state_value(state, "as_of")
        monitoring_result = run_project_monitor(
            project_id,
            as_of=as_of,
            trigger_event=build_trigger_event_context(state, project_id),
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
                "notification_id": monitoring_result["notification_id"],
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


def run_project_control_event(
        file_path: str | Path | None = None,
        event_type: ProjectEventType = "docx_changed",
        project_id: str | None = None,
        as_of: date | str | None = None,
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
        file_path=None if file_path is None else str(Path(file_path)),
        project_id=project_id,
        as_of=as_of,
    )
    return graph.invoke(initial_state.model_dump())
