"""Regression tests for task-store persistence across manager instances."""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from backend.task_manager import TaskManager


async def unused_processor(goal, language, context):
    return "unused"


class TaskManagerStorageTests(unittest.TestCase):
    def test_task_survives_manager_recreation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "tasks.sqlite3")
            with patch.dict(os.environ, {"NOX_TASK_DB": db_path}, clear=False):
                first = TaskManager(unused_processor)
                created = asyncio.run(first.create("Research public documentation", "en"))

                second = TaskManager(unused_processor)
                restored = second.get(created["id"])

            self.assertIsNotNone(restored)
            self.assertEqual(restored["goal"], "Research public documentation")
            self.assertEqual(restored["status"], "queued")
            self.assertIsInstance(restored["events"], list)
            self.assertGreaterEqual(len(restored["events"]), 1)

    def test_list_limit_is_respected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"NOX_TASK_DB": os.path.join(temp_dir, "tasks.sqlite3")}, clear=False):
                manager = TaskManager(unused_processor)
                asyncio.run(manager.create("First research task", "en"))
                asyncio.run(manager.create("Second research task", "en"))
                self.assertEqual(len(manager.list(limit=1)), 1)

    def test_unknown_task_returns_none(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"NOX_TASK_DB": os.path.join(temp_dir, "tasks.sqlite3")}, clear=False):
                manager = TaskManager(unused_processor)
                self.assertIsNone(manager.get("missing-task-id"))


    def test_cancel_all_is_scoped_to_owner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"NOX_TASK_DB": os.path.join(temp_dir, "tasks.sqlite3")}, clear=False):
                manager = TaskManager(unused_processor)
                first = asyncio.run(manager.create("Research for owner one", "en", owner_id="one"))
                second = asyncio.run(manager.create("Research for owner two", "en", owner_id="two"))
                stopped = asyncio.run(manager.cancel_all(owner_id="one"))
                self.assertEqual([item["id"] for item in stopped], [first["id"]])
                self.assertEqual(manager.get(first["id"])["status"], "cancelled")
                self.assertEqual(manager.get(second["id"])["status"], "queued")


    def test_pause_all_is_scoped_to_owner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"NOX_TASK_DB": os.path.join(temp_dir, "tasks.sqlite3")}, clear=False):
                manager = TaskManager(unused_processor)
                first = asyncio.run(manager.create("Research for owner one", "en", owner_id="one"))
                second = asyncio.run(manager.create("Research for owner two", "en", owner_id="two"))
                paused = asyncio.run(manager.pause_all(owner_id="one"))
                self.assertEqual([item["id"] for item in paused], [first["id"]])
                self.assertEqual(manager.get(first["id"])["status"], "paused")
                self.assertEqual(manager.get(second["id"])["status"], "queued")


if __name__ == "__main__":
    unittest.main()
