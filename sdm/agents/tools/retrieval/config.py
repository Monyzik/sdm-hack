from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


class RerankSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    candidates: int = Field(default=16, ge=2, le=20)
    timeout_seconds: float = Field(default=30, gt=0, le=120)

    @classmethod
    def from_env(cls) -> RerankSettings:
        load_dotenv()
        return cls(
            enabled=os.getenv("RAG_RERANK_ENABLED") or "true",
            candidates=os.getenv("RAG_RERANK_CANDIDATES") or 16,
            timeout_seconds=os.getenv("RAG_RERANK_TIMEOUT_SECONDS") or 30,
        )
