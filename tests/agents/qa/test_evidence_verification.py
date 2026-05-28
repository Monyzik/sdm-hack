"""Проверки цитат и ограничений дополнительного поиска без сети."""

import asyncio
from functools import wraps
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from sdm.agents.project_qa.evidence.models import AnswerDraft, ClaimSupport, EvidenceReview
from sdm.agents.project_qa.evidence.validation import (
    grounded_draft_model,
    invalid_quote_indices,
    supported_claims,
    validate_review,
)
from sdm.agents.project_qa.nodes.draft import draft_answer_node
from sdm.agents.project_qa.nodes.recovery import (
    request_evidence_recovery,
    route_after_review,
)
from sdm.agents.project_qa.nodes.verify import verify_answer_node
from sdm.agents.project_qa.recovery import recovery_calls


def async_test(func):
    @wraps(func)
    def run(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return run


def source(identifier="observed", text="Решение не согласовано.", tool="search_project_evidence"):
    return {
        "id": identifier,
        "tool": tool,
        "reference": "P007:documents:D:v1:c0001",
        "title": "Decision",
        "excerpt": "preview is not evidence",
        "data": {"id": "P007:documents:D:v1:c0001", "text": text},
    }


def draft(quote="Решение не согласовано.", text="Решение не согласовано."):
    return AnswerDraft(
        claims=[{"text": text, "evidence": [{"source_id": "observed", "quote": quote}]}],
        unanswered_aspects=[],
    )


def review(**overrides):
    return EvidenceReview.model_validate(
        {
            "claims": [{"claim_index": 0, "verdict": "supported"}],
            "missing_aspects": [],
            "searches": [],
            "context_source_ids": [],
            **overrides,
        }
    )


def support(**overrides):
    return ClaimSupport(
        entailed=True,
        all_numbers_supported=True,
        status_and_modality_supported=True,
        contradicted=False,
    ).model_copy(update=overrides)


def judge_llm(overall_review):
    async def parse_pydantic(*, response_model, **kwargs):
        return support() if response_model is ClaimSupport else overall_review

    return SimpleNamespace(parse_pydantic=AsyncMock(side_effect=parse_pydantic))


def state(**overrides):
    return {
        "question": "Каково решение и кто согласует?",
        "project_id": "P007",
        "as_of": "2026-06-19",
        "answer_draft": draft(),
        "evidence_review": review(),
        "tool_sources": [source()],
        "messages": [ToolMessage(content="facts", tool_call_id="1")],
        **overrides,
    }


def test_fabricated_quote_overrides_supported_judge_and_cannot_be_published():
    fabricated = draft(quote="Решение согласовано.", text="Решение согласовано.")
    checked = validate_review(review(), fabricated, [source()])
    assert checked.claims[0].verdict == "unsupported"
    assert supported_claims(fabricated, checked) == []
    assert review().claims[0].verdict == "supported"  # Исходные данные не меняются.


@pytest.mark.parametrize("indices", [[], [1], [0, 0], [0, 1]])
def test_missing_wrong_or_duplicate_judge_indices_fail_closed(indices):
    malformed = review(claims=[{"claim_index": index, "verdict": "supported"} for index in indices])
    with pytest.raises(ValueError, match="every claim exactly once"):
        validate_review(malformed, draft(), [source()])


def test_whitespace_is_equivalent_but_negation_numbers_and_case_are_not():
    sources = [source(text="Решение\nне  согласовано. Срок: 12 дней.")]
    assert invalid_quote_indices(draft(), sources) == set()
    for quote in ["Решение согласовано.", "Срок: 21 дней.", "решение не согласовано."]:
        assert invalid_quote_indices(draft(quote=quote), sources) == {0}
    assert invalid_quote_indices(draft(quote="preview is not evidence"), sources) == {0}


def test_draft_schema_allows_only_observed_artifact_ids():
    model = grounded_draft_model([source()])
    payload = draft().model_dump()
    model.model_validate(payload)
    payload["claims"][0]["evidence"][0]["source_id"] = "invented"
    with pytest.raises(ValueError):
        model.model_validate(payload)


def test_recovery_separates_searches_reads_observed_indexed_ids_and_caps_batch():
    planned = review(
        claims=[{"claim_index": 0, "verdict": "unsupported"}],
        missing_aspects=["Владелец согласования"],
        searches=[
            {"query": "Протокол согласования"},
            {"query": "Владелец решения"},
            {"query": "Дата согласования"},
        ],
        context_source_ids=["invented", "summary", "observed"],
    )
    current = state(
        evidence_review=planned,
        tool_sources=[source(), source("summary", tool="get_project_summary")],
    )
    calls = recovery_calls(current)
    assert len(calls) == 3
    assert calls[0] == {
        "name": "get_evidence_context",
        "args": {"evidence_id": "P007:documents:D:v1:c0001", "neighbors": 1},
    }
    assert [c["args"]["query"] for c in calls[1:]] == ["Протокол согласования", "Владелец решения"]
    assert route_after_review(current) == "recover"
    with (
        patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None),
        patch("sdm.agents.project_qa.nodes.recovery.emit_stream_event") as emit,
    ):
        update = request_evidence_recovery(current)
    assert update["recovery_rounds"] == 1
    assert len(update["messages"][0].tool_calls) == 3
    assert len({c["id"] for c in update["messages"][0].tool_calls}) == 3
    emit.assert_called_once_with(
        "evidence_recovery",
        round=1,
        queries=["Протокол согласования", "Владелец решения"],
        context_source_ids=["P007:documents:D:v1:c0001"],
    )
    exhausted = {**current, **update}
    assert recovery_calls(exhausted) == []
    assert route_after_review(exhausted) == "finalize"


