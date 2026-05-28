import json

import pytest

from sdm.evaluation.runner import (
    Case,
    export_reports,
    load_cases,
    parse_sse,
    retrieval_scores,
    validate_citations,
    validate_retrieval,
)


def case_data(**overrides):
    return {
        "id": "one",
        "project_id": "P1",
        "question": "Вопрос?",
        "as_of": "2026-06-19",
        "entity_id": None,
        "category": "fact",
        "required_evidence_groups": [["S1"]],
        "expected_claims": ["факт"],
        "forbidden_claims": [],
        "expect_abstention": False,
        "run_qa": True,
        **overrides,
    }


def test_disjunctive_groups_and_single_group_mrr():
    items = [{"id": "P1:tasks:S2", "source_id": "S2"}, {"id": "P1:tasks:S1", "source_id": "S1"}]
    assert retrieval_scores([["S1", "S2"], ["S3"]], items) == {
        "group_recall_at_8": 0.5,
        "mrr": None,
    }
    assert retrieval_scores([["S1"]], items) == {"group_recall_at_8": 1, "mrr": 0.5}
    assert retrieval_scores([["S3"]], items) == {"group_recall_at_8": 0, "mrr": 0}
    assert retrieval_scores([["P1:tasks:S2"]], items)["mrr"] == 1


def test_absent_gold_or_abstention_is_na_not_zero():
    assert retrieval_scores([], []) == {"group_recall_at_8": None, "mrr": None}
    assert retrieval_scores([["S1"]], [], True) == {"group_recall_at_8": None, "mrr": None}


@pytest.mark.parametrize(
    "records",
    [
        [case_data(), case_data()],
        [case_data(required_evidence_groups=[["IMPOSSIBLE"]])],
        [case_data(required_evidence_groups=[["S2"]])],
        [case_data(required_evidence_groups=[[]])],
        [case_data(as_of="2026-06-20")],
    ],
)
def test_dataset_rejects_duplicates_impossible_cross_project_and_future(tmp_path, records):
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records))
    with pytest.raises(ValueError):
        load_cases(path, {"S1": "P1", "S2": "P2"})


def test_sse_unicode_keeps_answer_but_discards_reasoning_and_provider_data():
    payload = {
        "answer": {"answer": "Подтверждено"},
        "metrics": {"duration_ms": 12, "llm_calls": [{"raw": "secret"}], "total_tokens": 9},
    }
    lines = [
        "event: reasoning_delta",
        "data: secret reasoning",
        "",
        "event: raw_llm",
        "data: secret",
        "",
        "event: final",
        "data: " + json.dumps(payload, ensure_ascii=False),
        "",
    ]
    result = parse_sse(iter(lines))
    assert result["answer"]["answer"] == "Подтверждено"
    assert result["reasoning_delta_count"] == 1
    assert result["metrics"] == {"duration_ms": 12, "total_tokens": 9}
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "lines",
    [
        ["event: error", 'data: {"message":"secret"}', ""],
        [],
        ["event: final", "data: not json", ""],
    ],
)
def test_sse_errors_or_missing_final_fail(lines):
    with pytest.raises(ValueError):
        parse_sse(lines)


def test_citation_aliases_must_exist_and_match_project():
    answer = {
        "evidence_ids": ["t1"],
        "evidence_sources": [{"id": "tool:1", "reference": "T1", "data": {"project_id": "P1"}}],
    }
    validate_citations(answer, "P1")
    with pytest.raises(ValueError):
        validate_citations({**answer, "evidence_ids": ["FAKE"]}, "P1")
    with pytest.raises(ValueError):
        validate_citations(answer, "P2")


@pytest.mark.parametrize(
    "change",
    [
        {"project_id": "P2"},
        {"occurred_at": "2026-06-20T00:00:00"},
        {"entity_id": "T2"},
        {"id": "FAKE"},
    ],
)
def test_retrieval_enforces_isolation_date_entity_and_known_ids(change):
    case = Case.model_validate(case_data(entity_id="T1"))
    item = {"id": "P1:tasks:S1", "source_id": "S1", "project_id": "P1", "entity_id": "T1", **change}
    with pytest.raises(ValueError):
        validate_retrieval(
            case,
            {"project_id": "P1", "as_of_date": "2026-06-19", "items": [item]},
            {"S1": "P1", "P1:tasks:S1": "P1"},
        )


