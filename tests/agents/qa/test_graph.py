"""Проверки маршрутов, лимитов инструментов и истории сообщений без сети."""

from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sdm.agents.project_qa.agent import ProjectQuestionAgent
from sdm.agents.project_qa.evidence.models import AnswerDraft, ClaimSupport, EvidenceReview
from sdm.agents.project_qa.graph import build_project_question_graph
from sdm.agents.project_qa.messages import _parse_tool_arguments
from sdm.agents.project_qa.nodes.tool_call import _tool_sources_from_messages, run_tools_node
from sdm.agents.project_qa.schemas import ProjectQuestionLLMAnswer, RequestRoute
from sdm.agents.tools.registry import build_project_tools


class FakeExecutor:
    max_depth = 2

    async def calculate_delay_cost(self, delay_days, daily_cost=None, resource_count=None):
        raise AssertionError("Расчёт стоимости не нужен в этом сценарии")

    def __init__(self):
        self.calls = []

    async def project_summary(self):
        self.calls.append("get_project_summary")
        return {"project_id": "P001", "blocked_tasks": [{"id": "T001", "title": "Проверить план"}]}

    async def problem_context(self, *, max_depth):
        self.calls.append("get_problem_context")
        assert max_depth is None or max_depth == self.max_depth
        return {"project": {"id": "P001", "name": "План"}, "problem_tasks": [{"id": "T001"}]}

    async def search_project_evidence(self, arguments):
        self.calls.append("search_project_evidence")
        assert arguments["query"] == "Какие задачи?"
        return {
            "items": [{"id": "EV001", "entity_id": "T001", "text": "Подтверждение из документа"}]
        }

    async def search_tasks(self, arguments):
        self.calls.append("search_tasks")
        return {"items": [{"id": "T001", "title": "Проверить план"}]}


class FakeLLM:
    def __init__(self, *, intent="project_question", keep_calling=True):
        self.route = RequestRoute(intent=intent)
        self.keep_calling = keep_calling
        self.chat_requests = []
        self.final_prompts = []
        self.review_prompts = []

    async def parse_pydantic(self, *, response_model, **kwargs):
        if response_model is ClaimSupport:
            return ClaimSupport(
                entailed=True,
                all_numbers_supported=True,
                status_and_modality_supported=True,
                contradicted=False,
            )
        if response_model is RequestRoute:
            return self.route
        if response_model is EvidenceReview:
            self.review_prompts.append(kwargs["user_prompt"])
            return EvidenceReview(
                claims=[{"claim_index": 0, "verdict": "supported"}],
                missing_aspects=[],
                searches=[],
                context_source_ids=[],
            )
        self.final_prompts.append(kwargs["user_prompt"])
        if issubclass(response_model, AnswerDraft):
            sources = prompt_payload(kwargs["user_prompt"])["evidence_sources"]
            source = next(s for s in sources if s["data"].get("title") == "Проверить план")
            return response_model(
                claims=[
                    {
                        "text": "Задача T001: Проверить план.",
                        "evidence": [{"source_id": source["id"], "quote": "Проверить план"}],
                    }
                ],
                unanswered_aspects=[],
            )
        return ProjectQuestionLLMAnswer(answer="Готово", evidence_ids=["T001", "INVENTED"])

    async def chat_completion(self, **kwargs):
        self.chat_requests.append(kwargs)
        call_id = f"call-{len(self.chat_requests)}"
        tool_calls = []
        if self.keep_calling:
            tool_calls.append(
                SimpleNamespace(
                    id=call_id,
                    function=SimpleNamespace(name="search_tasks", arguments="{}"),
                )
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="" if tool_calls else "Данных достаточно для ответа.",
                        tool_calls=tool_calls,
                    )
                )
            ]
        )


def prompt_payload(text):
    return json.loads(text.split("<untrusted_data>")[1].split("</untrusted_data>")[0])["data"]


def initial_state():
    return {
        "project_id": "P001",
        "question": "Какие задачи?",
        "as_of": "2026-06-19",
        "messages": [HumanMessage(content="Какие задачи?", id="question-1")],
        "used_tools": [],
        "tool_sources": [],
        "tool_rounds": 0,
    }


