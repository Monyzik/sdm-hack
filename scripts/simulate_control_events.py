from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.project_control_graph import ProjectControlData, build_project_control_graph
from backend.app.database.models import Base
from backend.app.database.session import create_engine_from_env, create_session_factory


EVENTS_FILE = PROJECT_ROOT / "data/control_events.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data/agents_json/control_event_simulation_output.json"


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл событий: {path}")

    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        try:
            event = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Некорректный JSON на строке {line_number}: {path}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"Событие на строке {line_number} должно быть JSON-объектом")
        events.append(normalize_event_paths(event))
    return events


def normalize_event_paths(event: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(event)
    file_path = normalized.get("file_path")
    if isinstance(file_path, str) and file_path:
        path = Path(file_path).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        normalized["file_path"] = str(path)
    return normalized


def json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    events = load_events(EVENTS_FILE)

    engine = create_engine_from_env()
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    graph = build_project_control_graph(session_factory=session_factory)

    results = []
    for index, raw_event in enumerate(events, start=1):
        print(f"[{index}/{len(events)}] {raw_event.get('event_type')}")

        try:
            event = ProjectControlData.model_validate(raw_event)
            result = graph.invoke(event.model_dump())
            results.append(
                {
                    "event": event.model_dump(exclude_none=True),
                    "project_id": result.get("project_id"),
                    "parsed_project": result.get("parsed_project"),
                    "monitoring": result.get("monitoring"),
                    "error": None,
                }
            )
        except Exception as exc:
            print(exc)
            results.append(
                {
                    "event": raw_event,
                    "project_id": raw_event.get("project_id"),
                    "parsed_project": None,
                    "monitoring": None,
                    "error": str(exc),
                }
            )

    failed = sum(1 for item in results if item["error"])
    payload = {
        "source": str(EVENTS_FILE),
        "total": len(results),
        "processed": len(results) - failed,
        "failed": failed,
        "items": results,
    }
    save_json(OUTPUT_FILE, payload)

    print(f"События: {payload['processed']}/{payload['total']} обработано")
    print(f"JSON результата: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
