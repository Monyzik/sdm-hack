import json
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import httpx

from sdm.backend.services.embeddings import (
    EmbeddingSettings,
    OpenAIEmbeddingClient,
    validate_embedding,
)


class EmbeddingTests(unittest.IsolatedAsyncioTestCase):
    def settings(self, **kwargs):
        return EmbeddingSettings(
            api_key="embedding-key",
            base_url="https://embedding.example/v1",
            dimensions=32,
            **kwargs,
        )

    async def test_openai_payload_and_query_only_instruction(self):
        requests = []

        def handle(request):
            requests.append(request)
            return httpx.Response(200, json={"data": [{"embedding": [0.5] * 32}]})

        client = OpenAIEmbeddingClient(self.settings(), transport=httpx.MockTransport(handle))
        self.assertEqual(await client.embed_document("Document"), [0.5] * 32)
        await client.embed_query("Question")
        self.assertEqual(str(requests[0].url), "https://embedding.example/v1/embeddings")
        self.assertEqual(requests[0].headers["authorization"], "Bearer embedding-key")
        self.assertEqual(json.loads(requests[0].content)["input"], "Document")
        self.assertTrue(json.loads(requests[1].content)["input"].endswith("\nQuery:Question"))
        self.assertEqual(json.loads(requests[0].content)["dimensions"], 32)

    async def test_retry_bounded_and_retry_after_capped(self):
        requests = []

        def handle(request):
            requests.append(request)
            return httpx.Response(429, headers={"retry-after": "999999"})

        client = OpenAIEmbeddingClient(
            self.settings(max_retries=2), transport=httpx.MockTransport(handle)
        )
        with patch(
            "sdm.backend.services.embeddings.client.asyncio.sleep", new_callable=AsyncMock
        ) as sleep:
            with self.assertRaisesRegex(RuntimeError, "429"):
                await client.embed_document("document")
        self.assertEqual(len(requests), 3)
        self.assertEqual([call.args[0] for call in sleep.await_args_list], [30, 30])

    async def test_invalid_vector_and_auth_failure_not_retried(self):
        for status, body in [(200, {"data": [{"embedding": [1]}]}), (401, {})]:
            requests = []

            def handle(request):
                requests.append(request)
                return httpx.Response(status, json=body)

            client = OpenAIEmbeddingClient(self.settings(), transport=httpx.MockTransport(handle))
            with self.assertRaises(RuntimeError):
                await client.embed_document("document")
            self.assertEqual(len(requests), 1)

    def test_identity_separates_provider_model_dimensions_instruction(self):
        settings = self.settings()
        for kwargs in [
            {"base_url": "https://other.example/v1"},
            {"model": "other"},
            {"dimensions": 64},
            {"query_instruction": "different"},
        ]:
            self.assertNotEqual(settings.index_identity, replace(settings, **kwargs).index_identity)
        self.assertEqual(
            settings.index_identity, replace(settings, api_key="rotated").index_identity
        )

    def test_invalid_settings_and_vectors(self):
        for kwargs in [
            {"base_url": ""},
            {"dimensions": 0},
            {"timeout_seconds": float("nan")},
            {"max_retries": 11},
        ]:
            with self.assertRaises(ValueError):
                replace(self.settings(), **kwargs)
        for vector in [
            [],
            [0.0] * 32,
            [float("nan")] * 32,
            [float("inf")] * 32,
            [True] * 32,
            ["1"] * 32,
        ]:
            with self.assertRaises(ValueError):
                validate_embedding(vector, 32)


if __name__ == "__main__":
    unittest.main()
