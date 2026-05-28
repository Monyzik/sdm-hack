from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
import pandas as pd
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from . import SCHEMA_VERSION

RETRIEVAL_MODES = ("dense", "bm25", "hybrid")


def retrieval_mode_order(modes: list[str], case_index: int) -> list[str]:
    """Rotate the configured order over selected cases; QA runs after retrieval."""
    offset = case_index % len(modes)
    return modes[offset:] + modes[:offset]


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    as_of: date
    entity_id: str | None = None
    category: str = Field(min_length=1)
    required_evidence_groups: list[list[str]]
    expected_claims: list[str]
    forbidden_claims: list[str]
    expect_abstention: StrictBool
    run_qa: StrictBool


def corpus_catalog(root: Path, document_root: Path):
    """Source aliases and project ownership from local fixtures, without provider calls."""
    from sdm.backend.services.document_evidence import load_document_evidence, load_manifest
    from scripts.generate_interview_data import build_records

    catalog = {}
    files = sorted((root / "data/demo").glob("*.csv"))
    indexed_tables = {
        "projects",
        "tasks",
        "task_comments",
        "task_history",
        "risks",
        "communications",
        "communication_messages",
        "task_dependencies",
        "dependencies",
        "decisions",
        "change_requests",
        "budget_line_items",
    }
    for table, rows in build_records(document_root).items():
        if table not in indexed_tables:
            continue
        for row in rows:
            source = row.get("id")
            project = source if table == "projects" else row.get("project_id")
            if source and project:
                catalog[source] = project
                catalog[f"{project}:{table}:{source}"] = project
    manifest = load_manifest(document_root)
    files += [
        root / "scripts/generate_interview_data.py",
        root / "scripts/demo_schema.py",
        document_root / "scenario.json",
        document_root / "conversations.json",
        document_root / "task-comments.json",
        document_root / "manifest.json",
        *[document_root / doc["path"] for doc in manifest],
    ]
    for project in sorted({doc["project_id"] for doc in manifest}):
        for item in load_document_evidence(project, document_root):
            catalog[item.source_id] = project
            catalog[f"{project}:documents:{item.source_id}"] = project
    return catalog, files


