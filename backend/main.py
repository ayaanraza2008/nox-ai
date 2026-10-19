import json
import logging
import os
import secrets
import sqlite3
import string
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend.task_manager import TaskManager
from backend.autonomous_agent import run_autonomous_task

logger = logging.getLogger("nox.provider")
app = FastAPI(title="NOX AI API", version="0.1.0")
ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    language: Literal["auto", "en", "hi", "ur", "hinglish"] = "auto"
    history: list[dict] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    mode: str


class TaskCreateRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=6000)
    language: Literal["auto", "en", "hi", "ur", "hinglish"] = "auto"


class PairCreateRequest(BaseModel):
    device_name: str = Field(default="NOX browser", min_length=1, max_length=80)


class PairJoinRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    device_name: str = Field(default="NOX device", min_length=1, max_length=80)


class SharedChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class SharedChatPayload(BaseModel):
    chat_id: str = Field(min_length=1, max_length=100)
    title: str = Field(default="New conversation", max_length=120)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    messages: list[SharedChatMessage] = Field(min_length=1, max_length=300)


class UserChatPayload(BaseModel):
    chat_id: str = Field(min_length=1, max_length=100)
    title: str = Field(default="New conversation", max_length=120)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    messages: list[SharedChatMessage] = Field(min_length=1, max_length=300)


PAIR_DB = Path(os.getenv("NOX_PAIRING_DB", str(ROOT / "nox_pairing.sqlite3")))
# Supabase uses PostgreSQL; keep the connection string server-side only.
# SUPABASE_DB_URL is an optional explicit alias; DATABASE_URL remains compatible with Render/Postgres.
DATABASE_URL = (os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or "").strip()


class PairDBConnection:
    """Small SQLite/Postgres compatibility layer for NOX pairing storage."""
    def __init__(self, connection, postgres=False):
        self.connection = connection
        self.postgres = postgres

    def execute(self, query, params=()):
        if self.postgres:
            query = query.replace("?", "%s")
            return self.connection.execute(query, params)
        return self.connection.execute(query, params)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