def test_html_is_escaped_and_qa_remains_unreviewed(tmp_path):
    export_reports(
        [
            {
                "case_id": "<script>alert(1)</script>",
                "category": "x",
                "mode": "dense",
                "duration_ms": 1,
                "group_recall_at_8": None,
                "mrr": None,
                "failure": None,
            }
        ],
        tmp_path,
    )
    html = (tmp_path / "report.html").read_text()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "QA is unreviewed" in html
    assert "caching confounds latency differences" in html
    assert "not a causal comparison" in html
    assert "reviewer" in (tmp_path / "manual_review.csv").read_text()


def test_cli_persists_transport_failure_and_returns_nonzero(tmp_path, monkeypatch):
    import httpx
    import sdm.evaluation.runner as runner

    dataset = tmp_path / "gold.jsonl"
    dataset.write_text(json.dumps(case_data(run_qa=False)))
    monkeypatch.setattr(runner, "corpus_catalog", lambda *args: ({"S1": "P1"}, []))
    monkeypatch.setattr(runner, "metadata", lambda *args: {"schema_version": 1})
    original_client = httpx.Client
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, json={"error": "private server details"})
    )
    monkeypatch.setattr(
        runner.httpx, "Client", lambda **kwargs: original_client(transport=transport, **kwargs)
    )
    output = tmp_path / "run"
    assert runner.main(["--dataset", str(dataset), "--output", str(output), "--skip-qa"]) == 1
    records = [json.loads(line) for line in (output / "raw.jsonl").read_text().splitlines()]
    assert len(records) == 3
    assert all(record["failure"] == "HTTPStatusError" for record in records)
    assert "private server details" not in (output / "raw.jsonl").read_text()
    assert (output / "summary.csv").exists()


def test_structural_summary_citation_is_valid_without_document_gold():
    answer = {
        "answer": "Статус проекта из сводки",
        "evidence_ids": ["P007"],
        "evidence_sources": [
            {
                "id": "get_project_summary:P007",
                "tool": "get_project_summary",
                "source_type": "project",
                "reference": "P007",
                "data": {"project_id": "P007", "blocked_count": 3},
            }
        ],
    }
    validate_citations(answer, "P007")
    assert "correctness" not in answer


def test_manual_review_keeps_all_judgments_blank(tmp_path):
    import pandas as pd

    record = {
        "case_id": "one",
        "case": case_data(),
        "category": "fact",
        "mode": "qa",
        "duration_ms": 1,
        "failure": None,
        "answer": {"answer": "Факт"},
    }
    export_reports([record], tmp_path)
    review = pd.read_csv(tmp_path / "manual_review.csv", keep_default_na=False)
    assert review.loc[0, "run_id"] == tmp_path.name
    for column in [
        "reviewer",
        "support",
        "correctness",
        "abstention",
        "reviewed_at",
        "source_exists",
        "source_entails_claim",
        "required_facts_covered",
        "no_forbidden_claims",
        "abstention_correct",
        "project_and_date_correct",
        "label_gap",
        "verdict",
        "notes",
    ]:
        assert review.loc[0, column] == ""


def test_catalog_uses_single_project_scenario_and_hashes_sources():
    from pathlib import Path
    from sdm.evaluation.runner import corpus_catalog

    root = Path(__file__).resolve().parents[1]
    catalog, files = corpus_catalog(root, root / "data/interview")
    assert set(catalog.values()) == {"P007"}
    assert "P001" not in catalog
    assert catalog["P007:projects:P007"] == "P007"
    assert catalog["P007:tasks:T701"] == "P007"
    assert catalog["P007:tasks:T702"] == "P007"
    assert root / "scripts/generate_interview_data.py" in files
    assert root / "scripts/demo_schema.py" in files
    for name in ["scenario.json", "conversations.json", "task-comments.json"]:
        assert root / "data/interview" / name in files
    assert "B007" not in catalog  # budgets are not indexed evidence chunks


