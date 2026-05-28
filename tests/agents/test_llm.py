import json
import traceback
import unittest
from unittest.mock import patch

import httpx
import openai
from pydantic import BaseModel, Field, ValidationError

from sdm.agents.llm import (
    IncompleteOutputError,
    LLMSettings,
    OpenAICompatibleLLMAdapter,
    StructuredOutputError,
)
from sdm.agents.project_qa.evidence.validation import grounded_draft_model
from sdm.agents.streaming import collect_stream_metrics


class NestedResult(BaseModel):
    label: str
    note: str | None = None


class StructuredResult(BaseModel):
    result: NestedResult
    count: int = Field(default=0)


def completion(
    content='{"result":{"label":"ok","note":null},"count":1}', *, finish_reason="stop", refusal=None
):
    return {
        "id": "chat-test",
        "object": "chat.completion",
        "created": 1,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content, "refusal": refusal},
            }
        ],
    }


def tool_completion(arguments=None, *, name="submit_result"):
    payload = completion(None, finish_reason="tool_calls")
    payload["choices"][0]["message"]["tool_calls"] = [
        {
            "id": "call-result",
            "type": "function",
            "function": {
                "name": name,
                "arguments": (
                    '{"result":{"label":"ok","note":null},"count":1}'
                    if arguments is None
                    else arguments
                ),
            },
        }
    ]
    return payload


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def adapter(self, payload, *, status_code=200, **settings_overrides):
        settings = LLMSettings(
            api_key="offline-test-secret",
            base_url="https://llm.invalid/v1",
            model="test-model",
            **settings_overrides,
        )
        requests = []

        def handle(request):
            requests.append(request)
            response = payload[len(requests) - 1] if isinstance(payload, list) else payload
            return httpx.Response(status_code, json=response)

        transport = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        client = openai.AsyncOpenAI(
            api_key="offline-test-secret",
            base_url="https://llm.invalid/v1",
            http_client=transport,
            max_retries=0,
        )
        adapter = OpenAICompatibleLLMAdapter(settings)
        factory = patch.object(adapter, "_client", return_value=client)
        factory.start()
        self.addCleanup(factory.stop)
        self.addAsyncCleanup(transport.aclose)
        return adapter, requests, transport

    async def parse(self, adapter):
        return await adapter.parse_pydantic(
            response_model=StructuredResult,
            system_prompt="Summarize",
            user_prompt="Facts",
            temperature=0.2,
        )

    async def test_all_structured_modes_use_chat_completions_and_close_transport(self):
        for mode in ["tool_calling", "json_schema"]:
            with self.subTest(mode=mode):
                response = tool_completion() if mode == "tool_calling" else completion()
                adapter, requests, transport = self.adapter(response, response_format=mode)
                result = await self.parse(adapter)
                self.assertEqual(result.result.label, "ok")
                self.assertEqual(result.count, 1)
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0].method, "POST")
                self.assertEqual(requests[0].url.path, "/v1/chat/completions")
                payload = json.loads(requests[0].content)
                self.assertEqual(payload["model"], "test-model")
                self.assertEqual(payload["temperature"], 0.2)
                self.assertEqual(payload["max_tokens"], 8192)
                if mode == "tool_calling":
                    self.assertNotIn("response_format", payload)
                    self.assertEqual(payload["tool_choice"], "auto")
                    self.assertEqual(len(payload["tools"]), 1)
                    function = payload["tools"][0]["function"]
                    self.assertEqual(function["name"], "submit_result")
                    self.assertEqual(function["parameters"], StructuredResult.model_json_schema())
                    self.assertNotIn("strict", function)
                    self.assertNotIn("parallel_tool_calls", payload)
                else:
                    self.assertEqual(payload["response_format"]["type"], mode)
                    self.assertNotIn("tools", payload)
                    self.assertEqual(payload["messages"][0]["content"], "Summarize")
                self.assertEqual(payload["messages"][1]["content"], "Facts")
                self.assertNotIn("JSON", payload["messages"][0]["content"])
                self.assertNotIn('"properties"', json.dumps(payload["messages"]))
                self.assertTrue(transport.is_closed)

    async def test_schema_mode_uses_sdk_strict_nested_schema(self):
        adapter, requests, _ = self.adapter(completion(), response_format="json_schema")
        await self.parse(adapter)
        response_format = json.loads(requests[0].content)["response_format"]
        self.assertTrue(response_format["json_schema"]["strict"])
        schema = response_format["json_schema"]["schema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), {"result", "count"})
        nested = schema["$defs"]["NestedResult"]
        self.assertFalse(nested["additionalProperties"])
        self.assertEqual(set(nested["required"]), {"label", "note"})

    async def test_tool_calls_forwarded_with_optional_temperature_disabled(self):
        payload = completion(None, finish_reason="tool_calls")
        payload["choices"][0]["message"]["tool_calls"] = [
            {"id": "call-1", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}
        ]
        adapter, requests, transport = self.adapter(payload, send_temperature=False)
        tools = [
            {
                "type": "function",
                "function": {"name": "lookup", "parameters": {"type": "object", "properties": {}}},
            }
        ]
        response = await adapter.chat_completion(
            messages=[{"role": "user", "content": "Find facts"}],
            temperature=0.2,
            tools=tools,
            tool_choice="auto",
        )
        sent = json.loads(requests[0].content)
        self.assertEqual(sent["tools"], tools)
        self.assertEqual(sent["tool_choice"], "auto")
        self.assertNotIn("temperature", sent)
        self.assertNotIn("response_format", sent)
        self.assertEqual(response.choices[0].message.tool_calls[0].function.name, "lookup")
        self.assertTrue(transport.is_closed)

    async def test_refusal_truncation_and_missing_choices_fail_without_format_retry(self):
        cases = [
            ("refusal", completion(None, refusal="Cannot answer")),
            ("truncated", completion(finish_reason="length")),
            ("filtered", completion(finish_reason="content_filter")),
            ("no choices", dict(completion(), choices=[])),
        ]
        for mode in ["tool_calling", "json_schema"]:
            for label, payload in cases:
                with self.subTest(mode=mode, case=label):
                    adapter, requests, transport = self.adapter(payload, response_format=mode)
                    with self.assertRaises(
                        (
                            ValueError,
                            openai.LengthFinishReasonError,
                            openai.ContentFilterFinishReasonError,
                        )
                    ):
                        await self.parse(adapter)
                    self.assertEqual(len(requests), 1)
                    self.assertTrue(transport.is_closed)

    async def test_incomplete_response_is_typed_and_accounts_usage_without_format_retry(self):
        secret = "private-response-never-publish"
        cases = [
            (completion(secret, finish_reason="length"), "length", "incomplete", "length"),
            (
                completion(secret, finish_reason="content_filter"),
                "content_filter",
                "refused",
                "content_filter",
            ),
            (completion(None, refusal=secret), "refusal", "refused", "stop"),
            (dict(completion(), choices=[]), "missing_choices", "incomplete", None),
        ]
        for payload, reason, status, finish_reason in cases:
            with self.subTest(reason=reason):
                payload["usage"] = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
                adapter, requests, transport = self.adapter(payload)
                events = []
                with (
                    collect_stream_metrics() as metrics,
                    patch("sdm.agents.streaming.get_stream_writer", return_value=events.append),
                    self.assertRaises(IncompleteOutputError) as caught,
                ):
                    await self.parse(adapter)
                self.assertEqual(caught.exception.reason, reason)
                self.assertNotIn(secret, str(caught.exception))
                self.assertNotIn(secret, json.dumps(events))
                self.assertEqual(len(requests), 1)
                self.assertNotIn("llm_retry", [event["event"] for event in events])
                finishes = [event["data"] for event in events if event["event"] == "llm_finished"]
                self.assertEqual(len(finishes), 1)
                self.assertEqual(finishes[0]["status"], status)
                self.assertEqual(finishes[0]["finish_reason"], finish_reason)
                self.assertEqual(
                    metrics.snapshot()["usage"],
                    {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                    },
                )
                self.assertTrue(transport.is_closed)

    async def test_invalid_tool_outputs_are_rejected_after_bounded_retry(self):
        multiple = tool_completion()
        multiple["choices"][0]["message"]["tool_calls"].append(
            tool_completion()["choices"][0]["message"]["tool_calls"][0]
        )
        cases = {
            "text JSON is not a tool response": completion(),
            "fenced JSON is not a tool response": completion("```json\n{}\n```"),
            "empty": completion(" "),
            "malformed arguments": tool_completion("{broken"),
            "invalid schema": tool_completion('{"result":{}}'),
            "incorrect types": tool_completion('{"result":{"label":"ok"},"count":"1"}'),
            "arguments array": tool_completion("[]"),
            "arguments null": tool_completion("null"),
            "wrong tool": tool_completion(name="lookup"),
            "multiple tools": multiple,
        }
        for label, response in cases.items():
            with self.subTest(case=label):
                adapter, requests, transport = self.adapter(response)
                with self.assertRaisesRegex(StructuredOutputError, "после 2 попыток"):
                    await self.parse(adapter)
                self.assertEqual(len(requests), 2)
                self.assertTrue(transport.is_closed)

    async def test_tool_output_can_recover_without_replaying_malformed_tool_history(self):
        adapter, requests, transport = self.adapter([tool_completion("{broken"), tool_completion()])
        self.assertEqual((await self.parse(adapter)).count, 1)
        self.assertEqual(len(requests), 2)
        retry = json.loads(requests[1].content)
        self.assertEqual([m["role"] for m in retry["messages"]], ["system", "user", "user"])
        self.assertNotIn("{broken", json.dumps(retry))
        self.assertTrue(transport.is_closed)

    async def test_grounded_draft_retry_explains_shape_errors_without_replaying_output(self):
        source = {"id": "observed-source", "data": {"text": "Пилот требует согласования."}}
        schema = grounded_draft_model([source])
        claim = {
            "text": "Пилот требует согласования.",
            "evidence": [{"source_id": source["id"], "quote": source["data"]["text"]}],
        }
        secret = "private-model-output-never-repeat"
        broken = {"claims": [{**claim, "unanswered_aspects": [secret]}, secret]}
        corrected = {"claims": [claim], "unanswered_aspects": []}
        adapter, requests, transport = self.adapter(
            [tool_completion(json.dumps(broken)), tool_completion(json.dumps(corrected))]
        )
        with (
            patch("sdm.agents.llm.client.emit_stream_event") as events,
            self.assertLogs("sdm.agents.llm.client", level="WARNING") as logs,
        ):
            result = await adapter.parse_pydantic(
                response_model=schema,
                system_prompt="Подготовь черновик по источникам.",
                user_prompt="При каких условиях можно начать пилот?",
                temperature=0.1,
            )
        self.assertEqual(result.model_dump(), corrected)
        self.assertEqual(len(requests), 2)
        initial, retry = [json.loads(request.content) for request in requests]
        self.assertEqual(retry["tools"], initial["tools"])
        self.assertEqual(retry["tools"][0]["function"]["parameters"], schema.model_json_schema())
        self.assertEqual(retry["messages"][:2], initial["messages"])
        self.assertEqual(
            [message["role"] for message in retry["messages"]], ["system", "user", "user"]
        )
        feedback = retry["messages"][-1]["content"]
        payload = json.loads(
            feedback.split("<untrusted_data>\n", 1)[1].split("\n</untrusted_data>", 1)[0]
        )
        self.assertEqual(
            payload,
            {
                "label": "validation_errors",
                "data": [
                    {"loc": ["claims", 0, "unanswered_aspects"], "type": "extra_forbidden"},
                    {"loc": ["claims", 1], "type": "model_type"},
                    {"loc": ["unanswered_aspects"], "type": "missing"},
                ],
            },
        )
        for leaked in [secret, "input_value", '"input":', '"ctx":', '"msg":', '"tool_calls":']:
            self.assertNotIn(leaked, json.dumps(retry, ensure_ascii=False))
            self.assertNotIn(leaked, "\n".join(logs.output))
        retries = [call for call in events.call_args_list if call.args[0] == "llm_retry"]
        self.assertEqual(len(retries), 1)
        self.assertEqual(
            retries[0].kwargs,
            {
                "operation": "GroundedAnswerDraft",
                "attempt": 2,
                "max_attempts": 2,
            },
        )
        self.assertTrue(transport.is_closed)

    async def test_grounded_draft_exhaustion_stays_strict_and_hides_raw_failure(self):
        schema = grounded_draft_model([{"id": "observed-source", "data": {"text": "Fact"}}])
        secret = "private-invalid-claim-value"
        broken = {
            "claims": [
                {
                    "text": "Fact",
                    "evidence": [{"source_id": "observed-source", "quote": "Fact"}],
                    "unanswered_aspects": [secret],
                },
                secret,
            ],
        }
        adapter, requests, transport = self.adapter(tool_completion(json.dumps(broken)))
        with (
            patch("sdm.agents.llm.client.emit_stream_event") as events,
            self.assertLogs("sdm.agents.llm.client", level="WARNING") as logs,
            self.assertRaisesRegex(StructuredOutputError, "после 2 попыток") as caught,
        ):
            await adapter.parse_pydantic(
                response_model=schema,
                system_prompt="Подготовь черновик по источникам.",
                user_prompt="При каких условиях можно начать пилот?",
                temperature=0.1,
            )
        self.assertIsInstance(caught.exception, ValueError)
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertNotIn(secret, "".join(traceback.format_exception(caught.exception)))
        self.assertNotIn(secret, "\n".join(logs.output))
        self.assertEqual(len(requests), 2)
        self.assertEqual(sum(call.args[0] == "llm_retry" for call in events.call_args_list), 1)
        self.assertTrue(transport.is_closed)

    async def test_schema_mode_rejects_empty_malformed_and_nonconforming_results(self):
        for content in [
            " ",
            "{broken",
            '{"result":{}}',
            '{"result":{"label":"ok"},"count":"1"}',
        ]:
            with self.subTest(content=content):
                adapter, requests, transport = self.adapter(
                    completion(content), response_format="json_schema"
                )
                with self.assertRaises(ValueError):
                    await self.parse(adapter)
                self.assertEqual(len(requests), 1)
                self.assertTrue(transport.is_closed)

    async def test_http_failure_closes_transport(self):
        adapter, requests, transport = self.adapter(
            {"error": {"message": "Unavailable", "type": "server_error"}},
            status_code=503,
        )
        with self.assertRaises(openai.APIStatusError):
            await self.parse(adapter)
        self.assertEqual(len(requests), 1)
        self.assertTrue(transport.is_closed)


class SettingsTests(unittest.TestCase):
    def from_env(self, values):
        with (
            patch.dict("os.environ", values, clear=True),
            patch("sdm.agents.llm.settings.load_dotenv"),
        ):
            return LLMSettings.from_env()

    def test_requires_agent_settings_independently_of_embeddings(self):
        with self.assertRaises(ValueError) as error:
            self.from_env({"OPENAI_API_KEY": "embedding-secret", "OPENAI_MODEL": "embedding-model"})
        message = str(error.exception)
        for name in ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"]:
            self.assertIn(name, message)
        self.assertNotIn("embedding-secret", message)

    def test_missing_settings_error_never_exposes_present_key(self):
        with self.assertRaises(ValueError) as error:
            self.from_env({"LLM_API_KEY": "private-key"})
        self.assertNotIn("private-key", str(error.exception))

    def test_config_defaults_and_secret_repr(self):
        settings = self.from_env(
            {
                "LLM_API_KEY": "private-key",
                "LLM_BASE_URL": "https://llm.invalid/v1",
                "LLM_MODEL": "chat-model",
            }
        )
        self.assertEqual(settings.response_format, "tool_calling")
        self.assertEqual(settings.timeout_seconds, 60)
        self.assertEqual(settings.max_output_tokens, 8192)
        self.assertEqual(settings.max_retries, 2)
        self.assertTrue(settings.send_temperature)
        self.assertNotIn("private-key", repr(settings))

    def test_invalid_configuration_values(self):
        env = {
            "LLM_API_KEY": "private-key",
            "LLM_BASE_URL": "https://llm.invalid/v1",
            "LLM_MODEL": "chat-model",
        }
        for name, value in [
            ("LLM_TIMEOUT_SECONDS", "0"),
            ("LLM_TIMEOUT_SECONDS", "601"),
            ("LLM_TIMEOUT_SECONDS", "nan"),
            ("LLM_TIMEOUT_SECONDS", "not-a-number"),
            ("LLM_MAX_OUTPUT_TOKENS", "0"),
            ("LLM_MAX_OUTPUT_TOKENS", "-1"),
            ("LLM_MAX_OUTPUT_TOKENS", "1.5"),
            ("LLM_MAX_RETRIES", "-1"),
            ("LLM_MAX_RETRIES", "7"),
            ("LLM_MAX_RETRIES", "1.5"),
            ("LLM_BASE_URL", "not-a-url"),
            ("LLM_RESPONSE_FORMAT", "xml"),
            ("LLM_RESPONSE_FORMAT", "text"),
            ("LLM_RESPONSE_FORMAT", "json_object"),
            ("LLM_SEND_TEMPERATURE", "perhaps"),
        ]:
            with self.subTest(name=name, value=value), self.assertRaises(ValidationError) as error:
                self.from_env({**env, name: value})
            self.assertNotIn("private-key", str(error.exception))

    def test_optional_settings_are_parsed_from_environment(self):
        settings = self.from_env(
            {
                "LLM_API_KEY": "private-key",
                "LLM_BASE_URL": "https://llm.invalid/v1",
                "LLM_MODEL": "chat-model",
                "LLM_RESPONSE_FORMAT": "json_schema",
                "LLM_TIMEOUT_SECONDS": "12.5",
                "LLM_MAX_OUTPUT_TOKENS": "4096",
                "LLM_MAX_RETRIES": "0",
                "LLM_SEND_TEMPERATURE": "false",
            }
        )
        self.assertEqual(settings.timeout_seconds, 12.5)
        self.assertEqual(settings.max_output_tokens, 4096)
        self.assertEqual(settings.response_format, "json_schema")
        self.assertEqual(settings.max_retries, 0)
        self.assertFalse(settings.send_temperature)
