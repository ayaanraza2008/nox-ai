"""Regression tests for browser-session isolation on task and chat APIs."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from backend import main
from backend.task_manager import TaskManager


async def unused_processor(goal, language, history):
    return "test result"


class SessionIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.pair_db_patch = patch.object(main, "PAIR_DB", root / "pairing.sqlite3")
        self.db_url_patch = patch.object(main, "DATABASE_URL", "")
        self.pair_db_patch.start()
        self.db_url_patch.start()
        with patch.dict(os.environ, {"NOX_TASK_DB": str(root / "tasks.sqlite3")}, clear=False):
            self.manager = TaskManager(unused_processor)
        self.manager_patch = patch.object(main, "task_manager", self.manager)
        self.manager_patch.start()
        self.transport = httpx.ASGITransport(app=main.app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.manager_patch.stop()
        self.db_url_patch.stop()
        self.pair_db_patch.stop()
        self.temp_dir.cleanup()

    async def new_browser(self):
        client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")
        response = await client.get("/api/session")
        self.assertEqual(response.status_code, 200)
        self.assertIn("nox_session", client.cookies)
        return client

    async def test_task_endpoints_require_and_scope_browser_session(self):
        response = await self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 401)

        first = await self.new_browser()
        created = await first.post("/api/tasks", json={"goal": "Research public docs", "language": "en"})
        self.assertEqual(created.status_code, 202, created.text)
        task_id = created.json()["task"]["id"]

        second = await self.new_browser()
        self.assertEqual((await second.get("/api/tasks")).json()["tasks"], [])
        self.assertEqual((await second.get(f"/api/tasks/{task_id}")).status_code, 404)
        self.assertEqual((await second.post(f"/api/tasks/{task_id}/cancel")).status_code, 404)
        self.assertEqual(len((await first.get("/api/tasks")).json()["tasks"]), 1)

        await first.aclose()
        await second.aclose()

    async def test_saved_chat_history_is_scoped_to_cookie_not_query_user_id(self):
        first = await self.new_browser()
        payload = {
            "chat_id": "conversation-1",
            "title": "Private conversation",
            "updated_at": "2026-10-20T00:00:00Z",
            "messages": [{"role": "user", "content": "private test text"}],
        }
        saved = await first.put("/api/chats?user_id=attacker-controlled", json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)

        second = await self.new_browser()
        chats = await second.get("/api/chats?user_id=attacker-controlled")
        self.assertEqual(chats.status_code, 200, chats.text)
        self.assertEqual(chats.json()["chats"], [])

        no_session = await self.client.get("/api/chats?user_id=attacker-controlled")
        self.assertEqual(no_session.status_code, 401)

        await first.aclose()
        await second.aclose()


if __name__ == "__main__":
    unittest.main()