def test_recovery_deduplicates_observed_calls_and_reviewer_requests():
    call = {
        "name": "get_evidence_context",
        "args": {"evidence_id": "P007:documents:D:v1:c0001", "neighbors": 1},
        "id": "already",
    }
    current = state(
        messages=[AIMessage(content="", tool_calls=[call])],
        evidence_review=review(
            claims=[{"claim_index": 0, "verdict": "unsupported"}],
            missing_aspects=["Владелец"],
            context_source_ids=["observed", "observed"],
            searches=[{"query": "Владелец"}, {"query": "владелец"}],
        ),
    )
    assert recovery_calls(current) == [
        {"name": "search_project_evidence", "args": {"query": "Владелец"}}
    ]
    assert recovery_calls({**current, "verification_failed": True}) == []
    assert recovery_calls({**current, "evidence_unavailable": True}) == []
    assert recovery_calls(state()) == []


@pytest.mark.parametrize("error", [TimeoutError("secret draft"), ValueError("secret draft")])
@async_test
async def test_judge_failure_returns_only_failure_state_and_safe_event(error):
    llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=error))
    with (
        patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None),
        patch("sdm.agents.project_qa.nodes.verify.emit_stream_event") as emit,
    ):
        update = await verify_answer_node(llm=llm)(state())
    assert update == {"verification_failed": True}
    assert "secret draft" not in str(emit.call_args)
    emit.assert_called_once_with(
        "verification_failed", message="Не удалось проверить подтверждения."
    )
    assert route_after_review({**state(), **update}) == "finalize"


@async_test
async def test_judge_counts_report_deterministically_rejected_quote():
    llm = SimpleNamespace(parse_pydantic=AsyncMock(return_value=review()))
    current = state(answer_draft=draft(quote="Решение согласовано."))
    with (
        patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None),
        patch("sdm.agents.project_qa.nodes.verify.emit_stream_event") as emit,
    ):
        update = await verify_answer_node(llm=llm)(current)
    assert update["evidence_review"].claims[0].verdict == "unsupported"
    (event,) = emit.call_args.args
    assert event == "evidence_review"
    assert emit.call_args.kwargs == {
        "round": 1,
        "claims_total": 1,
        "supported": 0,
        "unsupported": 1,
        "contradicted": 0,
        "missing_aspects": [],
        "recovery_available": True,
    }


@async_test
async def test_draft_with_no_artifacts_skips_provider_even_when_tools_failed():
    llm = SimpleNamespace(parse_pydantic=AsyncMock())
    node = draft_answer_node(llm=llm, temperature=0)
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        assert await node(state(tool_sources=[])) == {"evidence_unavailable": True}
        assert await node(
            state(
                tool_sources=[],
                messages=[ToolMessage(content="failed", status="error", tool_call_id="1")],
            )
        ) == {"evidence_unavailable": True}
    llm.parse_pydantic.assert_not_awaited()


