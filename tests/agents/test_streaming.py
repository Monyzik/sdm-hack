import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import openai
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from sdm.agents.api import create_app
from sdm.agents.llm import IncompleteOutputError, LLMSettings, OpenAICompatibleLLMAdapter
from sdm.agents.project_qa.nodes.tool_call import run_tools_node
from sdm.agents.project_qa.schemas import ProjectQuestionAnswer
from sdm.agents.project_qa.state import ProjectQuestionState
from sdm.agents.streaming import collect_stream_metrics
from sdm.agents.tools.registry import build_project_tools


def sse_events(response):
    events = []
    for frame in response.text.replace("\r\n", "\n").split("\n\n"):
        name = None
        data = []
        for line in frame.splitlines():
            if line.startswith("event:"):
                name = line.partition(":")[2].strip()
            elif line.startswith("data:"):
                data.append(line.partition(":")[2].lstrip())
        if data:
            events.append((name, json.loads("\n".join(data))))
    return events


class StreamingApiTests(unittest.TestCase):
    def setUp(self):
        adapter = patch("sdm.agents.project_qa.agent.get_llm_adapter", return_value=object())
        adapter.start()
        self.addCleanup(adapter.stop)
        self.client = TestClient(create_app())
        self.addCleanup(self.client.close)
        self.url = "/api/v1/agents/projects/P1/ask/stream"

    def test_validated_answer_is_last_event_and_unicode_survives(self):
        answer = ProjectQuestionAnswer(answer="Готово\nВторая строка", used_tools=[])

        async def stream(state, **kwargs):
            yield {
                "type": "values",
                "data": {
                    **state,
                    "final_content": answer.model_dump_json(exclude={"evidence_sources"}),
                    "request_intent": "small_talk",
                },
            }

        with patch(
            "sdm.agents.project_qa.agent.ProjectQuestionAgent._graph",
            return_value=SimpleNamespace(astream=stream),
        ) as run:
            response = self.client.post(self.url, json={"question": "Статус?"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        events = sse_events(response)
        self.assertEqual(events[0][0], "run_started")
        self.assertEqual(events[-1][0], "final")
        self.assertNotIn("error", [name for name, _ in events])
        self.assertIn("Готово", json.dumps(events[-1][1], ensure_ascii=False))
        self.assertEqual(run.call_args.args[0]["project_id"], "P1")
        self.assertEqual(run.call_args.args[0]["question"], "Статус?")

    def test_service_failure_is_terminal_and_does_not_expose_details(self):
        with patch(
            "sdm.agents.project_qa.agent.ProjectQuestionAgent._graph",
            side_effect=RuntimeError("secret-key-123 https://private.internal"),
        ):
            response = self.client.post(self.url, json={"question": "Status?"})
        self.assertEqual(response.status_code, 200)
        events = sse_events(response)
        self.assertEqual(events[-1][0], "error")
        self.assertNotIn("final", [name for name, _ in events])
        self.assertNotIn("secret-key-123", response.text)
        self.assertNotIn("private.internal", response.text)

    def test_deadline_cancels_incomplete_graph_without_publishing_a_draft(self):
        cancelled = []

        async def stream(state, **kwargs):
            self.assertIn("request_deadline", state)
            try:
                yield {"type": "values", "data": {**state, "final_content": "UNVERIFIED"}}
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        with (
            patch("sdm.agents.project_qa.agent.request_budget_seconds", return_value=0.05),
            patch(
                "sdm.agents.project_qa.agent.ProjectQuestionAgent._graph",
                return_value=SimpleNamespace(astream=stream),
            ),
        ):
            response = self.client.post(self.url, json={"question": "Статус?"})
        self.assertEqual(cancelled, [True])
        events = sse_events(response)
        self.assertEqual([name for name, _ in events], ["run_started", "error"])
        self.assertIn("лимит времени", events[-1][1]["message"])
        self.assertNotIn("UNVERIFIED", response.text)

    def test_invalid_result_is_never_published_as_final(self):
        async def stream(state, **kwargs):
            yield {
                "type": "values",
                "data": {
                    **state,
                    "final_content": '{"answer":{"private":"invalid-result"}}',
                    "request_intent": "small_talk",
                },
            }

        with patch(
            "sdm.agents.project_qa.agent.ProjectQuestionAgent._graph",
            return_value=SimpleNamespace(astream=stream),
        ):
            response = self.client.post(self.url, json={"question": "Status?"})
        events = sse_events(response)
        self.assertEqual(events[-1][0], "error")
        self.assertNotIn("final", [name for name, _ in events])
        self.assertNotIn("invalid-result", response.text)

    def test_invalid_request_is_rejected_before_streaming(self):
        with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as run:
            response = self.client.post(self.url, json={"question": ""})
        self.assertEqual(response.status_code, 422)
        run.assert_not_called()


class ToolStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_can_run_without_langgraph_runtime(self):
        executor = AsyncMock()
        executor.search_tasks.return_value = {"items": [{"id": "T1", "title": "Проверить план"}]}
        tool = next(
            tool for tool in build_project_tools(executor, executor) if tool.name == "search_tasks"
        )
        # LangChain передаёт контекст вызова, но в нём нет потока графа.
        with patch("sdm.agents.streaming.get_stream_writer", side_effect=KeyError):
            result = await tool.ainvoke(
                {"type": "tool_call", "id": "standalone", "name": "search_tasks", "args": {}}
            )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.artifact["items"][0]["id"], "T1")
        executor.search_tasks.assert_awaited_once()

    async def test_tool_events_are_paired_and_do_not_contain_raw_result(self):
        executor = AsyncMock()
        executor.search_tasks.return_value = {
            "items": [{"id": "T1", "title": "sensitive-tool-result"}]
        }
        tools = build_project_tools(executor, executor)
        events = []
        state = {
            "messages": [
                AIMessage(
                    content="", tool_calls=[{"id": "call-1", "name": "search_tasks", "args": {}}]
                )
            ],
            "used_tools": [],
            "tool_sources": [],
            "tool_rounds": 0,
        }
        builder = StateGraph(ProjectQuestionState)
        builder.add_node("tools", run_tools_node(tools))
        builder.add_edge(START, "tools")
        builder.add_edge("tools", END)
        with patch("sdm.agents.streaming.get_stream_writer", return_value=events.append):
            result = await builder.compile().ainvoke(state)
        self.assertEqual(result["messages"][-1].tool_call_id, "call-1")
        starts = [event["data"] for event in events if event["event"] == "tool_started"]
        finishes = [event["data"] for event in events if event["event"] == "tool_finished"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(finishes), 1)
        self.assertEqual(starts[0]["call_id"], finishes[0]["call_id"])
        self.assertEqual(finishes[0]["status"], "success")
        self.assertNotIn("sensitive-tool-result", json.dumps(events))


def chunk(delta=None, *, finish_reason=None, usage=None):
    return {
        "id": "chat-stream-test",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "test-model",
        "choices": []
        if delta is None
        else [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        "usage": usage,
    }


class AdapterStreamingTests(unittest.IsolatedAsyncioTestCase):
    def adapter(self, chunks, *, expose_reasoning=False):
        wire = "".join("data: " + json.dumps(item) + "\n\n" for item in chunks)
        wire += "data: [DONE]\n\n"
        requests = []

        def handle(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=wire)

        transport = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        client = openai.AsyncOpenAI(
            api_key="offline-test-secret",
            base_url="https://llm.invalid/v1",
            http_client=transport,
            max_retries=0,
        )
        adapter = OpenAICompatibleLLMAdapter(
            LLMSettings(
                api_key="offline-test-secret",
                base_url="https://llm.invalid/v1",
                model="test-model",
                expose_reasoning=expose_reasoning,
            )
        )
        factory = patch.object(adapter, "_client", return_value=client)
        factory.start()
        self.addCleanup(factory.stop)
        self.addAsyncCleanup(transport.aclose)
        return adapter, requests, transport

    async def test_fragmented_tool_call_reassembled_and_usage_only_chunk_counted(self):
        adapter, requests, transport = self.adapter(
            [
                chunk({"reasoning_content": "private-reasoning"}),
                chunk(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "lookup", "arguments": '{"id":'},
                            }
                        ]
                    }
                ),
                chunk(
                    {"tool_calls": [{"index": 0, "function": {"arguments": '"T1"}'}}]},
                    finish_reason="tool_calls",
                ),
                chunk(usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            ]
        )
        events = []
        with patch("sdm.agents.streaming.get_stream_writer", return_value=events.append):
            response = await adapter.chat_completion(
                messages=[{"role": "user", "content": "Find facts"}],
                temperature=0,
                stream=True,
            )
        call = response.choices[0].message.tool_calls[0]
        self.assertEqual(call.id, "call-1")
        self.assertEqual(call.function.name, "lookup")
        self.assertEqual(json.loads(call.function.arguments), {"id": "T1"})
        progress = [event for event in events if event["event"] == "llm_progress"]
        self.assertTrue(progress)
        self.assertGreater(progress[0]["data"]["received_characters"], 0)
        event_names = [event["event"] for event in events]
        self.assertLess(event_names.index("llm_progress"), event_names.index("llm_finished"))
        self.assertNotIn("private-reasoning", json.dumps(progress))
        self.assertNotIn("T1", json.dumps(progress))
        self.assertEqual(response.usage.total_tokens, 15)
        self.assertTrue(requests[0]["stream"])
        self.assertTrue(transport.is_closed)
        self.assertNotIn("private-reasoning", json.dumps(events))
        finish = next(event["data"] for event in events if event["event"] == "llm_finished")
        self.assertEqual(finish["usage"]["total_tokens"], 15)
        self.assertIsNotNone(finish["ttft_ms"])

    async def test_truncated_structured_stream_counts_usage_once_without_retry_or_raw_output(self):
        secret = "private-truncated-output"
        adapter, requests, transport = self.adapter(
            [
                chunk({"reasoning_content": "private-truncated-reasoning"}),
                chunk(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-result",
                                "type": "function",
                                "function": {
                                    "name": "submit_result",
                                    "arguments": '{"answer":"' + secret,
                                },
                            }
                        ]
                    }
                ),
                chunk({}, finish_reason="length"),
                chunk(usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            ]
        )
        events = []
        with (
            collect_stream_metrics() as metrics,
            patch("sdm.agents.streaming.get_stream_writer", return_value=events.append),
            self.assertRaises(IncompleteOutputError) as caught,
        ):
            await adapter.parse_pydantic(
                response_model=ProjectQuestionAnswer,
                system_prompt="Answer",
                user_prompt="Facts",
                temperature=0,
                stream=True,
            )
        self.assertEqual(caught.exception.reason, "length")
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn(secret, json.dumps(events))
        self.assertNotIn("private-truncated-reasoning", json.dumps(events))
        self.assertEqual(len(requests), 1)
        self.assertNotIn("llm_retry", [event["event"] for event in events])
        finishes = [event["data"] for event in events if event["event"] == "llm_finished"]
        self.assertEqual(len(finishes), 1)
        self.assertEqual(finishes[0]["status"], "incomplete")
        self.assertEqual(finishes[0]["finish_reason"], "length")
        self.assertIsNotNone(finishes[0]["ttft_ms"])
        self.assertEqual(
            metrics.snapshot()["usage"],
            {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        )
        self.assertTrue(transport.is_closed)

    async def test_reasoning_opt_in_and_unterminated_stream_rejected(self):
        adapter, _, transport = self.adapter(
            [
                chunk({"reasoning_content": "Проверяю факты"}),
                chunk({"content": "incomplete"}),
            ],
            expose_reasoning=True,
        )
        events = []
        with patch("sdm.agents.streaming.get_stream_writer", return_value=events.append):
            with self.assertRaises(ValueError):
                await adapter.chat_completion(
                    messages=[{"role": "user", "content": "Facts"}],
                    temperature=0,
                    stream=True,
                )
        self.assertTrue(transport.is_closed)
        reasoning = [
            event["data"]["text"] for event in events if event["event"] == "reasoning_delta"
        ]
        self.assertEqual(reasoning, ["Проверяю факты"])
        self.assertNotIn("llm_finished", [event["event"] for event in events])
