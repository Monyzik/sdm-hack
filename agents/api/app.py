from __future__ import annotations

import os
from datetime import date

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from agents.use_cases.control_event_simulation import (
    SimulationClearResult,
    SimulationJob,
    clear_control_event_simulation,
    get_control_event_simulation,
    start_control_event_simulation,
)
from agents.use_cases.project_brief import ProjectManagerBrief, run_project_brief
from agents.use_cases.project_qa import (
    ProjectQuestionAnswer,
    ProjectQuestionRequest,
    run_project_question,
)


def get_cors_origins() -> list[str]:
    raw_value = os.getenv("AGENTS_CORS_ORIGINS", "http://localhost:5180,http://127.0.0.1:5180")
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


app = FastAPI(title="AI Project Control Tower Agents")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/agents/control-events/simulation", response_model=SimulationJob)
async def start_control_event_simulation_job() -> SimulationJob:
    try:
        return await start_control_event_simulation()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось запустить симуляцию: {exc}") from exc


@app.get("/api/v1/agents/control-events/simulation/{job_id}", response_model=SimulationJob)
async def get_control_event_simulation_job(job_id: str) -> SimulationJob:
    try:
        return get_control_event_simulation(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Симуляция не найдена") from exc


@app.delete("/api/v1/agents/control-events/simulation", response_model=SimulationClearResult)
async def clear_control_event_simulation_job() -> SimulationClearResult:
    try:
        return await clear_control_event_simulation()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось очистить симуляцию: {exc}") from exc


@app.get("/api/v1/agents/projects/{project_id}/brief", response_model=ProjectManagerBrief)
async def get_project_ai_brief(
    project_id: str,
    as_of: date | None = Query(default=None),
    max_depth: int = Query(default=2, ge=1, le=4),
) -> ProjectManagerBrief:
    backend_api_url = os.getenv("BACKEND_API_URL", "http://backend:8000")
    try:
        return await run_project_brief(
            project_id=project_id,
            as_of=as_of,
            max_depth=max_depth,
            backend_api_url=backend_api_url,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Backend не вернул problem context") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Backend недоступен: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка LLM-агента: {exc}") from exc


@app.post("/api/v1/agents/projects/{project_id}/ask", response_model=ProjectQuestionAnswer)
async def ask_project_agent(
    project_id: str,
    payload: ProjectQuestionRequest,
) -> ProjectQuestionAnswer:
    backend_api_url = os.getenv("BACKEND_API_URL", "http://backend:8000")
    try:
        return await run_project_question(
            project_id=project_id,
            question=payload.question,
            as_of=payload.as_of,
            max_depth=payload.max_depth,
            conversation_context=payload.conversation_context,
            backend_api_url=backend_api_url,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Backend не вернул данные проекта") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Backend недоступен: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка Q&A-агента: {exc}") from exc
