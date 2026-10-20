"""Tests for the owner-scoped live task event stream."""
import json
import unittest
from unittest.mock import patch

from backend import main


class FinishedRequest:
    async def is_disconnected(self):
        return False


class TaskEventStreamTests(unittest.IsolatedAsyncioTestCase):
    def test_task_event_route_is_registered(self):
        routes = {route.path for route in main.app.routes if hasattr(route, "path")}
        self.assertIn("/api/tasks/{task_id}/events", routes)

    async def test_stream_emits_terminal_task_snapshot_as_sse(self):
        task = {
            "id": "task-123",
            "owner_id": "browser-a",
            "status": "completed",
            "progress": 100,
            "updated_at": "2026-10-20T10:00:00+00:00",
            "events": [{"message": "Task completed."}],
        }
        with patch.object(main.task_manager, "get", return_value=task):
            chunks = [
                chunk async for chunk in main._task_event_stream(
                    "task-123", "browser-a", FinishedRequest()
                )
            ]

        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].startswith("data: "))
        self.assertTrue(chunks[0].endswith("\n\n"))
        payload = json.loads(chunks[0][len("data: "):].strip())
        self.assertEqual(payload["task"]["id"], "task-123")
        self.assertEqual(payload["task"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
