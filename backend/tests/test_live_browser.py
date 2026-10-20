import asyncio
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from backend import live_browser


class _BrowserTestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"""<!doctype html><html><head><title>NOX Browser Test</title></head><body>
        <label for="q">Search</label><input id="q">
        <button onclick="document.getElementById('status').textContent='clicked'">More</button>
        <div id="status">ready</div></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


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


class LiveBrowserIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_chromium_navigation_fill_click_inspect_and_screenshot(self):
        try:
            import playwright.async_api  # noqa: F401
        except ImportError:
            self.skipTest("Optional Playwright dependency is not installed.")
        server = ThreadingHTTPServer(("127.0.0.1", 0), _BrowserTestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        session = live_browser.BrowserSession("isolated-test-owner")
        try:
            with patch.dict(os.environ, {"NOX_BROWSER_ALLOW_LOCAL_TESTS": "1", "NOX_BROWSER_HEADLESS": "1"}):
                url = f"http://127.0.0.1:{server.server_port}/"
                await session.run_action("navigate", value=url)
                await session.run_action("fill", value="Search", text="NOX test")
                await session.run_action("click", value="More")
                report = await session.run_action("inspect")
                self.assertEqual(report["page_title"], "NOX Browser Test")
                self.assertIn("clicked", report["result"])
                screenshot = await session.screenshot()
                self.assertTrue(screenshot.startswith(b"\\x89PNG\\r\\n\\x1a\\n"))
        finally:
            await session.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
