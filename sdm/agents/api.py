from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import dispose_shared_engine
from .routes import assistance


async def health() -> dict[str, str]:
    return {"status": "ok"}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    try:
        yield
    finally:
        await dispose_shared_engine()


def create_app() -> FastAPI:
    load_dotenv()
    app = FastAPI(title="Project QA Agent", lifespan=lifespan)
    cors_origins = os.getenv(
        "AGENTS_CORS_ORIGINS", "http://localhost:5180,http://127.0.0.1:5180"
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_api_route("/health", health, methods=["GET"])
    app.include_router(assistance.router)
    return app


app = create_app()
