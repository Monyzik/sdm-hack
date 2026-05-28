"""Проверки графа без сети: поиск источников, проверка и публикация."""

import json
import unittest

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sdm.agents.project_qa.answer import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    VERIFICATION_UNAVAILABLE_ANSWER,
)
from sdm.agents.project_qa.evidence.models import AnswerDraft, ClaimSupport, EvidenceReview
from sdm.agents.project_qa.graph import build_project_question_graph
from sdm.agents.project_qa.schemas import RequestRoute
from sdm.agents.tools.registry import build_project_tools

QUESTION = "Что было и что стало?"
QUERIES = ["Прежнее состояние", "Новое состояние"]
FACTS = ["Ранее план был предварительным.", "Новый план утверждён."]


def payload(prompt):
    return json.loads(prompt.split("<untrusted_data>")[1].split("</untrusted_data>")[0])["data"]


class RecoveryExecutor:
    max_depth = 2

    async def calculate_delay_cost(self, delay_days, daily_cost=None, resource_count=None):
        raise AssertionError("Расчёт стоимости не нужен в этом сценарии")

    def __init__(self, fail_recovery=False):
        self.fail_recovery = fail_recovery
        self.searches = []
        self.reads = []

    async def project_summary(self):
        self.reads.append("get_project_summary")
        return {"project_id": "P007"}

    async def problem_context(self, *, max_depth):
        self.reads.append("get_problem_context")
        return {"project": {"id": "P007"}}

    async def search_project_evidence(self, arguments):
        query = arguments["query"]
        self.searches.append(query)
        if self.fail_recovery and query == QUERIES[0]:
            raise RuntimeError("SECRET RECOVERY BACKEND DETAILS")
        index = QUERIES.index(query) + 1 if query in QUERIES else 0
        text = FACTS[index - 1] if index else "План требует уточнения."
        return {
            "items": [
                {
                    "id": f"P007:documents:PLAN:v1:c{index:04d}",
                    "source_table": "documents",
                    "source_id": f"PLAN:v1:c{index:04d}",
                    "title": "План",
                    "text": text,
                    "metadata": {"document_id": "PLAN", "version": "1"},
                }
            ]
        }


class RecoveryLLM:
    def __init__(self, outcome="supported"):
        self.outcome = outcome
        self.drafts = []
        self.reviews = []
        self.chat_calls = 0

    async def chat_completion(self, **kwargs):
        self.chat_calls += 1
        raise AssertionError("max_tool_rounds=1 must proceed from preload straight to drafting")

    async def parse_pydantic(self, *, response_model, **kwargs):
        if response_model is ClaimSupport:
            return ClaimSupport(
                entailed=True,
                all_numbers_supported=True,
                status_and_modality_supported=True,
                contradicted=False,
            )
        if response_model is RequestRoute:
            return RequestRoute(intent="project_question")
        data = payload(kwargs["user_prompt"])
        if issubclass(response_model, AnswerDraft):
            self.drafts.append(data)
            sources = data["evidence_sources"]
            if len(self.drafts) == 1 or self.outcome != "supported":
                src = next(s for s in sources if s["data"].get("text") == "План требует уточнения.")
                claims = [
                    {
                        "text": QUERIES[0],
                        "evidence": [{"source_id": src["id"], "quote": "План требует уточнения."}],
                    }
                ]
            else:
                claims = []
                for fact in FACTS:
                    src = next(s for s in sources if s["data"].get("text") == fact)
                    claims.append(
                        {"text": fact, "evidence": [{"source_id": src["id"], "quote": fact}]}
                    )
            return response_model(claims=claims, unanswered_aspects=[])
        if response_model is EvidenceReview:
            self.reviews.append(data)
            if self.outcome == "timeout":
                raise TimeoutError("SECRET PROVIDER DETAILS")
            if self.outcome == "invalid":
                return EvidenceReview(
                    claims=[], missing_aspects=[], searches=[], context_source_ids=[]
                )
            supported = self.outcome == "supported" and len(self.reviews) == 2
            return EvidenceReview(
                claims=[
                    {"claim_index": i, "verdict": "supported" if supported else "unsupported"}
                    for i in range(len(data["draft"]["claims"]))
                ],
                missing_aspects=[],
                context_source_ids=[],
                searches=[] if supported else [{"query": query} for query in QUERIES],
            )
        raise AssertionError("Project facts cannot be rewritten by a final LLM call")


