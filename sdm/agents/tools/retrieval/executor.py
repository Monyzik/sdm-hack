from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sdm.agents.db import get_shared_session_factory
from sdm.agents.llm import LLMAdapter, get_llm_adapter
from sdm.agents.text import bounded_limit
from sdm.backend.services.embeddings import EmbeddingClient, get_embedding_client
from sdm.backend.services.project_summary_repository import ProjectSummaryRepository
from sdm.backend.services.retrieval import get_evidence_context, search_project_rag

from .config import RerankSettings
from .reranking import rerank_with_fallback


class ProjectEvidenceExecutor:
    """Читает текстовые свидетельства проекта и упорядочивает результаты поиска."""

    def __init__(
        self,
        *,
        project_id: str,
        as_of: str,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        embedding_client: EmbeddingClient | None = None,
        llm: LLMAdapter | None = None,
        rerank_settings: RerankSettings | None = None,
    ) -> None:
        self.project_id = project_id
        self.as_of = as_of
        self._llm = llm
        self._rerank_settings = (
            rerank_settings if rerank_settings is not None else RerankSettings.from_env()
        )
        self._session_factory = (
            session_factory if session_factory is not None else get_shared_session_factory()
        )
        self._embedding_client = embedding_client

    async def search_project_evidence(self, arguments: dict[str, Any]) -> dict[str, Any]:
        limit_value = bounded_limit(arguments.get("limit"), default=8, maximum=20)
        entity_id = arguments.get("entity_id")
        query = str(arguments.get("query") or "")
        settings = self._rerank_settings
        retrieval_limit = max(limit_value, settings.candidates) if settings.enabled else limit_value
        async with self._session_factory() as session:
            repository = ProjectSummaryRepository(session)
            source = await repository.get_project_source(self.project_id)
            result = await search_project_rag(
                session,
                source,
                query=query,
                embedding_client=(
                    self._embedding_client
                    if self._embedding_client is not None
                    else get_embedding_client()
                ),
                as_of=_as_date(self.as_of),
                limit=retrieval_limit,
                entity_id=str(entity_id) if entity_id else None,
            )
        # Освобождаем соединение до вызова модели. Отмена запроса прерывает работу;
        # при ожидаемых ошибках модели или схемы сохраняем порядок RRF.
        if settings.enabled and len(result.items) > 1:
            llm = self._llm if self._llm is not None else get_llm_adapter()
            result = await rerank_with_fallback(
                result, top_k=limit_value, llm=llm, settings=settings
            )
        else:
            result = result.model_copy(
                update={
                    "items": result.items[:limit_value],
                    "count": min(len(result.items), limit_value),
                }
            )
        return result.model_dump(mode="json")

    async def get_evidence_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        async with self._session_factory() as session:
            return await get_evidence_context(
                session,
                project_id=self.project_id,
                evidence_id=arguments["evidence_id"],
                neighbors=arguments.get("neighbors", 1),
                embedding_client=(
                    self._embedding_client
                    if self._embedding_client is not None
                    else get_embedding_client()
                ),
                as_of=_as_date(self.as_of),
            )


def _as_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
