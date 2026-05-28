"""Метрики не смешивают сбои судьи, ошибки агента и отсутствие наблюдений."""

import copy
import csv
import tempfile
import unittest
from pathlib import Path

from sdm.evaluation.agent_metrics import export_agent_reports, score_record


def record():
    return {
        "case_id": "C1",
        "mode": "standard",
        "case": {
            "question": "Статус?",
            "project_id": "P007",
            "intent": "project_question",
            "expected_claims": ["План утверждён"],
            "forbidden_claims": ["План отменён"],
            "expect_abstention": False,
        },
        "failure": None,
        "judge_failure": None,
        "answer": {
            "answer": "План утверждён",
            "evidence_ids": ["s1"],
            "evidence_sources": [{"id": "s1", "data": {"project_id": "P007"}}],
            "verification": {"status": "passed"},
        },
        "judge": {
            "expected_claims": [{"index": 0, "covered": True}],
            "forbidden_claims": [{"index": 0, "present": False}],
            "answer_claims": [
                {"text": "План утверждён", "verdict": "supported", "evidence_ids": ["s1"]}
            ],
            "abstained": False,
            "relevant": True,
            "reason": "Проверено",
        },
        "duration_ms": 100,
        "first_answer_ms": 90,
        "metrics": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "ttft_ms": 20},
        "tools": [
            {"name": name, "args": {}, "status": "success"}
            for name in ["get_project_summary", "get_problem_context", "search_project_evidence"]
        ],
        "llm_call_count": 3,
        "format_retries": 0,
        "rerank_fallbacks": 0,
    }


