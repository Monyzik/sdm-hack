import asyncio
import json
from pathlib import Path

import httpx
import pytest

from sdm.evaluation.agent import AgentCase, load_agent_cases, run_agent_case


def case(**changes):
    return AgentCase.model_validate(
        {
            "id": "A1",
            "project_id": "P007",
            "as_of": "2026-06-19",
            "question": "А кто принимает результат?",
            "category": "dialogue",
            "expected_claims": ["Анна"],
            "forbidden_claims": [],
            "expect_abstention": False,
            "intent": "project_question",
            "conversation_context": [{"role": "user", "content": "Обсуждаем маскирование."}],
            **changes,
        }
    )


def event(name, data):
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def run_with_response(body, *, mode="standard", status=200):
    requests = []

    async def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(status, text=body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await run_agent_case(client, "http://agent", case(), mode, 3)

    return asyncio.run(run()), requests


@pytest.mark.parametrize("mode,verify", [("standard", False), ("verified", True)])
def test_real_request_modes_history_trace_and_no_reasoning(mode, verify):
    body = (
        event("reasoning_delta", {"text": "PRIVATE_REASONING"})
        + event("llm_started", {"operation": "RequestRoute"})
        + event("llm_retry", {"operation": "RequestRoute", "attempt": 2})
        + event("llm_started", {"operation": "RequestRoute"})
        + event(
            "llm_finished",
            {
                "operation": "RequestRoute",
                "status": "completed",
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 2,
                    "total_tokens": 14,
                    "raw": "PRIVATE_USAGE",
                },
            },
        )
        + event(
            "tool_started",
            {
                "call_id": "t1",
                "name": "get_evidence_context",
                "args": {"evidence_id": "DOC1", "neighbors": 1},
            },
        )
        + event(
            "tool_finished",
            {
                "call_id": "t1",
                "name": "get_evidence_context",
                "status": "success",
                "duration_ms": 2,
            },
        )
        + event("answer_delta", {"text": "Анна"})
        + event(
            "final", {"answer": {"answer": "Анна"}, "metrics": {"total_tokens": 14, "ttft_ms": 5}}
        )
    )
    record, requests = run_with_response(body, mode=mode)
    assert requests == [
        {
            "question": case().question,
            "as_of": "2026-06-19",
            "verify_claims": verify,
            "conversation_context": [{"role": "user", "content": "Обсуждаем маскирование."}],
        }
    ]
    assert record["failure"] is None
    assert record["answer"]["answer"] == "Анна"
    assert record["first_answer_ms"] is not None
    assert record["llm_call_count"] == 2
    assert record["format_retries"] == 1
    assert record["tools"][0]["status"] == "success"
    assert record["tools"][0]["args"] == {"evidence_id": "DOC1", "neighbors": 1}
    assert record["metrics"]["total_tokens"] == 14
    assert "PRIVATE" not in json.dumps(record)


@pytest.mark.parametrize("tail", ["", event("error", {"message": "PRIVATE_PROVIDER_ERROR"})])
def test_failure_keeps_completed_work_without_becoming_an_abstention(tail):
    body = (
        event(
            "tool_started",
            {"call_id": "t1", "name": "search_project_evidence", "args": {"query": "маскирование"}},
        )
        + event("tool_finished", {"call_id": "t1", "status": "success", "duration_ms": 4})
        + event("llm_finished", {"operation": "Draft", "usage": {"total_tokens": 100}})
        + tail
    )
    record, _ = run_with_response(body)
    assert record["failure"] == "ValueError"
    assert record["answer"] is None
    assert record["judge"] is None
    assert record["first_answer_ms"] is None
    assert record["tools"][0]["status"] == "success"
    assert record["metrics"]["total_tokens"] == 100
    assert "PRIVATE" not in json.dumps(record)


def test_http_error_does_not_publish_provider_body():
    record, _ = run_with_response("PRIVATE_SERVER_DATA", status=502)
    assert record["failure"] == "HTTPStatusError"
    assert record["http_status"] == 502
    assert "PRIVATE" not in json.dumps(record)


def test_duplicate_final_is_failed_protocol():
    final = event("final", {"answer": {"answer": "Анна"}})
    record, _ = run_with_response(final + final)
    assert record["failure"] == "ValueError"


def test_dataset_is_fixed_and_reuses_gold_without_changing_it(tmp_path):
    path = Path("data/interview/agent_cases.jsonl")
    cases = load_agent_cases(path)
    assert len(cases) == 16
    original = {
        row["id"]: row
        for line in Path("data/interview/eval_cases.jsonl").read_text().splitlines()
        if (row := json.loads(line))
    }
    for row in cases[:9]:
        gold = original[row.gold_case_id]
        assert row.expected_claims == gold["expected_claims"]
        assert row.forbidden_claims == gold["forbidden_claims"]
        assert row.expect_abstention == gold["expect_abstention"]
    assert len([row for row in cases if row.conversation_context]) == 2
    assert len([row for row in cases if row.required_tool_calls]) == 2
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text(cases[0].model_dump_json() + "\n" + cases[0].model_dump_json())
    with pytest.raises(ValueError):
        load_agent_cases(duplicate)


def test_empty_dataset_is_rejected(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    with pytest.raises(ValueError):
        load_agent_cases(empty)
