from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Project Control Tower Backend"
    api_prefix: str = "/api/v1"
    database_url: str | None = None
    cors_origins: tuple[str, ...] = ("http://localhost:5180", "http://127.0.0.1:5180")


def get_settings() -> Settings:
    load_dotenv()
    cors_origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "BACKEND_CORS_ORIGINS",
            "http://localhost:5180,http://127.0.0.1:5180",
        ).split(",")
        if origin.strip()
    )
    return Settings(database_url=os.getenv("DATABASE_URL"), cors_origins=cors_origins)