def load_cases(path: Path, catalog: dict[str, str]) -> list[Case]:
    cases = [
        Case.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    seen = set()
    for case in cases:
        if case.id in seen:
            raise ValueError(f"Duplicate case id: {case.id}")
        seen.add(case.id)
        if case.as_of > date(2026, 6, 19):
            raise ValueError(f"Unexpected snapshot date in {case.id}")
        for group in case.required_evidence_groups:
            if not group or len(group) != len(set(group)):
                raise ValueError(f"Empty or duplicate evidence alternatives in {case.id}")
            for identifier in group:
                if catalog.get(identifier) != case.project_id:
                    raise ValueError(
                        f"Unknown or cross-project gold source {identifier} in {case.id}"
                    )
    if not cases:
        raise ValueError("Empty dataset")
    return cases


def retrieval_scores(groups: list[list[str]], items: list[dict], abstain=False):
    if abstain or not groups:
        return {"group_recall_at_8": None, "mrr": None}
    aliases = [{str(item.get("id", "")), str(item.get("source_id", ""))} for item in items[:8]]
    ranks = [
        next((i + 1 for i, ids in enumerate(aliases) if ids.intersection(group)), None)
        for group in groups
    ]
    return {
        "group_recall_at_8": sum(rank is not None for rank in ranks) / len(groups),
        "mrr": (1 / ranks[0] if ranks[0] else 0.0) if len(groups) == 1 else None,
    }


def validate_retrieval(case: Case, payload: dict, catalog: dict[str, str], *, max_items: int = 8):
    if (
        payload.get("project_id") != case.project_id
        or payload.get("as_of_date") != case.as_of.isoformat()
    ):
        raise ValueError("Retrieval project/date envelope violation")
    items = payload.get("items")
    if not isinstance(items, list) or len(items) > max_items:
        raise ValueError("Invalid top-8 retrieval payload")
    seen = set()
    for item in items:
        identifier = item.get("id")
        if identifier in seen:
            raise ValueError("Duplicate retrieval ID")
        seen.add(identifier)
        if item.get("project_id") != case.project_id or catalog.get(identifier) != case.project_id:
            raise ValueError("Unknown or cross-project retrieval ID")
        if catalog.get(item.get("source_id")) != case.project_id:
            raise ValueError("Unknown retrieval source ID")
        occurred = item.get("occurred_at")
        if occurred and date.fromisoformat(occurred[:10]) > case.as_of:
            raise ValueError("Retrieval future-date violation")
        if case.entity_id and case.entity_id not in {
            item.get("entity_id"),
            item.get("source_id"),
            item.get("linked_task_id"),
            (item.get("metadata") or {}).get("external_id"),
            (item.get("metadata") or {}).get("document_id"),
        }:
            raise ValueError("Retrieval entity-filter violation")


def sanitize_metrics(metrics):
    """Keep measured numbers and known stage/tool labels, never provider content."""

    def numbers(values, keys):
        return {
            key: value
            for key, value in values.items()
            if key in keys and type(value) in (int, float)
        }

    usage_keys = {
        "input_tokens",
        "output_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_tokens",
        "reasoning_tokens",
    }
    result = numbers(metrics, usage_keys | {"duration_ms", "ttft_ms", "tool_calls"})
    if isinstance(metrics.get("usage"), dict):
        result["usage"] = numbers(metrics["usage"], usage_keys)
    if isinstance(metrics.get("stages_ms"), dict):
        result["stages_ms"] = numbers(
            metrics["stages_ms"],
            {
                "route_request",
                "request_project_context",
                "run_tools",
                "run_recovery_tools",
                "select_tools",
                "draft_answer",
                "verify_answer",
                "recover_evidence",
                "finalize_answer",
                "rerank",
            },
        )
    allowed_tools = {
        "get_project_summary",
        "get_problem_context",
        "get_critical_tasks",
        "search_tasks",
        "search_risks",
        "search_communications",
        "search_decisions",
        "search_dependencies",
        "search_project_evidence",
        "get_evidence_context",
        "get_budget",
        "get_resource_rates",
        "get_task_dependency_graph",
        "calculate_delay_cost",
    }
    if isinstance(metrics.get("tools"), list):
        result["tools"] = [
            {
                "name": tool["name"],
                **numbers(tool, {"duration_ms"}),
                **(
                    {"status": tool["status"]} if tool.get("status") in {"success", "error"} else {}
                ),
            }
            for tool in metrics["tools"]
            if isinstance(tool, dict) and tool.get("name") in allowed_tools
        ]
    return result


def parse_sse(lines):
    """Consume named events; drop reasoning and raw provider payloads immediately."""
    event, data = "message", []
    result = {"answer": None, "metrics": {}, "reasoning_delta_count": 0}

    def consume():
        if event == "reasoning_delta":
            result["reasoning_delta_count"] += 1
            return
        if event not in {"final", "error"}:
            return
        payload = json.loads("\n".join(data))
        if event == "error":
            raise ValueError("Agent emitted SSE error")
        if result["answer"] is not None:
            raise ValueError("Duplicate SSE final event")
        from sdm.agents.project_qa.schemas import ProjectQuestionAnswer

        result["answer"] = ProjectQuestionAnswer.model_validate(payload["answer"]).model_dump(
            mode="json"
        )
        metrics = payload.get("metrics") or {}
        result["metrics"] = sanitize_metrics(metrics)

    for line in [*lines, ""] if isinstance(lines, list) else _terminated(lines):
        if not line:
            if data or event == "reasoning_delta":
                consume()
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:") and event != "reasoning_delta":
            data.append(line[5:].lstrip(" "))
    if result["answer"] is None:
        raise ValueError("Missing SSE final answer")
    return result


def _terminated(lines):
    yield from lines
    yield ""


def validate_citations(answer: dict, project_id: str):
    from sdm.agents.tools.sources import SOURCE_ID_FIELDS

    aliases = set()
    for source in answer.get("evidence_sources", []):
        data = source.get("data") or {}
        if data.get("project_id") and data["project_id"] != project_id:
            raise ValueError("Cross-project QA citation")
        source_metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        aliases.update(
            str(value).strip().casefold()
            for value in [
                source.get("id"),
                source.get("reference"),
                *[data.get(key) for key in SOURCE_ID_FIELDS],
                *[source_metadata.get(key) for key in SOURCE_ID_FIELDS],
            ]
            if value
        )
    if any(
        str(identifier).strip().casefold() not in aliases
        for identifier in answer.get("evidence_ids", [])
    ):
        raise ValueError("QA citation does not match returned evidence_sources")


def metadata(dataset: Path, files: list[Path], root: Path):
    def git(*args):
        run = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        return run.stdout.strip() if run.returncode == 0 else None

    config = dotenv_values(root / ".env")
    hashes = {
        str(path.relative_to(root)) if path.is_relative_to(root) else str(path): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in files
    }
    code_hashes = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((root / "sdm").rglob("*.py"))
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "source_files_sha256": hashes,
        "corpus_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        "git_revision": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "code_files_sha256": code_hashes,
        "code_sha256": hashlib.sha256(json.dumps(code_hashes, sort_keys=True).encode()).hexdigest(),
        "models": {
            key: os.getenv(key) or config.get(key) for key in ("LLM_MODEL", "EMBEDDING_MODEL")
        },
        "index_preflight": "not performed; first retrieval may include cold index work",
        "qa_review_status": "unreviewed",
        "retrieval_top_k": 8,
    }


