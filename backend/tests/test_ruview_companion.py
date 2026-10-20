"""Safety and capability tests for the optional RuView companion adapter."""
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Request
from backend import main, ruview_companion as ruview


class RuViewCompanionTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(ruview.enabled())
            self.assertFalse(ruview.status()["available"])

    def test_requires_explicit_enable_flag(self):
        with patch.dict(os.environ, {"NOX_RUVIEW_ENABLED": "true"}, clear=True):
            self.assertFalse(ruview.enabled())
        with patch.dict(os.environ, {"NOX_RUVIEW_ENABLED": "1"}, clear=True):
            self.assertTrue(ruview.enabled())

    def test_command_is_allowlisted_and_never_shell_text(self):
        instance = ruview.RuViewRunner()
        with patch.object(ruview.shutil, "which", return_value="/usr/bin/node"), patch.object(
            ruview.Path, "is_file", return_value=True
        ):
            self.assertEqual(instance._command("doctor")[-1], "doctor")
            self.assertEqual(instance._command("devices")[-1], "devices")
            command = instance._command("capture")
            self.assertEqual(command[-3:], ["--seconds", str(ruview.CAPTURE_SECONDS), "--analyze"])
            with self.assertRaises(ruview.RuViewUnavailable):
                instance._command("echo injected")

    def test_missing_node_fails_closed(self):
        instance = ruview.RuViewRunner()
        with patch.object(ruview.shutil, "which", return_value=None):
            with self.assertRaises(ruview.RuViewUnavailable):
                instance._command("doctor")

    def test_snapshot_does_not_claim_live_measurements(self):
        snapshot = ruview.RuViewRunner().snapshot()
        self.assertFalse(snapshot["running"])
        self.assertIn("ordinary browser Wi-Fi readings are not CSI", snapshot["hardware_note"])

    def _request(self, client_host="127.0.0.1", host="127.0.0.1:8000", origin=None, method="GET"):
        headers = [(b"host", host.encode())]
        if origin is not None:
            headers.append((b"origin", origin.encode()))
        scope = {
            "type": "http", "method": method, "scheme": "http",
            "server": ("127.0.0.1", 8000), "client": (client_host, 43210),
            "path": "/api/ruview/status", "raw_path": b"/api/ruview/status",
            "query_string": b"", "headers": headers,
        }
        return Request(scope)

    def test_remote_client_is_rejected_even_if_url_looks_local(self):
        with self.assertRaises(HTTPException) as caught:
            main._require_local_ruview_request(self._request(client_host="192.0.2.10"))
        self.assertEqual(caught.exception.status_code, 403)

    def test_post_requires_same_origin(self):
        with self.assertRaises(HTTPException) as caught:
            main._require_local_ruview_request(
                self._request(origin="https://attacker.example", method="POST")
            )
        self.assertEqual(caught.exception.status_code, 403)

    def test_loopback_same_origin_post_is_allowed(self):
        main._require_local_ruview_request(
            self._request(origin="http://127.0.0.1:8000", method="POST")
        )


if __name__ == "__main__":
    unittest.main()