@contextmanager
def pair_db():
    postgres = DATABASE_URL.startswith(("postgres://", "postgresql://"))
    if postgres:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("DATABASE_URL is set but psycopg is not installed.") from exc
        raw_conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
        conn = PairDBConnection(raw_conn, postgres=True)
    else:
        PAIR_DB.parent.mkdir(parents=True, exist_ok=True)
        raw_conn = sqlite3.connect(PAIR_DB, timeout=10)
        raw_conn.row_factory = sqlite3.Row
        conn = PairDBConnection(raw_conn)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS pair_sessions (
            session_id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS pair_devices (
            device_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, name TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, last_seen TEXT NOT NULL,
            disconnected INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS pair_commands (
            command_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, source_device TEXT NOT NULL,
            target_device TEXT NOT NULL, command TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
            created_at TEXT NOT NULL, result TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS pair_chat_history (
            session_id TEXT NOT NULL, chat_id TEXT NOT NULL, title TEXT NOT NULL,
            updated_at TEXT NOT NULL, messages TEXT NOT NULL,
            PRIMARY KEY(session_id, chat_id))""")
        conn.commit()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def utc_now():
    return datetime.now(timezone.utc)


def iso_now():
    return utc_now().isoformat()


def device_from_token(conn, token):
    if not token:
        raise HTTPException(status_code=401, detail="Device pairing token required.")
    row = conn.execute("SELECT * FROM pair_devices WHERE token=? AND disconnected=0", (token,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or disconnected device pairing.")
    return row



async def provider_reply(message: str, language: str, history: list[dict]) -> str | None:
    messages = [
        {
            "role": "system",
            "content": (
                "You are NOX, a helpful, natural, concise multilingual assistant and proactive executor. "
                "Understand Hindi, Urdu, English, and Hinglish. Match the user's language when possible. "
                "When the user gives a clear, allowed command, do it immediately using available tools instead of asking for confirmation or repeating the request. "
                "Do not ask unnecessary follow-up questions; infer sensible, low-risk defaults and report the result. "
                "Ask one concise question only when a missing detail is essential, multiple choices are materially different, or proceeding could cause a significant, irreversible, financial, privacy, or external side effect. "
                "For consequential actions such as sending/posting messages, purchases/payments, deleting or overwriting data, sharing private information, or changing security settings, require explicit confirmation. "
                "Never bypass authentication, OS/browser permission prompts, or security controls. Be honest about limitations and never claim actions you did not do. "
                f"Preferred language: {language}."
            ),
        }
    ]
    for item in history[-12:]:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": message})

    # Try configured providers in priority order. A failing key, quota, model, or
    # provider connection must not prevent NOX from trying the next configured API.
    providers = []
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        providers.append({
            "name": "OpenRouter",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "key": openrouter_key,
            "model": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            "headers": {
                "HTTP-Referer": os.getenv("APP_URL", "https://nox-ai-vcqx.onrender.com"),
                "X-Title": "NOX AI",
            },
        })
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        providers.append({
            "name": "Groq",
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "key": groq_key,
            "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "headers": {},
        })
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        providers.append({
            "name": "Gemini",
            "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "key": gemini_key,
            "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "headers": {},
        })

    if not providers:
        return None

    failures = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=12.0), trust_env=True) as client:
        for provider in providers:
            headers = {
                "Authorization": f"Bearer {provider['key']}",
                "Content-Type": "application/json",
                **provider["headers"],
            }
            for attempt in range(3):
                try:
                    response = await client.post(
                        provider["url"],
                        headers=headers,
                        json={"model": provider["model"], "messages": messages, "temperature": 0.7},
                    )
                    if response.status_code < 400:
                        try:
                            data = response.json()
                            answer = data["choices"][0]["message"]["content"]
                            if isinstance(answer, str) and answer.strip():
                                logger.info("Chat reply served by %s", provider["name"])
                                return answer.strip()
                            raise ValueError("Provider returned an empty message")
                        except (ValueError, KeyError, IndexError, TypeError) as exc:
                            logger.warning("%s returned an invalid/empty response: %s", provider["name"], type(exc).__name__)
                            failures.append(f"{provider['name']}: invalid response")
                            break

                    # Log a short response body for diagnostics, never request headers/secrets.
                    logger.warning("%s returned HTTP %s: %s", provider["name"], response.status_code, response.text[:500])
                    failures.append(f"{provider['name']}: HTTP {response.status_code}")
                    # Retry transient errors once. For a rejected/unavailable configured
                    # OpenRouter model, switch to its free-model router before giving up.
                    transient = response.status_code in (408, 429, 500, 502, 503, 504)
                    if transient and attempt == 0:
                        continue
                    if provider["name"] == "OpenRouter" and provider["model"] != "openrouter/free" and (not transient or attempt == 1):
                        provider["model"] = "openrouter/free"
                        logger.warning("Configured OpenRouter model failed; retrying with openrouter/free")
                        continue
                    break
                except httpx.TimeoutException as exc:
                    logger.warning("%s timed out (attempt %s)", provider["name"], attempt + 1)
                    if attempt == 0:
                        continue
                    failures.append(f"{provider['name']}: timeout")
                    break
                except httpx.RequestError as exc:
                    logger.warning("%s connection failed (%s): %s", provider["name"], type(exc).__name__, str(exc))
                    if attempt == 0:
                        continue
                    failures.append(f"{provider['name']}: connection failure")
                    break

    logger.error("All configured AI providers failed: %s", "; ".join(failures))
    raise HTTPException(
        status_code=503,
        detail="All configured AI providers are unavailable right now. Check API keys, model access, quotas, and Render logs.",
    )

task_manager = TaskManager(run_autonomous_task)


@app.on_event("startup")
async def start_task_worker():
    await task_manager.start()


@app.on_event("shutdown")
async def stop_task_worker():
    await task_manager.stop()


@app.post("/api/tasks", status_code=202)
async def create_task(payload: TaskCreateRequest):
    goal = payload.goal.strip()
    if len(goal) < 3:
        raise HTTPException(status_code=400, detail="Task goal must contain at least 3 characters.")
    return {"task": await task_manager.create(goal, payload.language)}


@app.get("/api/tasks")
async def list_tasks(limit: int = 20):
    limit = max(1, min(limit, 50))
    return {"tasks": task_manager.list(limit=limit)}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"task": task}


async def _task_action(task_id: str, action: str):
    try:
        task = await getattr(task_manager, action)(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"task": task}


@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    return await _task_action(task_id, "pause")


@app.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    return await _task_action(task_id, "resume")


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    return await _task_action(task_id, "cancel")


@app.post("/api/pairing/create")
async def pairing_create(payload: PairCreateRequest):
    now = utc_now()
    session_id = secrets.token_urlsafe(18)
    device_id = secrets.token_urlsafe(12)
    token = secrets.token_urlsafe(32)
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    expires = (now.replace(microsecond=0)).isoformat()
    expires_at = (now.replace(microsecond=0) + __import__("datetime").timedelta(minutes=5)).isoformat()
    with pair_db() as conn:
        session_created = False
        for _ in range(5):
            try:
                conn.execute("INSERT INTO pair_sessions(session_id,code,created_at,expires_at) VALUES(?,?,?,?)",
                             (session_id, code, expires, expires_at))
                session_created = True
                break
            except Exception as exc:
                if not isinstance(exc, sqlite3.IntegrityError) and exc.__class__.__name__ != "UniqueViolation":
                    raise
                conn.rollback()
                code = "".join(secrets.choice(string.digits) for _ in range(6))
        if not session_created:
            raise HTTPException(status_code=503, detail="Could not allocate a unique pairing code. Please retry.")
        conn.execute("INSERT INTO pair_devices(device_id,session_id,name,token,created_at,last_seen) VALUES(?,?,?,?,?,?)",
                     (device_id, session_id, payload.device_name.strip(), token, expires, expires))
    return {"session_id": session_id, "device_id": device_id, "device_token": token,
            "pair_code": code, "expires_at": expires_at, "message": "Pair code expires in five minutes. Store the device token securely."}


@app.post("/api/pairing/join")
async def pairing_join(payload: PairJoinRequest):
    now = utc_now()
    with pair_db() as conn:
        session = conn.execute("SELECT * FROM pair_sessions WHERE code=? AND revoked=0", (payload.code.strip(),)).fetchone()
        if not session or datetime.fromisoformat(session["expires_at"]) < now:
            raise HTTPException(status_code=404, detail="Pair code is invalid or expired. Generate a new code on the first device.")
        device_id = secrets.token_urlsafe(12)
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO pair_devices(device_id,session_id,name,token,created_at,last_seen) VALUES(?,?,?,?,?,?)",
                     (device_id, session["session_id"], payload.device_name.strip(), token, now.isoformat(), now.isoformat()))
    return {"session_id": session["session_id"], "device_id": device_id, "device_token": token,
            "message": "Device joined the pairing session. Native device control still requires a compatible companion."}


@app.get("/api/pairing/status")
async def pairing_status(session_id: str, x_nox_device_token: str | None = None):
    with pair_db() as conn:
        current = device_from_token(conn, x_nox_device_token)
        if current["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="This device does not belong to that pairing session.")
        now = iso_now()
        conn.execute("UPDATE pair_devices SET last_seen=? WHERE device_id=?", (now, current["device_id"]))
        rows = conn.execute("SELECT device_id,name,created_at,last_seen,disconnected FROM pair_devices WHERE session_id=? ORDER BY created_at",
                            (session_id,)).fetchall()
        return {"session_id": session_id, "devices": [dict(row) for row in rows],
                "current_device_id": current["device_id"], "connected": len([r for r in rows if not r["disconnected"]])}


@app.post("/api/pairing/disconnect")
async def pairing_disconnect(session_id: str, x_nox_device_token: str | None = None):
    with pair_db() as conn:
        current = device_from_token(conn, x_nox_device_token)
        if current["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="This device does not belong to that pairing session.")
        conn.execute("UPDATE pair_devices SET disconnected=1 WHERE device_id=?", (current["device_id"],))
        remaining = conn.execute("SELECT COUNT(*) FROM pair_devices WHERE session_id=? AND disconnected=0",
                                 (session_id,)).fetchone()[0]
        if remaining == 0:
            conn.execute("UPDATE pair_sessions SET revoked=1 WHERE session_id=?", (session_id,))
    return {"status": "disconnected", "message": "This device has been disconnected from the pairing session."}


@app.get("/api/pairing/history")
async def pairing_history(session_id: str, x_nox_device_token: str | None = None):
    """Return conversations shared only by devices in this authenticated pairing session."""
    with pair_db() as conn:
        current = device_from_token(conn, x_nox_device_token)
        if current["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="This device does not belong to that pairing session.")
        rows = conn.execute(
            "SELECT chat_id,title,updated_at,messages FROM pair_chat_history WHERE session_id=? ORDER BY updated_at DESC LIMIT 30",
            (session_id,),
        ).fetchall()
        return {"chats": [
            {"id": row["chat_id"], "title": row["title"], "updatedAt": row["updated_at"],
             "messages": json.loads(row["messages"])} for row in rows
        ]}


@app.put("/api/pairing/history")
async def save_pairing_chat(payload: SharedChatPayload, session_id: str, x_nox_device_token: str | None = None):
    """Save one conversation to the authenticated pairing session."""
    messages = [{"role": item.role, "content": item.content} for item in payload.messages[-300:]]
    serialized = json.dumps(messages, ensure_ascii=False)
    if len(serialized) > 1_000_000:
        raise HTTPException(status_code=413, detail="Conversation is too large to sync.")
    with pair_db() as conn:
        current = device_from_token(conn, x_nox_device_token)
        if current["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="This device does not belong to that pairing session.")
        conn.execute(
            """INSERT INTO pair_chat_history(session_id,chat_id,title,updated_at,messages)
               VALUES(?,?,?,?,?) ON CONFLICT(session_id,chat_id) DO UPDATE SET
               title=excluded.title,updated_at=excluded.updated_at,messages=excluded.messages""",
            (session_id, payload.chat_id, payload.title[:120], payload.updated_at[:80], serialized),
        )
        conn.execute(
            """DELETE FROM pair_chat_history WHERE session_id=? AND chat_id NOT IN
               (SELECT chat_id FROM pair_chat_history WHERE session_id=? ORDER BY updated_at DESC LIMIT 30)""",
            (session_id, session_id),
        )
    return {"status": "saved", "chat_id": payload.chat_id}


@app.delete("/api/pairing/history/{chat_id}")
async def delete_pairing_chat(chat_id: str, session_id: str, x_nox_device_token: str | None = None):
    with pair_db() as conn:
        current = device_from_token(conn, x_nox_device_token)
        if current["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="This device does not belong to that pairing session.")
        conn.execute("DELETE FROM pair_chat_history WHERE session_id=? AND chat_id=?", (session_id, chat_id))
    return {"status": "deleted", "chat_id": chat_id}


@app.post("/api/pairing/commands")
async def pairing_send_command(session_id: str, target_device: str, command: str, x_nox_device_token: str | None = None):
    command = command.strip()
    if not command or len(command) > 1000:
        raise HTTPException(status_code=400, detail="Command must contain 1–1000 characters.")
    with pair_db() as conn:
        source = device_from_token(conn, x_nox_device_token)
        if source["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="This device does not belong to that pairing session.")
        target = conn.execute("SELECT device_id FROM pair_devices WHERE device_id=? AND session_id=? AND disconnected=0",
                              (target_device, session_id)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Target device is not paired.")
        command_id = secrets.token_urlsafe(14)
        conn.execute("INSERT INTO pair_commands(command_id,session_id,source_device,target_device,command,created_at) VALUES(?,?,?,?,?,?)",
                     (command_id, session_id, source["device_id"], target_device, command, iso_now()))
    return {"command_id": command_id, "status": "queued", "message": "Queued for a compatible companion; queued does not mean executed."}


@app.get("/api/pairing/commands/next")
async def pairing_next_command(session_id: str, x_nox_device_token: str | None = None):
    with pair_db() as conn:
        current = device_from_token(conn, x_nox_device_token)
        if current["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="This device does not belong to that pairing session.")
        row = conn.execute("SELECT command_id,source_device,command,created_at FROM pair_commands WHERE session_id=? AND target_device=? AND status='queued' ORDER BY created_at LIMIT 1",
                           (session_id, current["device_id"])).fetchone()
        if not row:
            return {"command": None}
        conn.execute("UPDATE pair_commands SET status='delivered' WHERE command_id=?", (row["command_id"],))
        return {"command": dict(row)}


@app.post("/api/pairing/commands/{command_id}/result")
async def pairing_command_result(command_id: str, result: str, x_nox_device_token: str | None = None):
    # The companion reports compact JSON. Bound input before parsing so a paired
    # device cannot accidentally submit an unbounded result payload.
    if len(result) > 5000:
        raise HTTPException(status_code=413, detail="Command result is too large (maximum 5000 characters).")
    with pair_db() as conn:
        current = device_from_token(conn, x_nox_device_token)
        row = conn.execute("SELECT * FROM pair_commands WHERE command_id=? AND target_device=? AND session_id=?",
                           (command_id, current["device_id"], current["session_id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Command not found for this device.")
        # Make result retries idempotent: a duplicate report must not overwrite
        # the first terminal outcome if the companion retries after a timeout.
        if row["status"] in ("completed", "reported", "failed"):
            return {"status": "already_recorded", "command_status": row["status"]}
        try:
            result_data = json.loads(result)
        except (TypeError, ValueError):
            result_data = None
        if not isinstance(result_data, dict):
            raise HTTPException(status_code=400, detail="Command result must be a JSON object.")
        # Report execution truthfully. A delivered command is not the same as a
        # successful action; preserve the companion's actual result status.
        action_status = str(result_data.get("status", "error")).lower()
        if action_status == "success":
            command_status = "completed"
        elif action_status in ("launch_requested", "notification_sent"):
            # The OS accepted a launch request, but the companion cannot prove
            # the app became visible or remained open.
            command_status = "reported"
        else:
            command_status = "failed"
        # Keep stored JSON valid even when a companion returns long terminal output.
        stored_result = {}
        limits = {"status": 40, "message": 500, "output": 600, "command": 180, "target": 180, "software": 180}
        for key in ("status", "message", "output", "command", "target", "returncode", "software"):
            value = result_data.get(key)
            if isinstance(value, str):
                stored_result[key] = value[:limits.get(key, 180)]
            elif isinstance(value, (int, float, bool)) or value is None:
                if key in result_data:
                    stored_result[key] = value
        encoded_result = json.dumps(stored_result, ensure_ascii=False)
        conn.execute("UPDATE pair_commands SET status=?,result=? WHERE command_id=? AND status IN ('queued','delivered')",
                     (command_status, encoded_result, command_id))
    return {"status": "recorded", "command_status": command_status}


@app.get("/api/pairing/commands/{command_id}")
async def pairing_command_status(command_id: str, session_id: str, x_nox_device_token: str | None = None):
    with pair_db() as conn:
        current = device_from_token(conn, x_nox_device_token)
        row = conn.execute(
            "SELECT command_id, target_device, command, status, created_at, result FROM pair_commands WHERE command_id=? AND session_id=? AND source_device=?",
            (command_id, session_id, current["device_id"]),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Command not found for this paired source device.")
        return {"command": dict(row)}


@app.get("/api/chats")
async def list_user_chats(user_id: str):
    """List chats for a browser-generated private profile key."""
    if not user_id or len(user_id) > 100:
        raise HTTPException(status_code=400, detail="Invalid user identifier.")
    with pair_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS user_chat_history (
            user_id TEXT NOT NULL, chat_id TEXT NOT NULL, title TEXT NOT NULL,
            updated_at TEXT NOT NULL, messages TEXT NOT NULL,
            PRIMARY KEY(user_id, chat_id))""")
        rows = conn.execute(
            "SELECT chat_id,title,updated_at,messages FROM user_chat_history WHERE user_id=? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return {"chats": [
            {"id": row["chat_id"], "title": row["title"], "updatedAt": row["updated_at"],
             "messages": json.loads(row["messages"])} for row in rows
        ]}


@app.put("/api/chats")
async def save_user_chat(payload: UserChatPayload, user_id: str):
    """Persist a conversation until the user explicitly deletes it."""
    if not user_id or len(user_id) > 100:
        raise HTTPException(status_code=400, detail="Invalid user identifier.")
    messages = [{"role": item.role, "content": item.content} for item in payload.messages[-300:]]
    serialized = json.dumps(messages, ensure_ascii=False)
    if len(serialized) > 1_000_000:
        raise HTTPException(status_code=413, detail="Conversation is too large to save.")
    with pair_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS user_chat_history (
            user_id TEXT NOT NULL, chat_id TEXT NOT NULL, title TEXT NOT NULL,
            updated_at TEXT NOT NULL, messages TEXT NOT NULL,
            PRIMARY KEY(user_id, chat_id))""")
        conn.execute(
            """INSERT INTO user_chat_history(user_id,chat_id,title,updated_at,messages)
               VALUES(?,?,?,?,?) ON CONFLICT(user_id,chat_id) DO UPDATE SET
               title=excluded.title,updated_at=excluded.updated_at,messages=excluded.messages""",
            (user_id, payload.chat_id, payload.title[:120], payload.updated_at[:80], serialized),
        )
    return {"status": "saved", "chat_id": payload.chat_id}


@app.delete("/api/chats/{chat_id}")
async def delete_user_chat(chat_id: str, user_id: str):
    """Permanently remove a chat from persistent history."""
    if not user_id or len(user_id) > 100:
        raise HTTPException(status_code=400, detail="Invalid user identifier.")
    with pair_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS user_chat_history (
            user_id TEXT NOT NULL, chat_id TEXT NOT NULL, title TEXT NOT NULL,
            updated_at TEXT NOT NULL, messages TEXT NOT NULL,
            PRIMARY KEY(user_id, chat_id))""")
        conn.execute("DELETE FROM user_chat_history WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    return {"status": "deleted", "chat_id": chat_id}


@app.get("/api/health")
async def health():
    database_configured = DATABASE_URL.startswith(("postgres://", "postgresql://"))
    database_connected = False
    task_database_connected = False
    database_error = None
    task_database_error = None

    # Pairing/history and task orchestration use separate connection adapters.
    # Probe both so health cannot claim storage is healthy when one subsystem is broken.
    try:
        with pair_db() as conn:
            conn.execute("SELECT 1").fetchone()
        database_connected = True
    except Exception:
        # Never expose connection strings, passwords, or provider error details.
        database_error = "connection_failed"

    try:
        with task_manager._connect() as conn:
            conn.execute("SELECT 1").fetchone()
        task_database_connected = True
    except Exception:
        task_database_error = "connection_failed"

    storage_healthy = database_connected and task_database_connected
    ai_configured = any(os.getenv(key, "").strip() for key in ("OPENROUTER_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"))
    return {
        "status": "ok" if storage_healthy else "degraded",
        "service": "NOX AI",
        "ai_configured": ai_configured,
        "storage_backend": "postgresql" if database_configured else "sqlite",
        "task_storage_backend": "postgresql" if task_manager.use_postgres else "sqlite",
        "durable_storage_configured": database_configured and task_manager.use_postgres,
        "database_connected": database_connected,
        "task_database_connected": task_database_connected,
        "database_error": database_error,
        "task_database_error": task_database_error,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        answer = await provider_reply(message, payload.language, payload.history)
    except httpx.TimeoutException as exc:
        logger.warning("AI provider timed out (%s)", type(exc).__name__)
        raise HTTPException(status_code=504, detail="The AI provider timed out. Please try again.")
    except httpx.RequestError as exc:
        # Log the exception class and safe message so hosting logs identify DNS,
        # TLS, connection, or proxy failures without logging API keys or headers.
        logger.exception("AI provider connection failed (%s): %s", type(exc).__name__, str(exc))
        raise HTTPException(status_code=502, detail="Could not reach the AI provider. Check Render logs for the connection error.")
    except HTTPException:
        raise
    except Exception as exc:
        # Keep an unexpected provider/parser bug from becoming an opaque HTTP 500.
        logger.exception("Unexpected /api/chat failure (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="NOX hit an unexpected AI backend error. Check the server logs.")
    if answer:
        return ChatResponse(reply=answer, mode="ai")
    return ChatResponse(
        reply=(
            "NOX is online in demo mode. To enable real AI responses, add an OPENROUTER_API_KEY "
            "environment variable in your hosting dashboard. I received your message: " + message
        ),
        mode="demo",
    )


@app.get("/api/capabilities")
async def capabilities():
    """Return truthful implementation/setup status for the current NOX build."""
    ai_configured = any(os.getenv(key, "").strip() for key in ("OPENROUTER_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"))
    modules = [
        {"id": "chat", "name": "AI Chat", "status": "ready" if ai_configured else "setup_required", "detail": "Provider-backed chat configured." if ai_configured else "Add OPENROUTER_API_KEY in the hosting environment for real AI responses."},
        {"id": "tasks", "name": "Autonomous Task Orchestration", "status": "ready", "detail": "Persistent task queue with progress, event history, pause/resume/cancel, bounded retries, and a bounded tool-using web research loop. Public web search and page reading only; no login, form submission, purchases, or local-device control."},
        {"id": "voice", "name": "Browser Voice", "status": "limited", "detail": "Uses browser speech recognition/synthesis where supported; availability depends on the device and browser."},
        {"id": "hologram", "name": "Holographic Interface", "status": "ready", "detail": "Animated frontend is available; animation does not imply background task execution."},
        {"id": "research", "name": "Live Web Research", "status": "ready" if ai_configured else "setup_required", "detail": "Bounded public-web search and page reading through the configured AI provider." if ai_configured else "Add OPENROUTER_API_KEY to enable the autonomous research worker."},
        {"id": "coding", "name": "Coding Agent", "status": "setup_required", "detail": "Repository editing and isolated code execution are not exposed as a production tool yet."},
        {"id": "creative", "name": "Image & Video Studio", "status": "setup_required", "detail": "Generation/editing providers and media-processing workflows are not connected yet."},
        {"id": "vision", "name": "Camera & Media Analysis", "status": "setup_required", "detail": "No backend vision-analysis provider is connected in this build."},
        {"id": "browser", "name": "Browser Navigation", "status": "limited", "detail": "Clear commands open recognized websites in a new tab without redundant confirmation; this does not automate clicks or forms. High-impact actions still require confirmation."},
        {"id": "desktop", "name": "Paired Device Actions", "status": "limited", "detail": "Authenticated paired companions report live heartbeats and real command outcomes. Windows can launch Start Menu apps and run an explicit allowlist of diagnostics; optional Home Assistant integration can control supported configured lights, switches, media players, climate, covers and vacuums. Launch requests are labelled as unverified unless the companion reports actual success. Devices must be powered, online, paired and running a compatible companion; arbitrary desktop control and universal power-on/off are not available."},
        {"id": "security", "name": "Cybersecurity Lab", "status": "setup_required", "detail": "Security checks must be implemented and scoped to authorized targets before use."},
        {"id": "files", "name": "Files & Knowledge Base", "status": "setup_required", "detail": "A persistent indexed file store is not configured yet."},
        {"id": "memory", "name": "Persistent Memory", "status": "setup_required", "detail": "Conversation history is currently request-provided; persistent user-approved memory is not configured."},
        {"id": "analytics", "name": "Accounts & Analytics", "status": "setup_required", "detail": "Authentication, database-backed usage metrics, and admin analytics are not configured."},
    ]
    return {"service": "NOX AI", "version": app.version, "ai_configured": ai_configured, "modules": modules}


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