@pytest.mark.parametrize("indices", [[], [1], [0, 0]])
@async_test
async def test_malformed_review_node_fails_closed_before_recovery_or_counts(indices):
    malformed = review(claims=[{"claim_index": i, "verdict": "supported"} for i in indices])
    llm = judge_llm(malformed)
    with (
        patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None),
        patch("sdm.agents.project_qa.nodes.verify.emit_stream_event") as emit,
    ):
        update = await verify_answer_node(llm=llm)(state())
    assert update == {"verification_failed": True}
    assert [c.args[0] for c in emit.call_args_list] == ["verification_failed"]
    assert recovery_calls({**state(), **update}) == []


def test_publication_removes_rejected_claims_and_reports_partial_coverage():
    from sdm.agents.project_qa.answer import PARTIAL_ANSWER_NOTE, render_verified_answer

    mixed = AnswerDraft(
        claims=[
            *draft().claims,
            *draft(quote="Решение согласовано.", text="SECRET FABRICATED CLAIM").claims,
        ],
        unanswered_aspects=[],
    )
    judgments = review(
        claims=[
            {"claim_index": 0, "verdict": "supported"},
            {"claim_index": 1, "verdict": "supported"},
        ]
    )
    answer = render_verified_answer(
        state(
            answer_draft=mixed,
            evidence_review=judgments,
            recovery_rounds=1,
            used_tools=["search_project_evidence"],
        )
    )
    assert answer.answer == "Решение не согласовано.\n\n" + PARTIAL_ANSWER_NOTE
    assert "SECRET" not in answer.model_dump_json()
    assert answer.evidence_ids == ["observed"]
    assert len(answer.claims) == 1
    assert answer.verification.model_dump() == {
        "status": "partial",
        "checked_claims": 2,
        "supported_claims": 1,
        "recovery_rounds": 1,
    }


@pytest.mark.parametrize("unanswered", [[], ["Посторонняя деталь?"]])
def test_supported_answer_with_question_gap_remains_partial_without_recovery(unanswered):
    from sdm.agents.project_qa.answer import render_verified_answer

    current = state(
        answer_draft=draft().model_copy(update={"unanswered_aspects": unanswered}),
        evidence_review=review(missing_aspects=["Владелец?"]),
    )
    answer = render_verified_answer(current)
    assert answer.verification.status == "partial"
    assert answer.verification.supported_claims == 1
    assert route_after_review(current) == "finalize"
    assert recovery_calls(current) == []


def test_tentative_draft_gap_does_not_override_judge_complete_answer():
    from sdm.agents.project_qa.answer import render_verified_answer

    current = state(
        answer_draft=draft().model_copy(
            update={"unanswered_aspects": ["Посторонняя подробность, не нужная для ответа?"]}
        )
    )
    answer = render_verified_answer(current)
    assert answer.verification.status == "passed"
    assert answer.answer == "Решение не согласовано."
    assert recovery_calls(current) == []
    assert route_after_review(current) == "finalize"


def test_publication_complete_and_abstained_cases_are_deterministic():
    from sdm.agents.project_qa.answer import INSUFFICIENT_EVIDENCE_ANSWER, render_verified_answer

    answer = render_verified_answer(state())
    assert answer.answer == "Решение не согласовано."
    assert answer.verification.status == "passed"
    rejected = render_verified_answer(
        state(evidence_review=review(claims=[{"claim_index": 0, "verdict": "contradicted"}]))
    )
    assert rejected.answer == INSUFFICIENT_EVIDENCE_ANSWER
    assert rejected.verification.status == "abstained"
    assert rejected.evidence_ids == rejected.claims == []
    empty = render_verified_answer(
        state(
            answer_draft=AnswerDraft(claims=[], unanswered_aspects=[]),
            evidence_review=review(claims=[]),
        )
    )
    assert empty.answer == INSUFFICIENT_EVIDENCE_ANSWER
    assert empty.verification.status == "abstained"


