"""Интерфейс модели для агентских запросов."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from openai.types.chat import ChatCompletion
from pydantic import BaseModel

ParsedModel = TypeVar("ParsedModel", bound=BaseModel)


class LLMAdapter(Protocol):
    provider: str
    model: str

    async def parse_pydantic(
        self,
        *,
        response_model: type[ParsedModel],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        stream: bool = False,
    ) -> ParsedModel: ...

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stream: bool = False,
    ) -> ChatCompletion: ...