class RecoveryGraphTests(unittest.IsolatedAsyncioTestCase):
    async def run_graph(self, outcome, *, fail_recovery=False):
        llm, executor = RecoveryLLM(outcome), RecoveryExecutor(fail_recovery=fail_recovery)
        graph = build_project_question_graph(
            llm=llm, tools=build_project_tools(executor, executor), temperature=0, max_tool_rounds=1
        )
        events, result = [], None
        initial = {
            "project_id": "P007",
            "as_of": "2026-06-19",
            "question": QUESTION,
            "messages": [HumanMessage(content=QUESTION)],
            "used_tools": [],
            "tool_sources": [],
            "tool_rounds": 0,
            "stream_response": True,
        }
        async for mode, chunk in graph.astream(initial, stream_mode=["custom", "values"]):
            if mode == "custom":
                events.append(chunk)
            elif mode == "values":
                result = chunk
        self.assertIsNotNone(result)
        self.assertEqual(llm.chat_calls, 0)
        self.assertCountEqual(executor.reads, ["get_project_summary", "get_problem_context"])
        # Дополнительный поиск вызывает настоящие инструменты и сохраняет пары сообщений.
        pending = set()
        for message in result["messages"]:
            if isinstance(message, AIMessage):
                self.assertFalse(pending)
                pending.update(call["id"] for call in message.tool_calls)
            elif isinstance(message, ToolMessage):
                self.assertIn(message.tool_call_id, pending)
                pending.remove(message.tool_call_id)
            else:
                self.assertFalse(pending)
        self.assertFalse(pending)
        return result, llm, executor, events

    async def test_missing_aspects_trigger_two_real_searches_then_supported_final(self):
        result, llm, executor, events = await self.run_graph("supported")
        self.assertEqual(executor.searches[0], QUESTION)
        self.assertCountEqual(executor.searches[1:], QUERIES)
        self.assertEqual(len(llm.drafts), 2)
        self.assertEqual(len(llm.reviews), 2)
        self.assertEqual(result["recovery_rounds"], 1)
        self.assertEqual(result["tool_rounds"], 2)
        tools = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        self.assertEqual(len(tools), 2)
        self.assertTrue(all(m.status == "success" and m.artifact for m in tools))
        final = json.loads(result["final_content"])
        self.assertEqual(final["verification"]["status"], "passed")
        self.assertEqual(final["verification"]["supported_claims"], 2)
        self.assertEqual([claim["text"] for claim in final["claims"]], FACTS)
        self.assertNotIn(QUERIES[0], final["answer"])
        self.assertEqual(len(final["evidence_ids"]), 2)
        second_catalog = json.dumps(llm.drafts[1]["evidence_sources"], ensure_ascii=False)
        for fact in FACTS:
            self.assertIn(fact, second_catalog)
        self.assertIsNotNone(llm.drafts[1]["previous_review"])
        names = [event["event"] for event in events]
        reviews = [i for i, name in enumerate(names) if name == "evidence_review"]
        recovery = names.index("evidence_recovery")
        final_started = next(
            i
            for i, e in enumerate(events)
            if e["event"] == "stage_started" and e["data"]["stage"] == "finalize_answer"
        )
        self.assertLess(reviews[0], recovery)
        self.assertLess(recovery, reviews[1])
        self.assertLess(reviews[1], final_started)
        self.assertEqual([events[i]["data"]["supported"] for i in reviews], [0, 2])
        self.assertCountEqual(events[recovery]["data"]["queries"], QUERIES)

    async def test_persistent_unsupported_stops_after_one_recovery_and_abstains(self):
        result, llm, executor, events = await self.run_graph("unsupported")
        self.assertEqual(len(executor.searches), 3)
        self.assertEqual(len(llm.drafts), 2)
        self.assertEqual(len(llm.reviews), 2)
        self.assertEqual(result["recovery_rounds"], 1)
        self.assertEqual(sum(e["event"] == "evidence_recovery" for e in events), 1)
        final = json.loads(result["final_content"])
        self.assertEqual(final["answer"], INSUFFICIENT_EVIDENCE_ANSWER)
        self.assertEqual(final["verification"]["status"], "abstained")
        self.assertEqual(final["claims"], [])
        self.assertEqual(final["evidence_ids"], [])
        reviews = [e for e in events if e["event"] == "evidence_review"]
        self.assertFalse(reviews[-1]["data"]["recovery_available"])

    async def test_invalid_or_failed_judge_never_recovers_or_publishes_draft(self):
        for outcome in ("invalid", "timeout"):
            with self.subTest(outcome=outcome):
                result, llm, executor, events = await self.run_graph(outcome)
                self.assertEqual(executor.searches, [QUESTION])
                self.assertEqual(len(llm.drafts), 1)
                self.assertEqual(len(llm.reviews), 1)
                self.assertEqual(result.get("recovery_rounds", 0), 0)
                names = [event["event"] for event in events]
                self.assertNotIn("evidence_recovery", names)
                self.assertNotIn("evidence_review", names)
                self.assertIn("verification_failed", names)
                final = json.loads(result["final_content"])
                self.assertEqual(final["answer"], VERIFICATION_UNAVAILABLE_ANSWER)
                self.assertEqual(final["verification"]["status"], "unavailable")
                self.assertEqual(final["claims"], [])
                self.assertNotIn(QUERIES[0], final["answer"])
                self.assertNotIn("SECRET", result["final_content"])
                self.assertNotIn("SECRET", str(events))

    async def test_recovery_tool_error_is_safe_and_other_batch_artifacts_survive(self):
        result, llm, executor, events = await self.run_graph("unsupported", fail_recovery=True)
        self.assertCountEqual(executor.searches, [QUESTION, *QUERIES])
        self.assertEqual(result["recovery_rounds"], 1)
        self.assertEqual(len(llm.drafts), 2)
        self.assertEqual(len(llm.reviews), 2)
        messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        self.assertEqual(len(messages), 2)
        failures = [m for m in messages if m.status == "error"]
        successes = [m for m in messages if m.status == "success"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(len(successes), 1)
        self.assertIsNone(failures[0].artifact)
        self.assertIn("Не удалось получить дополнительные источники", failures[0].content)
        self.assertTrue(successes[0].artifact)
        texts = [s["data"].get("text") for s in result["tool_sources"]]
        self.assertIn(FACTS[1], texts)
        self.assertNotIn(FACTS[0], texts)
        final = json.loads(result["final_content"])
        self.assertEqual(final["answer"], INSUFFICIENT_EVIDENCE_ANSWER)
        self.assertEqual(final["verification"]["status"], "abstained")
        self.assertEqual(final["claims"], [])
        self.assertEqual(sum(e["event"] == "evidence_recovery" for e in events), 1)
        self.assertNotIn("SECRET", str(messages))
        self.assertNotIn("SECRET", str(result["tool_sources"]))
        self.assertNotIn("SECRET", result["final_content"])
        self.assertNotIn("SECRET", str(events))
