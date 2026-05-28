"""Проверки кеша базы и инструментов LangGraph без внешних сервисов."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from sdm.agents.tools.project.executor import ProjectFactToolExecutor
from sdm.agents.tools.registry import build_project_tools
from sdm.agents.tools.retrieval.executor import ProjectEvidenceExecutor


def executor(project_id="P001"):
    return ProjectFactToolExecutor(
        project_id=project_id, as_of="2026-06-19", max_depth=2, session_factory=AsyncMock()
    )


class ProjectFactCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_identical_concurrent_reads_are_coalesced(self):
        for method, loader in [
            ("project_summary", "_load_project_summary"),
            ("problem_context", "_load_problem_context"),
        ]:
            started, release = asyncio.Event(), asyncio.Event()

            async def load(*args):
                started.set()
                await release.wait()
                return {"project": {"id": "P001"}}

            facts = executor()
            mock = AsyncMock(side_effect=load)
            setattr(facts, loader, mock)
            pending = [asyncio.create_task(getattr(facts, method)()) for _ in range(5)]
            await asyncio.wait_for(started.wait(), 1)
            release.set()
            results = await asyncio.gather(*pending)
            self.assertTrue(all(value == results[0] for value in results))
            self.assertEqual(await getattr(facts, method)(), results[0])
            mock.assert_awaited_once()

    async def test_context_depths_load_independently(self):
        started = []
        both = asyncio.Event()

        async def load(depth):
            started.append(depth)
            if len(started) == 2:
                both.set()
            await asyncio.wait_for(both.wait(), 1)
            return {"depth": depth}

        facts = executor()
        facts._load_problem_context = AsyncMock(side_effect=load)
        self.assertEqual(
            await asyncio.gather(facts.problem_context(1), facts.problem_context(3)),
            [{"depth": 1}, {"depth": 3}],
        )
        self.assertEqual(await facts.problem_context(1), {"depth": 1})
        self.assertEqual(facts._load_problem_context.await_count, 2)

    async def test_failed_load_is_not_cached(self):
        for error in [RuntimeError("database unavailable"), ValueError("invalid data")]:
            facts = executor()
            facts._load_project_summary = AsyncMock(side_effect=[error, {"ok": True}])
            with self.assertRaises(type(error)):
                await facts.project_summary()
            self.assertEqual(await facts.project_summary(), {"ok": True})
            self.assertEqual(await facts.project_summary(), {"ok": True})
            self.assertEqual(facts._load_project_summary.await_count, 2)

    async def test_cancelled_load_releases_lock_and_waiter_retries(self):
        started = asyncio.Event()
        calls = 0

        async def load():
            nonlocal calls
            calls += 1
            if calls == 1:
                started.set()
                await asyncio.Event().wait()
            return {"ok": True}

        facts = executor()
        facts._load_project_summary = AsyncMock(side_effect=load)
        cancelled = asyncio.create_task(facts.project_summary())
        await asyncio.wait_for(started.wait(), 1)
        waiter = asyncio.create_task(facts.project_summary())
        cancelled.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await cancelled
        self.assertEqual(await asyncio.wait_for(waiter, 1), {"ok": True})
        self.assertEqual(await facts.project_summary(), {"ok": True})
        self.assertEqual(calls, 2)

    async def test_executors_have_request_scoped_caches(self):
        instances = [executor(), executor(), executor("P002")]
        for index, facts in enumerate(instances):
            facts._load_project_summary = AsyncMock(
                return_value={"request": index, "project_id": facts.project_id}
            )
        results = await asyncio.gather(*(facts.project_summary() for facts in instances))
        self.assertEqual(len({result["request"] for result in results}), 3)
        self.assertEqual(results[2]["project_id"], "P002")
        for facts in instances:
            await facts.project_summary()
            facts._load_project_summary.assert_awaited_once()


class ProjectFactToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_toolnode_returns_matching_json_and_artifact_and_validates_arguments(self):
        facts = executor()
        facts._load_project_summary = AsyncMock(
            return_value={"blocked_tasks": [{"id": "T001", "title": "Проверить план"}]}
        )
        node = ToolNode(build_project_tools(facts, AsyncMock(spec=ProjectEvidenceExecutor)))
        builder = StateGraph(MessagesState)
        builder.add_node("tools", node)
        builder.add_edge(START, "tools")
        builder.add_edge("tools", END)
        result = await builder.compile().ainvoke(
            {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "get_project_summary", "args": {}, "id": "summary"},
                            {
                                "name": "get_problem_context",
                                "args": {"max_depth": 99},
                                "id": "invalid-depth",
                            },
                            {
                                "name": "calculate_delay_cost",
                                "args": {},
                                "id": "missing-required-argument",
                            },
                        ],
                    )
                ]
            }
        )
        messages = {
            message.tool_call_id: message
            for message in result["messages"]
            if isinstance(message, ToolMessage)
        }
        success = messages["summary"]
        self.assertIsInstance(success, ToolMessage)
        self.assertEqual(success.status, "success")
        self.assertIsInstance(success.artifact, dict)
        self.assertEqual(json.loads(success.content), success.artifact)
        self.assertEqual(success.artifact["blocked_tasks"][0]["id"], "T001")
        for call_id in ("invalid-depth", "missing-required-argument"):
            self.assertEqual(messages[call_id].status, "error")
            self.assertIsNone(messages[call_id].artifact)
        facts._load_project_summary.assert_awaited_once()
