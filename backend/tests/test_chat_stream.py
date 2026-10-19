"""Regression tests for streaming chat, context, and provider selection."""
import json
import os
import unittest
from unittest.mock import patch

import httpx

from backend import main


class StreamingEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_endpoint_emits_incremental_sse_events_and_context(self):
        seen = {}

        async def fake_stream(message, language, history, images=None):
            seen.update(message=message, language=language, history=history, images=images)
            yield {"type": "delta", "text": "Hello "}
            yield {"type": "delta", "text": "there"}
            yield {"type": "done", "mode": "ai"}

        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch.object(main, "stream_provider_reply", fake_stream):
                response = await client.post("/api/chat/stream", json={
                    "message": "Continue this", "language": "hinglish",
                    "history": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}],
                    "images": [],
                })

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        packets = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        self.assertEqual([p["text"] for p in packets if p["type"] == "delta"], ["Hello ", "there"])
        self.assertEqual(packets[-1], {"type": "done", "mode": "ai"})
        self.assertEqual(seen["language"], "hinglish")
        self.assertEqual(seen["history"][-1]["content"], "Hello")

    async def test_stream_endpoint_rejects_invalid_image_before_streaming(self):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/chat/stream", json={
                "message": "Analyze this", "images": ["https://example.com/image.png"],
            })
        self.assertEqual(response.status_code, 400)

    def test_preferred_provider_is_moved_first_but_fallbacks_remain(self):
        providers = [{"name": "OpenRouter"}, {"name": "Groq"}, {"name": "Gemini"}]
        with patch.dict(os.environ, {"NOX_CHAT_PROVIDER": "gemini"}):
            ordered = main._prioritize_providers(providers)
        self.assertEqual([item["name"] for item in ordered], ["Gemini", "OpenRouter", "Groq"])

    def test_auto_provider_order_is_preserved(self):
        providers = [{"name": "OpenRouter"}, {"name": "Groq"}, {"name": "Gemini"}]
        with patch.dict(os.environ, {"NOX_CHAT_PROVIDER": "auto"}):
            self.assertEqual(main._prioritize_providers(providers), providers)


if __name__ == "__main__":
    unittest.main()
