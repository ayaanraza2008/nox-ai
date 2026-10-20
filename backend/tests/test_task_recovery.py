"""Regression tests for restart recovery of in-flight tasks."""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from backend.task_manager import TaskManager, utcnow


async def unused_processor(goal, language, context):
    return "unused"


class TaskRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_running_task_is_requeued_after_worker_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"NOX_TASK_DB": os.path.join(temp_dir, "tasks.sqlite3"),
             "DATABASE_URL": "", "SUPABASE_DB_URL": ""},
            clear=False,
        ):
            manager = TaskManager(unused_processor)
            item = {
                "id": "recovery-task",
                "goal": "Research public documentation",
                "language": "en",
                "owner_id": "browser-session-123",
                "idempotency_key": None,
                "status": "running",
                "progress": 65,
                "result": None,
                "error": None,
                "created_at": utcnow(),
                "updated_at": utcnow(),
                "events": [{"message": "Previous worker started."}],
                "attempts": 1,
            }
            manager._save(item)

            async def idle_worker():
                await asyncio.Event().wait()

            with patch.object(manager, "_work_loop", new=idle_worker):
                await manager.start()
                restored = manager.get("recovery-task")
                self.assertEqual(restored["status"], "queued")
                self.assertLessEqual(restored["progress"], 10)
                self.assertEqual(manager.queue.qsize(), 1)
                self.assertTrue(any("Worker restarted" in event["message"] for event in restored["events"]))
                await manager.stop()


if __name__ == "__main__":
    unittest.main()
