"""Tests for the persistent local companion Emergency Stop latch."""
import json
import os
import subprocess
import sys
import time
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from emergency_state import get_state, register_process, set_stopped, state_path, unregister_process


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

    def test_stop_terminates_only_a_registered_managed_process(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "state.json")
            with patch.dict(os.environ, {"NOX_COMPANION_STATE_PATH": path}, clear=False):
                process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
                try:
                    self.assertTrue(register_process(process))
                    result = set_stopped(True, "managed_process_test")
                    self.assertTrue(result["stopped"])
                    process.wait(timeout=2)
                    self.assertIsNotNone(process.returncode)
                    self.assertTrue(any(item["status"] == "terminated_managed_process"
                                        for item in result["process_cleanup"]))
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    unregister_process(process)

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "state.json")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("{broken")
            with patch.dict(os.environ, {"NOX_COMPANION_STATE_PATH": path}, clear=False):
                self.assertTrue(get_state()["stopped"])


if __name__ == "__main__":
    unittest.main()
