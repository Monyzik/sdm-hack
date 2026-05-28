"""Проверки запаса времени перед поиском без ожиданий и сетевых вызовов."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

from sdm.agents.project_qa.agent import _answer_from_state
from sdm.agents.project_qa.answer import INSUFFICIENT_EVIDENCE_ANSWER
from sdm.agents.project_qa.evidence.models import AnswerDraft, ClaimSupport, EvidenceReview
from sdm.agents.project_qa.graph import build_project_question_graph
from sdm.agents.project_qa.nodes.recovery import request_evidence_recovery, route_after_review
from sdm.agents.project_qa.schemas import RequestRoute

CLOCK = "sdm.agents.project_qa.nodes.recovery.monotonic"
EMIT = "sdm.agents.project_qa.nodes.recovery.emit_stream_event"
FACTS = [f"Условие {index} подтверждено." for index in range(4)]


def review_state(**updates):
    return {
        "question": "Условия пилота?",
        "request_deadline": 120.0,
        "answer_draft": AnswerDraft(
            claims=[{"text": FACTS[0], "evidence": [{"source_id": "s", "quote": FACTS[0]}]}],
            unanswered_aspects=[],
        ),
        "evidence_review": EvidenceReview(
            claims=[{"claim_index": 0, "verdict": "unsupported"}],
            missing_aspects=[],
            searches=[{"query": "Дополнительные условия"}],
            context_source_ids=[],
        ),
        **updates,
    }


@pytest.mark.parametrize("remaining,route", [(59.999, "finalize"), (60.0, "recover")])
def test_recovery_time_boundary(remaining, route):
    with patch(CLOCK, return_value=120 - remaining), patch(EMIT) as emit:
        assert route_after_review(review_state()) == route
    if route == "finalize":
        assert emit.call_count == 1
        assert emit.call_args.args == ("recovery_skipped",)
        assert emit.call_args.kwargs["reason"] == "time_budget"
    else:
        emit.assert_not_called()


@pytest.mark.parametrize("scenario", ["complete", "exhausted", "no_eligible"])
def test_no_false_time_skip_without_eligible_recovery(scenario):
    current = review_state()
    if scenario == "complete":
        current["evidence_review"] = current["evidence_review"].model_copy(
            update={
                "claims": [
                    current["evidence_review"].claims[0].model_copy(update={"verdict": "supported"})
                ],
                "searches": [],
            }
        )
    elif scenario == "exhausted":
        current["recovery_rounds"] = 1
    else:
        current["messages"] = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "previous",
                        "name": "search_project_evidence",
                        "args": {"query": "Дополнительные условия"},
                    }
                ],
            )
        ]
    with patch(CLOCK, return_value=119), patch(EMIT) as emit:
        assert route_after_review(current) == "finalize"
        emit.assert_not_called()


def test_recovery_admission_is_not_rechecked_after_clock_crosses_boundary():
    current = review_state()
    with (
        patch(CLOCK, return_value=59.999) as clock,
        patch(EMIT),
        patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None),
    ):
        assert route_after_review(current) == "recover"
        clock.return_value = 60.001
        update = request_evidence_recovery(current)
        assert clock.call_count == 1
    assert update["recovery_rounds"] == 1
    assert update["messages"][0].tool_calls[0]["args"] == {"query": "Дополнительные условия"}


class RecoveryBudgetGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_late_review_publishes_verified_partial_or_abstention_without_recovery(self):
        for supported in (3, 0):
            with self.subTest(supported=supported):
                clock = SimpleNamespace(now=0.0)
                calls = []
                model_calls = []

                async def summary():
                    calls.append("summary")
                    return "summary", {"project_id": "P007"}

                async def context():
                    calls.append("context")
                    return "context", {"project": {"id": "P007"}}

                async def search(query: str):
                    calls.append(query)
                    assert calls.count(query) == 1
                    assert query == "Условия пилота?"
                    return "facts", {
                        "items": [
                            {"id": f"D{index}", "text": fact, "title": f"Документ {index}"}
                            for index, fact in enumerate(FACTS)
                        ]
                    }

                async def parse_pydantic(*, response_model, **kwargs):
                    model_calls.append(response_model)
                    if response_model is RequestRoute:
                        return RequestRoute(intent="project_question")
                    if response_model is ClaimSupport:
                        return ClaimSupport(
                            entailed=True,
                            all_numbers_supported=True,
                            status_and_modality_supported=True,
                            contradicted=False,
                        )
                    data = json.loads(
                        kwargs["user_prompt"]
                        .split("<untrusted_data>")[1]
                        .split("</untrusted_data>")[0]
                    )["data"]
                    if issubclass(response_model, AnswerDraft):
                        assert sum(issubclass(model, AnswerDraft) for model in model_calls) == 1
                        claims = []
                        for fact in FACTS:
                            source = next(
                                item
                                for item in data["evidence_sources"]
                                if item["data"].get("text") == fact
                            )
                            claims.append(
                                {
                                    "text": fact,
                                    "evidence": [{"source_id": source["id"], "quote": fact}],
                                }
                            )
                        return response_model(claims=claims, unanswered_aspects=[])
                    assert response_model is EvidenceReview
                    clock.now = 143.0
                    return EvidenceReview(
                        claims=[
                            {
                                "claim_index": index,
                                "verdict": "supported" if index < supported else "unsupported",
                            }
                            for index in range(4)
                        ],
                        missing_aspects=["Остальные условия?"],
                        searches=[{"query": "Дополнительные условия"}],
                        context_source_ids=[],
                    )

                tools = [
                    StructuredTool.from_function(
                        coroutine=func,
                        name=name,
                        description="Локальный источник для теста.",
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
                events, result = [], None
                with patch(CLOCK, side_effect=lambda: clock.now):
                    async for mode, chunk in graph.astream(
                        {
                            "project_id": "P007",
                            "as_of": "2026-06-19",
                            "question": "Условия пилота?",
                            "messages": [HumanMessage(content="Условия пилота?")],
                            "request_deadline": 180.0,
                            "stream_response": True,
                        },
                        stream_mode=["custom", "values"],
                    ):
                        if mode == "custom":
                            events.append(chunk)
                        else:
                            result = chunk
                answer = _answer_from_state(result)
                assert calls == ["summary", "context", "Условия пилота?"]
                assert model_calls.count(ClaimSupport) == 4
                assert model_calls.count(EvidenceReview) == 1
                assert sum(issubclass(model, AnswerDraft) for model in model_calls) == 1
                assert answer.verification.status == ("partial" if supported else "abstained")
                assert answer.verification.checked_claims == 4
                assert answer.verification.supported_claims == supported
                assert answer.verification.recovery_rounds == 0
                assert [claim.text for claim in answer.claims] == FACTS[:supported]
                assert len(answer.evidence_ids) == len(answer.evidence_sources) == supported
                assert {source.data["text"] for source in answer.evidence_sources} == set(
                    FACTS[:supported]
                )
                for fact in FACTS[supported:]:
                    assert fact not in answer.answer
                if not supported:
                    assert answer.answer == INSUFFICIENT_EVIDENCE_ANSWER
                skipped = [event for event in events if event["event"] == "recovery_skipped"]
                assert len(skipped) == 1
                assert skipped[0]["data"] == {
                    "reason": "time_budget",
                    "remaining_seconds": 37.0,
                    "required_seconds": 60.0,
                }
                assert not any(event["event"] == "evidence_recovery" for event in events)
                assert not any(
                    message.tool_calls
                    for message in result["messages"]
                    if isinstance(message, AIMessage)
                )