class ProjectQuestionGraphTests(unittest.IsolatedAsyncioTestCase):
    def graph(self, llm, rounds=3, executor=None):
        executor = executor if executor is not None else FakeExecutor()
        return build_project_question_graph(
            llm=llm,
            tools=build_project_tools(executor, executor),
            temperature=0,
            max_tool_rounds=rounds,
        )

    async def test_repeated_calls_stop_at_bound_with_paired_tool_results(self):
        for limit in (1, 3, 12):
            with self.subTest(limit=limit):
                llm = FakeLLM()
                state = initial_state()
                original = copy.deepcopy(state)
                result = await self.graph(llm, rounds=limit).ainvoke(state)
                self.assertEqual(state, original)
                self.assertEqual(result["tool_rounds"], limit)
                self.assertEqual(len(llm.chat_requests), limit - 1)
                self.assertEqual(len(llm.final_prompts), 1)
                self.assertEqual(len(llm.review_prompts), 1)
                self.assertEqual(
                    result["used_tools"],
                    ["get_project_summary", "get_problem_context", "search_project_evidence"]
                    + (["search_tasks"] if limit > 1 else []),
                )
                self.assertTrue(
                    any(source["data"].get("id") == "T001" for source in result["tool_sources"])
                )
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

    async def test_project_intent_reads_structured_and_document_context_at_round_limit_one(self):
        llm = FakeLLM()
        executor = FakeExecutor()
        result = await self.graph(llm, rounds=1, executor=executor).ainvoke(initial_state())
        self.assertEqual(result["request_intent"], "project_question")
        self.assertEqual(llm.chat_requests, [])
        self.assertCountEqual(
            executor.calls,
            ["get_project_summary", "get_problem_context", "search_project_evidence"],
        )
        self.assertEqual(
            result["used_tools"],
            ["get_project_summary", "get_problem_context", "search_project_evidence"],
        )
        preloaded = [
            message
            for message in result["messages"]
            if message.id and message.id.startswith("preloaded:")
        ]
        self.assertEqual(
            [prompt_payload(message.content)["args"] for message in preloaded],
            [{}, {}, {"query": initial_state()["question"]}],
        )
        self.assertEqual(len({message.id for message in preloaded}), 3)
        self.assertEqual(len(llm.review_prompts), 1)

    async def test_nonproject_intents_skip_all_executor_reads(self):
        for intent in ("small_talk", "out_of_scope"):
            with self.subTest(intent=intent):
                llm = FakeLLM(intent=intent)
                executor = FakeExecutor()
                result = await self.graph(llm, executor=executor).ainvoke(initial_state())
                self.assertEqual(result["request_intent"], intent)
                self.assertEqual(result["used_tools"], [])
                self.assertEqual(executor.calls, [])
                self.assertEqual(llm.chat_requests, [])
                self.assertEqual(len(llm.final_prompts), 1)

    async def test_model_never_requests_tools_but_receives_facts_before_answering(self):
        llm = FakeLLM(keep_calling=False)
        executor = FakeExecutor()
        result = await self.graph(llm, executor=executor).ainvoke(initial_state())
        self.assertEqual(result["tool_rounds"], 1)
        self.assertEqual(len(llm.chat_requests), 1)
        request = llm.chat_requests[0]
        self.assertEqual(request["tool_choice"], "auto")
        results = [
            prompt_payload(message["content"])
            for message in request["messages"]
            if "preloaded_tool_result" in message.get("content", "")
        ]
        self.assertCountEqual(
            [message["tool"] for message in results],
            ["get_project_summary", "get_problem_context", "search_project_evidence"],
        )
        self.assertTrue(all("T001" in json.dumps(message["result"]) for message in results))
        self.assertEqual(len(llm.final_prompts), 1)
        self.assertIn("T001", llm.final_prompts[0])
        self.assertEqual(
            sum(isinstance(message, HumanMessage) for message in result["messages"]), 4
        )
        self.assertCountEqual(
            executor.calls,
            ["get_project_summary", "get_problem_context", "search_project_evidence"],
        )

    async def test_base_read_failure_never_reaches_model_or_final_generation(self):
        llm = FakeLLM(keep_calling=False)
        executor = FakeExecutor()
        executor.project_summary = AsyncMock(side_effect=RuntimeError("backend unavailable"))
        executor.problem_context = AsyncMock(side_effect=RuntimeError("backend unavailable"))
        with self.assertRaisesRegex(RuntimeError, "backend unavailable"):
            await self.graph(llm, executor=executor).ainvoke(initial_state())
        self.assertEqual(llm.chat_requests, [])
        self.assertEqual(llm.final_prompts, [])

    async def test_model_failure_propagates_without_retry_or_finalization(self):
        llm = FakeLLM()
        error = ValueError("Model refused")
        llm.chat_completion = AsyncMock(side_effect=error)
        with self.assertRaises(ValueError) as caught:
            await self.graph(llm).ainvoke(initial_state())
        self.assertIs(caught.exception, error)
        llm.chat_completion.assert_awaited_once()
        self.assertEqual(llm.final_prompts, [])

    async def test_mandatory_retrieval_failure_never_finalizes_without_document_read(self):
        llm = FakeLLM(keep_calling=False)
        executor = FakeExecutor()
        executor.search_project_evidence = AsyncMock(
            side_effect=RuntimeError("retrieval unavailable")
        )
        with self.assertRaisesRegex(RuntimeError, "retrieval unavailable"):
            await self.graph(llm, rounds=1, executor=executor).ainvoke(initial_state())
        executor.search_project_evidence.assert_awaited_once()
        self.assertEqual(llm.chat_requests, [])
        self.assertEqual(llm.final_prompts, [])

    async def test_tool_node_receives_config_and_returns_updates_without_mutation(self):
        state = initial_state()
        original = copy.deepcopy(state)
        config = {"tags": ["regression"], "configurable": {"request_id": "test"}}
        tool_message = ToolMessage(content="{}", name="search_tasks", tool_call_id="call-1")
        with patch("sdm.agents.project_qa.nodes.tool_call.ToolNode") as tool_node:
            tool_node.return_value.ainvoke = AsyncMock(return_value={"messages": [tool_message]})
            update = await run_tools_node([])(state, config)
            tool_node.return_value.ainvoke.assert_awaited_once_with(state, config=config)
        self.assertEqual(state, original)
        self.assertEqual(update["tool_rounds"], 1)
        self.assertEqual(update["messages"], [tool_message])

    def test_artifact_is_authoritative_for_evidence(self):
        message = ToolMessage(
            name="search_tasks",
            tool_call_id="call-1",
            content='{"items": [{"id": "WRONG"}]}',
            artifact={"items": [{"id": "T001", "title": "Проверить план"}]},
        )
        self.assertEqual(
            [source["data"]["id"] for source in _tool_sources_from_messages([message])], ["T001"]
        )

    async def test_public_agent_uses_injected_model_and_executor(self):
        llm = FakeLLM()
        executor = FakeExecutor()
        with (
            patch(
                "sdm.agents.project_qa.agent.ProjectFactToolExecutor", return_value=executor
            ) as executor_class,
            patch(
                "sdm.agents.project_qa.agent.ProjectEvidenceExecutor", return_value=executor
            ) as evidence_class,
        ):
            agent = ProjectQuestionAgent(llm=llm, max_tool_rounds=1)
            answer = await agent.answer(
                project_id="P001", question="Какие задачи?", as_of=None, max_depth=2
            )
            self.assertEqual(executor_class.call_args.kwargs["project_id"], "P001")
            self.assertEqual(evidence_class.call_args.kwargs["project_id"], "P001")
            self.assertEqual(evidence_class.call_args.kwargs["llm"], llm)
        self.assertEqual(answer.answer, "Задача T001: Проверить план.")
        self.assertEqual(
            answer.used_tools,
            ["get_project_summary", "get_problem_context", "search_project_evidence"],
        )
        self.assertEqual(len(answer.evidence_ids), 1)
        self.assertEqual(answer.verification.status, "passed")
        self.assertEqual(answer.claims[0].evidence_ids, answer.evidence_ids)
        self.assertTrue(answer.evidence_sources)
        self.assertEqual(len(llm.chat_requests), 0)

    async def test_invalid_model_arguments_fail_before_requested_tool_execution(self):
        for arguments in ('{"query":', "[]", '"query"', "1", "null", "", None):
            with self.subTest(arguments=arguments):
                llm = FakeLLM()
                llm.chat_completion = AsyncMock(
                    return_value=SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(
                                    content="",
                                    tool_calls=[
                                        SimpleNamespace(
                                            id="bad-call",
                                            function=SimpleNamespace(
                                                name="search_tasks",
                                                arguments=arguments,
                                            ),
                                        ),
                                    ],
                                )
                            ),
                        ]
                    )
                )
                with patch.object(FakeExecutor, "search_tasks", new_callable=AsyncMock) as search:
                    with self.assertRaisesRegex(ValueError, "Tool-call arguments"):
                        await self.graph(llm).ainvoke(initial_state())
                    search.assert_not_awaited()
                self.assertEqual(llm.final_prompts, [])

    def test_empty_object_is_a_valid_tool_argument(self):
        self.assertEqual(_parse_tool_arguments("{}"), {})
        self.assertEqual(_parse_tool_arguments({}), {})

    async def test_failed_tool_attempt_is_recorded_without_creating_evidence(self):
        error_message = ToolMessage(
            name="search_tasks",
            tool_call_id="bad-call",
            status="error",
            content='{"items": [{"id": "WRONG"}]}',
            artifact={"items": [{"id": "WRONG"}]},
        )
        with patch("sdm.agents.project_qa.nodes.tool_call.ToolNode") as tool_node:
            tool_node.return_value.ainvoke = AsyncMock(return_value={"messages": [error_message]})
            update = await run_tools_node([])(initial_state(), {})
        self.assertEqual(update["used_tools"], ["search_tasks"])
        self.assertEqual(update["tool_sources"], [])
        self.assertEqual(update["messages"], [error_message])

    def test_round_limit_must_allow_at_least_one_tool_round(self):
        for limit in (0, -1):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.graph(FakeLLM(), rounds=limit)


if __name__ == "__main__":
    unittest.main()
