import json
import unittest
from datetime import date
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from sdm.agents.api import create_app
from sdm.agents.llm import IncompleteOutputError, StructuredOutputError

INVALID_OUTPUT_MESSAGE = (
    "Модель не смогла подготовить ответ по заданной структуре после повторной попытки. "
    "Повторите запрос."
)


class AgentsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())
        self.addCleanup(self.client.close)

    def test_health_and_public_routes(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertEqual(
            set(paths),
            {
                "/health",
                "/api/v1/agents/projects/{project_id}/ask",
                "/api/v1/agents/projects/{project_id}/ask/stream",
            },
        )

    def test_question_service_receives_validated_input(self):
        with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as agent:
            run = agent.return_value.answer = AsyncMock(return_value={"answer": "Ready"})
            response = self.client.post(
                "/api/v1/agents/projects/P1/ask",
                json={
                    "question": "Status?",
                    "as_of": "2026-06-19",
                    "max_depth": 3,
                    "conversation_context": [{"role": "user", "content": "Hello"}],
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Ready")
        self.assertEqual(run.call_args.kwargs["project_id"], "P1")
        self.assertEqual(run.call_args.kwargs["as_of"], date(2026, 6, 19))
        self.assertEqual(run.call_args.kwargs["conversation_context"][0].content, "Hello")

    def test_question_errors_are_sanitized(self):
        for error, status in [
            (TimeoutError("private secret"), 504),
            (ValueError("private secret"), 503),
            (RuntimeError("private secret"), 503),
            (Exception("private secret"), 502),
        ]:
            with (
                self.subTest(error=type(error)),
                patch(
                    "sdm.agents.routes.assistance.ProjectQuestionAgent",
                ) as agent,
            ):
                agent.return_value.answer = AsyncMock(side_effect=error)
                response = self.client.post(
                    "/api/v1/agents/projects/P1/ask", json={"question": "Status?"}
                )
                self.assertEqual(response.status_code, status)
                self.assertNotIn("private secret", response.text)

    def test_invalid_question_input_never_calls_service(self):
        with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as agent:
            for payload in [{"question": ""}, {"question": "Status?", "max_depth": 5}]:
                self.assertEqual(
                    self.client.post("/api/v1/agents/projects/P1/ask", json=payload).status_code,
                    422,
                )
            agent.assert_not_called()

    def test_verification_flag_is_forwarded_with_safe_default_on_both_endpoints(self):
        for suffix in ("", "/stream"):
            for extra, expected in [
                ({}, True),
                ({"verify_claims": True}, True),
                ({"verify_claims": False}, False),
            ]:
                with self.subTest(suffix=suffix, payload=extra):
                    captured = []

                    async def events(**kwargs):
                        captured.append(kwargs)
                        yield {"event": "final", "data": {"answer": "Ready"}}

                    with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as agent:
                        answer = agent.return_value.answer = AsyncMock(
                            return_value={"answer": "Ready"}
                        )
                        agent.return_value.answer_stream = events
                        response = self.client.post(
                            f"/api/v1/agents/projects/P007/ask{suffix}",
                            json={"question": "Статус проекта?", **extra},
                        )
                    self.assertEqual(response.status_code, 200)
                    if suffix:
                        self.assertEqual(len(captured), 1)
                        self.assertIs(captured[0]["verify_claims"], expected)
                    else:
                        answer.assert_awaited_once()
                        self.assertIs(answer.call_args.kwargs["verify_claims"], expected)

    def test_verification_flag_rejects_non_boolean_values_before_calling_agent(self):
        for suffix in ("", "/stream"):
            for invalid in ("true", "false", "0", "1", 0, 1, None):
                with self.subTest(suffix=suffix, invalid=invalid):
                    with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as agent:
                        response = self.client.post(
                            f"/api/v1/agents/projects/P007/ask{suffix}",
                            json={"question": "Статус проекта?", "verify_claims": invalid},
                        )
                    self.assertEqual(response.status_code, 422)
                    self.assertTrue(
                        any(
                            error["loc"] == ["body", "verify_claims"]
                            for error in response.json()["detail"]
                        )
                    )
                    agent.assert_not_called()

    def test_incomplete_output_is_a_model_error_without_provider_details(self):
        error = IncompleteOutputError("length")
        error.args = ("private provider output",)
        with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as agent:
            agent.return_value.answer = AsyncMock(side_effect=error)
            response = self.client.post(
                "/api/v1/agents/projects/P007/ask", json={"question": "Статус?"}
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {"detail": "Модель не смогла завершить генерацию ответа. Повторите запрос."},
        )
        self.assertNotIn("length", response.text)
        self.assertNotIn("private provider output", response.text)

    def test_incomplete_output_ends_stream_with_safe_model_error(self):
        async def events(**kwargs):
            yield {"event": "stage", "data": {"message": "Подготовка"}}
            error = IncompleteOutputError("length")
            error.args = ("private provider output",)
            raise error

        with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as agent:
            agent.return_value.answer_stream = events
            response = self.client.post(
                "/api/v1/agents/projects/P007/ask/stream", json={"question": "Статус?"}
            )
        self.assertEqual(response.status_code, 200)
        frames = [
            dict(line.split(": ", 1) for line in frame.splitlines())
            for frame in response.text.strip().split("\n\n")
        ]
        self.assertEqual([frame["event"] for frame in frames], ["stage", "error"])
        self.assertEqual(
            json.loads(frames[-1]["data"]),
            {"message": "Модель не смогла завершить генерацию ответа. Повторите запрос."},
        )
        self.assertNotIn("length", response.text)
        self.assertNotIn("private provider output", response.text)

    def test_invalid_structured_output_returns_actionable_public_error(self):
        with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as agent:
            agent.return_value.answer = AsyncMock(
                side_effect=StructuredOutputError("private secret: claims.6.unanswered_aspects")
            )
            response = self.client.post(
                "/api/v1/agents/projects/P007/ask",
                json={"question": "При каких условиях можно начать пилот?"},
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": INVALID_OUTPUT_MESSAGE})
        self.assertNotIn("private secret", response.text)
        self.assertNotIn("claims.6", response.text)

    def test_invalid_structured_output_ends_stream_with_public_error_without_final(self):
        async def events(**kwargs):
            yield {"event": "stage", "data": {"message": "Подготовка черновика"}}
            raise StructuredOutputError("private secret: claims.6.unanswered_aspects")

        with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as agent:
            agent.return_value.answer_stream = events
            response = self.client.post(
                "/api/v1/agents/projects/P007/ask/stream",
                json={"question": "При каких условиях можно начать пилот?"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        frames = [
            dict(line.split(": ", 1) for line in frame.splitlines())
            for frame in response.text.strip().split("\n\n")
        ]
        self.assertEqual([frame["event"] for frame in frames], ["stage", "error"])
        self.assertEqual(json.loads(frames[-1]["data"]), {"message": INVALID_OUTPUT_MESSAGE})
        self.assertNotIn("private secret", response.text)
        self.assertNotIn("claims.6", response.text)

    def test_stream_events_and_errors_are_sanitized(self):
        async def events(**kwargs):
            yield {"event": "stage", "data": {"message": "Проверка"}}
            raise RuntimeError("private secret")

        with patch("sdm.agents.routes.assistance.ProjectQuestionAgent") as agent:
            agent.return_value.answer_stream = events
            response = self.client.post(
                "/api/v1/agents/projects/P1/ask/stream", json={"question": "Status?"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: stage", response.text)
        self.assertIn("event: error", response.text)
        self.assertNotIn("private secret", response.text)
        self.assertEqual(response.headers["x-accel-buffering"], "no")

    def test_cors_configuration_is_read_per_app(self):
        with patch.dict("os.environ", {"AGENTS_CORS_ORIGINS": " https://example.com, "}):
            with TestClient(create_app()) as client:
                response = client.get("/health", headers={"Origin": "https://example.com"})
        self.assertEqual(response.headers["access-control-allow-origin"], "https://example.com")
