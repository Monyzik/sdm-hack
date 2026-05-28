"""Запросы к модели через API, совместимый с OpenAI."""

from __future__ import annotations

import logging
from functools import lru_cache
from time import perf_counter
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from pydantic import ValidationError

from ..prompt_utils import prompt_data
from ..streaming import emit_stream_event
from .interface import LLMAdapter, ParsedModel
from .settings import LLMSettings
from .stream import stream_completion

RESULT_TOOL_NAME = "submit_result"
STRUCTURED_OUTPUT_ATTEMPTS = 2
logger = logging.getLogger(__name__)


class IncompleteOutputError(ValueError):
    """Ответ модели оборван или отклонён до проверки структуры."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Модель не завершила ответ: {reason}.")


class StructuredOutputError(ValueError):
    """Модель не смогла вернуть результат по схеме за отведённые попытки."""


class OpenAICompatibleLLMAdapter:
    """Получает ответы через /chat/completions с проверкой структуры.

    По умолчанию передаёт схему через инструмент с tool_choice=auto.
    Формат json_schema включается настройкой. Каждый запрос закрывает клиент,
    чтобы адаптер можно было использовать в разных циклах событий.
    """

    provider = "openai_compatible"

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings if settings is not None else LLMSettings.from_env()
        self.model = self.settings.model

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=self.settings.api_key.get_secret_value(),
            base_url=str(self.settings.base_url),
            timeout=self.settings.timeout_seconds,
            max_retries=self.settings.max_retries,
        )

    async def parse_pydantic(
        self,
        *,
        response_model: type[ParsedModel],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        stream: bool = False,
    ) -> ParsedModel:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if self.settings.response_format == "json_schema":
            # SDK приводит вложенные Pydantic-схемы к строгому формату API.
            kwargs = self._completion_kwargs(messages=messages, temperature=temperature)
            started_at = perf_counter()
            emit_stream_event("llm_started", operation=response_model.__name__)
            async with self._client() as client:
                response = await client.chat.completions.parse(
                    **kwargs, response_format=response_model
                )
            _emit_llm_finished(response, response_model.__name__, started_at, None)
            message = _completed_message(response)
            if message.parsed is None or not message.content:
                raise ValueError("Модель не вернула структурированный ответ.")
            # Проверяем исходный JSON: приведение типов в SDK может скрыть ошибку
            # провайдера, который не соблюдает строгую схему.
            return response_model.model_validate_json(message.content, strict=True)

        messages[0]["content"] += (
            f"\n\nПередай результат ровно одним вызовом инструмента {RESULT_TOOL_NAME}."
        )
        result_tool = {
            "type": "function",
            "function": {
                "name": RESULT_TOOL_NAME,
                "description": f"Submit the final {response_model.__name__} result.",
                "parameters": response_model.model_json_schema(),
            },
        }
        async with self._client() as client:
            for attempt in range(STRUCTURED_OUTPUT_ATTEMPTS):
                response = await self._request_completion(
                    client=client,
                    kwargs={
                        **self._completion_kwargs(messages=messages, temperature=temperature),
                        "tools": [result_tool],
                        # Z.ai поддерживает auto, без strict и принудительного выбора функции.
                        "tool_choice": "auto",
                    },
                    operation=response_model.__name__,
                    stream=stream,
                )
                # Отказ и обрыв ответа не исправляются повторной проверкой формата.
                message = response.choices[0].message
                try:
                    return _parse_tool_result(message, response_model)
                except ValueError as error:
                    issues = _validation_issues(error)
                    logger.warning(
                        "Invalid LLM output: schema=%s attempt=%s issues=%s",
                        response_model.__name__,
                        attempt + 1,
                        issues,
                    )
                    if attempt == STRUCTURED_OUTPUT_ATTEMPTS - 1:
                        raise StructuredOutputError(
                            "Модель не вернула корректный структурированный результат "
                            f"через {RESULT_TOOL_NAME} после {STRUCTURED_OUTPUT_ATTEMPTS} попыток."
                        ) from None
                    # Повторяем запрос по исходным данным, без сломанных вызовов в истории.
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Предыдущая попытка не прошла проверку структуры результата. "
                                "Исправь перечисленные ошибки полей. Данные для ответа и схема "
                                "инструмента остаются прежними. Верни полный результат заново, "
                                "без комментариев об ошибках внутри полей ответа. "
                                f"Вызови {RESULT_TOOL_NAME} ровно один раз с аргументами, "
                                "соответствующими схеме инструмента.\n\n"
                                + prompt_data("validation_errors", issues)
                            ),
                        }
                    )
                    emit_stream_event(
                        "llm_retry",
                        operation=response_model.__name__,
                        attempt=attempt + 2,
                        max_attempts=STRUCTURED_OUTPUT_ATTEMPTS,
                    )
        raise AssertionError("Structured output attempt budget must be positive")

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stream: bool = False,
    ) -> ChatCompletion:
        kwargs = self._completion_kwargs(messages=messages, temperature=temperature)
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        async with self._client() as client:
            response = await self._request_completion(
                client=client,
                kwargs=kwargs,
                operation="tool_selection",
                stream=stream,
            )
        return response

    async def _request_completion(
        self,
        *,
        client: AsyncOpenAI,
        kwargs: dict[str, Any],
        operation: str,
        stream: bool,
    ) -> ChatCompletion:
        started_at = perf_counter()
        emit_stream_event("llm_started", operation=operation)
        if stream:
            response, first_delta_ms = await stream_completion(
                client,
                kwargs,
                expose_reasoning=self.settings.expose_reasoning,
                tool_stream=self.settings.tool_stream,
                operation=operation,
            )
        else:
            response = await client.chat.completions.create(**kwargs)
            first_delta_ms = None
        try:
            _completed_message(response)
        finally:
            _emit_llm_finished(response, operation, started_at, first_delta_ms)
        return response

    def _completion_kwargs(
        self, *, messages: list[dict[str, Any]], temperature: float
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.settings.max_output_tokens,
        }
        if self.settings.send_temperature:
            kwargs["temperature"] = temperature
        provider_options: dict[str, Any] = {}
        if self.settings.reasoning_effort is not None:
            provider_options["reasoning_effort"] = self.settings.reasoning_effort
        if self.settings.thinking_mode is not None:
            provider_options["thinking"] = {"type": self.settings.thinking_mode}
        if provider_options:
            kwargs["extra_body"] = provider_options
        return kwargs


@lru_cache(maxsize=1)
def get_llm_adapter() -> LLMAdapter:
    return OpenAICompatibleLLMAdapter()


def _completed_message(response: ChatCompletion) -> Any:
    if not response.choices:
        raise IncompleteOutputError("missing_choices")
    choice = response.choices[0]
    if choice.message.refusal:
        raise IncompleteOutputError("refusal")
    if choice.finish_reason not in {"stop", "tool_calls"}:
        raise IncompleteOutputError(
            choice.finish_reason
            if choice.finish_reason in {"length", "content_filter"}
            else "other_finish"
        )
    return choice.message


def _parse_tool_result(message: Any, response_model: type[ParsedModel]) -> ParsedModel:
    calls = message.tool_calls or []
    if len(calls) != 1:
        raise ValueError(f"Ожидался ровно один вызов {RESULT_TOOL_NAME}.")
    call = calls[0]
    if call.type != "function" or call.function.name != RESULT_TOOL_NAME:
        raise ValueError(f"Ожидался инструмент {RESULT_TOOL_NAME}.")
    return response_model.model_validate_json(call.function.arguments, strict=True)


def _validation_issues(error: ValueError) -> list[dict[str, Any]]:
    """Оставляет пути и типы ошибок без текста ответа и входных значений."""
    if not isinstance(error, ValidationError):
        return [{"loc": [], "type": "invalid_tool_call"}]
    issues = []
    for item in error.errors(include_input=False, include_context=False, include_url=False)[:8]:
        path = [part if isinstance(part, int) else part[:120] for part in item["loc"][:8]]
        issues.append({"loc": path, "type": item["type"]})
    return issues


def _emit_llm_finished(
    response: ChatCompletion,
    operation: str,
    started_at: float,
    first_delta_ms: float | None,
) -> None:
    choice = response.choices[0] if response.choices else None
    finish_reason = choice.finish_reason if choice is not None else None
    if choice is not None and (choice.message.refusal or finish_reason == "content_filter"):
        status = "refused"
    elif choice is None or finish_reason not in {"stop", "tool_calls"}:
        status = "incomplete"
    else:
        status = "completed"
    usage = response.usage
    usage_data = {
        "input_tokens": usage.prompt_tokens if usage is not None else None,
        "output_tokens": usage.completion_tokens if usage is not None else None,
        "total_tokens": usage.total_tokens if usage is not None else None,
    }
    emit_stream_event(
        "llm_finished",
        operation=operation,
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
        ttft_ms=first_delta_ms,
        status=status,
        finish_reason=finish_reason,
        usage=usage_data,
    )
