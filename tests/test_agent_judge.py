"""Проверки контракта независимого judge без запросов к провайдеру."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from sdm.evaluation.agent_judge import AgentJudgeResult, judge_answer


@pytest.fixture
def case():
    return {
        "project_id": "P007",
        "as_of": "2026-06-19",
        "question": "Матрица доступа согласована?",
        "conversation_context": [{"role": "user", "content": "Речь о матрице пилота."}],
        "expected_claims": ["Матрица доступа не согласована.", "Подготовлен проект матрицы."],
        "forbidden_claims": ["Матрица утверждена."],
        "expect_abstention": False,
    }


@pytest.fixture
def answer():
    return {
        "answer": "Матрица доступа не согласована, подготовлен только проект.",
        "evidence_sources": [
            {"id": "doc-1", "data": {"text": "Проект матрицы подготовлен, но не согласован."}}
        ],
        "verification": {"status": "passed", "reason": "PRIVATE VERIFIER FEEDBACK"},
        "claims": [{"text": "PRIVATE CLAIM LIST"}],
        "evidence_ids": ["PRIVATE AGENT CITATION"],
        "metrics": {"reason": "PRIVATE METRICS"},
    }


def result_payload(**updates):
    return {
        "expected_claims": [{"index": 0, "covered": True}, {"index": 1, "covered": True}],
        "forbidden_claims": [{"index": 0, "present": False}],
        "answer_claims": [
            {"text": "Матрица не согласована.", "verdict": "supported", "evidence_ids": ["doc-1"]}
        ],
        "abstained": False,
        "relevant": True,
        "reason": "Статус указан с верным отрицанием.",
        **updates,
    }


def run_judge(case, answer, payload):
    llm = SimpleNamespace(
        parse_pydantic=AsyncMock(return_value=AgentJudgeResult.model_validate(payload))
    )
    result = asyncio.run(judge_answer(llm, case=case, answer=answer))
    return result, llm


def test_judge_receives_gold_negation_and_sources_but_not_agent_feedback(case, answer):
    result, llm = run_judge(case, answer, result_payload())
    llm.parse_pydantic.assert_awaited_once()
    request = llm.parse_pydantic.call_args.kwargs
    assert request["response_model"] is AgentJudgeResult
    assert request["temperature"] == 0
    assert request["stream"] is False
    data = json.loads(
        request["user_prompt"].split("<untrusted_data>")[1].split("</untrusted_data>")[0]
    )["data"]
    assert data == {
        **case,
        "answer": answer["answer"],
        "evidence_sources": answer["evidence_sources"],
    }
    assert "PRIVATE" not in request["user_prompt"]
    assert result.expected_claims[0].covered
    assert not result.forbidden_claims[0].present


@pytest.mark.parametrize("text", ["Матрица согласована.", "Матрица официально утверждена."])
def test_inverted_negation_and_strengthened_status_are_passed_to_independent_judge(
    case, answer, text
):
    answer["answer"] = text
    judgment = result_payload(
        expected_claims=[{"index": 0, "covered": False}, {"index": 1, "covered": False}],
        forbidden_claims=[{"index": 0, "present": True}],
        answer_claims=[{"text": text, "verdict": "contradicted", "evidence_ids": ["doc-1"]}],
    )
    result, llm = run_judge(case, answer, judgment)
    prompt = llm.parse_pydantic.call_args.kwargs["user_prompt"]
    assert text in prompt
    assert "не согласован" in prompt
    assert result.answer_claims[0].verdict == "contradicted"
    assert result.forbidden_claims[0].present
    assert not result.expected_claims[0].covered


@pytest.mark.parametrize(
    "field,indices",
    [
        ("expected_claims", []),
        ("expected_claims", [0]),
        ("expected_claims", [0, 0]),
        ("expected_claims", [0, 2]),
        ("forbidden_claims", []),
        ("forbidden_claims", [0, 0]),
        ("forbidden_claims", [1]),
    ],
)
def test_missing_duplicate_and_out_of_range_indices_are_rejected(case, answer, field, indices):
    flag = "covered" if field == "expected_claims" else "present"
    with pytest.raises(ValueError, match=field):
        run_judge(
            case,
            answer,
            result_payload(**{field: [{"index": index, flag: False} for index in indices]}),
        )


@pytest.mark.parametrize(
    "verdict,ids",
    [
        ("supported", []),
        ("supported", ["invented"]),
        ("supported", ["doc-1", "invented"]),
        ("unsupported", ["invented"]),
        ("contradicted", ["invented"]),
    ],
)
def test_supported_requires_sources_and_all_citations_must_exist(case, answer, verdict, ids):
    with pytest.raises(ValueError, match="источник"):
        run_judge(
            case,
            answer,
            result_payload(
                answer_claims=[
                    {
                        "text": "Матрица утверждена.",
                        "verdict": verdict,
                        "evidence_ids": ids,
                    }
                ]
            ),
        )


def test_empty_gold_and_explicit_abstention_are_valid_without_factual_claims(case, answer):
    case.update(expected_claims=[], forbidden_claims=[], expect_abstention=True)
    case.pop("conversation_context")
    answer.update(answer="В источниках не указан владелец решения.", evidence_sources=[])
    result, _ = run_judge(
        case,
        answer,
        result_payload(
            expected_claims=[],
            forbidden_claims=[],
            answer_claims=[],
            abstained=True,
        ),
    )
    assert result.abstained
    assert result.answer_claims == []


def test_expected_abstention_is_not_copied_over_judge_assessment(case, answer):
    case["expect_abstention"] = True
    result, _ = run_judge(case, answer, result_payload(abstained=False))
    assert not result.abstained


@pytest.mark.parametrize(
    "path", [(), ("expected_claims", 0), ("forbidden_claims", 0), ("answer_claims", 0)]
)
def test_result_rejects_extra_fields_at_each_object_level(path):
    payload = result_payload()
    target = payload
    for key in path:
        target = target[key]
    target["untrusted_verification"] = "passed"
    with pytest.raises(ValidationError) as caught:
        AgentJudgeResult.model_validate(payload)
    assert any(
        error["type"] == "extra_forbidden" and error["loc"] == (*path, "untrusted_verification")
        for error in caught.value.errors()
    )
