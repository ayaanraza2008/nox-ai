"""Safety and capability tests for the optional RuView companion adapter."""
import os
import unittest
from unittest.mock import patch

from backend import ruview_companion as ruview


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
            self.assertEqual(command[-4:], ["--seconds", str(ruview.CAPTURE_SECONDS), "--analyze"][-4:])
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


if __name__ == "__main__":
    unittest.main()
