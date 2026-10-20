"""Regression tests for remote browser destination safety."""
import unittest
from backend.browser_automation import BrowserAgent, BrowserAgentError

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
    async def test_idle_state(self):
        result = await BrowserAgent().state("test-owner")
        self.assertFalse(result["active"])
        self.assertEqual(result["status"], "idle")

if __name__ == "__main__":
    unittest.main()
