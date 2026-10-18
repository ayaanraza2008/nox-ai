import os
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
        {"id": "desktop", "name": "Local App & Desktop Control", "status": "unavailable", "detail": "A permissioned local companion is required to launch installed apps, read local files, or control the user's device; a hosted Render service cannot do this directly."},
        {"id": "security", "name": "Cybersecurity Lab", "status": "setup_required", "detail": "Security checks must be implemented and scoped to authorized targets before use."},
        {"id": "files", "name": "Files & Knowledge Base", "status": "setup_required", "detail": "A persistent indexed file store is not configured yet."},
        {"id": "memory", "name": "Persistent Memory", "status": "setup_required", "detail": "Conversation history is currently request-provided; persistent user-approved memory is not configured."},
        {"id": "analytics", "name": "Accounts & Analytics", "status": "setup_required", "detail": "Authentication, database-backed usage metrics, and admin analytics are not configured."},
    ]
    return {"service": "NOX AI", "version": app.version, "ai_configured": ai_configured, "modules": modules}


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
