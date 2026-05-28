"""Оценка ответов агента и отчёты с явными знаменателями метрик."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any

PRELOAD_TOOLS = {"get_project_summary", "get_problem_context", "search_project_evidence"}


def _indexed_flags(items: list[dict], count: int, field: str) -> list[bool] | None:
    """Не допускает пропусков и повторов в оценках эталонных утверждений."""
    indices = [item.get("index") for item in items]
    if any(type(index) is not int for index in indices) or sorted(indices) != list(range(count)):
        return None
    if any(type(item.get(field)) is not bool for item in items):
        return None
    return [item[field] for item in sorted(items, key=lambda item: item["index"])]


def _citations_valid(answer: dict, claims: list[dict], project_id: str) -> bool | None:
    from .runner import validate_citations

    if any(
        claim.get("verdict") == "supported" and not claim.get("evidence_ids") for claim in claims
    ):
        return False
    has_citations = bool(answer.get("evidence_ids")) or any(
        claim.get("evidence_ids") for claim in claims
    )
    if not has_citations:
        return None
    try:
        validate_citations(answer, project_id)
        for claim in claims:
            validate_citations(
                {**answer, "evidence_ids": claim.get("evidence_ids") or []}, project_id
            )
    except (ValueError, TypeError, KeyError):
        return False
    return True


def score_record(record: dict) -> dict[str, Any]:
    """Разделяет сбои агента, недоступную оценку и проверяемое качество ответа."""
    case = record.get("case") or {}
    answer = record.get("answer")
    completed = not record.get("failure") and isinstance(answer, dict)
    judge = record.get("judge")
    gold = case.get("expected_claims") or []
    forbidden = case.get("forbidden_claims") or []
    expected = banned = None
    if completed and not record.get("judge_failure") and isinstance(judge, dict):
        expected = _indexed_flags(judge.get("expected_claims", []), len(gold), "covered")
        banned = _indexed_flags(judge.get("forbidden_claims", []), len(forbidden), "present")
    claims = judge.get("answer_claims", []) if isinstance(judge, dict) else []
    evaluable = (
        completed
        and not record.get("judge_failure")
        and expected is not None
        and banned is not None
        and isinstance(claims, list)
        and all(
            isinstance(claim, dict)
            and claim.get("verdict") in {"supported", "unsupported", "contradicted"}
            for claim in claims
        )
        and type(judge.get("abstained")) is bool
        and type(judge.get("relevant")) is bool
    )
    project = case.get("intent", "project_question") == "project_question"
    tools = record.get("tools") or []
    successful = {tool.get("name") for tool in tools if tool.get("status") == "success"}
    policy = (
        (PRELOAD_TOOLS <= successful)
        if project
        else (
            not tools
            and not (answer or {}).get("evidence_sources")
            and not (answer or {}).get("evidence_ids")
        )
    )
    required = case.get("required_tool_calls") or []
    required_ok = (
        all(
            any(
                tool.get("name") == requirement["name"]
                and tool.get("status") == "success"
                and all(
                    key in (tool.get("args") or {})
                    and json.dumps(tool["args"][key], sort_keys=True)
                    == json.dumps(value, sort_keys=True)
                    for key, value in requirement.get("arguments", {}).items()
                )
                for tool in tools
            )
            for requirement in required
        )
        if required
        else None
    )
    citations = (
        _citations_valid(answer, claims if evaluable else [], case.get("project_id", ""))
        if completed
        else None
    )
    supported = sum(claim["verdict"] == "supported" for claim in claims) if evaluable else None
    abstention_expected = case.get("expect_abstention", False)
    task = None
    if not completed:
        task = False
    elif evaluable:
        nonvacuous = not (project and gold and not abstention_expected) or bool(claims)
        task = bool(
            all(expected)
            and not any(banned)
            and supported == len(claims)
            and nonvacuous
            and judge["relevant"]
            and judge["abstained"] == abstention_expected
            and policy
            and citations is not False
            and required_ok is not False
        )
    metrics = record.get("metrics") or {}
    return {
        "case_id": record.get("case_id", case.get("id", "")),
        "mode": record.get("mode", ""),
        "question": case.get("question", ""),
        "category": case.get("category", ""),
        "completed": completed,
        "quality_evaluable": evaluable,
        "scored": task is not None,
        "task_success": task,
        "failure": record.get("failure"),
        "judge_failure": record.get("judge_failure"),
        "quality_unavailable": completed and not evaluable,
        "expected_claims_covered": sum(expected) if evaluable else None,
        "expected_claims_total": len(gold) if evaluable else None,
        "supported_claims": supported,
        "answer_claims_total": len(claims) if evaluable else None,
        "forbidden_claims_present": sum(banned) if evaluable else None,
        "forbidden_claims_total": len(forbidden) if evaluable else None,
        "abstention_expected": abstention_expected,
        "known_project_answer": project and bool(gold) and not abstention_expected,
        "abstained": judge["abstained"] if evaluable else None,
        "relevant": judge["relevant"] if evaluable else None,
        "tool_policy_correct": policy,
        "required_tool_correct": required_ok,
        "citations_valid": citations,
        "duration_ms": record.get("duration_ms"),
        "first_answer_ms": record.get("first_answer_ms"),
        "ttft_ms": metrics.get("ttft_ms"),
        "input_tokens": metrics.get("input_tokens"),
        "output_tokens": metrics.get("output_tokens"),
        "total_tokens": metrics.get("total_tokens"),
        "llm_call_count": record.get("llm_call_count", len(record.get("llm_calls") or [])),
        "format_retries": record.get("format_retries"),
        "rerank_fallbacks": record.get("rerank_fallbacks"),
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def _summary(mode: str, rows: list[dict], planned: int) -> dict:
    result = {
        "mode": mode,
        "planned_cases": planned,
        "observed_cases": len(rows),
        "completed_cases": sum(row["completed"] for row in rows),
        "agent_failed_cases": sum(not row["completed"] for row in rows),
        "judge_failed_cases": sum(bool(row["judge_failure"]) for row in rows),
        "quality_evaluable_cases": sum(row["quality_evaluable"] for row in rows),
        "quality_unavailable_cases": sum(row["quality_unavailable"] for row in rows),
        "scored_cases": sum(row["scored"] for row in rows),
    }

    def metric(name, numerator, denominator):
        result[name + "_numerator"] = numerator
        result[name + "_denominator"] = denominator
        result[name] = _ratio(numerator, denominator)

    metric("completion_rate", result["completed_cases"], planned)
    metric("task_success", sum(row["task_success"] is True for row in rows), result["scored_cases"])
    for name, numerator, denominator in (
        ("fact_coverage", "expected_claims_covered", "expected_claims_total"),
        ("grounded_claim_precision", "supported_claims", "answer_claims_total"),
        ("forbidden_claim_rate", "forbidden_claims_present", "forbidden_claims_total"),
    ):
        metric(
            name,
            sum(row[numerator] or 0 for row in rows),
            sum(row[denominator] or 0 for row in rows),
        )
    for name, field in (
        ("tool_policy_accuracy", "tool_policy_correct"),
        ("required_tool_accuracy", "required_tool_correct"),
        ("citations_valid", "citations_valid"),
    ):
        selected = [row for row in rows if row[field] is not None]
        metric(name, sum(row[field] for row in selected), len(selected))
    for name, expected in (("abstention_recall", True), ("false_abstention_rate", False)):
        selected = [
            row
            for row in rows
            if row["quality_evaluable"]
            and row["abstention_expected"] == expected
            and (expected or row["known_project_answer"])
        ]
        metric(name, sum(row["abstained"] for row in selected), len(selected))
    for suffix, completed in (("success", True), ("failure", False)):
        for field in ("duration_ms", "first_answer_ms", "ttft_ms"):
            values = [
                row[field]
                for row in rows
                if row["completed"] == completed and row[field] is not None
            ]
            result[f"{field}_{suffix}_count"] = len(values)
            for quantile, percentile in (("p50", 0.5), ("p95", 0.95)):
                result[f"{field}_{suffix}_{quantile}"] = _percentile(values, percentile)
    for field in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "llm_call_count",
        "format_retries",
        "rerank_fallbacks",
    ):
        values = [row[field] for row in rows if row[field] is not None]
        result[field + "_observed_cases"] = len(values)
        result[field] = sum(values) if values else None
    return result


def _csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields or list(rows[0]) if rows else fields or ["mode"]
        )
        writer.writeheader()
        writer.writerows(rows)


def export_agent_reports(records: list[dict], output: Path, planned_counts: dict[str, int]) -> None:
    """Сохраняет оценки, агрегаты и таблицу ручной проверки без включения расходов судьи."""
    output.mkdir(parents=True, exist_ok=True)
    scored = [score_record(record) for record in records]
    modes = sorted(set(planned_counts) | {row["mode"] for row in scored})
    summaries = [
        _summary(
            mode,
            [row for row in scored if row["mode"] == mode],
            planned_counts.get(mode, sum(row["mode"] == mode for row in scored)),
        )
        for mode in modes
    ]
    _csv(output / "cases.csv", scored)
    _csv(output / "summary.csv", summaries)
    manual = [
        {
            "case_id": row["case_id"],
            "mode": row["mode"],
            "question": row["question"],
            "task_success": row["task_success"],
            "failure": row["failure"],
            "judge_failure": row["judge_failure"],
            "answer": (record.get("answer") or {}).get("answer", ""),
            "judge_reason": (record.get("judge") or {}).get("reason", ""),
            "review_status": "unreviewed",
            "reviewer": "",
            "notes": "",
        }
        for record, row in zip(records, scored)
    ]
    _csv(
        output / "manual_review.csv",
        manual,
        list(manual[0]) if manual else ["case_id", "mode", "review_status", "reviewer", "notes"],
    )

    def table(rows):
        if not rows:
            return "<p>Нет наблюдений.</p>"
        headers = list(rows[0])
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{html.escape(key)}</th>" for key in headers)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>"
                + "".join(
                    f"<td>{html.escape(str(row[key])) if row[key] is not None else ''}</td>"
                    for key in headers
                )
                + "</tr>"
                for row in rows
            )
            + "</tbody></table>"
        )

    document = (
        "<!doctype html><html lang='ru'><meta charset='utf-8'><title>Оценка агента</title><style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px;text-align:left}section{overflow:auto}</style><h1>Оценка агента</h1><p>Пустые значения означают отсутствие применимых наблюдений. Качество оценивается по внешнему судье, а не verification.status. Сбои судьи исключены из качества; сбои агента считаются неуспехом задачи. Runtime success означает полученный ответ, независимо от качества. first_answer_ms измеряет начало ответа пользователю; ttft_ms измеряет первый токен модели. Токены и вызовы относятся только к агенту.</p><h2>Сводка</h2><section>"
        + table(summaries)
        + "</section><h2>Кейсы</h2><section>"
        + table(scored)
        + "</section></html>"
    )
    (output / "report.html").write_text(document, encoding="utf-8")
