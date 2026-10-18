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


PAIR_DB = Path(os.getenv("NOX_PAIRING_DB", str(ROOT / "nox_pairing.sqlite3")))


@contextmanager
def pair_db():
    PAIR_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(PAIR_DB, timeout=10)
    conn.row_factory = sqlite3.Row
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
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    messages = [
        {
            "role": "system",
            "content": (
                "You are NOX, a helpful, natural, concise multilingual assistant. "
                "Understand Hindi, Urdu, English, and Hinglish. Match the user's language "
                "when possible. Be honest about limitations and never claim actions you did not do. "
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

    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("APP_URL", "https://nox-ai.onrender.com"),
                "X-Title": "NOX AI",
            },
            json={"model": model, "messages": messages, "temperature": 0.7},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="AI provider request failed. Check the provider key/model and try again.")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail="AI provider returned an unexpected response.")


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
        for _ in range(5):
            try:
                conn.execute("INSERT INTO pair_sessions(session_id,code,created_at,expires_at) VALUES(?,?,?,?)",
                             (session_id, code, expires, expires_at))
                break
            except sqlite3.IntegrityError:
                code = "".join(secrets.choice(string.digits) for _ in range(6))
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
    with pair_db() as conn:
        current = device_from_token(conn, x_nox_device_token)
        row = conn.execute("SELECT * FROM pair_commands WHERE command_id=? AND target_device=? AND session_id=?",
                           (command_id, current["device_id"], current["session_id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Command not found for this device.")
        conn.execute("UPDATE pair_commands SET status='completed',result=? WHERE command_id=?", (result[:2000], command_id))
    return {"status": "recorded"}


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


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "NOX AI", "ai_configured": bool(os.getenv("OPENROUTER_API_KEY"))}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        answer = await provider_reply(message, payload.language, payload.history)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="The AI provider timed out. Please try again.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not reach the AI provider. Please try again.")
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
    ai_configured = bool(os.getenv("OPENROUTER_API_KEY"))
    modules = [
        {"id": "chat", "name": "AI Chat", "status": "ready" if ai_configured else "setup_required", "detail": "Provider-backed chat configured." if ai_configured else "Add OPENROUTER_API_KEY in the hosting environment for real AI responses."},
        {"id": "tasks", "name": "Autonomous Task Orchestration", "status": "ready", "detail": "Persistent task queue with progress, event history, pause/resume/cancel, bounded retries, and a bounded tool-using web research loop. Public web search and page reading only; no login, form submission, purchases, or local-device control."},
        {"id": "voice", "name": "Browser Voice", "status": "limited", "detail": "Uses browser speech recognition/synthesis where supported; availability depends on the device and browser."},
        {"id": "hologram", "name": "Holographic Interface", "status": "ready", "detail": "Animated frontend is available; animation does not imply background task execution."},
        {"id": "research", "name": "Live Web Research", "status": "ready" if ai_configured else "setup_required", "detail": "Bounded public-web search and page reading through the configured AI provider." if ai_configured else "Add OPENROUTER_API_KEY to enable the autonomous research worker."},
        {"id": "coding", "name": "Coding Agent", "status": "setup_required", "detail": "Repository editing and isolated code execution are not exposed as a production tool yet."},
        {"id": "creative", "name": "Image & Video Studio", "status": "setup_required", "detail": "Generation/editing providers and media-processing workflows are not connected yet."},
        {"id": "vision", "name": "Camera & Media Analysis", "status": "setup_required", "detail": "No backend vision-analysis provider is connected in this build."},
        {"id": "browser", "name": "Browser Navigation", "status": "limited", "detail": "The frontend can open recognized websites or explicit HTTP(S) URLs in a new tab after user confirmation; it cannot yet automate clicks or forms."},
        {"id": "desktop", "name": "Local App Launch", "status": "limited", "detail": "An opt-in Windows companion can request launch of a fixed allowlist of apps after confirmation and token authentication. Browser local-network/mixed-content policy may block the hosted web bridge. General desktop control, file access, and arbitrary commands are not available."},
        {"id": "security", "name": "Cybersecurity Lab", "status": "setup_required", "detail": "Security checks must be implemented and scoped to authorized targets before use."},
        {"id": "files", "name": "Files & Knowledge Base", "status": "setup_required", "detail": "A persistent indexed file store is not configured yet."},
        {"id": "memory", "name": "Persistent Memory", "status": "setup_required", "detail": "Conversation history is currently request-provided; persistent user-approved memory is not configured."},
        {"id": "analytics", "name": "Accounts & Analytics", "status": "setup_required", "detail": "Authentication, database-backed usage metrics, and admin analytics are not configured."},
    ]
    return {"service": "NOX AI", "version": app.version, "ai_configured": ai_configured, "modules": modules}


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
