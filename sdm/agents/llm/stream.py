"""Сборка ответа модели из частей потока."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from ..streaming import emit_stream_event


async def stream_completion(
    client: AsyncOpenAI,
    kwargs: dict[str, Any],
    *,
    expose_reasoning: bool,
    tool_stream: bool,
    operation: str,
) -> tuple[ChatCompletion, float | None]:
    """Собирает части потока в полный ответ модели."""
    request = dict(kwargs)
    extra_body = dict(request.pop("extra_body", {}) or {})
    if tool_stream:
        extra_body["tool_stream"] = True
    if extra_body:
        request["extra_body"] = extra_body

    started_at = perf_counter()
    first_delta_ms: float | None = None
    reasoning_parts: list[str] = []
    content_parts: list[str] = []
    refusal_parts: list[str] = []
    tool_calls: dict[int, dict[str, str]] = {}
    finish_reason: str | None = None
    response_id = ""
    created = 0
    model = request["model"]
    usage: Any = None
    received_characters = 0
    reported_characters = 0

    stream = await client.chat.completions.create(**request, stream=True)
    async with stream:
        async for chunk in stream:
            response_id = chunk.id or response_id
            created = chunk.created or created
            model = chunk.model or model
            if chunk.usage is not None:
                usage = chunk.usage
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason is not None:
                finish_reason = choice.finish_reason
            delta = choice.delta
            reasoning = getattr(delta, "reasoning_content", None)
            if not isinstance(reasoning, str):
                reasoning = ""
            content = delta.content or ""
            refusal = delta.refusal or ""
            has_tool_delta = bool(delta.tool_calls)
            received_characters += len(reasoning) + len(content)
            if first_delta_ms is None and (reasoning or content or refusal or has_tool_delta):
                first_delta_ms = round((perf_counter() - started_at) * 1000, 1)
            if reasoning and expose_reasoning:
                emit_stream_event("reasoning_delta", text=reasoning)
            if reasoning:
                reasoning_parts.append(reasoning)
            if content:
                content_parts.append(content)
            if refusal:
                refusal_parts.append(refusal)
            for partial in delta.tool_calls or []:
                current = tool_calls.setdefault(
                    partial.index,
                    {"id": "", "name": "", "arguments": "", "type": "function"},
                )
                if partial.id:
                    current["id"] = partial.id
                if partial.type:
                    current["type"] = partial.type
                if partial.function is not None:
                    if partial.function.name:
                        current["name"] += partial.function.name
                    if partial.function.arguments:
                        fragment = _argument_fragment(partial.function.arguments)
                        current["arguments"] += fragment
                        received_characters += len(fragment)
            if received_characters > reported_characters and (
                reported_characters == 0 or received_characters - reported_characters >= 64
            ):
                # Показываем число полученных символов. Порядок источников ещё не проверен.
                emit_stream_event(
                    "llm_progress", operation=operation, received_characters=received_characters
                )
                reported_characters = received_characters

    raw: dict[str, Any] = {
        "id": response_id or "streamed-completion",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {
                    "role": "assistant",
                    "content": "".join(content_parts) or None,
                    "refusal": "".join(refusal_parts) or None,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": call["type"],
                            "function": {
                                "name": call["name"],
                                "arguments": call["arguments"],
                            },
                        }
                        for _, call in sorted(tool_calls.items())
                    ]
                    or None,
                    "reasoning_content": "".join(reasoning_parts) or None,
                },
            }
        ],
    }
    if usage is not None:
        raw["usage"] = usage
    response = ChatCompletion.model_validate(raw)
    return response, first_delta_ms


def _argument_fragment(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
