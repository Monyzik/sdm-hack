from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any, Literal, Protocol, TypeVar

import openai
from dotenv import load_dotenv
from pydantic import BaseModel


load_dotenv()

_ParsedModelT = TypeVar("_ParsedModelT", bound=BaseModel)
_ProviderName = Literal["openai", "yandex"]


class LLMAdapter(Protocol):
    provider: _ProviderName
    model: str

    async def parse_pydantic(
        self,
        *,
        response_model: type[_ParsedModelT],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> _ParsedModelT:
        ...

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        ...


class OpenAILLMAdapter:
    provider: _ProviderName = "openai"

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Не задан OPENAI_API_KEY в окружении.")

        self.model = os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL")
        if not self.model:
            raise ValueError("Не задан OPENAI_MODEL или LLM_MODEL в окружении.")

        base_url = os.getenv("OPENAI_BASE_URL")
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = openai.AsyncOpenAI(**client_kwargs)

    async def parse_pydantic(
        self,
        *,
        response_model: type[_ParsedModelT],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> _ParsedModelT:
        response = await self.client.responses.parse(
            model=self.model,
            instructions=system_prompt,
            input=user_prompt,
            temperature=temperature,
            text_format=response_model,
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is not None:
            return parsed

        for output in getattr(response, "output", []):
            if getattr(output, "type", None) != "message":
                continue
            for item in getattr(output, "content", []):
                if getattr(item, "type", None) == "refusal":
                    raise ValueError(f"Модель отказалась отвечать: {item.refusal}")
                item_parsed = getattr(item, "parsed", None)
                if item_parsed is not None:
                    return item_parsed

        raise ValueError("Модель не вернула распарсенный ответ.")

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        return await self.client.chat.completions.create(
            **_chat_completion_kwargs(
                model=self.model,
                messages=messages,
                temperature=temperature,
                tools=tools,
                tool_choice=tool_choice,
                response_format=response_format,
            )
        )


class YandexLLMAdapter:
    provider: _ProviderName = "yandex"

    def __init__(self) -> None:
        api_key = os.getenv("YANDEX_CLOUD_API_KEY")
        if not api_key:
            raise ValueError("Не задан YANDEX_CLOUD_API_KEY в окружении.")

        folder = os.getenv("YANDEX_CLOUD_FOLDER")
        raw_model = os.getenv("YANDEX_CLOUD_MODEL") or os.getenv("LLM_MODEL")
        if not raw_model:
            raise ValueError("Не задан YANDEX_CLOUD_MODEL в окружении.")
        if raw_model.startswith("gpt://"):
            self.model = raw_model
        else:
            if not folder:
                raise ValueError("Не задан YANDEX_CLOUD_FOLDER в окружении.")
            self.model = f"gpt://{folder}/{raw_model}"

        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=folder,
        )

    async def parse_pydantic(
        self,
        *,
        response_model: type[_ParsedModelT],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> _ParsedModelT:
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False, indent=2)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{system_prompt}\n\n"
                        "Отвечай только валидным JSON без markdown. "
                        f"Ответ должен соответствовать Pydantic-схеме {response_model.__name__}."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{user_prompt}\n\nJSON Schema {response_model.__name__}:\n{schema}",
                },
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        response_text = response.choices[0].message.content or "{}"
        return response_model.model_validate(_parse_json(response_text))

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        return await self.client.chat.completions.create(
            **_chat_completion_kwargs(
                model=self.model,
                messages=messages,
                temperature=temperature,
                tools=tools,
                tool_choice=tool_choice,
                response_format=response_format,
            )
        )


@lru_cache(maxsize=1)
def get_llm_adapter() -> LLMAdapter:
    provider = _provider_name()
    if provider == "openai":
        return OpenAILLMAdapter()
    return YandexLLMAdapter()


def _provider_name() -> _ProviderName:
    provider = (os.getenv("LLM_PROVIDER") or "yandex").strip().casefold()
    if provider in {"openai", "yandex"}:
        return provider
    raise ValueError("LLM_PROVIDER должен быть openai или yandex.")


def _chat_completion_kwargs(
    *,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    tools: list[dict[str, Any]] | None,
    tool_choice: str | dict[str, Any] | None,
    response_format: dict[str, Any] | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools is not None:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice
    if response_format is not None:
        kwargs["response_format"] = response_format
    return kwargs


def _parse_json(response_text: str) -> dict[str, Any]:
    try:
        value = json.loads(response_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Модель вернула JSON не в формате объекта.")
    return value
