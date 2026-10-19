"""Regression tests for the session-scoped Agent Swarm SSE stream."""
import json
import unittest
from unittest.mock import patch

from backend import main


class FakeRequest:
    async def is_disconnected(self):
        return False


class FakeSwarmManager:
    def __init__(self, job):
        self.job = job
        self.calls = []

    def get(self, job_id, owner_id=None):
        self.calls.append((job_id, owner_id))
        if self.job and self.job["id"] == job_id and self.job["owner_id"] == owner_id:
            return dict(self.job)
        return None


class SwarmEventStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_sends_initial_snapshot_and_stops_on_terminal_state(self):
        job = {
            "id": "job-1",
            "owner_id": "owner-a",
            "status": "completed",
            "updated_at": "2026-10-20T00:00:00+00:00",
            "events": [{"message": "finished"}],
        }
        manager = FakeSwarmManager(job)
        with patch.object(main, "swarm_manager", manager):
            chunks = [chunk async for chunk in main._swarm_event_stream("job-1", "owner-a", FakeRequest())]

        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].startswith("data: "))
        self.assertTrue(chunks[0].endswith("\n\n"))
        payload = json.loads(chunks[0][6:].strip())
        self.assertEqual(payload["job"]["id"], "job-1")
        self.assertEqual(payload["job"]["status"], "completed")

    async def test_stream_does_not_emit_jobs_owned_by_another_session(self):
        manager = FakeSwarmManager({
            "id": "job-1", "owner_id": "owner-a", "status": "completed",
            "updated_at": "now", "events": [],
        })
        with patch.object(main, "swarm_manager", manager):
            chunks = [chunk async for chunk in main._swarm_event_stream("job-1", "owner-b", FakeRequest())]

        self.assertEqual(chunks, [])
        self.assertEqual(manager.calls, [("job-1", "owner-b")])


if __name__ == "__main__":
    unittest.main()