class AgentMetricsTests(unittest.TestCase):
    def test_success_requires_facts_even_if_internal_verification_passed(self):
        source = record()
        self.assertTrue(score_record(source)["task_success"])
        source["judge"]["answer_claims"] = []
        self.assertFalse(score_record(source)["task_success"])
        self.assertEqual(score_record(source)["answer_claims_total"], 0)
        source = record()
        source["judge"]["answer_claims"][0]["verdict"] = "unsupported"
        self.assertFalse(score_record(source)["task_success"])

    def test_agent_failure_is_scored_but_judge_failure_is_not(self):
        source = record()
        source["judge_failure"] = "timeout"
        self.assertIsNone(score_record(source)["task_success"])
        self.assertFalse(score_record(source)["quality_evaluable"])
        source["failure"] = "agent timeout"
        source["answer"] = None
        self.assertFalse(score_record(source)["task_success"])
        self.assertTrue(score_record(source)["scored"])

    def test_invalid_or_incomplete_judge_cannot_manufacture_coverage(self):
        for assessments in (
            [],
            [{"index": 0, "covered": True}] * 2,
            [{"index": 1, "covered": True}],
        ):
            source = record()
            source["judge"]["expected_claims"] = assessments
            self.assertIsNone(score_record(source)["task_success"])

    def test_citations_checked_for_answer_and_judged_claims(self):
        for target in ("answer", "claim", "project", "missing"):
            with self.subTest(target=target):
                source = record()
                if target == "answer":
                    source["answer"]["evidence_ids"] = ["invented"]
                elif target == "claim":
                    source["judge"]["answer_claims"][0]["evidence_ids"] = ["invented"]
                elif target == "missing":
                    source["answer"]["evidence_ids"] = []
                    source["judge"]["answer_claims"][0]["evidence_ids"] = []
                else:
                    source["answer"]["evidence_sources"][0]["data"]["project_id"] = "P008"
                self.assertFalse(score_record(source)["citations_valid"])
                self.assertFalse(score_record(source)["task_success"])

    def test_uncited_unsupported_claim_is_not_a_broken_citation(self):
        source = record()
        source["answer"]["evidence_ids"] = []
        source["judge"]["answer_claims"][0].update(verdict="unsupported", evidence_ids=[])
        scored = score_record(source)
        self.assertIsNone(scored["citations_valid"])
        self.assertFalse(scored["task_success"])
        source["judge"]["answer_claims"][0]["verdict"] = "contradicted"
        self.assertIsNone(score_record(source)["citations_valid"])

    def test_required_calculation_matches_values_and_success(self):
        source = record()
        source["case"]["required_tool_calls"] = [
            {"name": "calculate_delay_cost", "arguments": {"delay_days": 1}}
        ]
        tool = {"name": "calculate_delay_cost", "args": {"delay_days": True}, "status": "success"}
        source["tools"].append(tool)
        self.assertFalse(score_record(source)["required_tool_correct"])
        tool["args"]["delay_days"] = 1
        self.assertTrue(score_record(source)["task_success"])
        tool["status"] = "error"
        self.assertFalse(score_record(source)["task_success"])
        self.assertIsNone(score_record(record())["required_tool_correct"])

    def test_nonproject_policy_requires_no_tools_or_sources(self):
        source = record()
        source["case"].update(intent="small_talk", expected_claims=[], forbidden_claims=[])
        source["judge"].update(expected_claims=[], forbidden_claims=[], answer_claims=[])
        source["tools"] = []
        self.assertFalse(score_record(source)["tool_policy_correct"])
        source["answer"] = {"answer": "Здравствуйте"}
        self.assertTrue(score_record(source)["task_success"])
        source["tools"] = [{"name": "search_project_evidence", "status": "error"}]
        self.assertFalse(score_record(source)["tool_policy_correct"])

    def test_micro_aggregation_denominators_and_runtime_are_separate(self):
        good = record()
        partial = copy.deepcopy(good)
        partial["case_id"] = "C2"
        partial["case"]["expected_claims"] *= 3
        partial["judge"]["expected_claims"] = [{"index": i, "covered": i == 0} for i in range(3)]
        partial["duration_ms"] = 300
        judge_failed = copy.deepcopy(good)
        judge_failed.update(case_id="C3", judge_failure="unavailable")
        failed = copy.deepcopy(good)
        failed.update(
            case_id="C4",
            failure="timeout",
            answer=None,
            judge=None,
            duration_ms=900,
            first_answer_ms=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            export_agent_reports(
                [good, partial, judge_failed, failed], output, {"standard": 5, "verified": 0}
            )
            rows = list(csv.DictReader((output / "summary.csv").open()))
            summary = next(row for row in rows if row["mode"] == "standard")
            self.assertEqual(float(summary["completion_rate"]), 3 / 5)
            self.assertEqual(summary["quality_evaluable_cases"], "2")
            self.assertEqual(summary["scored_cases"], "3")
            self.assertEqual(float(summary["task_success"]), 1 / 3)
            self.assertEqual(float(summary["fact_coverage"]), 2 / 4)
            self.assertEqual(summary["fact_coverage_denominator"], "4")
            self.assertEqual(summary["required_tool_accuracy"], "")
            self.assertEqual(summary["abstention_recall"], "")
            self.assertEqual(float(summary["duration_ms_success_p50"]), 100)
            self.assertEqual(float(summary["duration_ms_failure_p95"]), 900)
            self.assertEqual(float(summary["first_answer_ms_success_p50"]), 90)
            self.assertEqual(float(summary["ttft_ms_success_p50"]), 20)
            self.assertEqual(summary["total_tokens"], "60")
            self.assertEqual(summary["llm_call_count"], "12")
            empty = next(row for row in rows if row["mode"] == "verified")
            self.assertEqual(empty["completion_rate"], "")
            self.assertEqual(empty["grounded_claim_precision"], "")
            self.assertEqual(len(list(csv.DictReader((output / "manual_review.csv").open()))), 4)
            self.assertTrue((output / "report.html").exists())

    def test_unknown_and_false_abstention_use_distinct_populations(self):
        unknown, known = record(), record()
        unknown["case"].update(expected_claims=[], expect_abstention=True)
        unknown["judge"].update(expected_claims=[], answer_claims=[], abstained=True)
        unknown["answer"] = {"answer": "Недостаточно данных"}
        self.assertTrue(score_record(unknown)["task_success"])
        known["judge"]["abstained"] = True
        self.assertFalse(score_record(known)["task_success"])
        with tempfile.TemporaryDirectory() as directory:
            export_agent_reports([unknown, known], Path(directory), {"standard": 2})
            summary = next(csv.DictReader((Path(directory) / "summary.csv").open()))
            self.assertEqual(summary["abstention_recall_denominator"], "1")
            self.assertEqual(summary["false_abstention_rate_denominator"], "1")
            self.assertEqual(float(summary["abstention_recall"]), 1)
            self.assertEqual(float(summary["false_abstention_rate"]), 1)
