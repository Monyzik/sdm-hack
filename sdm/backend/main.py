from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sdm.backend.api.project_summary import router as project_summary_router
from sdm.backend.core.config import get_settings
from sdm.backend.dependencies import async_engine


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(project_summary_router, prefix=settings.api_prefix)
app.include_router(project_summary_router, prefix=f"/api{settings.api_prefix}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
