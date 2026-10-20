"""Regression tests for remote browser destination safety."""
import unittest
from backend.browser_automation import BrowserAgent, BrowserAgentError, page_state_changed

class BrowserSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_http_scheme(self):
        with self.assertRaises(BrowserAgentError):
            await BrowserAgent()._public_url("file:///etc/passwd")
    async def test_rejects_localhost(self):
        with self.assertRaises(BrowserAgentError):
            await BrowserAgent()._public_url("http://localhost:8000/")
    async def test_rejects_private_ip(self):
        with self.assertRaises(BrowserAgentError):
            await BrowserAgent()._public_url("http://127.0.0.1/")
    async def test_rejects_embedded_credentials(self):
        with self.assertRaises(BrowserAgentError):
            await BrowserAgent()._public_url("https://user:password@example.com/")
    async def test_field_values_are_redacted_from_task_summary(self):
        summary = BrowserAgent()._safe_command_summary("type MySecret123 into the password field")
        self.assertNotIn("MySecret123", summary)
        self.assertIn("[value redacted]", summary)

    async def test_page_state_change_requires_observable_change(self):
        before = {"url": "https://example.com/", "title": "Example", "body_sha256": "same"}
        self.assertFalse(page_state_changed(before, dict(before)))
        self.assertTrue(page_state_changed(before, {**before, "url": "https://example.com/next"}))
        self.assertTrue(page_state_changed(before, {**before, "body_sha256": "changed"}))

    async def test_idle_state(self):
        result = await BrowserAgent().state("test-owner")
        self.assertFalse(result["active"])
        self.assertEqual(result["status"], "idle")

if __name__ == "__main__":
    unittest.main()
