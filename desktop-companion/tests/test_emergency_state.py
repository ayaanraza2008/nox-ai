"""Tests for the persistent local companion Emergency Stop latch."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from emergency_state import get_state, set_stopped, state_path


class EmergencyStateTests(unittest.TestCase):
    def test_stop_persists_across_reads_and_resume_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "state.json")
            with patch.dict(os.environ, {"NOX_COMPANION_STATE_PATH": path}, clear=False):
                self.assertFalse(get_state()["stopped"])
                stopped = set_stopped(True, "test")
                self.assertTrue(stopped["stopped"])
                self.assertTrue(get_state()["stopped"])
                resumed = set_stopped(False, "explicit_test_resume")
                self.assertFalse(resumed["stopped"])
                self.assertFalse(get_state()["stopped"])

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "state.json")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("{broken")
            with patch.dict(os.environ, {"NOX_COMPANION_STATE_PATH": path}, clear=False):
                self.assertTrue(get_state()["stopped"])


if __name__ == "__main__":
    unittest.main()
