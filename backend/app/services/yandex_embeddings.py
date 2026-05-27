from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Literal

import httpx
from dotenv import load_dotenv


EmbeddingKind = Literal["document", "query"]
EMBEDDING_ENDPOINT = "https://ai.api.cloud.yandex.net/foundationModels/v1/textEmbedding"


class YandexEmbeddingClient:
    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.getenv("YANDEX_CLOUD_API_KEY")
        if not self.api_key:
            raise ValueError("Не задан YANDEX_CLOUD_API_KEY в окружении.")

        self.folder = os.getenv("YANDEX_CLOUD_FOLDER")
        if not self.folder:
            raise ValueError("Не задан YANDEX_CLOUD_FOLDER в окружении.")

        self.doc_model = _model_uri(
            os.getenv("YANDEX_EMBEDDING_DOC_MODEL", "text-search-doc/latest"),
            self.folder,
        )
        self.query_model = _model_uri(
            os.getenv("YANDEX_EMBEDDING_QUERY_MODEL", "text-search-query/latest"),
            self.folder,
        )
        try:
            self.timeout = float(os.getenv("YANDEX_EMBEDDING_TIMEOUT_SECONDS", "30"))
        except ValueError as exc:
            raise ValueError("YANDEX_EMBEDDING_TIMEOUT_SECONDS должен быть числом.") from exc

    async def embed_document(self, text: str) -> list[float]:
        return await self._embed(text, kind="document")

    async def embed_query(self, text: str) -> list[float]:
        return await self._embed(text, kind="query")

    async def _embed(self, text: str, *, kind: EmbeddingKind) -> list[float]:
        model_uri = self.doc_model if kind == "document" else self.query_model
        payload = {"modelUri": model_uri, "text": text[:8000]}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-folder-id": self.folder,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(EMBEDDING_ENDPOINT, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Сервис эмбеддингов Yandex вернул HTTP {exc.response.status_code}."
                ) from exc
            except httpx.RequestError as exc:
                raise RuntimeError("Не удалось обратиться к сервису эмбеддингов Yandex.") from exc
        return _parse_embedding(response.json())


@lru_cache(maxsize=1)
def get_yandex_embedding_client() -> YandexEmbeddingClient:
    return YandexEmbeddingClient()


def _model_uri(value: str, folder: str) -> str:
    if value.startswith("emb://"):
        return value
    return f"emb://{folder}/{value}"


def _parse_embedding(payload: dict[str, Any]) -> list[float]:
    raw_embedding = payload.get("embedding") or payload.get("vector")
    if isinstance(raw_embedding, dict):
        raw_embedding = raw_embedding.get("values") or raw_embedding.get("embedding")
    if not isinstance(raw_embedding, list):
        raise ValueError("API эмбеддингов Yandex не вернул вектор.")
    try:
        return [float(item) for item in raw_embedding]
    except (TypeError, ValueError) as exc:
        raise ValueError("API эмбеддингов Yandex вернул вектор в неожиданном формате.") from exc
