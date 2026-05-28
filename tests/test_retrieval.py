import asyncio
import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sdm.backend.services.project_evidence import build_project_evidence
from sdm.backend.services.retrieval import (
    EvidenceCandidate,
    _indexed_chunks_count,
    _vector_literal,
    ensure_project_rag_schema,
    reindex_project_rag,
    search_project_rag,
)


class RetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def test_index_embedding_requests_are_bounded_and_preserve_all_rows(self):
        active, peak = 0, 0

        async def embed_document(_text):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.005)
                return [1.0] * 32
            finally:
                active -= 1

        client = self.client()
        client.embed_document.side_effect = embed_document
        session = AsyncMock()
        with patch(
            "sdm.backend.services.retrieval.build_project_evidence",
            return_value=[self.candidate()] * 7,
        ):
            result = await reindex_project_rag(session, self.source(), embedding_client=client)
        self.assertEqual(peak, 3)
        self.assertEqual(active, 0)
        self.assertEqual(result.chunks_indexed, 7)
        session.commit.assert_awaited_once()

    async def test_blank_query_does_not_start_indexing_or_call_provider(self):
        session = AsyncMock()
        client = self.client()
        with self.assertRaises(ValueError):
            await search_project_rag(session, self.source(), query="  ", embedding_client=client)
        session.execute.assert_not_awaited()
        client.embed_document.assert_not_awaited()
        client.embed_query.assert_not_awaited()

    def client(self):
        return SimpleNamespace(
            doc_model="Qwen/Qwen3-Embedding-8B",
            query_model="Qwen/Qwen3-Embedding-8B",
            dimensions=32,
            index_identity="profile-new",
            embed_document=AsyncMock(return_value=[1.0] * 32),
            embed_query=AsyncMock(return_value=[1.0] * 32),
        )

    async def test_schema_preserves_legacy_table_and_checks_dimensions(self):
        session = AsyncMock()
        await ensure_project_rag_schema(session)
        sql = "\n".join(str(call.args[0]) for call in session.execute.await_args_list)
        self.assertIn("project_rag_chunks_v2", sql)
        self.assertIn("embedding vector NOT NULL", sql)
        self.assertIn("vector_dims(embedding) = embedding_dimensions", sql)
        self.assertNotIn("DROP", sql)
        self.assertIn("PRIMARY KEY (id, embedding_profile)", sql)

    async def test_count_and_search_use_profile_and_dimension_guard(self):
        session = AsyncMock()
        session.scalar.return_value = 1
        result = MagicMock()
        result.mappings.return_value.all.return_value = []
        session.execute.return_value = result
        client = self.client()
        await _indexed_chunks_count(session, "P001", client)
        self.assertEqual(session.scalar.await_args.args[1]["profile"], "profile-new")
        await search_project_rag(
            session,
            SimpleNamespace(project=SimpleNamespace(id="P001")),
            query="query",
            embedding_client=client,
        )
        sql, params = session.execute.await_args.args
        self.assertIn("AS MATERIALIZED", str(sql))
        self.assertIn("FROM matching_chunks", str(sql))
        self.assertEqual(params["embedding_profile"], "profile-new")
        self.assertEqual(params["embedding_dimensions"], 32)

    async def test_embedding_failure_does_not_delete_index(self):
        session = AsyncMock()
        client = self.client()
        client.embed_document.side_effect = RuntimeError("provider offline")
        with patch(
            "sdm.backend.services.retrieval.build_project_evidence",
            return_value=[self.candidate()],
        ):
            with self.assertRaises(RuntimeError):
                await reindex_project_rag(session, self.source(), embedding_client=client)
        session.execute.assert_not_awaited()
        session.commit.assert_not_awaited()

    async def test_replacement_is_profile_scoped_and_rolls_back_insert_failure(self):
        session = AsyncMock()

        async def execute(sql, *args):
            if "INSERT INTO" in str(sql):
                raise RuntimeError("insert failed")

        session.execute.side_effect = execute
        with patch(
            "sdm.backend.services.retrieval.build_project_evidence",
            return_value=[self.candidate()],
        ):
            with self.assertRaises(RuntimeError):
                await reindex_project_rag(session, self.source(), embedding_client=self.client())
        delete = next(
            call for call in session.execute.await_args_list if "DELETE FROM" in str(call.args[0])
        )
        self.assertIn("embedding_profile = :profile", str(delete.args[0]))
        self.assertEqual(delete.args[1]["profile"], "profile-new")
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()

    async def test_success_commits_complete_index(self):
        session = AsyncMock()
        with patch(
            "sdm.backend.services.retrieval.build_project_evidence",
            return_value=[self.candidate()],
        ) as candidates:
            result = await reindex_project_rag(
                session, self.source(), embedding_client=self.client()
            )
        self.assertEqual(candidates.call_args.kwargs["as_of"], None)
        session.commit.assert_awaited_once()
        self.assertEqual(result.embedding_dimensions, 32)

    def test_vectors_validated_before_sql(self):
        with self.assertRaises(ValueError):
            _vector_literal([1] * 256, 4096)
        with self.assertRaises(ValueError):
            _vector_literal([float("nan")] * 32, 32)

    def source(self):
        return SimpleNamespace(project=SimpleNamespace(id="P001"))

    def candidate(self):
        return EvidenceCandidate("P001", "projects", "P001", "project", "P001", "Title", "Evidence")