def append_record(path: Path, record: dict):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def export_reports(records, output: Path):
    rows = [
        {
            key: row.get(key)
            for key in (
                "case_id",
                "mode",
                "category",
                "duration_ms",
                "group_recall_at_8",
                "mrr",
                "failure",
            )
        }
        for row in records
    ]
    for row, record in zip(rows, records, strict=True):
        row["ttft_ms"] = (record.get("metrics") or {}).get("ttft_ms")
    frame = pd.DataFrame(
        rows,
        columns=[
            "case_id",
            "mode",
            "category",
            "duration_ms",
            "group_recall_at_8",
            "mrr",
            "failure",
            "ttft_ms",
        ],
    )
    frame.to_csv(output / "cases.csv", index=False)
    summaries = []
    for mode, group in frame.groupby("mode"):
        successful = group[group.failure.isna()]
        failed = group[group.failure.notna()]
        summaries.append(
            {
                "mode": mode,
                "cases": len(group),
                "failures": group.failure.notna().sum(),
                "rerank_fallback_count": sum(
                    bool((record.get("retrieval") or {}).get("rerank_fallback"))
                    for record in records
                    if record["mode"] == mode
                )
                if mode == "hybrid_rerank"
                else 0,
                "group_recall_at_8": group.group_recall_at_8.mean(),
                "mrr": group.mrr.mean(),
                "success_count": len(successful),
                "success_duration_p50_ms": successful.duration_ms.quantile(0.5),
                "success_duration_p95_ms": successful.duration_ms.quantile(0.95),
                "failure_duration_p50_ms": failed.duration_ms.quantile(0.5),
                "failure_duration_p95_ms": failed.duration_ms.quantile(0.95),
                "qa_ttft_p50_ms": successful.ttft_ms.dropna().quantile(0.5)
                if mode == "qa"
                else None,
                "qa_ttft_p95_ms": successful.ttft_ms.dropna().quantile(0.95)
                if mode == "qa"
                else None,
            }
        )
    summary = pd.DataFrame(summaries)
    summary.to_csv(output / "summary.csv", index=False)
    (output / "report.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Evaluation</title><body><h1>Retrieval evaluation</h1><p>QA is unreviewed. No automatic correctness judgment. Success and failure latencies are reported separately and include request overhead and possible cold indexing. QA TTFT is the first streamed token from any model call, including routing, not time to the final answer. Retrieval mode order rotates deterministically across selected cases; actual request order and configuration are recorded in metadata.json. This reduces fixed-order bias, but caching confounds latency differences and cold-index work remains possible, so these measurements are not a causal comparison of algorithm speeds.</p>'
        + summary.to_html(index=False, escape=True)
        + frame.to_html(index=False, escape=True)
        + "</body></html>",
        encoding="utf-8",
    )
    review_fields = [
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
    ]
    review = []
    for record in records:
        if record["mode"] == "qa":
            case = record["case"]
            review.append(
                {
                    "run_id": output.name,
                    "case_id": case["id"],
                    "question": case["question"],
                    "expected_claims": json.dumps(case["expected_claims"], ensure_ascii=False),
                    "forbidden_claims": json.dumps(case["forbidden_claims"], ensure_ascii=False),
                    "expect_abstention": case["expect_abstention"],
                    "response": (record.get("answer") or {}).get("answer", ""),
                    "failure": record.get("failure"),
                    **{field: "" for field in review_fields},
                }
            )
    pd.DataFrame(
        review,
        columns=[
            "run_id",
            "case_id",
            "question",
            "expected_claims",
            "forbidden_claims",
            "expect_abstention",
            "response",
            "failure",
            *review_fields,
        ],
    ).to_csv(output / "manual_review.csv", index=False)


