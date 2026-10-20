"""Regression tests for background task timeouts and pause/resume recovery."""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from backend.task_manager import TaskManager


class TaskResilienceTests(unittest.TestCase):
    def test_unreachable_postgres_falls_back_without_crashing_and_stays_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {
                "SUPABASE_DB_URL": "",
                "DATABASE_URL": "postgresql://nox:test@db.invalid/nox",
                "NOX_TASK_DB": os.path.join(temp_dir, "fallback.sqlite3"),
            }
            with patch.dict(os.environ, env, clear=False), patch("psycopg.connect", side_effect=OSError("database unavailable")):
                manager = TaskManager(lambda goal, language, context: asyncio.sleep(0, result="unused"))
                self.assertFalse(manager.use_postgres)
                self.assertTrue(manager.emergency_storage_degraded)
                self.assertTrue(manager.emergency_status("deploy-test-owner")["stopped"])
                with self.assertRaisesRegex(RuntimeError, "database is unavailable"):
                    asyncio.run(manager.resume_emergency_stop("deploy-test-owner"))

    def test_provider_timeout_fails_clearly_and_queue_continues(self):
        async def processor(goal, language, context):
            if goal == "slow task":
                await asyncio.sleep(1)
                return "late result"
            return "quick result"

        async def scenario():
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"NOX_TASK_DB": os.path.join(temp_dir, "tasks.sqlite3")}, clear=False):
                    manager = TaskManager(processor)
                    await manager.start()
                    try:
                        slow = await manager.create("slow task", "en", owner_id="test-owner")
                        quick = await manager.create("quick task", "en", owner_id="test-owner")
                        for _ in range(200):
                            slow_now = manager.get(slow["id"], owner_id="test-owner")
                            quick_now = manager.get(quick["id"], owner_id="test-owner")
                            if slow_now["status"] in ("failed", "completed", "cancelled") and quick_now["status"] in ("failed", "completed", "cancelled"):
                                break
                            await asyncio.sleep(0.01)
                        self.assertEqual(slow_now["status"], "failed")
                        self.assertIn("timed out", slow_now["error"].lower())
                        self.assertEqual(quick_now["status"], "completed")
                        self.assertEqual(quick_now["result"], "quick result")
                    finally:
                        await manager.stop()

        with patch("backend.task_manager.TASK_PROCESSOR_TIMEOUT_SECONDS", 0.01):
            asyncio.run(scenario())

    def test_paused_task_survives_manager_recreation_without_auto_resume(self):
        async def processor(goal, language, context):
            return "unused"

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "tasks.sqlite3")
            with patch.dict(os.environ, {"NOX_TASK_DB": db_path}, clear=False):
                first = TaskManager(processor)
                created = asyncio.run(first.create("Persist a paused task", "en", owner_id="test-owner"))
                paused = asyncio.run(first.pause(created["id"], owner_id="test-owner"))
                self.assertEqual(paused["status"], "paused")

                second = TaskManager(processor)
                restored = second.get(created["id"], owner_id="test-owner")
                self.assertEqual(restored["status"], "paused")
                self.assertIsNone(second.get(created["id"], owner_id="another-owner"))


if __name__ == "__main__":
    unittest.main()
