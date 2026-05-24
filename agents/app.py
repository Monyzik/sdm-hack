from __future__ import annotations

import os
from datetime import date
from urllib.error import HTTPError, URLError

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from agents.project_brief_graph import ProjectManagerBrief, run_project_brief


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
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/agents/projects/{project_id}/brief", response_model=ProjectManagerBrief)
def get_project_ai_brief(
    project_id: str,
    as_of: date | None = Query(default=None),
    max_depth: int = Query(default=2, ge=1, le=4),
) -> ProjectManagerBrief:
    backend_api_url = os.getenv("BACKEND_API_URL", "http://backend:8000")
    try:
        return run_project_brief(
            project_id=project_id,
            as_of=as_of,
            max_depth=max_depth,
            backend_api_url=backend_api_url,
        )
    except HTTPError as exc:
        raise HTTPException(status_code=exc.code, detail="Backend не вернул problem context") from exc
    except URLError as exc:
        raise HTTPException(status_code=503, detail=f"Backend недоступен: {exc.reason}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка LLM-агента: {exc}") from exc