@pytest.mark.parametrize("failure", [TimeoutError("secret draft"), ValueError("secret draft")])
@async_test
async def test_failed_judge_final_answer_is_fixed_and_draft_is_never_rewritten_or_leaked(failure):
    import json

    from sdm.agents.project_qa.answer import VERIFICATION_UNAVAILABLE_ANSWER
    from sdm.agents.project_qa.nodes.final import finalize_answer_node

    llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=failure))
    current = state(answer_draft=draft(text="SECRET UNCHECKED DRAFT"))
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        update = await verify_answer_node(llm=llm)(current)
        final = await finalize_answer_node(llm=llm, temperature=0)({**current, **update})
    assert llm.parse_pydantic.await_count == 1
    content = json.loads(final["final_content"])
    assert content["answer"] == VERIFICATION_UNAVAILABLE_ANSWER
    assert content["verification"]["status"] == "unavailable"
    assert content["evidence_ids"] == content["claims"] == []
    assert "SECRET" not in final["final_content"]
    assert "secret draft" not in final["final_content"]


@async_test
async def test_successful_project_finalization_has_no_second_llm_rewrite():
    import json

    from sdm.agents.project_qa.nodes.final import finalize_answer_node

    llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=AssertionError("No rewrite")))
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        final = await finalize_answer_node(llm=llm, temperature=0)(state())
    assert json.loads(final["final_content"])["answer"] == "Решение не согласовано."
    llm.parse_pydantic.assert_not_awaited()


@pytest.mark.parametrize(
    "messages",
    [[], [ToolMessage(content="failed late recovery", status="error", tool_call_id="later")]],
)
@async_test
async def test_preloaded_artifacts_support_drafting_and_finalization_without_successful_tool_message(
    messages,
):
    import json

    from sdm.agents.project_qa.nodes.final import finalize_answer_node

    llm = SimpleNamespace(parse_pydantic=AsyncMock(return_value=draft()))
    current = state(messages=messages, used_tools=["get_project_summary"], evidence_review=None)
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        update = await draft_answer_node(llm=llm, temperature=0)(current)
        assert update["evidence_unavailable"] is False
        final = await finalize_answer_node(llm=llm, temperature=0)(
            {**current, **update, "evidence_review": review()}
        )
    assert json.loads(final["final_content"])["answer"] == "Решение не согласовано."
    llm.parse_pydantic.assert_awaited_once()


@pytest.mark.parametrize("node_type", ["draft", "verify"])
@async_test
async def test_private_draft_and_judge_suppress_reasoning_but_keep_progress_usage_and_restore_context(
    node_type,
):
    from sdm.agents.streaming import collect_stream_metrics, emit_stream_event

    events = []

    async def parse_pydantic(**kwargs):
        assert kwargs["stream"] is True
        emit_stream_event("llm_started", operation="private")
        emit_stream_event("reasoning_delta", text="SECRET UNCHECKED REASONING")
        emit_stream_event(
            "llm_finished",
            operation="private",
            usage={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        )
        if kwargs["response_model"] is ClaimSupport:
            return support()
        return draft() if node_type == "draft" else review()

    llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=parse_pydantic))
    node = (
        draft_answer_node(llm=llm, temperature=0)
        if node_type == "draft"
        else verify_answer_node(llm=llm)
    )
    with (
        patch("sdm.agents.streaming.get_stream_writer", return_value=events.append),
        collect_stream_metrics() as metrics,
    ):
        await node(state(stream_response=True))
        emit_stream_event("reasoning_delta", text="outside protected scope")
    assert [event["data"]["text"] for event in events if event["event"] == "reasoning_delta"] == [
        "outside protected scope"
    ]
    assert "SECRET" not in str(events)
    names = [event["event"] for event in events]
    assert "llm_started" in names and "llm_finished" in names
    assert "stage_started" in names and "stage_finished" in names
    assert metrics.snapshot()["total_tokens"] == (12 if node_type == "draft" else 24)
    if node_type == "verify":
        assert "evidence_review" in names


def claim_scoped_fixture():
    claims = AnswerDraft(
        claims=[
            {
                "text": "План предложен.",
                "evidence": [{"source_id": "proposal", "quote": "План предложен."}],
            },
            {
                "text": "Оценка резерва: 987654.",
                "evidence": [{"source_id": "estimate", "quote": "987654"}],
            },
        ],
        unanswered_aspects=[],
    )
    sources = [
        source("proposal", text="План предложен."),
        source("estimate", text="Оценка резерва: 987654.", tool="get_budget"),
        source("unrelated-snapshot", text="UNRELATED STRUCTURED ROW", tool="get_project_summary"),
        source("conflicting-document", text="Предложение отклонено."),
        source("neighboring-section", text="Требуется новый расчёт.", tool="get_evidence_context"),
    ]
    return claims, sources


