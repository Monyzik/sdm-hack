import asyncio
import unittest
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from openai import APIError

from sdm.agents.tools.retrieval.config import RerankSettings
from sdm.agents.tools.retrieval.executor import ProjectEvidenceExecutor
from sdm.backend.schemas.retrieval import ProjectRetrievalContext


def shortlist():
    return ProjectRetrievalContext.model_validate(
        {
            "project_id": "P007",
            "query": "Вопрос",
            "as_of_date": "2026-06-19",
            "ranking": "hybrid",
            "candidate_limit": 60,
            "candidate_counts": {"dense": 16, "bm25": 16},
            "fusion_rank_constant": 60,
            "count": 16,
            "items": [
                {
                    "id": f"D{i}",
                    "project_id": "P007",
                    "source_table": "documents",
                    "source_id": f"S{i}",
                    "entity_type": "document",
                    "entity_id": f"DOC{i}",
                    "title": "Источник",
                    "text": "Факт",
                    "score": 0.02,
                    "retrieval": {"dense_rank": i + 1, "fusion_score": 0.02},
                }
                for i in range(16)
            ],
        }
    )


class RerankingExecutorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session_open = False

        @asynccontextmanager
        async def session_factory():
            self.session_open = True
            try:
                yield object()
            finally:
                self.session_open = False

        self.factory = session_factory
        self.llm = SimpleNamespace(model="fake", parse_pydantic=AsyncMock())
        self.repository_patch = patch(
            "sdm.agents.tools.retrieval.executor.ProjectSummaryRepository"
        )
        repository = self.repository_patch.start()
        repository.return_value.get_project_source = AsyncMock(return_value=object())
        self.addCleanup(self.repository_patch.stop)
        self.embedding_patch = patch(
            "sdm.agents.tools.retrieval.executor.get_embedding_client", return_value=object()
        )
        self.embedding_patch.start()
        self.addCleanup(self.embedding_patch.stop)
        self.search_patch = patch(
            "sdm.agents.tools.retrieval.executor.search_project_rag",
            new=AsyncMock(return_value=shortlist()),
        )
        self.search = self.search_patch.start()
        self.addCleanup(self.search_patch.stop)
        self.event_patch = patch("sdm.agents.tools.retrieval.reranking.emit_stream_event")
        self.events = self.event_patch.start()
        self.addCleanup(self.event_patch.stop)

    def executor(self, **settings):
        return ProjectEvidenceExecutor(
            project_id="P007",
            as_of="2026-06-19",
            session_factory=self.factory,
            llm=self.llm,
            rerank_settings=RerankSettings(**settings),
        )

    async def test_injected_embedding_and_request_scope_reach_both_retrieval_operations(self):
        embedding = object()
        executor = ProjectEvidenceExecutor(
            project_id="P007",
            as_of="2026-06-19",
            session_factory=self.factory,
            embedding_client=embedding,
            rerank_settings=RerankSettings(enabled=False),
        )
        await executor.search_project_evidence({"query": "Вопрос", "entity_id": "T007"})
        search_args = self.search.await_args.kwargs
        self.assertIs(search_args["embedding_client"], embedding)
        self.assertEqual(search_args["as_of"], date(2026, 6, 19))
        self.assertEqual(search_args["entity_id"], "T007")
        with patch(
            "sdm.agents.tools.retrieval.executor.get_evidence_context",
            new=AsyncMock(return_value={"status": "not_found", "items": []}),
        ) as context:
            result = await executor.get_evidence_context(
                {"evidence_id": "document:version:chunk", "neighbors": 2}
            )
        context_args = context.await_args.kwargs
        self.assertIs(context_args["embedding_client"], embedding)
        self.assertEqual(context_args["project_id"], "P007")
        self.assertEqual(context_args["as_of"], date(2026, 6, 19))
        self.assertEqual(context_args["evidence_id"], "document:version:chunk")
        self.assertEqual(context_args["neighbors"], 2)
        self.assertEqual(result["status"], "not_found")
        self.assertFalse(self.session_open)

    async def test_session_closed_before_llm_and_sixteen_candidates_return_eight(self):
        async def parse(**kwargs):
            self.assertFalse(self.session_open)
            return kwargs["response_model"](ordered_ids=[f"D{i}" for i in reversed(range(16))])

        self.llm.parse_pydantic.side_effect = parse
        result = await self.executor().search_project_evidence({"query": "Вопрос"})
        self.assertEqual(self.search.await_args.kwargs["limit"], 16)
        self.assertEqual(result["count"], 8)
        self.assertEqual(
            [item["id"] for item in result["items"]], [f"D{i}" for i in range(15, 7, -1)]
        )
        self.assertTrue(result["rerank_applied"])

    async def test_disabled_never_calls_llm_and_queries_requested_count(self):
        result = await self.executor(enabled=False).search_project_evidence({"query": "Вопрос"})
        self.llm.parse_pydantic.assert_not_awaited()
        self.assertEqual(self.search.await_args.kwargs["limit"], 8)
        self.assertFalse(result["rerank_applied"])
        self.assertEqual([item["id"] for item in result["items"]], [f"D{i}" for i in range(8)])
        self.events.assert_not_called()

    async def test_provider_and_validation_errors_emit_explicit_rrf_fallback(self):
        for error in [
            APIError("offline", request=httpx.Request("POST", "http://fake"), body=None),
            ValueError("bad permutation"),
        ]:
            with self.subTest(error=type(error)):
                self.events.reset_mock()
                self.llm.parse_pydantic.side_effect = error
                result = await self.executor().search_project_evidence({"query": "Вопрос"})
                self.assertFalse(result["rerank_applied"])
                self.assertEqual(
                    [item["id"] for item in result["items"]], [f"D{i}" for i in range(8)]
                )
                self.assertEqual(
                    sum(call.args[0] == "rerank_failed" for call in self.events.call_args_list), 1
                )
                self.assertEqual(self.events.call_args.args[0], "rerank_failed")
                self.assertEqual(self.events.call_args.kwargs["fallback"], "rrf")
                self.assertEqual(self.events.call_args.kwargs["reason"], type(error).__name__)

    async def test_bounded_timeout_falls_back_but_caller_cancellation_propagates(self):
        started = asyncio.Event()

        async def blocked(**kwargs):
            started.set()
            await asyncio.Event().wait()

        self.llm.parse_pydantic.side_effect = blocked
        result = await self.executor(timeout_seconds=0.01).search_project_evidence(
            {"query": "Вопрос"}
        )
        self.assertFalse(result["rerank_applied"])
        self.assertEqual(result["count"], 8)
        self.assertEqual(self.events.call_args.kwargs["reason"], "TimeoutError")
        self.events.reset_mock()
        started.clear()
        task = asyncio.create_task(self.executor().search_project_evidence({"query": "Вопрос"}))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(self.session_open)
        self.assertNotIn("rerank_failed", [call.args[0] for call in self.events.call_args_list])
