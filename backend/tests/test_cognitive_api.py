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
