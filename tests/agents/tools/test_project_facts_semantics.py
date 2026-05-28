"""Проверки всех инструментов через LangGraph на подготовленных данных."""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from sdm.agents.tools.project.executor import ProjectFactToolExecutor
from sdm.agents.tools.registry import build_project_tools
from sdm.agents.tools.retrieval.executor import ProjectEvidenceExecutor
from sdm.agents.tools.sources import collect_tool_sources, select_answer_sources


def make_executor():
    return ProjectFactToolExecutor(
        project_id="P001",
        as_of="2026-06-19",
        max_depth=2,
        session_factory=AsyncMock(),
    )


async def run_tools(executor, evidence_executor, calls):
    graph = StateGraph(MessagesState)
    graph.add_node("tools", ToolNode(build_project_tools(executor, evidence_executor)))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    result = await graph.compile().ainvoke(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": name, "args": args, "id": str(index)}
                        for index, (name, args) in enumerate(calls)
                    ],
                )
            ]
        }
    )
    return [message for message in result["messages"] if isinstance(message, ToolMessage)]


class ToolContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_tools_return_json_artifacts(self):
        task = {
            "id": "T001",
            "title": "critical path discussion",
            "status": "blocked",
            "priority": "high",
        }
        context = {
            "project": {"id": "P001", "status": "active"},
            "budget": {"cost_of_delay_per_day": 100, "currency": "RUB"},
            "problem_tasks": [task],
            "linked_risks": [{"id": "RK001", "score": 10, "status": "open"}],
            "linked_communications": [{"id": "C001", "topic": "Review"}],
            "pending_decisions": [{"id": "DEC001", "description": "Approve"}],
            "linked_project_dependencies": [{"id": "D001", "depends_on": "Other project"}],
            "project_resources": [{"resource_id": "R001", "daily_project_cost": 20}],
            "task_dependency_graph": [
                {"id": "E001", "task_id": "T001", "depends_on_task_id": "T002"}
            ],
        }
        summary = {"project_id": "P001", "budget": context["budget"], "blocked_tasks": [task]}

        facts = make_executor()
        evidence_executor = AsyncMock(spec=ProjectEvidenceExecutor)
        facts._load_project_summary = AsyncMock(return_value=summary)
        facts._load_problem_context = AsyncMock(return_value=context)
        evidence_executor.search_project_evidence = AsyncMock(
            return_value={
                "query": "discussion",
                "count": 1,
                "items": [{"id": "EV001", "entity_id": "T001", "text": "critical path discussion"}],
            }
        )
        evidence_executor.get_evidence_context = AsyncMock(
            return_value={
                "status": "found",
                "items": [{"id": "EV001", "text": "critical path discussion"}],
            }
        )
        tools = build_project_tools(facts, evidence_executor)
        self.assertEqual(len(tools), 14)
        calls = [
            (
                tool.name,
                {"delay_days": 2}
                if tool.name == "calculate_delay_cost"
                else {"query": "discussion"}
                if tool.name == "search_project_evidence"
                else {"evidence_id": "EV001"}
                if tool.name == "get_evidence_context"
                else {},
            )
            for tool in tools
        ]
        messages = await run_tools(facts, evidence_executor, calls)
        self.assertEqual(len(messages), 14)
        for message in messages:
            with self.subTest(tool=message.name):
                self.assertEqual(message.status, "success")
                self.assertEqual(json.loads(message.content), message.artifact)
        results = {message.name: message.artifact for message in messages}
        self.assertEqual(results["calculate_delay_cost"]["total_cost"], 240)
        self.assertTrue(results["calculate_delay_cost"]["is_complete"])
        self.assertEqual(results["search_tasks"]["items"][0]["status"], "blocked")
        self.assertEqual(results["search_tasks"]["items"][0]["title"], "critical path discussion")

    async def test_unsupported_aliases_and_unknown_arguments_never_execute(self):
        facts = make_executor()
        evidence_executor = AsyncMock(spec=ProjectEvidenceExecutor)
        facts._load_project_summary = AsyncMock(
            side_effect=AssertionError("must not execute DB read")
        )
        facts._load_problem_context = AsyncMock(
            side_effect=AssertionError("must not execute DB read")
        )
        evidence_executor.search_project_evidence = AsyncMock(
            side_effect=AssertionError("must not execute retrieval")
        )
        calls = [
            (tool.name, {"unsupported_filter": "value"})
            for tool in build_project_tools(facts, evidence_executor)
        ]
        calls += [
            ("search_tasks", args)
            for args in (
                {"status_in": ["open"]},
                {"status_in": ["open", "blocked"]},
                {"status": "open", "status_in": ["blocked"]},
                {"status": ["open", "blocked"]},
                {"query": "   "},
                {"status": ""},
                {"limit": 0},
            )
        ]
        calls += [("search_project_evidence", {"query": "x", "entity_id": " "})]
        messages = await run_tools(facts, evidence_executor, calls)
        self.assertTrue(all(message.status == "error" for message in messages))
        facts._load_project_summary.assert_not_awaited()
        facts._load_problem_context.assert_not_awaited()
        evidence_executor.search_project_evidence.assert_not_awaited()

    async def test_exact_filters_do_not_match_substrings_and_names_still_do(self):
        facts = make_executor()
        evidence_executor = AsyncMock(spec=ProjectEvidenceExecutor)
        facts.project_summary = AsyncMock(return_value={})
        facts.problem_context = AsyncMock(
            return_value={
                "problem_tasks": [
                    {
                        "id": "T1",
                        "status": "open",
                        "priority": "high",
                        "assignee_name": "Иван Петров",
                    },
                    {
                        "id": "T2",
                        "status": "reopened",
                        "priority": "high",
                        "assignee_name": "Иван Петров",
                    },
                    {
                        "id": "T3",
                        "status": "open",
                        "priority": "high",
                        "assignee_name": "Анна Иванова",
                    },
                ]
            }
        )
        messages = await run_tools(
            facts,
            evidence_executor,
            [
                ("search_tasks", {"status": " OPEN ", "assignee": "Петров"}),
                ("search_tasks", {"query": "T2"}),
            ],
        )
        self.assertEqual([item["id"] for item in messages[0].artifact["items"]], ["T1"])
        self.assertEqual([item["id"] for item in messages[1].artifact["items"]], ["T2"])

    async def test_unknown_risk_score_does_not_pass_a_numeric_filter(self):
        facts = make_executor()
        evidence_executor = AsyncMock(spec=ProjectEvidenceExecutor)
        facts.project_summary = AsyncMock(return_value={})
        facts.problem_context = AsyncMock(
            return_value={
                "linked_risks": [
                    {"id": "UNKNOWN"},
                    {"id": "ZERO", "score": 0},
                    {"id": "HIGH", "score": 20},
                ]
            }
        )
        messages = await run_tools(facts, evidence_executor, [("search_risks", {"min_score": 0})])
        self.assertEqual([item["id"] for item in messages[0].artifact["items"]], ["ZERO", "HIGH"])

    async def test_limit_twenty_is_honored_and_snapshot_counts_describe_truncation(self):
        facts = make_executor()
        evidence_executor = AsyncMock(spec=ProjectEvidenceExecutor)
        tasks = [{"id": f"T{i}", "status": "open"} for i in range(25)]
        facts.project_summary = AsyncMock(return_value={"blocked_tasks": tasks})
        facts.problem_context = AsyncMock(return_value={"problem_tasks": tasks})
        evidence_executor.search_project_evidence = AsyncMock(
            return_value={"count": 20, "items": tasks[:20]}
        )
        search, evidence, summary = await run_tools(
            facts,
            evidence_executor,
            [
                ("search_tasks", {"limit": 20}),
                ("search_project_evidence", {"query": "x", "limit": 20}),
                ("get_project_summary", {}),
            ],
        )
        self.assertEqual(search.artifact["returned_count"], 20)
        self.assertEqual(search.artifact["count"], 25)
        self.assertTrue(search.artifact["truncated"])
        self.assertEqual(search.artifact["scope"], "problem_snapshot")
        self.assertEqual(evidence.artifact["returned_count"], 20)
        self.assertFalse(evidence.artifact["truncated"])
        self.assertEqual(
            summary.artifact["collections"]["blocked_tasks"],
            {"count": 25, "returned_count": 6, "truncated": True},
        )

    async def test_retrieval_preserves_qualifications_at_the_end_of_document_chunks(self):
        facts = make_executor()
        evidence_executor = AsyncMock(spec=ProjectEvidenceExecutor)
        text = "Контекст совещания. " * 40 + "Резерв 600 тысяч запрошен, но не утверждён."
        evidence_executor.search_project_evidence = AsyncMock(
            return_value={"count": 1, "items": [{"id": "doc:v1:c0001", "text": text}]}
        )
        (message,) = await run_tools(
            facts, evidence_executor, [("search_project_evidence", {"query": "резерв"})]
        )
        self.assertEqual(message.artifact["items"][0]["text"], text)
        self.assertIn("не утверждён", json.loads(message.content)["items"][0]["text"])

    async def test_retrieval_provenance_reaches_model_and_source_artifact(self):
        facts = make_executor()
        evidence_executor = AsyncMock(spec=ProjectEvidenceExecutor)
        scores = {"dense_rank": 2, "bm25_rank": 1, "fusion_score": 1 / 62 + 1 / 61}
        evidence_executor.search_project_evidence = AsyncMock(
            return_value={
                "ranking": "hybrid",
                "count": 1,
                "candidate_counts": {"dense": 40, "bm25": 22},
                "items": [
                    {"id": "doc:v1:c0001", "text": "Резерв не утверждён.", "retrieval": scores}
                ],
            }
        )
        (message,) = await run_tools(
            facts, evidence_executor, [("search_project_evidence", {"query": "резерв"})]
        )
        self.assertEqual(message.artifact["items"][0]["retrieval"], scores)
        payload = json.loads(message.content)
        self.assertEqual(payload["ranking"], "hybrid")
        self.assertEqual(payload["candidate_counts"], {"dense": 40, "bm25": 22})
        self.assertEqual(payload["items"][0]["retrieval"], scores)

    async def test_resource_and_dependency_lists_report_their_output_caps(self):
        facts = make_executor()
        evidence_executor = AsyncMock(spec=ProjectEvidenceExecutor)
        facts.problem_context = AsyncMock(
            return_value={
                "project_resources": [{"resource_id": f"R{i}"} for i in range(25)],
                "task_dependency_graph": [{"id": f"E{i}"} for i in range(70)],
            }
        )
        resources, edges = await run_tools(
            facts,
            evidence_executor,
            [
                ("get_resource_rates", {}),
                ("get_task_dependency_graph", {}),
            ],
        )
        for message, count, returned in ((resources, 25, 20), (edges, 70, 60)):
            self.assertEqual(message.artifact["count"], count)
            self.assertEqual(message.artifact["returned_count"], returned)
            self.assertEqual(len(message.artifact["items"]), returned)
            self.assertTrue(message.artifact["truncated"])

    async def test_delay_estimate_distinguishes_missing_values_from_explicit_zero(self):
        for context, include_burn, expected_total, expected_complete in (
            ({}, True, None, False),
            ({"budget": {"cost_of_delay_per_day": 100}}, True, None, False),
            (
                {"budget": {"cost_of_delay_per_day": 100}, "project_resources": [{}]},
                True,
                None,
                False,
            ),
            ({"budget": {"cost_of_delay_per_day": 0}, "project_resources": []}, True, 0, True),
            ({"budget": {"cost_of_delay_per_day": 100}}, False, 200, True),
        ):
            with self.subTest(context=context, include_burn=include_burn):
                facts = make_executor()
                facts.problem_context = AsyncMock(return_value=context)
                result = await facts.calculate_delay_cost(
                    delay_days=2, include_resource_burn=include_burn
                )
                self.assertEqual(result["total_cost"], expected_total)
                self.assertEqual(result["is_complete"], expected_complete)
                self.assertEqual(bool(result["missing_data"]), not expected_complete)


