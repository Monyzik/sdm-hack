"""Exercise the running backend and agent services, without direct provider calls."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.parse import quote, urlsplit

import httpx
from dotenv import dotenv_values

DEFAULT_QUESTION = (
    "Почему заблокирована задача T702 и что обсуждали по её согласованию? Укажи источники."
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class DemoFailure(Exception):
    """A concise failure safe to display without request details."""


def endpoint(value: str) -> str:
    url = urlsplit(value)
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise argparse.ArgumentTypeError("Ожидается HTTP(S) URL без credentials/query/fragment.")
    return value.rstrip("/")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=endpoint, default="http://localhost:8000")
    parser.add_argument("--agents", type=endpoint, default="http://localhost:8010")
    parser.add_argument("--project", default="P007")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 6, 19))
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--retrieval-query", default="Почему заблокирована T702")
    parser.add_argument("--entity-id", default="T702")
    parser.add_argument("--output", type=Path, default=Path("outputs/provider_demo.json"))
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    if not 0 < args.timeout <= 3600:
        parser.error("--timeout должен быть от 0 до 3600 секунд (не включая 0).")
    if not args.project.strip() or not args.question.strip():
        parser.error("--project и --question не должны быть пустыми.")
    return args


def configured_models() -> dict[str, str | None]:
    # Read only the two named values into the report, never configuration or credentials.
    values = dotenv_values(REPOSITORY_ROOT / ".env", interpolate=False)
    return {
        name: os.environ.get(name) or values.get(name) for name in ("LLM_MODEL", "EMBEDDING_MODEL")
    }


async def request(
    client: httpx.AsyncClient,
    timings: dict[str, float],
    stage: str,
    method: str,
    url: str,
    **kwargs: object,
) -> dict:
    started = perf_counter()
    try:
        response = await client.request(method, url, **kwargs)
        if not response.is_success:
            raise DemoFailure(f"{stage}: HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            raise DemoFailure(f"{stage}: ответ сервиса не является JSON") from None
        if not isinstance(payload, dict):
            raise DemoFailure(f"{stage}: ожидался объект ответа")
        return payload
    except httpx.TimeoutException:
        raise DemoFailure(f"{stage}: превышено время ожидания") from None
    except httpx.RequestError:
        raise DemoFailure(f"{stage}: сервис недоступен или соединение прервано") from None
    finally:
        timings[stage] = round(perf_counter() - started, 3)


def source_aliases(sources: list[dict]) -> set[str]:
    """Match citations to public source identifiers, not only synthetic source IDs."""
    id_fields = (
        "id",
        "project_id",
        "resource_id",
        "source_id",
        "entity_id",
        "task_id",
        "linked_task_id",
        "depends_on_task_id",
        "root_task_id",
        "external_id",
    )
    aliases: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        for field in ("id", "reference"):
            value = source.get(field)
            if isinstance(value, str) and value:
                aliases.add(value)
        data = source.get("data")
        if not isinstance(data, dict):
            continue
        for record in (data, data.get("metadata")):
            if not isinstance(record, dict):
                continue
            for field in id_fields:
                value = record.get(field)
                if isinstance(value, (str, int)) and not isinstance(value, bool) and value != "":
                    aliases.add(str(value))
    return aliases


async def run(args: argparse.Namespace, report: dict) -> None:
    timings = report["timings_seconds"]
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        for name, base in (("backend", args.backend), ("agents", args.agents)):
            health = await request(client, timings, f"{name}_health", "GET", f"{base}/health")
            if health.get("status") != "ok":
                raise DemoFailure(f"{name}_health: сервис не подтвердил status=ok")
            report["health"][name] = health

        project = quote(args.project, safe="")
        retrieval = await request(
            client,
            timings,
            "retrieval",
            "GET",
            f"{args.backend}/api/v1/summaries/projects/{project}/retrieval-context",
            params={
                "query": args.retrieval_query,
                "entity_id": args.entity_id,
                "as_of": args.as_of.isoformat(),
                "limit": 3,
            },
        )
        report["retrieval"] = retrieval
        if not retrieval.get("items") or not retrieval.get("count"):
            raise DemoFailure("retrieval: поиск не вернул документы")

        answer = await request(
            client,
            timings,
            "question_answer",
            "POST",
            f"{args.agents}/api/v1/agents/projects/{project}/ask",
            json={"question": args.question, "as_of": args.as_of.isoformat(), "max_depth": 2},
        )
        report["qa"] = answer
        if not isinstance(answer.get("answer"), str) or not answer["answer"].strip():
            raise DemoFailure("question_answer: агент не вернул ответ")
        sources = answer.get("evidence_sources", [])
        citations = answer.get("evidence_ids", [])
        source_ids = source_aliases(sources)
        if not source_ids.intersection(citations):
            raise DemoFailure("question_answer: нет ссылок на полученные источники")
        report["success"] = True
        print(f"Документы: {len(retrieval['items'])}; источники ответа: {len(sources)}")
        print(answer["answer"])
        print("Инструменты: " + ", ".join(answer.get("used_tools", [])))
        print("Evidence IDs: " + ", ".join(citations))


def main() -> int:
    args = arguments()
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "configured_model_names": configured_models(),
        "project_id": args.project,
        "as_of": args.as_of.isoformat(),
        "question": args.question,
        "health": {},
        "timings_seconds": {},
        "success": False,
    }
    started = perf_counter()
    try:
        asyncio.run(run(args, report))
    except DemoFailure as exc:
        report["error"] = str(exc)
        print(f"Демо не подтверждено: {exc}", file=sys.stderr)
    except (TypeError, ValueError, KeyError):
        report["error"] = "Некорректная структура ответа сервиса"
        print(report["error"], file=sys.stderr)
    except KeyboardInterrupt:
        report["error"] = "Демо прервано пользователем"
    finally:
        report["timings_seconds"]["total"] = round(perf_counter() - started, 3)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        print("Не удалось сохранить отчет демо", file=sys.stderr)
        return 1
    print(f"Отчет: {args.output}")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