def test_verification_evidence_keeps_each_claim_citations_separate_and_excludes_unrelated_snapshots():
    import json

    from sdm.agents.project_qa.evidence.validation import verification_evidence

    claims, sources = claim_scoped_fixture()
    evidence = verification_evidence(claims, sources)
    per_claim = evidence["claim_evidence"]
    assert [item["claim_index"] for item in per_claim] == [0, 1]
    assert [s["id"] for s in per_claim[0]["sources"]] == ["proposal"]
    assert [s["id"] for s in per_claim[1]["sources"]] == ["estimate"]
    # Число из источника другого утверждения не подтверждает это утверждение.
    assert "987654" not in json.dumps(per_claim[0], ensure_ascii=False)
    assert "987654" in json.dumps(per_claim[1], ensure_ascii=False)
    assert "UNRELATED STRUCTURED ROW" not in json.dumps(evidence, ensure_ascii=False)
    assert [s["id"] for s in evidence["other_retrieved_sources"]] == [
        "conflicting-document",
        "neighboring-section",
    ]
    assert evidence["other_retrieved_sources"][0]["data"]["text"] == "Предложение отклонено."


@async_test
async def test_judge_prompt_uses_claim_scoped_artifacts_without_reintroducing_global_catalog():
    import json

    claims, sources = claim_scoped_fixture()
    llm = judge_llm(
        review(
            claims=[
                {"claim_index": 0, "verdict": "unsupported"},
                {"claim_index": 1, "verdict": "unsupported"},
            ]
        )
    )
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        await verify_answer_node(llm=llm)(state(answer_draft=claims, tool_sources=sources))
    prompt = llm.parse_pydantic.call_args.kwargs["user_prompt"]
    data = json.loads(prompt.split("<untrusted_data>")[1].split("</untrusted_data>")[0])["data"]
    assert "evidence_sources" not in data
    assert [s["id"] for s in data["claim_evidence"][0]["sources"]] == ["proposal"]
    assert "987654" not in json.dumps(data["claim_evidence"][0], ensure_ascii=False)
    assert "UNRELATED STRUCTURED ROW" not in prompt
    assert [s["id"] for s in data["other_retrieved_sources"]] == [
        "conflicting-document",
        "neighboring-section",
    ]


@async_test
async def test_isolated_claim_request_excludes_other_claims_sources_and_question_facts():
    import json

    claims, sources = claim_scoped_fixture()
    llm = judge_llm(review(claims=[{"claim_index": i, "verdict": "supported"} for i in range(2)]))
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        await verify_answer_node(llm=llm)(
            state(
                answer_draft=claims,
                tool_sources=sources,
                question="QUESTION ONLY FACT 135790",
                conversation_context="HISTORY ONLY FACT 246801",
            )
        )
    requests = [
        call.kwargs
        for call in llm.parse_pydantic.await_args_list
        if call.kwargs["response_model"] is ClaimSupport
    ]
    assert len(requests) == 2
    data = [
        json.loads(r["user_prompt"].split("<untrusted_data>")[1].split("</untrusted_data>")[0])[
            "data"
        ]
        for r in requests
    ]
    first = next(item for item in data if item["claim"]["text"] == "План предложен.")
    assert set(first) == {"project_id", "as_of", "claim", "sources"}
    assert [s["id"] for s in first["sources"]] == ["proposal"]
    assert "987654" not in json.dumps(first, ensure_ascii=False)
    for request in requests:
        assert "QUESTION ONLY" not in request["user_prompt"]
        assert "HISTORY ONLY" not in request["user_prompt"]
        assert "UNRELATED STRUCTURED" not in request["user_prompt"]
        assert "Предложение отклонено." not in request["user_prompt"]


@pytest.mark.parametrize(
    "isolated",
    [
        support(entailed=False),
        support(all_numbers_supported=False),
        support(status_and_modality_supported=False),
        support(contradicted=True),
    ],
)
@async_test
async def test_global_supported_cannot_override_any_isolated_veto(isolated):
    async def parse_pydantic(*, response_model, **kwargs):
        return isolated if response_model is ClaimSupport else review()

    llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=parse_pydantic))
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        update = await verify_answer_node(llm=llm)(state())
    assert update["evidence_review"].claims[0].verdict == isolated.verdict
    assert supported_claims(draft(), update["evidence_review"]) == []
    assert [c.kwargs["response_model"] for c in llm.parse_pydantic.await_args_list] == [
        ClaimSupport,
        EvidenceReview,
    ]


