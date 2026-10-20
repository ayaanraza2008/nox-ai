import os
import unittest
from unittest.mock import patch

from backend.main import _gods_eye_view_config


class GodsEyeViewConfigTests(unittest.TestCase):
    def test_external_service_url_never_enables_navigation(self):
        with patch.dict(os.environ, {"GODS_EYE_VIEW_URL": "https://nox-gods-eye-view.onrender.com/"}):
            result = _gods_eye_view_config()
        self.assertFalse(result["configured"])
        self.assertIsNone(result["url"])
        self.assertEqual(result["launch_mode"], "native_integration_pending")
        self.assertIn("External dashboard launches are intentionally disabled", result["reason"])

    def test_unset_service_url_reports_native_integration_pending(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GODS_EYE_VIEW_URL", None)
            result = _gods_eye_view_config()
        self.assertFalse(result["configured"])
        self.assertIsNone(result["url"])
        self.assertEqual(result["status"], "native_integration_pending")

    def test_upstream_reference_is_preserved_for_traceability(self):
        result = _gods_eye_view_config()
        self.assertEqual(result["upstream_repository"], "https://github.com/bilawalsidhu/gods-eye-view")
        self.assertEqual(result["upstream_commit"], "505d2cb5861905c76a98465799a29e1fd71b869b")


if __name__ == "__main__":
    unittest.main()
