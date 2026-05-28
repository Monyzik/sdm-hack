from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

DEFAULT_QUERY_INSTRUCTION = (
    "Given a web search query, retrieve relevant passages that answer the query"
)


@dataclass(frozen=True)
class EmbeddingSettings:
    api_key: str = field(repr=False)
    base_url: str
    model: str = "Qwen/Qwen3-Embedding-8B"
    dimensions: int = 4096
    query_instruction: str = DEFAULT_QUERY_INSTRUCTION
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_base_delay_seconds: float = 1.0

    def __post_init__(self) -> None:
        url = urlsplit(self.base_url)
        if not self.api_key.strip():
            raise ValueError("EMBEDDING_API_KEY обязателен.")
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.query
            or url.fragment
            or url.username
        ):
            raise ValueError(
                "EMBEDDING_BASE_URL должен быть HTTP(S) URL провайдера без credentials/query/fragment."
            )
        if not self.model.strip():
            raise ValueError("EMBEDDING_MODEL обязателен.")
        if not 32 <= self.dimensions <= 4096:
            raise ValueError("EMBEDDING_DIMENSIONS должен быть от 32 до 4096.")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("EMBEDDING_TIMEOUT_SECONDS должен быть конечным положительным числом.")
        if not 0 <= self.max_retries <= 10:
            raise ValueError("EMBEDDING_MAX_RETRIES должен быть от 0 до 10.")
        if not math.isfinite(self.retry_base_delay_seconds) or self.retry_base_delay_seconds < 0:
            raise ValueError(
                "EMBEDDING_RETRY_BASE_DELAY_SECONDS должен быть конечным неотрицательным числом."
            )
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    @property
    def index_identity(self) -> str:
        profile = {
            "provider": self.base_url,
            "model": self.model,
            "dimensions": self.dimensions,
            "query_instruction": self.query_instruction,
            "format": "qwen-instruct-v1",
        }
        return hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()

    @classmethod
    def from_env(cls) -> EmbeddingSettings:
        return cls(
            api_key=os.getenv("EMBEDDING_API_KEY", ""),
            base_url=os.getenv("EMBEDDING_BASE_URL", ""),
            model=os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B"),
            dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "4096")),
            query_instruction=os.getenv("EMBEDDING_QUERY_INSTRUCTION", DEFAULT_QUERY_INSTRUCTION),
            timeout_seconds=float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("EMBEDDING_MAX_RETRIES", "3")),
            retry_base_delay_seconds=float(os.getenv("EMBEDDING_RETRY_BASE_DELAY_SECONDS", "1.0")),
        )
