from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from agents.project_control_graph import (
    DocxEventType,
    ProjectControlData,
    build_project_control_graph,
)
from backend.app.database.models import Base
from backend.app.database.session import create_engine_from_env, create_session_factory


DOCX_DIR = Path("data/project_documents")
OUTPUT_FILE = Path("data/agents_json/batch_output.json")
PER_FILE_OUTPUT_DIR = Path("data/per_file_json")
MONITORING_OUTPUT_FILE = Path("data/agents_json/project_monitoring_output.json")


def get_docx_files(folder: Path) -> list[Path]:
    files = sorted(
        file_path
        for file_path in folder.glob("*.docx")
        if not file_path.name.startswith("~$")
    )
    if not files:
        raise FileNotFoundError(f"В папке нет DOCX-файлов: {folder}")
    return files


def json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def detect_docx_event(file_path: Path) -> DocxEventType:
    parsed_json_path = PER_FILE_OUTPUT_DIR / f"{file_path.stem}.json"
    if parsed_json_path.exists():
        return "docx_changed"
    return "docx_added"


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    files = get_docx_files(DOCX_DIR)
    event_results = []
    monitoring_results = []
    engine = create_engine_from_env()
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    graph = build_project_control_graph(session_factory=session_factory)

    print("Обработка DOCX-событий через LangGraph")
    for index, file_path in enumerate(files, start=1):
        event_type = detect_docx_event(file_path)
        print(f"[{index}/{len(files)}] {event_type}: {file_path.name}")

        try:
            result = graph.invoke(
                ProjectControlData(
                    event_type=event_type,
                    file_path=str(file_path),
                ).model_dump()
            )
            parsed_project = result.get("parsed_project")
            monitoring = result.get("monitoring")
            project_id = result.get("project_id")

            if parsed_project:
                save_json(PER_FILE_OUTPUT_DIR / f"{file_path.stem}.json", parsed_project)
            if monitoring:
                monitoring_results.append(
                    {
                        "project_id": project_id,
                        "project": monitoring["project"],
                        "metrics": monitoring["metrics"],
                        "alerts": monitoring["alerts"],
                        "analysis": monitoring["analysis"],
                        "notification_draft": monitoring["notification_draft"],
                        "notification_id": monitoring["notification_id"],
                        "error": None,
                    }
                )

            event_results.append(
                {
                    "file": file_path.name,
                    "event_type": event_type,
                    "project_id": project_id,
                    "parsed_project": parsed_project,
                    "monitoring": monitoring,
                    "error": None,
                }
            )
        except Exception as exc:
            print(exc)
            event_results.append(
                {
                    "file": file_path.name,
                    "event_type": event_type,
                    "project_id": None,
                    "parsed_project": None,
                    "monitoring": None,
                    "error": str(exc),
                }
            )

    failed = sum(1 for item in event_results if item["error"])
    monitoring_failed = sum(1 for item in monitoring_results if item["error"])
    payload = {
        "docx_events": {
            "source": str(DOCX_DIR),
            "total": len(event_results),
            "processed": len(event_results) - failed,
            "failed": failed,
            "items": event_results,
        },
        "project_monitoring": {
            "total": len(monitoring_results),
            "processed": len(monitoring_results) - monitoring_failed,
            "failed": monitoring_failed,
            "items": monitoring_results,
        },
    }

    save_json(OUTPUT_FILE, payload)
    save_json(MONITORING_OUTPUT_FILE, monitoring_results)

    print(
        f"DOCX-события: {payload['docx_events']['processed']}/{payload['docx_events']['total']} обработано"
    )
    print(
        "Мониторинг: "
        f"{payload['project_monitoring']['processed']}/{payload['project_monitoring']['total']} проектов обработано"
    )
    print(f"Общий JSON: {OUTPUT_FILE}")
    print(f"JSON мониторинга: {MONITORING_OUTPUT_FILE}")
    print(f"JSON по файлам: {PER_FILE_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
