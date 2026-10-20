import os
import unittest
from unittest.mock import patch

from backend.main import _gods_eye_view_config


class GodsEyeViewConfigTests(unittest.TestCase):
    def test_missing_url_is_setup_required(self):
        with patch.dict(os.environ, {}, clear=True):
            result = _gods_eye_view_config()
        self.assertFalse(result["configured"])
        self.assertEqual(result["status"], "setup_required")
        self.assertIsNone(result["url"])

    def test_render_https_url_is_accepted(self):
        with patch.dict(os.environ, {"GODS_EYE_VIEW_URL": "https://nox-gods-eye-view.onrender.com/"}, clear=True):
            result = _gods_eye_view_config()
        self.assertTrue(result["configured"])
        self.assertEqual(result["url"], "https://nox-gods-eye-view.onrender.com")
        self.assertEqual(result["upstream_commit"], "505d2cb5861905c76a98465799a29e1fd71b869b")

    def test_plain_http_is_rejected(self):
        with patch.dict(os.environ, {"GODS_EYE_VIEW_URL": "http://nox-gods-eye-view.onrender.com"}, clear=True):
            result = _gods_eye_view_config()
        self.assertFalse(result["configured"])
        self.assertIn("HTTPS", result["reason"])

    def test_custom_host_requires_exact_allowlist_entry(self):
        env = {
            "GODS_EYE_VIEW_URL": "https://globe.example.org",
            "GODS_EYE_VIEW_ALLOWED_HOSTS": "other.example.org",
        }
        with patch.dict(os.environ, env, clear=True):
            denied = _gods_eye_view_config()
        self.assertFalse(denied["configured"])
        env["GODS_EYE_VIEW_ALLOWED_HOSTS"] = "globe.example.org"
        with patch.dict(os.environ, env, clear=True):
            allowed = _gods_eye_view_config()
        self.assertTrue(allowed["configured"])

    def test_credentials_and_paths_are_rejected(self):
        for url in (
            "https://user:pass@nox-gods-eye-view.onrender.com",
            "https://nox-gods-eye-view.onrender.com/some/path",
            "https://nox-gods-eye-view.onrender.com/?next=https://example.org",
        ):
            with self.subTest(url=url), patch.dict(os.environ, {"GODS_EYE_VIEW_URL": url}, clear=True):
                self.assertFalse(_gods_eye_view_config()["configured"])


if __name__ == "__main__":
    unittest.main()