class CitationTests(unittest.TestCase):
    def test_cited_document_keeps_full_text_beyond_the_preview(self):
        text = "Контекст. " * 80 + "Резерв не утверждён."
        records = collect_tool_sources(
            "search_project_evidence",
            {
                "items": [
                    {
                        "id": "P007:documents:DOC1:v1:c0001",
                        "source_table": "documents",
                        "text": text,
                    }
                ]
            },
        )
        selected = select_answer_sources(records, [records[0]["id"]])
        self.assertEqual(selected[0]["data"]["text"], text)
        self.assertLess(len(selected[0]["excerpt"]), len(text))

    def test_only_matched_sources_are_selected_including_source_and_dependency_ids(self):
        records = collect_tool_sources(
            "get_task_dependency_graph",
            {
                "items": [
                    {"id": "EDGE1", "task_id": "T1", "depends_on_task_id": "T2"},
                    {"id": "EDGE2", "task_id": "T3", "depends_on_task_id": "T4"},
                ]
            },
        )
        self.assertEqual(select_answer_sources(records, []), [])
        self.assertEqual(select_answer_sources(records, ["UNKNOWN"]), [])
        self.assertEqual(len(select_answer_sources(records + records, ["T2"])), 1)
        for evidence_id in ("t2", records[0]["id"]):
            selected = select_answer_sources(records, [evidence_id])
            self.assertEqual([source["reference"] for source in selected], ["EDGE1"])
            self.assertNotIn("_match_keys", selected[0])

    def test_summary_metrics_and_all_returned_dependency_edges_can_be_cited(self):
        sources = collect_tool_sources(
            "get_project_summary", {"project_id": "P001", "blocked_count": 5}
        )
        self.assertEqual(len(select_answer_sources(sources, ["P001"])), 1)
        edges = [{"id": f"E{i}", "task_id": f"T{i}"} for i in range(60)]
        records = collect_tool_sources("get_task_dependency_graph", {"items": edges})
        self.assertEqual(len(records), 60)
        self.assertEqual(len(select_answer_sources(records, ["E59"])), 1)


