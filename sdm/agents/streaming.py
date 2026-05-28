"""События LangGraph и метрики отдельного запроса."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Iterator

from langgraph.config import get_stream_writer


@dataclass
class StreamMetrics:
    started_at: float = field(default_factory=perf_counter)
    stages: dict[str, list[float]] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    rerank_calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def record(self, event: str, data: dict[str, Any]) -> None:
        if event == "stage_finished" and data.get("status") == "success":
            self.stages.setdefault(data["stage"], []).append(data["duration_ms"])
        elif event == "tool_finished":
            self.tools.append(dict(data))
        elif event in {"rerank_completed", "rerank_failed"}:
            self.rerank_calls.append(
                {
                    "status": "success" if event == "rerank_completed" else "fallback",
                    **{
                        key: data[key]
                        for key in ("model", "duration_ms", "candidate_count", "returned_count")
                        if key in data
                    },
                }
            )
            self.stages.setdefault("rerank", []).append(data["duration_ms"])
        elif event == "llm_finished":
            self.llm_calls.append(dict(data))
            usage = data.get("usage") or {}
            self.input_tokens += usage.get("input_tokens") or 0
            self.output_tokens += usage.get("output_tokens") or 0
            self.total_tokens += usage.get("total_tokens") or 0

    def snapshot(self) -> dict[str, Any]:
        ttft = next(
            (call["ttft_ms"] for call in self.llm_calls if call.get("ttft_ms") is not None),
            None,
        )
        return {
            "duration_ms": round((perf_counter() - self.started_at) * 1000, 1),
            "ttft_ms": ttft,
            "stages_ms": {
                name: round(sum(durations), 1) for name, durations in self.stages.items()
            },
            "tool_calls": len(self.tools),
            "tools": self.tools,
            "llm_calls": self.llm_calls,
            "rerank_calls": self.rerank_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
            },
        }


_metrics: ContextVar[StreamMetrics | None] = ContextVar("agent_stream_metrics", default=None)
_suppress_reasoning: ContextVar[bool] = ContextVar("suppress_reasoning_stream", default=False)


@contextmanager
def suppress_reasoning_stream() -> Iterator[None]:
    """Скрывает рассуждения из SSE, сохраняя события прогресса и метрики."""
    token = _suppress_reasoning.set(True)
    try:
        yield
    finally:
        _suppress_reasoning.reset(token)


@contextmanager
def collect_stream_metrics() -> Iterator[StreamMetrics]:
    metrics = StreamMetrics()
    token = _metrics.set(metrics)
    try:
        yield metrics
    finally:
        _metrics.reset(token)


def emit_stream_event(event: str, **data: Any) -> None:
    if event == "reasoning_delta" and _suppress_reasoning.get():
        return
    metrics = _metrics.get()
    if metrics is not None:
        metrics.record(event, data)
    try:
        writer = get_stream_writer()
    except (RuntimeError, KeyError):
        # У отдельного инструмента может быть контекст LangChain без потока LangGraph.
        return
    writer({"event": event, "data": data})


@contextmanager
def streamed_stage(name: str) -> Iterator[None]:
    started_at = perf_counter()
    emit_stream_event("stage_started", stage=name)
    try:
        yield
    except BaseException:
        emit_stream_event(
            "stage_finished",
            stage=name,
            status="error",
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
        )
        raise
    emit_stream_event(
        "stage_finished",
        stage=name,
        status="success",
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
    )
