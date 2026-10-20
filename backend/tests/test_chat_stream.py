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
            client.cookies.set("nox_account_session", "verified-session")
            with patch.object(main.accounts, "resolve_session", return_value={"id": "account-1", "status": "active"}), \
                 patch.object(main, "stream_provider_reply", fake_stream):
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

    async def test_stream_endpoint_emits_safe_error_event_for_unexpected_failure(self):
        async def broken_stream(message, language, history, images=None, knowledge_context=None):
            if False:
                yield {"type": "delta", "text": "unreachable"}
            raise RuntimeError("private internal detail")

        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.cookies.set("nox_account_session", "verified-session")
            with patch.object(main.accounts, "resolve_session", return_value={"id": "account-1", "status": "active"}), \
                 patch.object(main, "stream_provider_reply", broken_stream):
                response = await client.post("/api/chat/stream", json={"message": "Hello", "images": []})

        packets = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(packets[-1]["type"], "error")
        self.assertIn("Please retry", packets[-1]["message"])
        self.assertNotIn("private internal detail", response.text)
    async def test_stream_endpoint_rejects_invalid_image_before_streaming(self):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.cookies.set("nox_account_session", "verified-session")
            with patch.object(main.accounts, "resolve_session", return_value={"id": "account-1", "status": "active"}):
                response = await client.post("/api/chat/stream", json={
                    "message": "Analyze this", "images": ["https://example.com/image.png"],
                })
        self.assertEqual(response.status_code, 400)

    def test_streaming_retries_transient_provider_errors_once(self):
        provider = {"name": "Groq", "model": "llama-3.3-70b-versatile"}
        retry = main._stream_retry_provider(provider, status_code=503)
        self.assertIsNotNone(retry)
        self.assertEqual(retry["model"], provider["model"])
        self.assertTrue(retry["_stream_retried"])
        self.assertIsNone(main._stream_retry_provider(retry, status_code=503))

    def test_streaming_openrouter_model_error_falls_back_to_free_router(self):
        provider = {"name": "OpenRouter", "model": "some/configured-model", "key": "test"}
        fallback = main._stream_retry_provider(provider, status_code=404)
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback["model"], "openrouter/free")
        self.assertTrue(fallback["_stream_fallback_model"])
        self.assertIsNone(main._stream_retry_provider(fallback, status_code=404))

    def test_streaming_does_not_retry_authentication_failures(self):
        provider = {"name": "Groq", "model": "test-model"}
        self.assertIsNone(main._stream_retry_provider(provider, status_code=401))
        self.assertIsNone(main._stream_retry_provider(provider, status_code=403))

    def test_preferred_provider_is_moved_first_but_fallbacks_remain(self):
        providers = [{"name": "OpenRouter"}, {"name": "Groq"}, {"name": "Gemini"}]
        with patch.dict(os.environ, {"NOX_CHAT_PROVIDER": "gemini"}):
            ordered = main._prioritize_providers(providers)
        self.assertEqual([item["name"] for item in ordered], ["Gemini", "OpenRouter", "Groq"])

    def test_auto_provider_order_is_preserved(self):
        providers = [{"name": "OpenRouter"}, {"name": "Groq"}, {"name": "Gemini"}]
        with patch.dict(os.environ, {"NOX_CHAT_PROVIDER": "auto"}):
            self.assertEqual(main._prioritize_providers(providers), providers)

    def test_prompt_prioritizes_direct_relevant_answers_and_followup_context(self):
        prompt = main.build_nox_system_prompt("hinglish").lower()
        self.assertIn("answer that message directly", prompt)
        self.assertIn("use the recent conversation", prompt)
        self.assertIn("do not restate their whole prompt", prompt)
        self.assertIn("reply in the language/script the user is using", prompt)

    def test_shared_builder_keeps_followup_context_and_current_message_last(self):
        messages = main.build_chat_messages("Aur short kar", "hinglish", [
            {"role": "user", "content": "Mujhe NOX ke liye prompt bana"},
            {"role": "assistant", "content": "Ye raha prompt"},
        ])
        self.assertEqual(messages[1]["content"], "Mujhe NOX ke liye prompt bana")
        self.assertEqual(messages[2]["content"], "Ye raha prompt")
        self.assertEqual(messages[-1], {"role": "user", "content": "Aur short kar"})
        self.assertEqual(messages[0]["role"], "system")

    def test_context_builder_discards_invalid_turns_and_bounds_old_messages(self):
        messages = main.build_chat_messages("Current", "auto", [
            {"role": "tool", "content": "ignore"},
            {"role": "assistant", "content": "old assistant only"},
            {"role": "user", "content": "x" * 5000},
        ])
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(len(messages[1]["content"]), 2500)
        self.assertEqual(messages[-1]["content"], "Current")


if __name__ == "__main__":
    unittest.main()
