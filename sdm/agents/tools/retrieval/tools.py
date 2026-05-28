from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import Field

from ..base import ToolArgsModel, make_tool
from .executor import ProjectEvidenceExecutor
from .formatting import _compact_retrieval_result


class EvidenceContextArgs(ToolArgsModel):
    evidence_id: str = Field(
        min_length=1,
        max_length=256,
        description="Точный id или однозначный source_id чанка из search_project_evidence; не путь к файлу.",
    )
    neighbors: int = Field(
        default=1,
        ge=0,
        le=2,
        description="Число соседних чанков с каждой стороны того же документа и версии (0–2).",
    )


class EvidenceSearchArgs(ToolArgsModel):
    query: str = Field(
        min_length=1,
        max_length=500,
        description="Непустой поисковый запрос по текстовым свидетельствам проекта.",
    )
    entity_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="ID конкретной задачи или другой сущности для ограничения поиска.",
    )
    limit: int | None = Field(
        default=None, ge=1, le=20, description="Максимум возвращаемых записей; по умолчанию 8."
    )


def build_get_evidence_context(tool_executor: ProjectEvidenceExecutor) -> BaseTool:
    async def get_evidence_context(evidence_id: str, neighbors: int = 1) -> dict[str, Any]:
        return await tool_executor.get_evidence_context(
            {"evidence_id": evidence_id, "neighbors": neighbors}
        )

    return make_tool(
        name="get_evidence_context",
        description=(
            "Прочитать полный доступный индексированный текст по точному id/source_id "
            "из поиска и соседние разделы того же документа и версии. Область проекта "
            "и дата сохраняются. До 5 чанков, до 6000 символов каждый; text_truncated "
            "явно отмечает обрезку. Для других источников возвращается только сам чанк. "
            "not_found означает отсутствие однозначного доступного чанка; файлы не открываются."
        ),
        args_schema=EvidenceContextArgs,
        func=get_evidence_context,
    )


def build_search_project_evidence(tool_executor: ProjectEvidenceExecutor) -> BaseTool:
    async def search_project_evidence(
        query: str,
        entity_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_project_evidence(
            {
                "query": query,
                "entity_id": entity_id,
                "limit": limit,
            }
        )
        return _compact_retrieval_result(result)

    return make_tool(
        name="search_project_evidence",
        description=(
            "RAG-поиск по текстовому следу проекта: комментарии задач, сообщения коммуникаций, "
            "риски, решения, запросы на изменение, причины зависимостей и историю изменений. "
            "Используй для вопросов о причинах, истории обсуждения и уже согласованных действиях. Выборка релевантных фрагментов, не полный архив; используй entity_id для конкретной сущности. warning указывает на ограничения поиска."
        ),
        args_schema=EvidenceSearchArgs,
        func=search_project_evidence,
    )
