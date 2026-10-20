import os
import sys
import threading
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

COMPANION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPANION_DIR))
os.environ["NOX_COMPANION_TOKEN"] = "unit-test-companion-token"
import companion

client = TestClient(companion.app)
HEADERS = {"X-NOX-Token": "unit-test-companion-token"}

class LocalCybersecurityApiTests(unittest.TestCase):
    def test_status_requires_token(self):
        self.assertEqual(client.get("/v1/cybersecurity/status").status_code, 401)
        response = client.get("/v1/cybersecurity/status", headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertIn("tools", response.json())

    def test_scan_requires_exact_confirmation(self):
        response = client.post("/v1/cybersecurity/scans", headers=HEADERS, json={
            "target": "127.0.0.1", "authorized": True,
            "scope_note": "my local test lab", "confirmation": "yes"
        })
        self.assertEqual(response.status_code, 400)

    def test_cancel_sets_event_and_requires_token(self):
        task_id = "cyber-test-task"
        event = threading.Event()
        companion.ACTIVE_CYBER_SCANS[task_id] = {
            "task_id": task_id, "status": "running", "cancel_event": event,
            "result": None, "created_at": "test"
        }
        self.assertEqual(client.post("/v1/cybersecurity/scans/cancel", json={"task_id": task_id}).status_code, 401)
        response = client.post("/v1/cybersecurity/scans/cancel", headers=HEADERS, json={"task_id": task_id})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(event.is_set())
        companion.ACTIVE_CYBER_SCANS.pop(task_id, None)

if __name__ == "__main__":
    unittest.main()
