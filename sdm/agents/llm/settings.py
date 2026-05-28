"""Настройки модели для агентских запросов."""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr


class LLMSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key: SecretStr = Field(min_length=1)
    base_url: AnyHttpUrl
    model: str = Field(min_length=1)
    response_format: Literal["tool_calling", "json_schema"] = "tool_calling"
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    max_output_tokens: int = Field(default=8192, gt=0)
    max_retries: int = Field(default=2, ge=0, le=6)
    send_temperature: bool = True
    reasoning_effort: Literal["low", "high", "max"] | None = None
    thinking_mode: Literal["enabled", "disabled"] | None = None
    tool_stream: bool = False
    expose_reasoning: bool = False

    @classmethod
    def from_env(cls) -> LLMSettings:
        load_dotenv()
        required = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")
        missing = [name for name in required if not os.getenv(name, "").strip()]
        if missing:
            raise ValueError(f"Не заданы настройки LLM: {', '.join(missing)}.")
        return cls(
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ["LLM_BASE_URL"],
            model=os.environ["LLM_MODEL"],
            response_format=os.getenv("LLM_RESPONSE_FORMAT") or "tool_calling",
            timeout_seconds=os.getenv("LLM_TIMEOUT_SECONDS") or 60,
            max_output_tokens=os.getenv("LLM_MAX_OUTPUT_TOKENS") or 8192,
            max_retries=os.getenv("LLM_MAX_RETRIES") or 2,
            send_temperature=os.getenv("LLM_SEND_TEMPERATURE") or "true",
            reasoning_effort=os.getenv("LLM_REASONING_EFFORT") or None,
            thinking_mode=os.getenv("LLM_THINKING_MODE") or None,
            tool_stream=os.getenv("LLM_TOOL_STREAM") or "false",
            expose_reasoning=os.getenv("LLM_EXPOSE_REASONING") or "false",
        )
