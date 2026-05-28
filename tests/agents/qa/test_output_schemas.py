"""Схемы результата отклоняют лишние поля и сохраняют значения по умолчанию."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from sdm.agents.project_qa.evidence.models import (
    MAX_ANSWER_CLAIMS,
    AnswerDraft,
    ClaimReview,
    DraftClaim,
    EvidenceQuote,
    EvidenceReview,
)
from sdm.agents.project_qa.evidence.validation import grounded_draft_model
from sdm.agents.project_qa.nodes.draft import draft_answer_node
from sdm.agents.project_qa.nodes.verify import verify_answer_node
from sdm.agents.project_qa.schemas import ProjectQuestionLLMAnswer, RequestRoute
from sdm.agents.project_qa.state import ProjectQuestionState

CASES = [
    (ProjectQuestionLLMAnswer, {"answer": "Подтверждённый ответ", "evidence_ids": ["task:T1"]}),
    (RequestRoute, {"intent": "project_question", "reason": "Вопрос по проекту"}),
]


def object_paths(value, path=()):
    """Перебирает все заполненные объекты, в том числе вложенные в списки."""
    if isinstance(value, dict):
        yield path
        for key, item in value.items():
            yield from object_paths(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from object_paths(item, (*path, index))


UNKNOWN_FIELD_CASES = [
    pytest.param(model, payload, path, id=f"{model.__name__}:{'.'.join(map(str, path)) or 'root'}")
    for model, payload in CASES
    for path in object_paths(payload)
]


@pytest.mark.parametrize("model,payload,path", UNKNOWN_FIELD_CASES)
def test_unknown_tool_argument_fields_fail_at_every_object_level(model, payload, path):
    invalid = deepcopy(payload)
    target = invalid
    for part in path:
        target = target[part]
    target["unadvertised_field"] = "must not be discarded"
    with pytest.raises(ValidationError) as caught:
        model.model_validate(invalid)
    assert any(
        error["type"] == "extra_forbidden" and error["loc"] == (*path, "unadvertised_field")
        for error in caught.value.errors()
    )


@pytest.mark.parametrize(
    "model,payload", CASES, ids=lambda value: getattr(value, "__name__", "input")
)
def test_valid_arguments_keep_defaults(model, payload):
    result = model.model_validate(payload)
    if model is ProjectQuestionLLMAnswer:
        assert result.used_tools == []
        assert result.suggested_questions == []
    else:
        assert result.intent == "project_question"


@pytest.mark.parametrize(
    "model,payload", CASES, ids=lambda value: getattr(value, "__name__", "input")
)
def test_advertised_tool_schema_forbids_additional_properties_in_nested_models(model, payload):
    schema = model.model_json_schema()
    for path in object_paths(schema):
        node = schema
        for part in path:
            node = node[part]
        if node.get("type") == "object":
            assert node["additionalProperties"] is False


def test_dynamic_draft_schema_preserves_required_fields_descriptions_and_strict_objects():
    model = grounded_draft_model(
        [
            {"id": "observed-1", "data": {"text": "Пилот не начат."}},
            {"id": "observed-2", "data": {"text": "Нужно согласование."}},
        ]
    )
    schema = model.model_json_schema()
    claim_schema = schema["$defs"][schema["properties"]["claims"]["items"]["$ref"].split("/")[-1]]
    quote_schema = schema["$defs"][
        claim_schema["properties"]["evidence"]["items"]["$ref"].split("/")[-1]
    ]
    for base, advertised in [
        (AnswerDraft, schema),
        (DraftClaim, claim_schema),
        (EvidenceQuote, quote_schema),
    ]:
        assert advertised["additionalProperties"] is False
        assert set(advertised["required"]) == set(base.model_fields)
        for name, field in base.model_fields.items():
            assert field.description
            assert advertised["properties"][name]["description"] == field.description
    assert quote_schema["properties"]["source_id"]["enum"] == ["observed-1", "observed-2"]
    with pytest.raises(ValidationError) as caught:
        model.model_validate({"claims": []})
    assert any(
        error["loc"] == ("unanswered_aspects",) and error["type"] == "missing"
        for error in caught.value.errors()
    )
    assert model.model_validate({"claims": [], "unanswered_aspects": []}).claims == []


def test_draft_and_review_limits_accept_four_claims_and_reject_a_fifth():
    dynamic = grounded_draft_model([{"id": "observed", "data": {"text": "Есть основание."}}])
    claim = {
        "text": "Есть основание.",
        "evidence": [{"source_id": "observed", "quote": "Есть основание."}],
    }
    assert MAX_ANSWER_CLAIMS == 4
    for model in (AnswerDraft, dynamic):
        assert model.model_json_schema()["properties"]["claims"]["maxItems"] == 4
        assert (
            len(model.model_validate({"claims": [claim] * 4, "unanswered_aspects": []}).claims) == 4
        )
        with pytest.raises(ValidationError) as caught:
            model.model_validate({"claims": [claim] * 5, "unanswered_aspects": []})
        assert any(
            error["loc"] == ("claims",) and error["type"] == "too_long"
            for error in caught.value.errors()
        )
    assert EvidenceReview.model_json_schema()["properties"]["claims"]["maxItems"] == 4
    index_schema = ClaimReview.model_json_schema()["properties"]["claim_index"]
    assert (index_schema["minimum"], index_schema["maximum"]) == (0, 3)
    payload = {
        "claims": [{"claim_index": index, "verdict": "supported"} for index in range(4)],
        "missing_aspects": [],
        "searches": [],
        "context_source_ids": [],
    }
    assert len(EvidenceReview.model_validate(payload).claims) == 4
    with pytest.raises(ValidationError):
        ClaimReview(claim_index=4, verdict="supported")
    with pytest.raises(ValidationError) as caught:
        EvidenceReview.model_validate(
            {**payload, "claims": payload["claims"] + [payload["claims"][0]]}
        )
    assert any(
        error["loc"] == ("claims",) and error["type"] == "too_long"
        for error in caught.value.errors()
    )


def test_fifth_draft_claim_stops_graph_before_any_verifier_request():
    async def parse_pydantic(*, response_model, **kwargs):
        assert issubclass(response_model, AnswerDraft), (
            "Проверка не должна получать невалидный черновик"
        )
        return response_model.model_validate(
            {
                "claims": [
                    {
                        "text": "Есть основание.",
                        "evidence": [{"source_id": "observed", "quote": "Есть основание."}],
                    }
                ]
                * 5,
                "unanswered_aspects": [],
            }
        )

    llm = SimpleNamespace(parse_pydantic=AsyncMock(side_effect=parse_pydantic))
    graph = StateGraph(ProjectQuestionState)
    graph.add_node("draft", draft_answer_node(llm=llm, temperature=0))
    graph.add_node("verify", verify_answer_node(llm=llm))
    graph.add_edge(START, "draft")
    graph.add_edge("draft", "verify")
    graph.add_edge("verify", END)
    with patch("sdm.agents.streaming.get_stream_writer", return_value=lambda _: None):
        with pytest.raises(ValidationError) as caught:
            asyncio.run(
                graph.compile().ainvoke(
                    {
                        "project_id": "P007",
                        "question": "Есть основание?",
                        "as_of": "2026-06-19",
                        "used_tools": ["search_project_evidence"],
                        "tool_sources": [{"id": "observed", "data": {"text": "Есть основание."}}],
                    }
                )
            )
    assert any(
        error["loc"] == ("claims",) and error["type"] == "too_long"
        for error in caught.value.errors()
    )
    assert llm.parse_pydantic.await_count == 1
