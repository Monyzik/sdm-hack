from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Awaitable, Callable
from uuid import uuid4

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ConfigDict

from sdm.agents.streaming import emit_stream_event


class ToolArgsModel(BaseModel):
    """Принимает только объявленные аргументы, чтобы не терять фильтры молча."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoArgs(ToolArgsModel):
    pass


def make_tool(
    *,
    name: str,
    description: str,
    args_schema: type[BaseModel],
    func: Callable[..., Awaitable[dict[str, Any]]],
) -> BaseTool:
    async def invoke_with_artifact(**arguments: Any) -> tuple[str, dict[str, Any]]:
        # JSON-схема сохраняет неизвестные аргументы, даже у инструментов без параметров.
        # Проверяем их до чтения из базы.
        validated = args_schema.model_validate(arguments).model_dump()
        call_id = f"tool_{uuid4().hex}"
        started_at = perf_counter()
        emit_stream_event("tool_started", call_id=call_id, name=name, args=validated)
        status = "success"
        try:
            result = await func(**validated)
        except BaseException:
            status = "error"
            raise
        finally:
            emit_stream_event(
                "tool_finished",
                call_id=call_id,
                name=name,
                status=status,
                duration_ms=round((perf_counter() - started_at) * 1000, 1),
            )
        # Модель читает JSON, а ссылки на источники берутся из артефакта.
        return json.dumps(result, ensure_ascii=False), result

    return StructuredTool.from_function(
        coroutine=invoke_with_artifact,
        name=name,
        description=description,
        args_schema=args_schema.model_json_schema(),
        handle_validation_error=str,
        response_format="content_and_artifact",
    )
