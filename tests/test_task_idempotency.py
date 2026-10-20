"""Regression tests for persistent NOX task idempotency."""
import os
import tempfile
import unittest

from backend.task_manager import TaskManager


async def fake_processor(goal, language, context):
    return "ok"


class TaskIdempotencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("NOX_TASK_DB")
        self.old_database_url = os.environ.get("DATABASE_URL")
        self.old_supabase_url = os.environ.get("SUPABASE_DB_URL")
        os.environ["NOX_TASK_DB"] = os.path.join(self.temp_dir.name, "tasks.sqlite3")
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("SUPABASE_DB_URL", None)
        self.manager = TaskManager(fake_processor)

    async def asyncTearDown(self):
        if self.old_db is None:
            os.environ.pop("NOX_TASK_DB", None)
        else:
            os.environ["NOX_TASK_DB"] = self.old_db
        if self.old_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self.old_database_url
        if self.old_supabase_url is None:
            os.environ.pop("SUPABASE_DB_URL", None)
        else:
            os.environ["SUPABASE_DB_URL"] = self.old_supabase_url
        self.temp_dir.cleanup()

    async def test_same_key_returns_same_task_without_duplicate_queue_entry(self):
        first = await self.manager.create(
            "Research a topic", "en", owner_id="browser-a", idempotency_key="request-0001"
        )
        retry = await self.manager.create(
            "Research a topic", "en", owner_id="browser-a", idempotency_key="request-0001"
        )
        self.assertEqual(first["id"], retry["id"])
        self.assertEqual(self.manager.queue.qsize(), 1)

    async def test_key_reuse_with_different_payload_is_rejected(self):
        await self.manager.create(
            "Research a topic", "en", owner_id="browser-a", idempotency_key="request-0002"
        )
        with self.assertRaisesRegex(ValueError, "different task"):
            await self.manager.create(
                "Research another topic", "en", owner_id="browser-a", idempotency_key="request-0002"
            )

    async def test_same_key_is_isolated_between_owners(self):
        first = await self.manager.create(
            "Research a topic", "en", owner_id="browser-a", idempotency_key="request-0003"
        )
        second = await self.manager.create(
            "Research a topic", "en", owner_id="browser-b", idempotency_key="request-0003"
        )
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.manager.queue.qsize(), 2)


if __name__ == "__main__":
    unittest.main()