if __name__ == "__main__":
    unittest.main()


class CitationCoverageRegressionTests(unittest.TestCase):
    def test_broad_project_alias_does_not_displace_late_unique_citation(self):
        from copy import deepcopy

        records = collect_tool_sources(
            "search_project_evidence",
            {
                "items": [
                    {"id": f"EV{i}", "project_id": "P001", "source_id": f"S{i}", "text": "Evidence"}
                    for i in range(30)
                ]
            },
        )
        original = deepcopy(records)
        targets = ["p001", *[f"S{i}" for i in range(17, 30)]]
        selected = select_answer_sources(records + records, targets)
        self.assertLessEqual(len(selected), 14)
        for target in targets:
            self.assertTrue(
                any(
                    target.casefold()
                    in {
                        str(value).casefold()
                        for value in [source["id"], source["reference"], *source["data"].values()]
                    }
                    for source in selected
                ),
                target,
            )
        self.assertEqual(records, original)
        self.assertTrue(all("_match_keys" not in source for source in selected))
        self.assertEqual(selected, select_answer_sources(records, targets))

    def test_canonical_then_reference_then_alias_priority_and_deduplication(self):
        records = [
            {"id": "alias", "reference": "other", "_match_keys": ["wanted"], "data": {}},
            {"id": "reference", "reference": "wanted", "_match_keys": ["wanted"], "data": {}},
            {
                "id": "wanted",
                "reference": "canonical",
                "_match_keys": ["wanted", "also"],
                "data": {},
            },
        ]
        self.assertEqual(
            [
                source["id"]
                for source in select_answer_sources(records, ["WANTED", "also", "wanted"])
            ],
            ["wanted"],
        )
        self.assertEqual(
            [source["id"] for source in select_answer_sources(records[:2], ["wanted"])],
            ["reference"],
        )
        self.assertEqual(
            [source["id"] for source in select_answer_sources(records[:1], ["wanted"])], ["alias"]
        )
        self.assertEqual(select_answer_sources(records, ["wanted"], max_sources=0), [])
