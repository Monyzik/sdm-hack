"""Расширение контекста сохраняет область поиска и текст, прочитанный моделью."""

import asyncio
from datetime import date, datetime
from functools import wraps
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from sdm.agents.tools.project.executor import ProjectFactToolExecutor
from sdm.agents.tools.registry import build_project_tools
from sdm.agents.tools.retrieval.executor import ProjectEvidenceExecutor
from sdm.agents.tools.retrieval.tools import EvidenceContextArgs
from sdm.agents.tools.sources import collect_tool_sources, select_answer_sources
from sdm.backend.services.retrieval import get_evidence_context


def async_test(func):
    @wraps(func)
    def run():
        return asyncio.run(func())

    return run


def client():
    return SimpleNamespace(
        index_identity="profile", dimensions=32, embed_query=AsyncMock(), embed_document=AsyncMock()
    )


@async_test
async def test_read_query_scopes_anchor_and_neighbors_and_never_writes_or_embeds():
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    session.execute.return_value = result
    embeddings = client()
    response = await get_evidence_context(
        session,
        project_id="P007",
        evidence_id="P007:documents:D:v1:c0002",
        embedding_client=embeddings,
        as_of=date(2026, 6, 19),
        neighbors=2,
    )
    statement, params = session.execute.await_args.args
    sql = str(statement)
    # SQLAlchemy ищет параметры и внутри строк SQL, поэтому передаём регулярку как данные.
    bindings = set(statement.compile().params)
    assert "c" not in bindings
    assert bindings == set(params)
    assert params["chunk_ordinal_pattern"] == ":c([0-9]+)$"
    assert params["chunk_id_pattern"] == ":c[0-9]+$"
    scope = sql.split("), anchors AS")[0]
    for guard in (
        "project_id = :project_id",
        "embedding_profile = :embedding_profile",
        "embedding_dimensions = :embedding_dimensions",
        "vector_dims(embedding) = :embedding_dimensions",
        "occurred_at::date <= CAST(:as_of_date AS date)",
    ):
        assert guard in scope
    assert "FROM eligible WHERE id = :evidence_id OR source_id = :evidence_id" in sql
    assert "(SELECT count(*) FROM anchors) = 1" in sql
    assert "e.metadata ->> 'document_id' = a.metadata ->> 'document_id'" in sql
    assert "e.metadata ->> 'version' = a.metadata ->> 'version'" in sql
    assert "e.source_table = 'documents' AND a.source_table = 'documents'" in sql
    assert "abs(d.ordinal - center.ordinal) <= :neighbors" in sql
    assert "left(e.text, 6000)" in sql and "LIMIT 5" in sql
    assert params["project_id"] == "P007"
    assert params["embedding_profile"] == "profile"
    assert params["embedding_dimensions"] == 32
    assert params["as_of_date"] == date(2026, 6, 19)
    assert response["status"] == "not_found" and response["items"] == []
    assert collect_tool_sources("get_evidence_context", response) == []
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()
    embeddings.embed_query.assert_not_awaited()
    embeddings.embed_document.assert_not_awaited()
    for forbidden in ("CREATE ", "INSERT ", "UPDATE ", "DELETE "):
        assert forbidden not in sql


@async_test
async def test_context_tool_content_artifact_and_citation_keep_full_text_and_identity():
    row = dict(
        id="P007:documents:D:v1:c0002",
        source_id="D:v1:c0002",
        source_table="documents",
        title="Section",
        text="Evidence " * 400,
        occurred_at=datetime(2026, 6, 18),
        text_truncated=False,
        metadata={"document_id": "D", "version": "1", "section": "Section"},
        relative_position=0,
    )
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = [row]
    session.execute.return_value = result
    response = await get_evidence_context(
        session, project_id="P007", evidence_id=row["id"], embedding_client=client()
    )
    executor = AsyncMock(spec=ProjectEvidenceExecutor)
    executor.get_evidence_context.return_value = response
    tool = next(
        t
        for t in build_project_tools(AsyncMock(spec=ProjectFactToolExecutor), executor)
        if t.name == "get_evidence_context"
    )
    with patch("sdm.agents.tools.base.emit_stream_event"):
        message = await tool.ainvoke(
            {
                "name": tool.name,
                "args": {"evidence_id": row["id"]},
                "id": "read",
                "type": "tool_call",
            }
        )
    import json

    assert json.loads(message.content) == message.artifact == response
    records = collect_tool_sources(tool.name, message.artifact)
    sources = select_answer_sources(records, [row["id"]])
    assert len(sources) == 1
    assert sources[0]["data"]["text"] == row["text"]
    assert sources[0]["data"]["id"] == row["id"]
    assert sources[0]["data"]["metadata"] == row["metadata"]
    executor.get_evidence_context.assert_awaited_once_with(
        {"evidence_id": row["id"], "neighbors": 1}
    )


@pytest.mark.parametrize(
    "args",
    [
        {"evidence_id": ""},
        {"evidence_id": "x", "neighbors": 3},
        {"evidence_id": "x", "neighbors": -1},
        {"evidence_id": "x", "project_id": "other"},
    ],
)
def test_context_schema_rejects_invalid_bounds_and_scope_overrides(args):
    with pytest.raises(ValidationError):
        EvidenceContextArgs.model_validate(args)