class EvidenceTimeTests(unittest.TestCase):
    def source(self, **overrides):
        collections = dict.fromkeys(
            (
                "tasks",
                "task_comments",
                "task_history",
                "risks",
                "communications",
                "communication_messages",
                "task_dependencies",
                "dependencies",
                "decisions",
                "change_requests",
                "budget_line_items",
                "milestones",
            ),
            (),
        )
        return SimpleNamespace(
            project=SimpleNamespace(
                id="P007",
                name="Demo",
                business_goal="Goal",
                expected_result="Target",
                business_value="Value",
                priority="high",
                lifecycle_status="active",
            ),
            **(collections | overrides),
        )

    def test_future_deadlines_do_not_hide_known_snapshot_entities(self):
        due = date(2026, 6, 22)
        source = self.source(
            tasks=[
                SimpleNamespace(
                    id="T701",
                    external_id="EXT",
                    title="Mask data",
                    blocker_reason=None,
                    planned_due_date=due,
                    status="open",
                    priority="high",
                    assignee_name="Anna",
                )
            ],
            dependencies=[
                SimpleNamespace(
                    id="DEP1",
                    depends_on="Access approval",
                    dependency_type="external",
                    owner_team="Reviewers",
                    status="pending",
                    criticality="high",
                    expected_date=due,
                    linked_task_id="T701",
                )
            ],
        )
        candidates = build_project_evidence(source, as_of=date(2026, 6, 19))
        task, dependency = candidates[1:]
        self.assertIsNone(task.occurred_at)
        self.assertIsNone(dependency.occurred_at)
        self.assertEqual(task.metadata["planned_due_date"], "2026-06-22")
        self.assertEqual(dependency.metadata["expected_date"], "2026-06-22")

    def test_future_aggregate_excluded_but_observed_messages_preserved(self):
        communication = SimpleNamespace(
            id="C1",
            topic="Access approval",
            from_team="A",
            to_team="B",
            status="closed",
            channel="email",
            last_message_date=date(2026, 6, 22),
            linked_task_id=None,
            importance="high",
            expected_response_date=date(2026, 6, 23),
        )

        def message(id, day):
            return SimpleNamespace(
                id=id,
                communication_id="C1",
                summary="Review update",
                message_time=datetime(2026, 6, day, 10),
                linked_task_id=None,
                sender_team="A",
                recipient_team="B",
                channel="email",
                message_type="update",
                status="sent",
                is_escalation=False,
            )

        source = self.source(
            communications=[communication],
            communication_messages=[message("M1", 18), message("M2", 22)],
        )
        observed = build_project_evidence(source, as_of=date(2026, 6, 19))
        self.assertEqual([c.source_id for c in observed], ["P007", "M1"])
        self.assertEqual(observed[-1].occurred_at, datetime(2026, 6, 18, 10))
        all_candidates = build_project_evidence(source, as_of=None)
        self.assertEqual([c.source_id for c in all_candidates], ["P007", "C1", "M1", "M2"])
        self.assertEqual(all_candidates[1].occurred_at.date(), date(2026, 6, 22))

    def test_real_event_dates_remain_and_future_events_are_filtered(self):
        comments = [
            SimpleNamespace(
                id=f"COMMENT{day}",
                task_id="T1",
                created_at=datetime(2026, 6, day),
                text="Status",
                author_name="Anna",
                channel="local",
                source_system="demo",
            )
            for day in (18, 22)
        ]
        history = [
            SimpleNamespace(
                id=f"HISTORY{day}",
                task_id="T1",
                changed_at=datetime(2026, 6, day),
                field_changed="status",
                old_value="new",
                new_value="open",
                changed_by="Anna",
                source_system="demo",
            )
            for day in (18, 22)
        ]
        decisions = [
            SimpleNamespace(
                id=f"DECISION{day}",
                decision_date=date(2026, 6, day),
                linked_milestone_id=None,
                decision_type="review",
                description="Review",
                decision_owner="Anna",
                status="requested",
            )
            for day in (18, 22)
        ]
        requests = [
            SimpleNamespace(
                id=f"REQUEST{day}",
                request_date=date(2026, 6, day),
                change_type="reserve",
                description="Request",
                requested_by="Anna",
                requested_budget_delta=600000,
                requested_timeline_delta_days=0,
                status="requested",
            )
            for day in (18, 22)
        ]
        observed = build_project_evidence(
            self.source(
                task_comments=comments,
                task_history=history,
                decisions=decisions,
                change_requests=requests,
            ),
            as_of=date(2026, 6, 19),
        )
        self.assertEqual(
            {c.source_id for c in observed[1:]},
            {"COMMENT18", "HISTORY18", "DECISION18", "REQUEST18"},
        )
        self.assertTrue(all(c.occurred_at.date() == date(2026, 6, 18) for c in observed[1:]))


