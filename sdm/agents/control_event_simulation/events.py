from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVENTS_FILE = PROJECT_ROOT / "data/demo/control_events.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "outputs/agents_json/control_event_simulation_output.json"
SIMULATION_START_DATE = date(2026, 6, 19)

EVENT_FIELD_ALIASES = {
    "тип_события": "event_type",
    "путь_файла": "file_path",
    "идентификатор_проекта": "project_id",
    "дата_среза": "as_of",
}

EVENT_TYPE_ALIASES = {
    "документ_добавлен": "docx_added",
    "документ_изменен": "docx_changed",
    "задача_изменена": "task_changed",
    "риск_изменен": "risk_changed",
    "бюджет_изменен": "budget_changed",
    "зависимость_изменена": "dependency_changed",
    "коммуникация_изменена": "communication_changed",
    "ручной_мониторинг": "manual_monitoring_requested",
}


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
        events.append(normalize_event_paths(normalize_event_fields(event)))
    return assign_unique_as_of_dates(events)


def assign_unique_as_of_dates(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dated_events: list[dict[str, Any]] = []
    used_dates: set[str] = set()
    offset = 0

    for event in events:
        normalized = dict(event)
        as_of = normalized.get("as_of")
        if isinstance(as_of, str) and as_of and as_of not in used_dates:
            used_dates.add(as_of)
            dated_events.append(normalized)
            continue

        while True:
            next_as_of = (SIMULATION_START_DATE + timedelta(days=offset)).isoformat()
            offset += 1
            if next_as_of not in used_dates:
                normalized["as_of"] = next_as_of
                used_dates.add(next_as_of)
                dated_events.append(normalized)
                break

    return dated_events


def normalize_event_paths(event: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(event)
    file_path = normalized.get("file_path")
    if isinstance(file_path, str) and file_path:
        path = Path(file_path).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        normalized["file_path"] = str(path)
    return normalized


def normalize_event_fields(event: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        EVENT_FIELD_ALIASES.get(key, key): value
        for key, value in event.items()
    }
    event_type = normalized.get("event_type")
    if isinstance(event_type, str):
        normalized["event_type"] = EVENT_TYPE_ALIASES.get(event_type, event_type)
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
