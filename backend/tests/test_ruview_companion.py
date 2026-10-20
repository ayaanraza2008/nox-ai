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

    def test_parses_only_bounded_documented_csi_fields(self):
        summary = ruview.parse_capture_summary(
            '{"nodes":[{"source":"esp32","nodeId":2,"packets":{"csi":25},'
            '"rssiMean":-54.5,"csiRateHz":5.0,"csiLossFraction":0.02,'
            '"csi":{"frames":25,"synthetic":false},"lastVitals":{"heartBpm":70}}]}'
        )
        self.assertEqual(summary["source"], "ruview_esp32_csi_capture")
        self.assertEqual(summary["nodes"][0]["csi_frames"], 25)
        self.assertEqual(summary["nodes"][0]["rssi_mean_dbm"], -54.5)
        self.assertEqual(summary["quality"], "observed")
        self.assertNotIn("lastVitals", summary["nodes"][0])

    def test_malformed_or_non_csi_output_does_not_create_measurements(self):
        self.assertIsNone(ruview.parse_capture_summary("not JSON"))
        self.assertIsNone(ruview.parse_capture_summary('{"ok":true,"message":"no frames"}'))

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