if __name__ == "__main__":
    unittest.main()


class RankingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def row(self, identifier, text, score):
        return {
            "id": identifier,
            "project_id": "P007",
            "source_table": "documents",
            "source_id": identifier,
            "entity_type": "document",
            "entity_id": identifier,
            "title": "Evidence",
            "text": text,
            "occurred_at": None,
            "linked_task_id": None,
            "metadata": {},
            "score": score,
        }

    def client(self):
        return SimpleNamespace(
            doc_model="model",
            query_model="model",
            dimensions=32,
            index_identity="profile",
            embed_query=AsyncMock(return_value=[1.0] * 32),
            embed_document=AsyncMock(),
        )

    async def search(self, ranking, rows, limit=8):
        session, client = AsyncMock(), self.client()
        with (
            patch("sdm.backend.services.retrieval.ensure_project_rag_schema", new=AsyncMock()),
            patch(
                "sdm.backend.services.retrieval._indexed_chunks_count",
                new=AsyncMock(return_value=1),
            ),
            patch(
                "sdm.backend.services.retrieval._load_search_candidates",
                new=AsyncMock(return_value=rows),
            ),
        ):
            result = await search_project_rag(
                session,
                SimpleNamespace(project=SimpleNamespace(id="P007")),
                query="маскирование",
                embedding_client=client,
                ranking=ranking,
                limit=limit,
            )
        return result, client

    async def test_hybrid_recovers_lexical_winner_outside_dense_pool_and_retains_provenance(self):
        rows = [
            self.row("dense", "другая тема", 0.99),
            self.row("lexical", "маскирование", None),
            self.row("both", "маскирование и согласование", 0.8),
        ]
        result, client = await self.search("hybrid", rows)
        self.assertEqual({item.id for item in result.items}, {"dense", "lexical", "both"})
        self.assertEqual(len(result.items), len({item.id for item in result.items}))
        self.assertEqual(result.candidate_counts, {"dense": 2, "bm25": 2})
        self.assertEqual(result.fusion_rank_constant, 60)
        lexical = next(item for item in result.items if item.id == "lexical")
        self.assertIsNone(lexical.retrieval.dense_rank)
        self.assertEqual(lexical.retrieval.bm25_rank, 1)
        self.assertGreater(lexical.retrieval.bm25_score, 0)
        self.assertEqual(lexical.score, lexical.retrieval.fusion_score)
        client.embed_query.assert_awaited_once()
        bounded, _ = await self.search("hybrid", rows, limit=1)
        self.assertEqual(bounded.count, 1)
        self.assertEqual(bounded.items[0].id, "both")

    async def test_dense_preserves_cosine_scores_and_does_not_run_lexical_search(self):
        rows = [self.row("B", "маскирование", 0.7), self.row("A", "другая тема", 0.9)]
        with patch("sdm.backend.services.retrieval.bm25_search") as lexical:
            result, _ = await self.search("dense", rows, limit=1)
        lexical.assert_not_called()
        self.assertEqual([(item.id, item.score) for item in result.items], [("A", 0.9)])
        self.assertEqual(result.items[0].retrieval.dense_rank, 1)
        self.assertIsNone(result.items[0].retrieval.bm25_score)
        self.assertIsNone(result.fusion_rank_constant)

    async def test_warm_bm25_never_calls_embedding_provider(self):
        result, client = await self.search(
            "bm25", [self.row("hit", "маскирование", None), self.row("miss", "прочее", None)]
        )
        self.assertEqual([item.id for item in result.items], ["hit"])
        client.embed_query.assert_not_awaited()
        client.embed_document.assert_not_awaited()
        self.assertIsNone(result.items[0].retrieval.dense_score)
        self.assertEqual(result.items[0].score, result.items[0].retrieval.bm25_score)

    async def test_invalid_mode_rejected_before_database_and_provider(self):
        session, client = AsyncMock(), self.client()
        with self.assertRaises(ValueError):
            await search_project_rag(
                session,
                SimpleNamespace(project=SimpleNamespace(id="P007")),
                query="x",
                embedding_client=client,
                ranking="invalid",
            )
        session.execute.assert_not_awaited()
        session.scalar.assert_not_awaited()
        client.embed_query.assert_not_awaited()

    async def test_both_branches_share_all_prefilters_in_single_materialized_snapshot(self):
        from sdm.backend.services.retrieval import _load_search_candidates

        for mode in ["dense", "bm25", "hybrid"]:
            with self.subTest(mode=mode):
                session = AsyncMock()
                result = MagicMock()
                result.mappings.return_value.all.return_value = []
                session.execute.return_value = result
                await _load_search_candidates(
                    session,
                    project_id="P007",
                    embedding_client=self.client(),
                    query_embedding=None if mode == "bm25" else [1.0] * 32,
                    as_of=date(2026, 6, 17),
                    entity_id="DOC1",
                    ranking=mode,
                    candidate_limit=40,
                )
                session.execute.assert_awaited_once()
                statement, params = session.execute.await_args.args
                sql = str(statement)
                prefilter = sql.split(")", 1)[0]
                # Inspect the whole scope before any dense branch, not a post-fusion filter.
                scope = sql.split(", dense_candidates", 1)[0].split("SELECT m.id", 1)[0]
                self.assertIn("AS MATERIALIZED", prefilter)
                for constraint in [
                    "project_id = :project_id",
                    "embedding_profile = :embedding_profile",
                    "embedding_dimensions = :embedding_dimensions",
                    "vector_dims(embedding) = :embedding_dimensions",
                    "occurred_at::date <= CAST(:as_of_date AS date)",
                    "source_id = CAST(:entity_id AS text)",
                    "entity_id = CAST(:entity_id AS text)",
                    "linked_task_id = CAST(:entity_id AS text)",
                    "metadata ->> 'external_id'",
                    "metadata ->> 'document_id'",
                ]:
                    self.assertIn(constraint, scope)
                self.assertEqual(params["project_id"], "P007")
                self.assertEqual(params["as_of_date"], date(2026, 6, 17))
                self.assertEqual(params["entity_id"], "DOC1")
                self.assertEqual(params["embedding_profile"], "profile")
                self.assertEqual(params["embedding_dimensions"], 32)
                if mode == "hybrid":
                    self.assertIn("LEFT JOIN dense_candidates", sql)
                elif mode == "dense":
                    self.assertIn("JOIN dense_candidates", sql)
                    self.assertNotIn("LEFT JOIN", sql)
                else:
                    self.assertNotIn("<=>", sql)
                    self.assertNotIn("embedding", {key for key in params if key == "embedding"})