@async_test
async def test_invalid_literal_quote_skips_isolated_provider_call():
    llm = judge_llm(review())
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        update = await verify_answer_node(llm=llm)(state(answer_draft=draft(quote="FABRICATED")))
    assert update["evidence_review"].claims[0].verdict == "unsupported"
    assert [c.kwargs["response_model"] for c in llm.parse_pydantic.await_args_list] == [
        EvidenceReview
    ]


@pytest.mark.parametrize(
    "round_state,available",
    [
        ({}, True),
        ({"recovery_rounds": 0}, True),
        ({"recovery_rounds": 1}, False),
        ({"recovery_rounds": 2}, False),
    ],
)
@async_test
async def test_review_receives_recovery_budget_without_bypassing_claim_verification(
    round_state, available
):
    import json

    async def parse_pydantic(*, response_model, **kwargs):
        if response_model is ClaimSupport:
            return support(entailed=False)
        return review(missing_aspects=["Кто согласует решение?"])

    llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=parse_pydantic))
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        update = await verify_answer_node(llm=llm)(state(**round_state))
    requests = [call.kwargs for call in llm.parse_pydantic.await_args_list]
    assert [request["response_model"] for request in requests] == [ClaimSupport, EvidenceReview]
    payload = json.loads(
        requests[-1]["user_prompt"].split("<untrusted_data>")[1].split("</untrusted_data>")[0]
    )["data"]
    assert payload["recovery_available"] is available
    assert update["verification_failed"] is False
    assert update["evidence_review"].claims[0].verdict == "unsupported"
    assert update["evidence_review"].missing_aspects == ["Кто согласует решение?"]
    assert supported_claims(draft(), update["evidence_review"]) == []
    if not available:
        assert route_after_review({**state(**round_state), **update}) == "finalize"


@async_test
async def test_isolated_checks_run_at_most_two_concurrently_then_global_review():
    active = peak = finished = 0
    many = AnswerDraft(claims=[draft().claims[0]] * 4, unanswered_aspects=[])

    async def parse_pydantic(*, response_model, **kwargs):
        nonlocal active, peak, finished
        if response_model is EvidenceReview:
            assert active == 0 and finished == 4
            return review(claims=[{"claim_index": i, "verdict": "supported"} for i in range(4)])
        assert response_model is ClaimSupport
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            finished += 1
            return support()
        finally:
            active -= 1

    llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=parse_pydantic))
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        update = await verify_answer_node(llm=llm)(state(answer_draft=many))
    assert peak == 2 and active == 0
    assert len(update["evidence_review"].claims) == 4
    assert llm.parse_pydantic.await_count == 5


@pytest.mark.parametrize("cancel_parent", [False, True])
@async_test
async def test_claim_failure_or_parent_cancellation_cancels_inflight_sibling(cancel_parent):
    both_started = asyncio.Event()
    active = started = cancelled = 0
    many = AnswerDraft(claims=[draft().claims[0]] * 2, unanswered_aspects=[])

    async def parse_pydantic(*, response_model, **kwargs):
        nonlocal active, started, cancelled
        assert response_model is ClaimSupport  # После сбоя отдельной проверки общая не запускается.
        started += 1
        own_index = started
        active += 1
        if started == 2:
            both_started.set()
        try:
            await both_started.wait()
            if own_index == 1 and not cancel_parent:
                raise TimeoutError("SECRET CLAIM PROVIDER FAILURE")
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled += 1
            raise
        finally:
            active -= 1

    llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=parse_pydantic))
    events = []
    with patch("sdm.agents.streaming.get_stream_writer", return_value=events.append):
        task = asyncio.create_task(verify_answer_node(llm=llm)(state(answer_draft=many)))
        await asyncio.wait_for(both_started.wait(), timeout=2)
        if cancel_parent:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            assert await task == {"verification_failed": True}
    assert active == 0 and started == 2
    assert cancelled == (2 if cancel_parent else 1)
    assert "SECRET" not in str(events)
    assert not any(event["event"] == "evidence_review" for event in events)
