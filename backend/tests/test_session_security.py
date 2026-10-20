"""Regression tests for the verified-account gate on protected NOX APIs."""
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

    async def test_anonymous_browser_cookie_cannot_unlock_protected_features(self):
        browser = await self.new_browser()
        self.assertEqual((await browser.get("/api/tasks")).status_code, 401)
        self.assertEqual((await browser.get("/api/chats")).status_code, 401)
        await browser.aclose()

    async def test_unverified_account_is_blocked_from_protected_features(self):
        self.client.cookies.set("nox_account_session", "pending-session")
        pending = {"id": "account-1", "status": "email_verified"}
        with patch.object(main.accounts, "resolve_session", return_value=pending):
            tasks = await self.client.get("/api/tasks")
            chats = await self.client.get("/api/chats")
        self.assertEqual(tasks.status_code, 403)
        self.assertEqual(chats.status_code, 403)
        self.assertIn("verification", tasks.json()["detail"].lower())

    async def test_verified_account_can_access_protected_apis(self):
        self.client.cookies.set("nox_account_session", "verified-session")
        active = {"id": "account-1", "status": "active"}
        with patch.object(main.accounts, "resolve_session", return_value=active):
            tasks = await self.client.get("/api/tasks")
            chats = await self.client.get("/api/chats")
        self.assertEqual(tasks.status_code, 200, tasks.text)
        self.assertEqual(chats.status_code, 200, chats.text)


if __name__ == "__main__":
    unittest.main()