def rerank_payload(payload, settings):
    from sdm.agents.llm import get_llm_adapter
    from sdm.agents.tools.retrieval.reranking import rerank_with_fallback
    from sdm.backend.schemas.retrieval import ProjectRetrievalContext

    result = asyncio.run(
        rerank_with_fallback(
            ProjectRetrievalContext.model_validate(payload),
            top_k=8,
            llm=get_llm_adapter(),
            settings=settings,
        )
    )
    return result.model_dump(mode="json")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--agents", default="http://localhost:8010")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--skip-qa", action="store_true")
    parser.add_argument("--qa-limit", type=int)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument(
        "--retrieval-modes",
        nargs="+",
        choices=(*RETRIEVAL_MODES, "hybrid_rerank"),
        default=list(RETRIEVAL_MODES),
        help="Retrieval modes in initial order; rotated deterministically across selected cases",
    )
    args = parser.parse_args(argv)
    if len(args.retrieval_modes) != len(set(args.retrieval_modes)):
        parser.error("--retrieval-modes must not contain duplicates")
    if args.qa_limit is not None and args.qa_limit < 0:
        parser.error("--qa-limit must be nonnegative")
    root = Path(__file__).resolve().parents[2]
    catalog, files = corpus_catalog(root, args.dataset.resolve().parent)
    cases = load_cases(args.dataset, catalog)
    if args.case_id:
        unknown = set(args.case_id) - {case.id for case in cases}
        if unknown:
            parser.error(f"Unknown case IDs: {sorted(unknown)}")
        cases = [case for case in cases if case.id in args.case_id]
    qa_ids = [case.id for case in cases if case.run_qa and not args.skip_qa]
    if args.qa_limit is not None:
        qa_ids = qa_ids[: args.qa_limit]
    rerank_settings = None
    if "hybrid_rerank" in args.retrieval_modes:
        from sdm.agents.tools.retrieval.config import RerankSettings

        rerank_settings = RerankSettings.from_env().model_copy(update={"enabled": True})
    args.output.mkdir(parents=True, exist_ok=False)
    meta = metadata(args.dataset, files, root)
    meta.update(
        {
            "case_count": len(cases),
            "qa_case_count": len(qa_ids),
            "qa_limit": args.qa_limit,
            "selected_case_ids": [case.id for case in cases],
            "incomplete": True,
            "skip_qa": args.skip_qa,
            "retrieval_modes": args.retrieval_modes,
            "retrieval_configuration": {
                "top_k": 8,
                "candidate_limit": 40,
                "candidate_limit_rule": "min(60, max(top_k * 5, 20))",
                "dense": "pgvector cosine over eligible scoped chunks",
                "bm25": "independent lexical ranking over all eligible scoped chunks",
                "hybrid": "reciprocal rank fusion: sum(1 / (60 + rank))",
                "rrf_k": 60,
                "qa_retrieval_mode": "hybrid + optional LLM rerank (agent configuration)",
                "qa_rerank_default": "16 fused candidates -> LLM permutation -> top8; explicit RRF fallback",
                "hybrid_rerank": (
                    {
                        "fused_shortlist": rerank_settings.candidates,
                        "top_k": 8,
                        "backend_candidate_limit": min(60, max(rerank_settings.candidates * 5, 20)),
                        "timeout_seconds": rerank_settings.timeout_seconds,
                        "latency": "includes provider cold connection and reranking; uses agent shared explicit RRF fallback",
                    }
                    if rerank_settings
                    else "not requested"
                ),
                "configuration_kind": "expected contract; actual response diagnostics in raw.jsonl",
            },
            "mode_order_policy": "left rotation by zero-based selected-case index; QA last",
            "planned_mode_order": [
                {
                    "case_id": case.id,
                    "modes": retrieval_mode_order(args.retrieval_modes, index)
                    + (["qa"] if case.id in qa_ids else []),
                }
                for index, case in enumerate(cases)
            ],
            "actual_request_order": [],
        }
    )
    (args.output / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    records = []
    interrupted = False
    try:
        with httpx.Client(timeout=300) as client:
            for case_index, case in enumerate(cases):
                modes = retrieval_mode_order(args.retrieval_modes, case_index) + (
                    ["qa"] if case.id in qa_ids else []
                )
                for mode_position, mode in enumerate(modes):
                    started = time.perf_counter()
                    request_index = len(meta["actual_request_order"])
                    meta["actual_request_order"].append(
                        {"request_index": request_index, "case_id": case.id, "mode": mode}
                    )
                    record = {
                        "schema_version": SCHEMA_VERSION,
                        "case_id": case.id,
                        "mode": mode,
                        "request_index": request_index,
                        "mode_position": mode_position,
                        "category": case.category,
                        "case": case.model_dump(mode="json"),
                        "failure": None,
                    }
                    try:
                        if mode == "qa":
                            with client.stream(
                                "POST",
                                f"{args.agents.rstrip('/')}/api/v1/agents/projects/{quote(case.project_id, safe='')}/ask/stream",
                                json={"question": case.question, "as_of": case.as_of.isoformat()},
                            ) as response:
                                response.raise_for_status()
                                record.update(parse_sse(response.iter_lines()))
                            validate_citations(record["answer"], case.project_id)
                            record["review_status"] = "unreviewed"
                        else:
                            params = {
                                "query": case.question,
                                "as_of": case.as_of.isoformat(),
                                "limit": rerank_settings.candidates
                                if mode == "hybrid_rerank"
                                else 8,
                                "ranking": "hybrid" if mode == "hybrid_rerank" else mode,
                            }
                            if case.entity_id:
                                params["entity_id"] = case.entity_id
                            response = client.get(
                                f"{args.backend.rstrip('/')}/api/v1/summaries/projects/{quote(case.project_id, safe='')}/retrieval-context",
                                params=params,
                            )
                            response.raise_for_status()
                            payload = response.json()
                            if mode == "hybrid_rerank":
                                validate_retrieval(
                                    case, payload, catalog, max_items=rerank_settings.candidates
                                )
                                payload = rerank_payload(payload, rerank_settings)
                                record["rerank_applied"] = payload["rerank_applied"]
                            record["retrieval"] = payload
                            validate_retrieval(case, payload, catalog)
                            record.update(
                                retrieval_scores(
                                    case.required_evidence_groups,
                                    payload["items"],
                                    case.expect_abstention,
                                )
                            )
                    except Exception as exc:
                        record["failure"] = type(exc).__name__ + (
                            ": " + str(exc) if isinstance(exc, ValueError) else ""
                        )
                    record["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
                    append_record(args.output / "raw.jsonl", record)
                    records.append(record)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        export_reports(records, args.output)
        meta.update(
            {
                "incomplete": interrupted
                or len(records) != len(args.retrieval_modes) * len(cases) + len(qa_ids),
                "completed_records": len(records),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        (args.output / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if interrupted:
        return 130
    return int(any(record["failure"] for record in records))
