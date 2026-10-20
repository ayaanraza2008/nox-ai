import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "cybersecurity_worker.py"
spec = importlib.util.spec_from_file_location("nox_cybersecurity_worker", path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

class LocalWorkerTests(unittest.TestCase):
    def test_rejects_missing_authorization(self):
        with self.assertRaises(worker.CybersecurityError):
            worker.validate_target("127.0.0.1", False, "my local lab")

    def test_rejects_public_target_without_allowlist(self):
        with patch.dict("os.environ", {"NOX_CYBER_ALLOWED_HOSTS": ""}):
            with self.assertRaises(worker.CybersecurityError):
                worker.validate_target("8.8.8.8", True, "authorized testing scope")

    def test_requires_exact_confirmation_before_scan(self):
        with self.assertRaises(worker.CybersecurityError):
            worker.scan_services("127.0.0.1", authorized=True, scope_note="local test lab", confirmation="yes")

    def test_discovery_does_not_launch_processes(self):
        with patch.object(worker.shutil, "which", return_value=None):
            tools = worker.discover_tools()
        self.assertTrue(tools)
        self.assertTrue(all(item["version"] is None for item in tools))

if __name__ == "__main__":
    unittest.main()
