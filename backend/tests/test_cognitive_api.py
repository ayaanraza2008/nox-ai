"""API-level tests for the Cognitive Intelligence workspace."""
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from backend import main
from backend.main import CognitiveAnalysisRequest


class CognitiveAnalysisAPITests(unittest.IsolatedAsyncioTestCase):
    def test_endpoint_is_registered(self):
        routes = {route.path for route in main.app.routes if hasattr(route, "path")}
        self.assertIn("/api/cognitive/analyze", routes)

    async def test_analysis_uses_existing_provider_and_does_not_claim_profile_storage(self):
        with patch.object(main, "provider_reply", new=AsyncMock(return_value="Observed facts and alternatives.")) as provider:
            result = await main.cognitive_analyze(CognitiveAnalysisRequest(
                mode="behavior",
                content="They have not replied to two messages.",
                language="hinglish",
            ))
        self.assertEqual(result["analysis"], "Observed facts and alternatives.")
        self.assertFalse(result["profile_saved"])
        self.assertEqual(result["data_scope"], "request_text_only")
        args = provider.await_args.args
        self.assertIn("SUPPLIED MATERIAL", args[0])
        self.assertEqual(args[1], "hinglish")
        self.assertEqual(args[2], [])

    async def test_opt_in_knowledge_uses_only_session_owner_index_and_returns_source_ids(self):
        request = object()
        source = {
            "title": "Personal notes", "text": "A habit tracking method",
            "url": "https://example.org/notes", "filename": "notes.txt",
            "source_type": "file",
        }
        with patch.object(main, "session_owner", return_value="owner-123") as owner, \
             patch.object(main.knowledge, "search_knowledge", return_value={"results": [source]}) as search, \
             patch.object(main, "provider_reply", new=AsyncMock(return_value="Evidence suggests [K1].")) as provider:
            result = await main.cognitive_analyze(CognitiveAnalysisRequest(
                mode="thinking", content="How can I improve my habit?", language="en", use_knowledge=True
            ), request=request)
        owner.assert_called_once_with(request)
        search.assert_called_once_with("owner-123", "How can I improve my habit?", limit=4)
        self.assertIn("AUTHORIZED KNOWLEDGE INDEX EVIDENCE", provider.await_args.args[0])
        self.assertTrue(result["knowledge_used"])
        self.assertTrue(result["knowledge_requested"])
        self.assertEqual(result["knowledge_sources"][0]["citation_id"], "K1")
        self.assertEqual(result["knowledge_sources"][0]["title"], "Personal notes")

    async def test_knowledge_index_is_not_touched_without_explicit_opt_in(self):
        with patch.object(main.knowledge, "search_knowledge") as search, \
             patch.object(main, "provider_reply", new=AsyncMock(return_value="Text-only analysis.")):
            result = await main.cognitive_analyze(CognitiveAnalysisRequest(
                mode="behavior", content="A supplied situation.", language="en"
            ))
        search.assert_not_called()
        self.assertFalse(result["knowledge_requested"])
        self.assertFalse(result["knowledge_used"])
        self.assertEqual(result["knowledge_sources"], [])

    async def test_knowledge_opt_in_requires_browser_session(self):
        with self.assertRaises(HTTPException) as error:
            await main.cognitive_analyze(CognitiveAnalysisRequest(
                mode="thinking", content="Find evidence", use_knowledge=True
            ))
        self.assertEqual(error.exception.status_code, 401)

    async def test_pattern_mode_returns_local_signals_without_provider(self):
        with patch.object(main, "provider_reply", new=AsyncMock(return_value=None)):
            result = await main.cognitive_analyze(CognitiveAnalysisRequest(
                mode="patterns",
                content="Deploy failed\nDeploy retried",
                language="en",
            ))
        self.assertEqual(result["provider_status"], "unavailable_local_patterns_only")
        self.assertEqual(result["observed_patterns"]["sample_count"], 2)
        self.assertIn("not proof", result["observed_patterns"]["limitations"])
        self.assertFalse(result["profile_saved"])

    async def test_missing_provider_returns_clear_service_error(self):
        with patch.object(main, "provider_reply", new=AsyncMock(return_value=None)):
            with self.assertRaises(HTTPException) as error:
                await main.cognitive_analyze(CognitiveAnalysisRequest(
                    mode="stoicism", content="A setback", language="en"
                ))
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("configured AI provider", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
