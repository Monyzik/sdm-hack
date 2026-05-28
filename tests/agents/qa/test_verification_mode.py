"""Оба режима ответа используют источники, проверка утверждений включается отдельно."""

import json
import unittest
from unittest.mock import patch

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from openai.types.chat import ChatCompletion
from pydantic import ValidationError

from sdm.agents.project_qa.agent import ProjectQuestionAgent, _answer_from_state
from sdm.agents.project_qa.evidence.models import AnswerDraft, ClaimSupport, EvidenceReview
from sdm.agents.project_qa.graph import build_project_question_graph
from sdm.agents.project_qa.schemas import (
    PROJECT_DATA_UNAVAILABLE_ANSWER,
    ProjectQuestionLLMAnswer,
    RequestRoute,
)
from sdm.agents.tools.base import NoArgs, make_tool
from sdm.agents.tools.retrieval.tools import EvidenceSearchArgs

FACT = "План требует уточнения."


class ModeLLM:
    def __init__(self, *, intent="project_question", fabricated=False):
        self.intent = intent
        self.fabricated = fabricated
        self.calls = []

    async def chat_completion(self, **kwargs):
        self.calls.append("chat_completion")
        return ChatCompletion.model_validate(
            {
                "id": "selection",
                "object": "chat.completion",
                "created": 1,
                "model": "offline",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "extra-search",
                                    "type": "function",
                                    "function": {
                                        "name": "search_project_evidence",
                                        "arguments": '{"query":"Уточнение плана"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        )

    async def parse_pydantic(self, *, response_model, **kwargs):
        self.calls.append(response_model.__name__)
        if response_model is RequestRoute:
            return response_model(intent=self.intent)
        if response_model is ClaimSupport:
            return response_model(
                entailed=True,
                all_numbers_supported=True,
                status_and_modality_supported=True,
                contradicted=False,
            )
        if response_model is EvidenceReview:
            return response_model(
                claims=[{"claim_index": 0, "verdict": "supported"}],
                missing_aspects=[],
                searches=[],
                context_source_ids=[],
            )
        if issubclass(response_model, AnswerDraft):
            data = json.loads(
                kwargs["user_prompt"].split("<untrusted_data>")[1].split("</untrusted_data>")[0]
            )["data"]
            source = next(s for s in data["evidence_sources"] if s["data"].get("text") == FACT)
            return response_model(
                claims=[
                    {
                        "text": FACT,
                        "evidence": [{"source_id": source["id"], "quote": FACT}],
                    }
                ],
                unanswered_aspects=[],
            )
        if issubclass(response_model, ProjectQuestionLLMAnswer):
            if self.intent != "project_question":
                return response_model(answer="Помогаю с вопросами по выбранному проекту.")
            self.assert_source_in_prompt(kwargs["user_prompt"])
            # Берём разрешённый id из фактической схемы, как это делает provider.
            field = response_model.model_json_schema()["properties"]["evidence_ids"]["items"]
            allowed = field.get("enum", [field.get("const")])
            source_id = next(
                identifier
                for identifier in allowed
                if str(identifier).startswith("search_project_evidence:")
            )
            return response_model.model_validate(
                {
                    "answer": FACT,
                    "evidence_ids": ["fabricated-source" if self.fabricated else source_id],
                },
                strict=True,
            )
        raise AssertionError(response_model)

    @staticmethod
    def assert_source_in_prompt(prompt):
        if FACT not in prompt:
            raise AssertionError("Ответ модели должен получать исходный факт")


def project_tools(reads, *, no_sources=False):
    tools = []
    for name in ("get_project_summary", "get_problem_context", "search_project_evidence"):
        schema = EvidenceSearchArgs if name == "search_project_evidence" else NoArgs

        async def read(_name=name, **kwargs):
            reads.append(_name)
            return {"items": [{"id": "doc-1", "title": "План", "text": FACT}]}

        async def empty(_name=name, **kwargs):
            reads.append(_name)
            return "", None

        if no_sources:
            tool = StructuredTool.from_function(
                name=name,
                description="Тестовое чтение",
                args_schema=schema,
                coroutine=empty,
                response_format="content_and_artifact",
            )
        else:
            tool = make_tool(
                name=name, description="Тестовое чтение", args_schema=schema, func=read
            )
        tools.append(tool)
    return tools


class VerificationModeTests(unittest.IsolatedAsyncioTestCase):
    async def run_graph(
        self,
        *,
        verify_claims=None,
        intent="project_question",
        fabricated=False,
        no_sources=False,
        max_tool_rounds=1,
    ):
        llm, reads = ModeLLM(intent=intent, fabricated=fabricated), []
        options = {} if verify_claims is None else {"verify_claims": verify_claims}
        graph = build_project_question_graph(
            llm=llm,
            tools=project_tools(reads, no_sources=no_sources),
            temperature=0,
            max_tool_rounds=max_tool_rounds,
            **options,
        )
        state = {
            "project_id": "P007",
            "as_of": "2026-06-19",
            "question": "Каков план?",
            "messages": [HumanMessage(content="Каков план?")],
            "used_tools": [],
            "tool_sources": [],
            "tool_rounds": 0,
            "stream_response": False,
            **options,
        }
        events, result = [], None
        async for mode, value in graph.astream(state, stream_mode=["custom", "values"]):
            if mode == "custom":
                events.append(value)
            else:
                result = value
        return _answer_from_state(result), llm.calls, reads, events

    async def test_disabled_keeps_context_and_citations_without_verification_calls(self):
        answer, calls, reads, events = await self.run_graph(verify_claims=False)
        self.assertEqual(calls, ["RequestRoute", "GroundedProjectQuestionLLMAnswer"])
        self.assertCountEqual(
            reads, ["get_project_summary", "get_problem_context", "search_project_evidence"]
        )
        self.assertEqual(answer.answer, FACT)
        self.assertEqual(answer.claims, [])
        self.assertEqual(answer.verification.status, "not_checked")
        self.assertEqual(answer.verification.checked_claims, 0)
        self.assertEqual(answer.verification.supported_claims, 0)
        self.assertEqual([source.id for source in answer.evidence_sources], answer.evidence_ids)
        self.assertTrue(answer.evidence_ids)
        stages = {event["data"].get("stage") for event in events}
        self.assertTrue(stages.isdisjoint({"draft_answer", "verify_answer", "recover_evidence"}))

    async def test_disabled_mode_allows_another_tool_round_before_final_answer(self):
        answer, calls, reads, _ = await self.run_graph(verify_claims=False, max_tool_rounds=2)
        self.assertEqual(
            calls, ["RequestRoute", "chat_completion", "GroundedProjectQuestionLLMAnswer"]
        )
        self.assertEqual(reads.count("search_project_evidence"), 2)
        self.assertEqual(answer.verification.status, "not_checked")
        self.assertTrue(answer.evidence_sources)

    async def test_default_and_explicit_enabled_run_draft_and_claim_checks(self):
        for enabled in (None, True):
            with self.subTest(verify_claims=enabled):
                answer, calls, _, _ = await self.run_graph(verify_claims=enabled)
                self.assertIn("GroundedAnswerDraft", calls)
                self.assertIn("ClaimSupport", calls)
                self.assertIn("EvidenceReview", calls)
                self.assertNotIn("GroundedProjectQuestionLLMAnswer", calls)
                self.assertEqual(answer.verification.status, "passed")
                self.assertEqual(len(answer.claims), 1)

    async def test_disabled_still_rejects_fabricated_source_identifiers(self):
        with self.assertRaises(ValidationError):
            await self.run_graph(verify_claims=False, fabricated=True)

    async def test_disabled_without_sources_never_generates_project_facts(self):
        answer, calls, reads, _ = await self.run_graph(verify_claims=False, no_sources=True)
        self.assertEqual(calls, ["RequestRoute"])
        self.assertEqual(len(reads), 3)
        self.assertEqual(answer.answer, PROJECT_DATA_UNAVAILABLE_ANSWER)
        self.assertEqual(answer.evidence_ids, [])
        self.assertEqual(answer.claims, [])

    async def test_nonproject_routes_do_not_load_or_publish_project_facts(self):
        for intent in ("small_talk", "out_of_scope"):
            with self.subTest(intent=intent):
                answer, calls, reads, _ = await self.run_graph(verify_claims=False, intent=intent)
                self.assertEqual(calls, ["RequestRoute", "ProjectQuestionLLMAnswer"])
                self.assertEqual(reads, [])
                self.assertNotIn(FACT, answer.answer)
                self.assertEqual(answer.evidence_sources, [])
                self.assertEqual(answer.claims, [])
                self.assertIsNone(answer.verification)

    async def test_facade_forwards_disabled_mode_for_answer_and_stream(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                llm, reads = ModeLLM(), []
                with (
                    patch("sdm.agents.project_qa.agent.ProjectFactToolExecutor"),
                    patch("sdm.agents.project_qa.agent.ProjectEvidenceExecutor"),
                    patch(
                        "sdm.agents.project_qa.agent.build_project_tools",
                        return_value=project_tools(reads),
                    ),
                ):
                    agent = ProjectQuestionAgent(llm=llm, max_tool_rounds=1)
                    if streaming:
                        events = [
                            event
                            async for event in agent.answer_stream(
                                project_id="P007",
                                question="Каков план?",
                                verify_claims=False,
                            )
                        ]
                        answer = events[-1]["data"]["answer"]
                    else:
                        answer = (
                            await agent.answer(
                                project_id="P007",
                                question="Каков план?",
                                verify_claims=False,
                            )
                        ).model_dump()
                self.assertEqual(answer["verification"]["status"], "not_checked")
                self.assertEqual(llm.calls, ["RequestRoute", "GroundedProjectQuestionLLMAnswer"])
