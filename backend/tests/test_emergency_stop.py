"""Regression tests for the persisted Emergency Stop invariant."""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from backend.task_manager import TaskManager


async def unused_processor(goal, language, context):
    return "unexpected task completion"


class EmergencyStopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"NOX_TASK_DB": os.path.join(self.temp.name, "tasks.sqlite3")}, clear=False)
        self.env.start()
        self.manager = TaskManager(unused_processor)

    async def asyncTearDown(self):
        await self.manager.stop()
        self.env.stop()
        self.temp.cleanup()

    async def test_stop_latches_and_rejects_new_tasks_until_explicit_resume(self):
        created = await self.manager.create("Research a public documentation topic", "en", owner_id="owner-a")
        stopped = await self.manager.emergency_stop("owner-a")
        self.assertTrue(stopped["stopped"])
        self.assertEqual(self.manager.get(created["id"], "owner-a")["status"], "cancelled")
        with self.assertRaisesRegex(RuntimeError, "Emergency Stop is latched"):
            await self.manager.create("Research another public topic", "en", owner_id="owner-a")
        resumed = await self.manager.resume_emergency_stop("owner-a")
        self.assertFalse(resumed["stopped"])
        next_task = await self.manager.create("Research a third public topic", "en", owner_id="owner-a")
        self.assertEqual(next_task["status"], "queued")
        self.assertEqual(self.manager.get(created["id"], "owner-a")["status"], "cancelled")

    async def test_stop_state_survives_manager_recreation_and_blocks_recovery(self):
        created = await self.manager.create("Research a persistent public topic", "en", owner_id="owner-a")
        await self.manager.emergency_stop("owner-a")
        restored_manager = TaskManager(unused_processor)
        self.assertTrue(restored_manager.emergency_status("owner-a")["stopped"])
        self.assertEqual(restored_manager.get(created["id"], "owner-a")["status"], "cancelled")
        with self.assertRaisesRegex(RuntimeError, "Emergency Stop is latched"):
            await restored_manager.create("Try to start after restart", "en", owner_id="owner-a")

    async def test_running_processor_is_cancelled_and_not_reported_as_resumed(self):
        started = asyncio.Event()
        async def blocking_processor(goal, language, context):
            started.set()
            await asyncio.Event().wait()
            return "should never be stored"

        manager = TaskManager(blocking_processor)
        created = await manager.create("Research a topic while cancellation is tested", "en", owner_id="owner-b")
        await manager.start()
        await asyncio.wait_for(started.wait(), timeout=2)
        result = await manager.emergency_stop("owner-b")
        self.assertTrue(result["stopped"])
        self.assertEqual(manager.get(created["id"], "owner-b")["status"], "cancelled")
        await manager.stop()


if __name__ == "__main__":
    unittest.main()
