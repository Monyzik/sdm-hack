from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select

from agents.agents.project_control import EVENT_LABELS, ProjectControlData, build_project_control_graph
from sdm.backend.database.models import Base, Notification
from sdm.backend.database.session import create_async_engine_from_env, create_async_session_factory
from scripts.simulate_control_events import EVENTS_FILE, OUTPUT_FILE, load_events, save_json

from .schemas import SimulationClearResult, SimulationEventResult, SimulationJob, SimulationStage, SimulationStageStatus


_jobs: dict[str, SimulationJob] = {}
_tasks: set[asyncio.Task[None]] = set()
_lock = threading.Lock()


async def start_control_event_simulation() -> SimulationJob:
    active_job = _active_job()
    if active_job is not None:
        return active_job

    job = SimulationJob(
        job_id=uuid4().hex,
        status="queued",
        stages=[
            _stage(
                "queued",
                "Симуляция поставлена в очередь",
                "Готовим поток control events для monitoring graph.",
                "pending",
            )
        ],
        results=[],
    )
    with _lock:
        _jobs[job.job_id] = job

    task = asyncio.create_task(_run_simulation_job(job.job_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return get_control_event_simulation(job.job_id)


def get_control_event_simulation(job_id: str) -> SimulationJob:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job.model_copy(deep=True)


async def clear_control_event_simulation() -> SimulationClearResult:
    engine = create_async_engine_from_env(_database_url())
    session_factory = create_async_session_factory(engine)
    deleted = 0

    async with session_factory() as session:
        result = await session.scalars(
            select(Notification).where(Notification.source == "monitoring_graph")
        )
        notifications = list(result.all())
        for notification in notifications:
            if _is_simulation_notification(notification):
                await session.delete(notification)
                deleted += 1
        await session.commit()
    await engine.dispose()

    output_file_removed = False
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()
        output_file_removed = True

    with _lock:
        _jobs.clear()

    return SimulationClearResult(
        deleted_notifications=deleted,
        output_file_removed=output_file_removed,
    )


async def _run_simulation_job(job_id: str) -> None:
    _update_job(job_id, status="running")
    _append_stage(
        job_id,
        "load_events",
        "Загружаем сценарий событий",
        f"Источник: {EVENTS_FILE.name}",
        "running",
    )

    engine = None
    try:
        events = await asyncio.to_thread(load_events, EVENTS_FILE)
        _update_job(job_id, total_events=len(events))
        _finish_stage(job_id, "load_events", "success", f"Найдено событий: {len(events)}")

        _append_stage(
            job_id,
            "prepare_graph",
            "Инициализируем project control graph",
            "Подключаем БД, parser, monitoring graph и notification agent.",
            "running",
        )
        engine = create_async_engine_from_env(_database_url())
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = create_async_session_factory(engine)
        graph = build_project_control_graph(session_factory=session_factory)
        _finish_stage(job_id, "prepare_graph", "success", "Граф готов к обработке событий.")

        persisted_results: list[dict[str, Any]] = []
        for index, raw_event in enumerate(events, start=1):
            event_type = str(raw_event.get("event_type") or "unknown")
            event_label = EVENT_LABELS.get(event_type, event_type)
            event_stage_id = f"event_{index}"
            _append_stage(
                job_id,
                event_stage_id,
                f"Вызываем event {index}/{len(events)}: {event_label}",
                _event_detail(raw_event),
                "running",
            )

            _append_stage(
                job_id,
                f"agent_{index}",
                "Monitoring graph анализирует проект",
                "Считаем метрики, классифицируем алерты, формируем draft уведомления.",
                "running",
            )
            try:
                event = ProjectControlData.model_validate(raw_event)
                result = await graph.ainvoke(event.model_dump())
                monitoring = result.get("monitoring") or {}
                notification_id = monitoring.get("notification_id")
                project_id = result.get("project_id") or raw_event.get("project_id")
                _finish_stage(
                    job_id,
                    f"agent_{index}",
                    "success",
                    "Уведомление сохранено." if notification_id else "Агент не создал новое уведомление.",
                )
                _finish_stage(
                    job_id,
                    event_stage_id,
                    "success",
                    f"Проект {project_id or '-'} обработан.",
                )
                _append_result(
                    job_id,
                    SimulationEventResult(
                        event_type=event_type,
                        event_label=event_label,
                        project_id=None if project_id is None else str(project_id),
                        notification_id=None if notification_id is None else str(notification_id),
                    ),
                )
                persisted_results.append(
                    {
                        "event": event.model_dump(exclude_none=True),
                        "project_id": project_id,
                        "parsed_project": result.get("parsed_project"),
                        "monitoring": monitoring,
                        "error": None,
                    }
                )
            except Exception as exc:
                _finish_stage(job_id, f"agent_{index}", "error", str(exc))
                _finish_stage(job_id, event_stage_id, "error", "Событие завершилось ошибкой.")
                _append_result(
                    job_id,
                    SimulationEventResult(
                        event_type=event_type,
                        event_label=event_label,
                        project_id=None if raw_event.get("project_id") is None else str(raw_event.get("project_id")),
                        error=str(exc),
                    ),
                )
                persisted_results.append(
                    {
                        "event": raw_event,
                        "project_id": raw_event.get("project_id"),
                        "parsed_project": None,
                        "monitoring": None,
                        "error": str(exc),
                    }
                )

        failed = sum(1 for item in persisted_results if item["error"])
        payload = {
            "source": str(EVENTS_FILE),
            "total": len(persisted_results),
            "processed": len(persisted_results) - failed,
            "failed": failed,
            "items": persisted_results,
        }
        _append_stage(
            job_id,
            "save_output",
            "Сохраняем результат симуляции",
            str(OUTPUT_FILE),
            "running",
        )
        await asyncio.to_thread(save_json, OUTPUT_FILE, payload)
        _finish_stage(job_id, "save_output", "success", "JSON результата обновлен.")
        _append_stage(
            job_id,
            "refresh_notifications",
            "Обновляем страницу уведомлений",
            "Фронтенд перечитает inbox после завершения job.",
            "success",
        )
        _update_job(
            job_id,
            status="completed" if failed == 0 else "failed",
            failed_events=failed,
            output_file=str(OUTPUT_FILE),
            error=None if failed == 0 else f"Событий с ошибкой: {failed}",
        )
    except Exception as exc:
        _append_stage(job_id, "fatal_error", "Симуляция остановлена", str(exc), "error")
        _update_job(job_id, status="failed", error=str(exc))
    finally:
        if engine is not None:
            await engine.dispose()


def _active_job() -> SimulationJob | None:
    with _lock:
        for job in _jobs.values():
            if job.status in {"queued", "running"}:
                return job.model_copy(deep=True)
    return None


def _database_url() -> str | None:
    return os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_DOCKER")


def _event_detail(event: dict[str, Any]) -> str:
    project_id = event.get("project_id")
    as_of = event.get("as_of")
    file_path = event.get("file_path")
    parts = []
    if project_id:
        parts.append(f"project_id={project_id}")
    if as_of:
        parts.append(f"as_of={as_of}")
    if file_path:
        parts.append(f"file={Path(str(file_path)).name}")
    return ", ".join(parts) or "Без дополнительных параметров."


def _is_simulation_notification(notification: Notification) -> bool:
    payload = notification.payload if isinstance(notification.payload, dict) else {}
    return bool(payload.get("trigger_event") or payload.get("trigger_event_type"))


def _stage(
    stage_id: str,
    label: str,
    detail: str | None,
    status: SimulationStageStatus,
) -> SimulationStage:
    return SimulationStage(
        id=stage_id,
        label=label,
        detail=detail,
        status=status,
        timestamp=datetime.utcnow(),
    )


def _append_stage(
    job_id: str,
    stage_id: str,
    label: str,
    detail: str | None,
    status: SimulationStageStatus,
) -> None:
    with _lock:
        job = _jobs[job_id]
        job.stages.append(_stage(stage_id, label, detail, status))


def _finish_stage(
    job_id: str,
    stage_id: str,
    status: Literal["success", "error"],
    detail: str | None = None,
) -> None:
    with _lock:
        job = _jobs[job_id]
        for index in range(len(job.stages) - 1, -1, -1):
            if job.stages[index].id == stage_id:
                stage = job.stages[index]
                job.stages[index] = stage.model_copy(
                    update={
                        "status": status,
                        "detail": detail or stage.detail,
                        "timestamp": datetime.utcnow(),
                    }
                )
                return


def _append_result(job_id: str, result: SimulationEventResult) -> None:
    with _lock:
        job = _jobs[job_id]
        job.results.append(result)
        job.processed_events = len(job.results)


def _update_job(job_id: str, **updates: Any) -> None:
    with _lock:
        job = _jobs[job_id]
        _jobs[job_id] = job.model_copy(update=updates)
