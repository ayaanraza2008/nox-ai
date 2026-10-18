"""Persistent, bounded task orchestration for NOX AI.

Tasks currently run as AI planning/response jobs. This manager does not execute
arbitrary shell commands, browse websites, modify repositories, or control a desktop.
SQLite persistence can be redirected with NOX_TASK_DB; on ephemeral hosts, use a
persistent disk or external database for survival across redeploys.
"""
import asyncio
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

Processor = Callable[[str, str, list[dict[str, str]]], Awaitable[str | None]]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskManager:
    def __init__(self, processor: Processor):
        self.processor = processor
        self.db_path = Path(os.getenv("NOX_TASK_DB", "/tmp/nox_tasks.sqlite3"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.runners: dict[str, asyncio.Task] = {}
        self.pause_events: dict[str, asyncio.Event] = {}
        self.cancel_events: dict[str, asyncio.Event] = {}
        self.worker: asyncio.Task | None = None
        self._init_db()

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, goal TEXT NOT NULL, language TEXT NOT NULL,
                status TEXT NOT NULL, progress INTEGER NOT NULL, result TEXT,
                error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                events TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0
            )""")

    def _row(self, row):
        if not row:
            return None
        item = dict(row)
        item["events"] = json.loads(item["events"] or "[]")
        return item

    def _get(self, task_id: str):
        with self._connect() as db:
            return self._row(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def _event(self, item: dict[str, Any], message: str, level: str = "info"):
        item["events"].append({"at": utcnow(), "level": level, "message": message[:500]})
        item["events"] = item["events"][-100:]
        item["updated_at"] = utcnow()

    def _save(self, item: dict[str, Any]):
        with self._connect() as db:
            db.execute("""INSERT INTO tasks
              (id,goal,language,status,progress,result,error,created_at,updated_at,events,attempts)
              VALUES (:id,:goal,:language,:status,:progress,:result,:error,:created_at,:updated_at,:events,:attempts)
              ON CONFLICT(id) DO UPDATE SET
              status=excluded.status,progress=excluded.progress,result=excluded.result,
              error=excluded.error,updated_at=excluded.updated_at,events=excluded.events,
              attempts=excluded.attempts""", {**item, "events": json.dumps(item["events"])})

    async def start(self):
        # A process restart cannot safely resume an in-flight network request.
        with self._connect() as db:
            rows = db.execute("SELECT * FROM tasks WHERE status IN ('queued','running','paused')").fetchall()
        for row in rows:
            item = self._row(row)
            if item["status"] == "running":
                item["status"] = "queued"
                item["progress"] = min(item["progress"], 10)
                self._event(item, "Worker restarted; task returned to the queue.")
                self._save(item)
            if item["status"] == "paused":
                continue
            await self.queue.put(item["id"])
        self.worker = asyncio.create_task(self._work_loop())

    async def stop(self):
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
            self.worker = None
        for runner in list(self.runners.values()):
            runner.cancel()
        self.runners.clear()

    async def create(self, goal: str, language: str) -> dict[str, Any]:
        task_id = uuid.uuid4().hex
        item = {"id": task_id, "goal": goal, "language": language, "status": "queued",
                "progress": 0, "result": None, "error": None, "created_at": utcnow(),
                "updated_at": utcnow(), "events": [], "attempts": 0}
        self._event(item, "Task accepted and added to the queue.")
        self._save(item)
        await self.queue.put(task_id)
        return item

    def get(self, task_id: str):
        return self._get(task_id)

    def list(self, limit: int = 50):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(row) for row in rows]

    async def pause(self, task_id: str):
        item = self._get(task_id)
        if not item:
            return None
        if item["status"] not in ("queued", "running"):
            raise ValueError("Only queued or running tasks can be paused.")
        event = self.pause_events.setdefault(task_id, asyncio.Event())
        event.clear()
        item["status"] = "paused"
        self._event(item, "Task paused by user.")
        self._save(item)
        return item

    async def resume(self, task_id: str):
        item = self._get(task_id)
        if not item:
            return None
        if item["status"] != "paused":
            raise ValueError("Only paused tasks can be resumed.")
        event = self.pause_events.setdefault(task_id, asyncio.Event())
        event.set()
        item["status"] = "queued"
        self._event(item, "Task resumed.")
        self._save(item)
        if task_id not in self.runners:
            await self.queue.put(task_id)
        return item

    async def cancel(self, task_id: str):
        item = self._get(task_id)
        if not item:
            return None
        if item["status"] in ("completed", "failed", "cancelled"):
            raise ValueError("Task is already finished.")
        self.cancel_events.setdefault(task_id, asyncio.Event()).set()
        self.pause_events.setdefault(task_id, asyncio.Event()).set()
        item["status"] = "cancelled"
        item["progress"] = min(item["progress"], 99)
        self._event(item, "Cancellation requested by user.", "warning")
        self._save(item)
        runner = self.runners.get(task_id)
        if runner and not runner.done():
            runner.cancel()
        return item

    async def _work_loop(self):
        while True:
            task_id = await self.queue.get()
            item = self._get(task_id)
            if not item or item["status"] != "queued":
                self.queue.task_done()
                continue
            if task_id in self.runners and not self.runners[task_id].done():
                self.queue.task_done()
                continue
            runner = asyncio.create_task(self._run(task_id))
            self.runners[task_id] = runner
            try:
                await runner
            except asyncio.CancelledError:
                pass
            finally:
                self.runners.pop(task_id, None)
                self.queue.task_done()

    async def _run(self, task_id: str):
        item = self._get(task_id)
        if not item or item["status"] != "queued":
            return
        cancel_event = self.cancel_events.setdefault(task_id, asyncio.Event())
        pause_event = self.pause_events.setdefault(task_id, asyncio.Event())
        pause_event.set()
        item["status"] = "running"
        item["progress"] = 10
        self._event(item, "Worker started.")
        self._save(item)
        try:
            await pause_event.wait()
            if cancel_event.is_set():
                return
            # A hosted worker cannot launch apps on the user's personal device.
            # Fail desktop-action requests clearly instead of reporting fake success.
            goal = item["goal"].strip()
            desktop_action = re.search(
                r"\b(open|launch|start|close|quit|kill)\b.{0,50}\b(instagram|chrome|browser|notepad|calculator|spotify|discord|whatsapp|file explorer|settings|camera|vs code|vscode)\b",
                goal,
                re.IGNORECASE,
            ) or re.search(
                r"\b(instagram|chrome|browser|notepad|calculator|spotify|discord|whatsapp|file explorer|settings|camera|vs code|vscode)\b.{0,50}\b(open|launch|start|close|quit|kill)\b",
                goal,
                re.IGNORECASE,
            )
            if desktop_action:
                item = self._get(task_id)
                if item and item["status"] != "cancelled":
                    item["status"] = "failed"
                    item["error"] = (
                        "This is a device action, but NOX is running on a hosted server and "
                        "cannot control your computer. A local desktop companion with explicit "
                        "user permission is required."
                    )
                    self._event(item, "Action not executed: a local desktop companion is required.", "warning")
                    self._save(item)
                return
            item = self._get(task_id)
            if not item or item["status"] == "cancelled":
                return
            item["progress"] = 25
            self._event(item, "Preparing AI task context.")
            self._save(item)
            # Pause/cancel is checked before provider work; an in-flight provider
            # request is not interruptible, but its result will not overwrite cancel.
            await pause_event.wait()
            if cancel_event.is_set():
                return
            item["attempts"] += 1
            self._event(item, "Sending task to configured AI provider.")
            self._save(item)
            answer = None
            try:
                answer = await self.processor(item["goal"], item["language"], [])
            except Exception:
                if item["attempts"] < 2 and not cancel_event.is_set():
                    item["attempts"] += 1
                    self._event(item, "Provider attempt failed; retrying once.", "warning")
                    self._save(item)
                    answer = await self.processor(item["goal"], item["language"], [])
                else:
                    raise
            # A pause cannot interrupt the provider request, but it must stop
            # result finalization until the user resumes the task.
            await pause_event.wait()
            if cancel_event.is_set():
                return
            if not answer:
                raise RuntimeError("AI provider is not configured. Add OPENROUTER_API_KEY to run AI tasks.")
            item = self._get(task_id)
            if not item or item["status"] == "cancelled":
                return
            item["progress"] = 90
            self._event(item, "AI response received; recording result.")
            item["result"] = answer
            item["progress"] = 100
            item["status"] = "completed"
            self._event(item, "Task completed. This is an AI-generated result, not an external action.")
            self._save(item)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            item = self._get(task_id)
            if item and item["status"] != "cancelled":
                item["status"] = "failed"
                item["error"] = str(exc)[:500]
                self._event(item, "Task failed: " + str(exc), "error")
                self._save(item)
        finally:
            item = self._get(task_id)
            if item and item["status"] == "cancelled":
                self._event(item, "Task stopped; cancelled status preserved.")
                self._save(item)
