from __future__ import annotations

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sdm.agents.control_event_simulation.events import (
    EVENTS_FILE,
    OUTPUT_FILE,
    load_events,
    save_json,
)
from sdm.agents.project_control import ProjectControlData, build_project_control_graph
from sdm.backend.database.models import Base
from sdm.backend.database.session import create_async_engine_from_env, create_async_session_factory


async def async_main() -> None:
    events = load_events(EVENTS_FILE)

    engine = create_async_engine_from_env()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_async_session_factory(engine)
    graph = build_project_control_graph(session_factory=session_factory)

    results = []
    for index, raw_event in enumerate(events, start=1):
        print(f"[{index}/{len(events)}] {raw_event.get('event_type')}")

        try:
            event = ProjectControlData.model_validate(raw_event)
            result = await graph.ainvoke(event.model_dump())
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
    await engine.dispose()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
