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


    def test_unreachable_postgres_falls_back_to_sqlite_for_task_queue(self):
        # A broken hosted DB must not prevent the whole FastAPI app from starting.
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "tasks.sqlite3")
            env = {
                "NOX_TASK_DB": db_path,
                "SUPABASE_DB_URL": "postgresql://nox:invalid@127.0.0.1:5432/nox",
                "DATABASE_URL": "postgresql://nox:invalid@127.0.0.1:5432/nox",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("psycopg.connect", side_effect=OSError("database unavailable")):
                    manager = TaskManager(unused_processor)

                self.assertFalse(manager.use_postgres)
                self.assertTrue(manager.emergency_storage_degraded)
                created = asyncio.run(manager.create("Check temporary fallback", "en"))
                self.assertIsNotNone(manager.get(created["id"]))

    def test_unknown_task_returns_none(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"NOX_TASK_DB": os.path.join(temp_dir, "tasks.sqlite3")}, clear=False):
                manager = TaskManager(unused_processor)
                self.assertIsNone(manager.get("missing-task-id"))


if __name__ == "__main__":
    unittest.main()
