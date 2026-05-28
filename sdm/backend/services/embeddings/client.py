from __future__ import annotations

import asyncio
import math
from functools import lru_cache
from typing import Protocol

import httpx
from dotenv import load_dotenv

from .config import EmbeddingSettings


class EmbeddingClient(Protocol):
    doc_model: str
    query_model: str
    dimensions: int
    index_identity: str

    async def embed_document(self, text: str) -> list[float]: ...
    async def embed_query(self, text: str) -> list[float]: ...


def validate_embedding(value: object, dimensions: int) -> list[float]:
    if not isinstance(value, list) or len(value) != dimensions or not value:
        raise ValueError(f"Ожидался непустой embedding размерности {dimensions}.")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise ValueError("Embedding должен содержать только числа.")
    try:
        vector = [float(item) for item in value]
    except OverflowError as exc:
        raise ValueError("Embedding содержит число вне диапазона float32.") from exc
    if any(not math.isfinite(item) or abs(item) > 3.402823466e38 for item in vector):
        raise ValueError("Embedding должен содержать конечные числа float32.")
    if not any(vector):
        raise ValueError("Нулевой embedding не подходит для cosine similarity.")
    return vector


class OpenAIEmbeddingClient:
    """Cache configuration, never an async connection pool tied to an event loop."""

    def __init__(
        self, settings: EmbeddingSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.settings = settings
        self.doc_model = self.query_model = settings.model
        self.dimensions = settings.dimensions
        self.index_identity = settings.index_identity
        self._transport = transport

    async def embed_document(self, text: str) -> list[float]:
        return await self._embed(text)

    async def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Запрос для embedding не должен быть пустым.")
        if self.settings.query_instruction:
            text = f"Instruct: {self.settings.query_instruction}\nQuery:{text}"
        return await self._embed(text)

    async def _embed(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Текст для embedding не должен быть пустым.")
        payload = {
            "model": self.doc_model,
            "input": text,
            "dimensions": self.dimensions,
            "encoding_format": "float",
        }
        async with httpx.AsyncClient(
            timeout=self.settings.timeout_seconds, transport=self._transport
        ) as client:
            for attempt in range(self.settings.max_retries + 1):
                try:
                    response = await client.post(
                        f"{self.settings.base_url}/embeddings",
                        json=payload,
                        headers={"Authorization": f"Bearer {self.settings.api_key}"},
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if (
                        status not in {408, 429} and status < 500
                    ) or attempt == self.settings.max_retries:
                        raise RuntimeError(f"Сервис эмбеддингов вернул HTTP {status}.") from exc
                    await asyncio.sleep(self._retry_delay(attempt, exc.response))
                    continue
                except httpx.RequestError as exc:
                    if attempt == self.settings.max_retries:
                        raise RuntimeError("Не удалось обратиться к сервису эмбеддингов.") from exc
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                try:
                    body = response.json()
                    data = body["data"]
                    if not isinstance(data, list) or len(data) != 1:
                        raise ValueError("Ожидался один embedding.")
                    return validate_embedding(data[0]["embedding"], self.dimensions)
                except (KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError("Сервис эмбеддингов вернул некорректный вектор.") from exc
        raise AssertionError("Embedding attempts exhausted")

    def _retry_delay(self, attempt: int, response: httpx.Response | None = None) -> float:
        if response is not None:
            try:
                retry_after = float(response.headers.get("retry-after", ""))
                if math.isfinite(retry_after):
                    return min(30.0, max(0.0, retry_after))
            except ValueError:
                pass
        return min(30.0, self.settings.retry_base_delay_seconds * 2**attempt)


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    load_dotenv()
    return OpenAIEmbeddingClient(EmbeddingSettings.from_env())