@pytest.mark.parametrize("key", ["external_id", "document_id"])
def test_retrieval_entity_filter_accepts_exact_metadata_aliases(key):
    case = Case.model_validate(case_data(entity_id="EXTERNAL"))
    payload = {
        "project_id": "P1",
        "as_of_date": "2026-06-19",
        "items": [
            {
                "id": "P1:tasks:S1",
                "source_id": "S1",
                "project_id": "P1",
                "entity_id": "T1",
                "metadata": {key: "EXTERNAL"},
            }
        ],
    }
    catalog = {"S1": "P1", "P1:tasks:S1": "P1"}
    validate_retrieval(case, payload, catalog)
    payload["items"][0]["metadata"][key] = "EXTERNAL-SUFFIX"
    with pytest.raises(ValueError, match="entity-filter"):
        validate_retrieval(case, payload, catalog)


def test_sse_retains_actual_stream_metrics_snapshot_without_raw_llm_content():
    from sdm.agents.streaming import StreamMetrics

    metrics = StreamMetrics()
    metrics.record("stage_finished", {"stage": "run_tools", "status": "success", "duration_ms": 15})
    metrics.record(
        "tool_finished",
        {
            "name": "search_project_evidence",
            "status": "success",
            "duration_ms": 12,
            "call_id": "ignored",
        },
    )
    metrics.record(
        "llm_finished",
        {
            "ttft_ms": 7,
            "usage": {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13},
            "raw": "secret reasoning",
        },
    )
    snapshot = metrics.snapshot()
    payload = {"answer": {"answer": "Ответ"}, "metrics": snapshot}
    parsed = parse_sse(["event: final", "data: " + json.dumps(payload), ""])["metrics"]
    assert parsed["usage"] == {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13}
    assert parsed["stages_ms"] == {"run_tools": 15}
    assert parsed["tools"] == [
        {"name": "search_project_evidence", "status": "success", "duration_ms": 12}
    ]
    assert parsed["ttft_ms"] == 7
    assert "secret" not in json.dumps(parsed)
    assert "llm_calls" not in parsed


def test_summary_separates_failure_latency_and_qa_ttft(tmp_path):
    import pandas as pd

    records = [
        {
            "case_id": str(i),
            "case": case_data(),
            "mode": "qa",
            "category": "fact",
            "duration_ms": duration,
            "failure": failure,
            "metrics": {"ttft_ms": ttft},
        }
        for i, (duration, failure, ttft) in enumerate(
            [(100, None, 10), (200, None, 20), (10000, "Timeout", 9000)]
        )
    ]
    export_reports(records, tmp_path)
    summary = pd.read_csv(tmp_path / "summary.csv").iloc[0]
    assert summary["success_duration_p50_ms"] == 150
    assert summary["failure_duration_p50_ms"] == 10000
    assert summary["qa_ttft_p50_ms"] == 15
    assert summary["qa_ttft_p95_ms"] == 19.5


