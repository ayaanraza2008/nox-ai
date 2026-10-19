"""Regression tests for multimodal chat provider routing."""
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend import main


class FakeResponse:
    status_code = 200
    text = ""

    def json(self):
        return {"choices": [{"message": {"content": "The image shows a sample object."}}]}


class FakeClient:
    def __init__(self, **kwargs):
        self.payload = None
        self.url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        self.url = url
        self.payload = json
        return FakeResponse()


class MultimodalChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_is_sent_as_multimodal_content_to_configured_vision_model(self):
        client = FakeClient()
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL": "openrouter/free",
            "OPENROUTER_VISION_MODEL": "provider/vision-model",
        }, clear=True), patch.object(main.httpx, "AsyncClient", return_value=client):
            answer = await main.provider_reply(
                "What is in this picture?",
                "en",
                [],
                ["data:image/png;base64,ZmFrZQ=="],
            )

        self.assertEqual(answer, "The image shows a sample object.")
        self.assertEqual(client.payload["model"], "provider/vision-model")
        content = client.payload["messages"][-1]["content"]
        self.assertEqual(content[0], {"type": "text", "text": "What is in this picture?"})
        self.assertEqual(content[1]["type"], "image_url")
        self.assertEqual(content[1]["image_url"]["url"], "data:image/png;base64,ZmFrZQ==")

    async def test_invalid_image_payload_is_rejected_before_provider_call(self):
        payload = main.ChatRequest(message="Analyze this", images=["https://example.com/not-a-data-url"])
        with patch.object(main, "provider_reply", side_effect=AssertionError("provider must not be called")):
            with self.assertRaises(HTTPException) as raised:
                await main.chat(payload)
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
