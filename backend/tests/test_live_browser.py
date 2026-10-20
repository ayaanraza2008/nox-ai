import os
import unittest
from unittest.mock import patch

from backend import live_browser


class BrowserPlannerTests(unittest.TestCase):
    def test_explicit_url_creates_navigation_and_inspection(self):
        plan = live_browser.plan_instruction("Open https://example.com and tell me what it does")
        self.assertEqual([step["action"] for step in plan], ["navigate", "inspect"])
        self.assertEqual(plan[0]["value"], "https://example.com")

    def test_search_command_uses_encoded_query(self):
        plan = live_browser.plan_instruction("NOX, search the web for free open source browser automation")
        self.assertEqual(plan[0]["action"], "navigate")
        self.assertIn("free+open+source+browser+automation", plan[0]["value"])

    def test_click_and_fill_commands_are_explicit(self):
        self.assertEqual(live_browser.plan_instruction('click "Sign in"')[0]["value"], "Sign in")
        fill = live_browser.plan_instruction('type "sample text" into "Search"')[0]
        self.assertEqual((fill["action"], fill["value"], fill["text"]), ("fill", "Search", "sample text"))

    def test_unknown_command_requests_clarification(self):
        plan = live_browser.plan_instruction("do my entire account setup")
        self.assertEqual(plan[0]["action"], "clarify")
        self.assertTrue(plan[0]["value"])

    def test_rejects_non_http_and_credential_urls(self):
        for url in ("javascript:alert(1)", "file:///etc/passwd", "https://user:pass@example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                live_browser._public_http_url(url)

    def test_rejects_local_destinations(self):
        for url in ("http://localhost", "http://127.0.0.1", "http://192.168.1.1", "http://router.local"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                live_browser._public_http_url(url)

    def test_session_status_does_not_report_fake_browser(self):
        session = live_browser.BrowserSession("test-owner")
        status = session.snapshot()
        self.assertFalse(status["available"])
        self.assertEqual(status["state"], "idle")
        self.assertFalse(status["history"])

    def test_feature_is_disabled_without_explicit_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            session = live_browser.BrowserSession("test-owner")
            self.assertFalse(session.snapshot()["enabled"])


if __name__ == "__main__":
    unittest.main()
