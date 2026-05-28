"""Прогон сценариев агента через SSE и отдельная оценка готовых ответов."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from sdm.agents.project_qa.schemas import ProjectConversationMessage, ProjectQuestionAnswer

from .runner import append_record, corpus_catalog, metadata, sanitize_metrics

MODES = ("standard", "verified")


class ExpectedToolCall(BaseModel):
    """Инструмент и значимые аргументы, без которых сценарий не выполнен."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    arguments: dict = Field(default_factory=dict)


class AgentCase(BaseModel):
    """Один вопрос с эталоном, историей диалога и требованиями к инструментам."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    as_of: date
    question: str = Field(min_length=1, max_length=1000)
    category: str = Field(min_length=1)
    expected_claims: list[str]
    forbidden_claims: list[str]
    expect_abstention: StrictBool
    intent: Literal["project_question", "small_talk", "out_of_scope"]
    conversation_context: list[ProjectConversationMessage] = Field(
        default_factory=list, max_length=8
    )
    required_tool_calls: list[ExpectedToolCall] = Field(default_factory=list)
    gold_case_id: str | None = None


def load_agent_cases(path: Path) -> list[AgentCase]:
    """Читает фиксированный набор и не допускает пустых наборов или повторных ID."""
    cases = [
        AgentCase.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("Набор должен быть непустым, ID сценариев не должны повторяться.")
    return cases


async def read_agent_stream(response: httpx.Response, record: dict, started: float) -> None:
    """Сохраняет публичный ответ и измерения. Сырые рассуждения сразу отбрасывает."""
    event, data = "message", []
    calls = {}

    def consume():
        nonlocal data
        if not data:
            return
        payload = json.loads("\n".join(data))
        if event == "error":
            raise ValueError("Агент завершил поток ошибкой.")
        if event == "final":
            if record.get("answer") is not None:
                raise ValueError("В потоке получен повторный финальный ответ.")
            record["answer"] = ProjectQuestionAnswer.model_validate(payload["answer"]).model_dump(
                mode="json"
            )
            record["metrics"] = sanitize_metrics(payload.get("metrics") or {})
        elif event == "answer_delta" and payload.get("text") and record["first_answer_ms"] is None:
            record["first_answer_ms"] = round((time.perf_counter() - started) * 1000, 2)
        elif event == "tool_started":
            call = {key: payload.get(key) for key in ("call_id", "name", "args")}
            call["status"] = "unfinished"
            calls[call["call_id"]] = call
            record["tools"].append(call)
        elif event == "tool_finished":
            call = calls.get(payload.get("call_id"))
            if call is not None:
                call.update({key: payload.get(key) for key in ("status", "duration_ms")})
        elif event == "llm_started":
            record["llm_call_count"] += 1
        elif event == "llm_finished":
            record["llm_calls"].append(
                {
                    **{key: payload.get(key) for key in ("operation", "duration_ms", "status")},
                    "usage": sanitize_metrics(payload.get("usage") or {}),
                }
            )
        elif event == "llm_retry":
            record["format_retries"] += 1
        elif event == "rerank_failed":
            record["rerank_fallbacks"] += 1

    accepted = {
        "final",
        "error",
        "answer_delta",
        "tool_started",
        "tool_finished",
        "llm_started",
        "llm_finished",
        "llm_retry",
        "rerank_failed",
    }
    async for line in response.aiter_lines():
        if not line:
            consume()
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:") and event in accepted:
            data.append(line[5:].lstrip(" "))
    consume()
    if record.get("answer") is None:
        raise ValueError("Поток завершился без финального ответа.")


async def run_agent_case(
    client: httpx.AsyncClient, base_url: str, case: AgentCase, mode: str, request_index: int
) -> dict:
    """Выполняет один настоящий запрос, сохраняя след инструментов даже при сбое."""
    started = time.perf_counter()
    record = {
        "case_id": case.id,
        "case": case.model_dump(mode="json"),
        "mode": mode,
        "request_index": request_index,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "failure": None,
        "judge_failure": None,
        "answer": None,
        "judge": None,
        "metrics": {},
        "first_answer_ms": None,
        "tools": [],
        "llm_calls": [],
        "llm_call_count": 0,
        "format_retries": 0,
        "rerank_fallbacks": 0,
    }
    try:
        async with asyncio.timeout(240):
            async with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/api/v1/agents/projects/{quote(case.project_id, safe='')}/ask/stream",
                json={
                    "question": case.question,
                    "as_of": case.as_of.isoformat(),
                    "conversation_context": [m.model_dump() for m in case.conversation_context],
                    "verify_claims": mode == "verified",
                },
            ) as response:
                response.raise_for_status()
                await read_agent_stream(response, record, started)
    except Exception as error:
        # HTTP-тело и текст исключения могут содержать сведения о провайдере.
        record["failure"] = type(error).__name__
        if isinstance(error, httpx.HTTPStatusError):
            record["http_status"] = error.response.status_code
    record["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    if not record["metrics"] and record["llm_calls"]:
        record["metrics"] = {
            key: sum(call["usage"].get(key, 0) for call in record["llm_calls"])
            for key in ("input_tokens", "output_tokens", "total_tokens")
        }
    return record


async def evaluate(cases, args, output: Path, meta: dict, records: list[dict]) -> None:
    """Сначала измеряет агента, затем судью, чтобы оценка не влияла на задержку ответа."""
    from sdm.agents.llm import OpenAICompatibleLLMAdapter
    from sdm.agents.llm.settings import LLMSettings
    from sdm.agents.streaming import collect_stream_metrics

    from .agent_judge import judge_answer

    settings = LLMSettings.from_env()
    if args.judge_model:
        settings = settings.model_copy(update={"model": args.judge_model})
    judge = OpenAICompatibleLLMAdapter(settings)
    meta["judge"] = {
        "model": judge.model,
        "same_model_as_agent_config": judge.model == meta["models"]["LLM_MODEL"],
        "kind": "LLM judge with gold and cited sources; not independent human review",
        "response_format": settings.response_format,
    }
    semaphore = asyncio.Semaphore(args.concurrency)
    request_counter = 0

    async with httpx.AsyncClient(timeout=240) as client:
        health = await client.get(f"{args.agents.rstrip('/')}/health")
        health.raise_for_status()

        async def run_pair(case_index, case):
            nonlocal request_counter
            order = (
                args.modes[case_index % len(args.modes) :]
                + args.modes[: case_index % len(args.modes)]
            )
            for mode in order:
                async with semaphore:
                    request_index = request_counter
                    request_counter += 1
                    record = await run_agent_case(client, args.agents, case, mode, request_index)
                    records.append(record)
                    append_record(output / "agent_raw.jsonl", record)
                    print(
                        f"{case.id} {mode}: {record['duration_ms'] / 1000:.1f} с, "
                        f"{record['failure'] or 'ответ получен'}",
                        flush=True,
                    )

        await asyncio.gather(*(run_pair(i, case) for i, case in enumerate(cases)))

    async def review(record):
        if record["failure"]:
            return
        async with semaphore:
            started = time.perf_counter()
            with collect_stream_metrics() as judge_metrics:
                try:
                    async with asyncio.timeout(180):
                        result = await judge_answer(
                            judge, case=record["case"], answer=record["answer"]
                        )
                    record["judge"] = result.model_dump()
                except Exception as error:
                    record["judge_failure"] = type(error).__name__
                record["judge_metrics"] = sanitize_metrics(judge_metrics.snapshot())
                record["judge_metrics"]["llm_call_count"] = len(judge_metrics.llm_calls)
            record["judge_duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
            append_record(output / "judgments.jsonl", record)
            print(
                f"Judge {record['case_id']} {record['mode']}: "
                f"{record['judge_failure'] or 'оценено'}",
                flush=True,
            )

    await asyncio.gather(*(review(record) for record in records))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/interview/agent_cases.jsonl"))
    parser.add_argument("--agents", default="http://localhost:8010")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--judge-model", help="Модель судьи на настроенном LLM-провайдере")
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args(argv)
    if not 1 <= args.concurrency <= 4:
        parser.error("--concurrency должен быть от 1 до 4")
    if len(args.modes) != len(set(args.modes)):
        parser.error("Режимы не должны повторяться")
    cases = load_agent_cases(args.dataset)
    if args.case_id:
        if set(args.case_id) - {case.id for case in cases}:
            parser.error("Неизвестный ID сценария")
        cases = [case for case in cases if case.id in args.case_id]
    root = Path(__file__).resolve().parents[2]
    catalog, files = corpus_catalog(root, root / "data/interview")
    if any(case.project_id not in catalog.values() for case in cases):
        parser.error("В наборе есть проект, отсутствующий в корпусе")
    meta = metadata(args.dataset, files, root)
    meta.update(
        {
            "evaluation_kind": "agent",
            "schema_version": 1,
            "case_count": len(cases),
            "selected_case_ids": [case.id for case in cases],
            "modes": args.modes,
            "concurrency": args.concurrency,
            "planned_requests": len(cases) * len(args.modes),
            "mode_order": "alternating first mode per case; actual start index in agent_raw.jsonl",
            "qa_review_status": "LLM judge; no independent human labels",
            "index_preflight": "existing index expected; no refresh performed by this runner",
            "incomplete": True,
        }
    )
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    records = []
    interrupted = False
    finished = False
    try:
        asyncio.run(evaluate(cases, args, args.output, meta, records))
        finished = True
    except KeyboardInterrupt:
        interrupted = True
    finally:
        from .agent_metrics import export_agent_reports

        export_agent_reports(records, args.output, {mode: len(cases) for mode in args.modes})
        meta.update(
            {
                "incomplete": not finished or len(records) != meta["planned_requests"],
                "completed_records": len(records),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        (args.output / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    if interrupted:
        return 130
    return int(any(record["failure"] or record["judge_failure"] for record in records))


if __name__ == "__main__":
    raise SystemExit(main())