@pytest.mark.parametrize("interrupt_after", [0, 1])
def test_keyboard_interrupt_exports_completed_rows_and_marks_incomplete(
    tmp_path, monkeypatch, interrupt_after
):
    import httpx
    import sdm.evaluation.runner as runner

    dataset = tmp_path / "gold.jsonl"
    dataset.write_text(json.dumps(case_data(run_qa=False)))
    monkeypatch.setattr(runner, "corpus_catalog", lambda *args: ({"S1": "P1"}, []))
    monkeypatch.setattr(runner, "metadata", lambda *args: {"schema_version": 1})
    original_client = httpx.Client
    calls = 0

    def respond(request):
        nonlocal calls
        if calls == interrupt_after:
            raise KeyboardInterrupt()
        calls += 1
        return httpx.Response(
            200, json={"project_id": "P1", "as_of_date": "2026-06-19", "items": []}
        )

    monkeypatch.setattr(
        runner.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    output = tmp_path / "run"
    assert runner.main(["--dataset", str(dataset), "--output", str(output)]) == 130
    meta = json.loads((output / "metadata.json").read_text())
    assert meta["incomplete"] is True
    assert meta["completed_records"] == interrupt_after
    assert (output / "report.html").exists()


def test_qa_limit_and_case_filter_apply_without_limiting_retrieval(tmp_path, monkeypatch):
    import httpx
    import sdm.evaluation.runner as runner

    dataset = tmp_path / "gold.jsonl"
    dataset.write_text("\n".join(json.dumps(case_data(id=str(i))) for i in range(3)))
    monkeypatch.setattr(runner, "corpus_catalog", lambda *args: ({"S1": "P1"}, []))
    monkeypatch.setattr(runner, "metadata", lambda *args: {"schema_version": 1})
    original_client = httpx.Client
    calls = []

    def respond(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, text='event: final\ndata: {"answer":{"answer":"Ответ"}}\n\n')
        return httpx.Response(
            200, json={"project_id": "P1", "as_of_date": "2026-06-19", "items": []}
        )

    monkeypatch.setattr(
        runner.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    output = tmp_path / "run"
    assert (
        runner.main(
            [
                "--dataset",
                str(dataset),
                "--output",
                str(output),
                "--qa-limit",
                "1",
                "--case-id",
                "1",
                "--case-id",
                "2",
            ]
        )
        == 0
    )
    assert calls.count("GET") == 6
    assert calls.count("POST") == 1
    meta = json.loads((output / "metadata.json").read_text())
    assert meta["incomplete"] is False
    assert meta["qa_case_count"] == 1


def test_public_metadata_citation_alias_is_valid_but_private_match_keys_are_not():
    source = {
        "id": "source",
        "reference": "T701",
        "data": {"project_id": "P007", "metadata": {"external_id": "ВЕД-701"}},
        "_match_keys": ["FAKE"],
    }
    validate_citations({"evidence_ids": ["вед-701"], "evidence_sources": [source]}, "P007")
    with pytest.raises(ValueError):
        validate_citations({"evidence_ids": ["FAKE"], "evidence_sources": [source]}, "P007")


@pytest.mark.parametrize(
    "configured,expected",
    [
        (
            [],
            [["dense", "bm25", "hybrid"], ["bm25", "hybrid", "dense"], ["hybrid", "dense", "bm25"]],
        ),
        (["hybrid", "bm25"], [["hybrid", "bm25"], ["bm25", "hybrid"], ["hybrid", "bm25"]]),
        (["bm25"], [["bm25"], ["bm25"], ["bm25"]]),
    ],
)
def test_cli_rotates_requested_modes_records_actual_order_and_preserves_diagnostics(
    tmp_path, monkeypatch, configured, expected
):
    import httpx
    import sdm.evaluation.runner as runner

    dataset = tmp_path / "gold.jsonl"
    dataset.write_text("\n".join(json.dumps(case_data(id=str(i), run_qa=False)) for i in range(3)))
    catalog = {"S1": "P1", "P1:tasks:S1": "P1"}
    monkeypatch.setattr(runner, "corpus_catalog", lambda *args: (catalog, []))
    monkeypatch.setattr(runner, "metadata", lambda *args: {"schema_version": 1})
    calls = []
    diagnostics = {
        "dense_rank": 2,
        "dense_score": 0.7,
        "bm25_rank": 1,
        "bm25_score": 4.2,
        "fusion_score": 1 / 62 + 1 / 61,
    }

    def respond(request):
        mode = request.url.params["ranking"]
        calls.append(mode)
        return httpx.Response(
            200,
            json={
                "project_id": "P1",
                "as_of_date": "2026-06-19",
                "ranking": mode,
                "candidate_limit": 40,
                "items": [
                    {
                        "id": "P1:tasks:S1",
                        "source_id": "S1",
                        "project_id": "P1",
                        "retrieval": diagnostics,
                    }
                ],
            },
        )

    client = httpx.Client
    monkeypatch.setattr(
        runner.httpx, "Client", lambda **kw: client(transport=httpx.MockTransport(respond), **kw)
    )
    output = tmp_path / "run"
    argv = ["--dataset", str(dataset), "--output", str(output), "--skip-qa"]
    if configured:
        argv += ["--retrieval-modes", *configured]
    assert runner.main(argv) == 0
    assert calls == [mode for order in expected for mode in order]
    meta = json.loads((output / "metadata.json").read_text())
    assert [row["modes"] for row in meta["planned_mode_order"]] == expected
    assert [row["mode"] for row in meta["actual_request_order"]] == calls
    assert meta["retrieval_configuration"]["candidate_limit"] == 40
    assert meta["retrieval_configuration"]["rrf_k"] == 60
    assert meta["completed_records"] == len(calls)
    assert meta["incomplete"] is False
    records = [json.loads(line) for line in (output / "raw.jsonl").read_text().splitlines()]
    assert [row["request_index"] for row in records] == list(range(len(calls)))
    assert all(row["retrieval"]["items"][0]["retrieval"] == diagnostics for row in records)
    assert [row["mode_position"] for row in records] == [
        index for order in expected for index in range(len(order))
    ]


@pytest.mark.parametrize("modes", [["dense", "dense"], ["dense_lexical"], ["unknown"]])
def test_cli_rejects_duplicate_or_unsupported_modes_before_output_creation(tmp_path, modes):
    from sdm.evaluation.runner import main

    output = tmp_path / "run"
    with pytest.raises(SystemExit) as exc:
        main(["--dataset", "missing.jsonl", "--output", str(output), "--retrieval-modes", *modes])
    assert exc.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize("applied,fallback", [(True, None), (False, "TimeoutError"), (False, None)])
def test_optin_hybrid_rerank_requests_shortlist_and_records_applied_or_fallback(
    tmp_path, monkeypatch, applied, fallback
):
    import httpx
    import pandas as pd
    import sdm.evaluation.runner as runner
    from sdm.agents.tools.retrieval.config import RerankSettings

    dataset = tmp_path / "gold.jsonl"
    dataset.write_text(json.dumps(case_data(run_qa=False)))
    monkeypatch.setattr(runner, "corpus_catalog", lambda *args: ({"S1": "P1"}, []))
    monkeypatch.setattr(runner, "metadata", lambda *args: {"schema_version": 1})
    monkeypatch.setattr(
        RerankSettings, "from_env", classmethod(lambda cls: cls(enabled=False, candidates=16))
    )
    original_client = httpx.Client
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200, json={"project_id": "P1", "as_of_date": "2026-06-19", "items": []}
        )

    def rerank(payload, settings):
        assert settings.enabled is True
        assert settings.candidates == 16
        return {
            **payload,
            "rerank_applied": applied,
            "rerank_fallback": fallback,
        }

    monkeypatch.setattr(runner, "rerank_payload", rerank)
    monkeypatch.setattr(
        runner.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    output = tmp_path / "run"
    assert (
        runner.main(
            [
                "--dataset",
                str(dataset),
                "--output",
                str(output),
                "--retrieval-modes",
                "hybrid_rerank",
                "--skip-qa",
            ]
        )
        == 0
    )
    assert requests[0].url.params["ranking"] == "hybrid"
    assert requests[0].url.params["limit"] == "16"
    record = json.loads((output / "raw.jsonl").read_text())
    assert record["mode"] == "hybrid_rerank"
    assert record["rerank_applied"] is applied
    assert record["failure"] is None
    summary = pd.read_csv(output / "summary.csv").iloc[0]
    assert summary["rerank_fallback_count"] == int(fallback is not None)
    meta = json.loads((output / "metadata.json").read_text())
    assert meta["retrieval_configuration"]["hybrid_rerank"]["backend_candidate_limit"] == 60
