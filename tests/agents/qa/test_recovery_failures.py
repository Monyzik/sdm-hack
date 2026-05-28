"""Сбой повторного черновика не позволяет публиковать старую проверку."""

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool

from sdm.agents.llm import IncompleteOutputError
from sdm.agents.project_qa.agent import _answer_from_state
from sdm.agents.project_qa.answer import VERIFICATION_UNAVAILABLE_ANSWER
from sdm.agents.project_qa.evidence.models import AnswerDraft, ClaimSupport, EvidenceReview
from sdm.agents.project_qa.graph import build_project_question_graph
from sdm.agents.project_qa.nodes.draft import draft_answer_node
from sdm.agents.project_qa.schemas import RequestRoute

FACTS = ["Пилот согласован.", "Ответственный назначен."]
CONTRADICTION = "Согласование пилота отозвано."
QUESTION = "Каковы условия пилота?"
DRAFT_MODULE = "sdm.agents.project_qa.nodes.draft"


def payload(prompt):
    return json.loads(prompt.split("<untrusted_data>")[1].split("</untrusted_data>")[0])["data"]


def review(verdicts):
    return EvidenceReview(
        claims=[
            {"claim_index": index, "verdict": verdict} for index, verdict in enumerate(verdicts)
        ],
        missing_aspects=["Нужны ли журналы за 30 дней?"],
        searches=[{"query": "Дополнительные условия"}],
        context_source_ids=[],
    )


def previous_state(**updates):
    return {
        "project_id": "P007",
        "as_of": "2026-06-19",
        "question": QUESTION,
        "used_tools": ["search_project_evidence"],
        "recovery_rounds": 1,
        "answer_draft": AnswerDraft(
            claims=[{"text": FACTS[0], "evidence": [{"source_id": "s", "quote": FACTS[0]}]}],
            unanswered_aspects=[],
        ),
        "evidence_review": review(["supported"]),
        "tool_sources": [{"id": "s", "data": {"text": FACTS[0]}}],
        **updates,
    }


class RecoveryFailureGraphTests(unittest.IsolatedAsyncioTestCase):
    async def run_graph(self, outcome):
        searches, drafts, reviews, isolated, events = [], [], [], [], []

        async def summary():
            return "summary", {"project_id": "P007"}

        async def context():
            return "context", {"project": {"id": "P007"}}

        async def search(query: str):
            searches.append(query)
            if query == QUESTION:
                texts = FACTS
            else:
                self.assertEqual(query, "Дополнительные условия")
                texts = [CONTRADICTION if outcome == "contradiction" else "Условия уточняются."]
            return "sources", {
                "items": [
                    {"id": f"D{len(searches)}-{index}", "title": f"Документ {index}", "text": text}
                    for index, text in enumerate(texts)
                ]
            }

        async def parse_pydantic(*, response_model, **kwargs):
            if response_model is RequestRoute:
                return RequestRoute(intent="project_question")
            data = payload(kwargs["user_prompt"])
            if response_model is ClaimSupport:
                isolated.append(data)
                return ClaimSupport(
                    entailed=True,
                    all_numbers_supported=True,
                    status_and_modality_supported=True,
                    contradicted=False,
                )
            if issubclass(response_model, AnswerDraft):
                drafts.append(data)
                if len(drafts) > 1:
                    raise IncompleteOutputError("length")
                claims = []
                for fact in FACTS:
                    src = next(
                        item
                        for item in data["evidence_sources"]
                        if item["data"].get("text") == fact
                    )
                    claims.append(
                        {"text": fact, "evidence": [{"source_id": src["id"], "quote": fact}]}
                    )
                return response_model(claims=claims, unanswered_aspects=[])
            self.assertIs(response_model, EvidenceReview)
            reviews.append(data)
            if outcome == "complete_with_gap":
                return review(["supported", "supported"])
            if len(reviews) == 1:
                return review(["supported", "unsupported"])
            if outcome == "failed_verification":
                raise ValueError("PRIVATE PROVIDER DETAILS")
            if outcome == "contradiction":
                new_sources = data["other_retrieved_sources"]
                self.assertTrue(
                    any(item["data"].get("text") == CONTRADICTION for item in new_sources)
                )
                return review(["contradicted", "unsupported"])
            return review(["supported", "unsupported"])

        tools = [
            StructuredTool.from_function(
                coroutine=func,
                name=name,
                description="Локальный источник для проверки графа.",
                response_format="content_and_artifact",
            )
            for name, func in [
                ("get_project_summary", summary),
                ("get_problem_context", context),
                ("search_project_evidence", search),
            ]
        ]
        graph = build_project_question_graph(
            llm=SimpleNamespace(parse_pydantic=parse_pydantic),
            tools=tools,
            temperature=0,
            max_tool_rounds=1,
        )
        result = None
        async for mode, chunk in graph.astream(
            {
                "project_id": "P007",
                "as_of": "2026-06-19",
                "question": QUESTION,
                "messages": [HumanMessage(content=QUESTION)],
                "stream_response": True,
            },
            stream_mode=["custom", "values"],
        ):
            if mode == "custom":
                events.append(chunk)
            else:
                result = chunk
        return _answer_from_state(result), searches, drafts, reviews, isolated, events

    async def test_all_supported_with_gap_finishes_partial_without_recovery(self):
        answer, searches, drafts, reviews, isolated, events = await self.run_graph(
            "complete_with_gap"
        )
        self.assertEqual(searches, [QUESTION])
        self.assertEqual((len(drafts), len(reviews), len(isolated)), (1, 1, 2))
        self.assertEqual(answer.verification.status, "partial")
        self.assertEqual([claim.text for claim in answer.claims], FACTS)
        self.assertEqual(answer.verification.recovery_rounds, 0)
        self.assertTrue(
            any(
                event["event"] == "recovery_skipped"
                and event["data"]["reason"] == "answer_supported"
                for event in events
            )
        )
        self.assertFalse(
            any(event["event"] in {"evidence_recovery", "draft_reused"} for event in events)
        )

    async def test_length_failure_rechecks_old_claims_against_new_sources(self):
        for outcome in ("contradiction", "rechecked", "failed_verification"):
            with self.subTest(outcome=outcome):
                answer, searches, drafts, reviews, isolated, events = await self.run_graph(outcome)
                self.assertEqual(searches, [QUESTION, "Дополнительные условия"])
                self.assertEqual((len(drafts), len(reviews), len(isolated)), (2, 2, 4))
                self.assertEqual(reviews[1]["draft"], reviews[0]["draft"])
                self.assertTrue(reviews[1]["other_retrieved_sources"])
                reused = [event for event in events if event["event"] == "draft_reused"]
                self.assertEqual(len(reused), 1)
                self.assertEqual(reused[0]["data"]["reason"], "length")
                self.assertEqual(answer.verification.recovery_rounds, 1)
                if outcome == "rechecked":
                    self.assertEqual(answer.verification.status, "partial")
                    self.assertEqual([claim.text for claim in answer.claims], FACTS[:1])
                    self.assertEqual(
                        [source.data["text"] for source in answer.evidence_sources], FACTS[:1]
                    )
                else:
                    self.assertEqual(answer.claims, [])
                    self.assertEqual(answer.evidence_sources, [])
                    self.assertNotIn(FACTS[0], answer.answer)
                    self.assertEqual(
                        answer.verification.status,
                        "unavailable" if outcome == "failed_verification" else "abstained",
                    )
                if outcome == "failed_verification":
                    self.assertEqual(answer.answer, VERIFICATION_UNAVAILABLE_ANSWER)
                    self.assertNotIn("PRIVATE", answer.model_dump_json())


class RecoveryDraftTimeoutTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        writer = patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None)
        writer.start()
        self.addCleanup(writer.stop)

    async def test_first_draft_failure_does_not_reuse_even_an_existing_draft(self):
        llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=IncompleteOutputError("length")))
        with patch(f"{DRAFT_MODULE}.emit_stream_event") as emit:
            with self.assertRaises(IncompleteOutputError):
                await draft_answer_node(llm=llm, temperature=0)(previous_state(recovery_rounds=0))
        emit.assert_not_called()

    async def test_failed_previous_verification_cannot_be_reused(self):
        llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=IncompleteOutputError("length")))
        with self.assertRaises(IncompleteOutputError):
            await draft_answer_node(llm=llm, temperature=0)(
                previous_state(verification_failed=True)
            )

    async def test_recovery_timeout_cancels_provider_and_invalidates_old_review(self):
        cancelled = asyncio.Event()

        async def blocked(**kwargs):
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=blocked))
        current = previous_state()
        with (
            patch(f"{DRAFT_MODULE}.RECOVERY_DRAFT_TIMEOUT_SECONDS", 0.01),
            patch(f"{DRAFT_MODULE}.emit_stream_event") as emit,
        ):
            update = await draft_answer_node(llm=llm, temperature=0)(current)
        self.assertTrue(cancelled.is_set())
        self.assertIs(update["answer_draft"], current["answer_draft"])
        self.assertIsNone(update["evidence_review"])
        emit.assert_called_once_with("draft_reused", reason="timeout")

    async def test_external_cancellation_propagates_without_reusing_draft(self):
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def blocked(**kwargs):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=blocked))
        with patch(f"{DRAFT_MODULE}.emit_stream_event") as emit:
            task = asyncio.create_task(draft_answer_node(llm=llm, temperature=0)(previous_state()))
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            emit.assert_not_called()
        self.assertTrue(cancelled.is_set())

    async def test_verification_reserve_bounds_timeout_or_skips_provider(self):
        real_timeout = asyncio.timeout
        for remaining, expected in [(100.0, 30.0), (45.0, 15.0), (30.0, None), (20.0, None)]:
            with self.subTest(remaining=remaining):
                current = previous_state(request_deadline=100.0 + remaining)
                llm = SimpleNamespace(
                    parse_pydantic=AsyncMock(return_value=current["answer_draft"])
                )
                with (
                    patch(f"{DRAFT_MODULE}.monotonic", return_value=100.0),
                    patch(f"{DRAFT_MODULE}.asyncio.timeout", wraps=real_timeout) as timer,
                ):
                    update = await draft_answer_node(llm=llm, temperature=0)(current)
                self.assertIsNone(update["evidence_review"])
                if expected is None:
                    timer.assert_not_called()
                    llm.parse_pydantic.assert_not_awaited()
                else:
                    timer.assert_called_once_with(expected)
                    llm.parse_pydantic.assert_awaited_once()
