"""Health endpoint regressions: liveness must not depend on optional storage."""
import asyncio
import unittest
from unittest.mock import patch

from backend import main


class HealthEndpointTests(unittest.TestCase):
    def test_liveness_health_is_fast_and_does_not_probe_databases(self):
        with patch.object(main, "pair_db", side_effect=AssertionError("liveness probed pairing DB")), patch.object(
            main.task_manager, "_connect", side_effect=AssertionError("liveness probed task DB")
        ):
            result = asyncio.run(main.health())

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["service"], "NOX AI")
        self.assertEqual(result["healthcheck"], "liveness_only")
        self.assertIn("ai_providers_configured", result)

    def test_detailed_health_reports_missing_ai_provider_as_degraded(self):
        with patch.dict("os.environ", {
            "OPENROUTER_API_KEY": "",
            "GROQ_API_KEY": "",
            "GEMINI_API_KEY": "",
        }), patch.object(main, "pair_db") as pair_db, patch.object(main.task_manager, "_connect") as task_connect:
            pair_db.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (1,)
            task_connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (1,)
            result = asyncio.run(main.health_details())

        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["ai_configured"])
        self.assertIsNotNone(result["ai_setup_message"])
        self.assertTrue(result["database_connected"])
        self.assertTrue(result["task_database_connected"])

    def test_detailed_health_reports_database_failures_without_secrets(self):
        with patch.object(main, "pair_db", side_effect=RuntimeError("private database URL must not leak")), patch.object(
            main.task_manager, "_connect", side_effect=RuntimeError("private database URL must not leak")
        ):
            result = asyncio.run(main.health_details())

        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["database_connected"])
        self.assertFalse(result["task_database_connected"])
        self.assertEqual(result["database_error"], "connection_failed")
        self.assertNotIn("private database URL", str(result))


if __name__ == "__main__":
    unittest.main()
