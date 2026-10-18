"""Bounded autonomous task runner for NOX AI.

Tasks run only through registered workspace tools. No shell execution, arbitrary
computer control, network browsing, or unrestricted filesystem access is exposed.
Task state is process-local in this starter implementation and resets on restart.
"""
import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])
ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = (ROOT / "workspace").resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)

ENABLED = False
TASKS: dict[str, dict[str, Any]] = {}
RUNNERS: dict[str, asyncio.Task] = {}
MAX_STEPS = 8
MAX_FILE_BYTES = 100_000
ALLOWED_TOOLS = {"workspace_list", "workspace_read", "workspace_search", "workspace_write"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def activity(task: dict[str, Any], message: str, level: str = "info") -> None:
    task["activity"].append({"at": now(), "level": level, "message": message[:500]})
    task["activity"] = task["activity"][-100:]
    task["updated_at"] = now()


def safe_path(relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("A workspace-relative path is required.")
    candidate = Path(relative)
    if candidate.is_absolute() or any(part in (".", "..") for part in candidate.parts):
        raise ValueError("Use a relative path inside the NOX workspace; parent traversal is not allowed.")
    resolved = (WORKSPACE / candidate).resolve()
    if not resolved.is_relative_to(WORKSPACE):
        raise ValueError("Path is outside the authorized workspace.")
    return resolved


def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name not in ALLOWED_TOOLS:
        raise ValueError("Tool is not registered or permitted.")
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object.")

    if name == "workspace_list":
        rel = args.get("path", " ")
        folder = WORKSPACE if not str(rel).strip() else safe_path(str(rel))
        if not folder.exists():
            return {"path": str(folder.relative_to(WORKSPACE)), "entries": []}
        if not folder.is_dir():
            raise ValueError("The requested workspace path is not a directory.")
        entries = []
        for child in sorted(folder.iterdir(), key=lambda p: p.name.lower())[:200]:
            entries.append({"name": child.name, "type": "directory" if child.is_dir() else "file"})
        return {"path": str(folder.relative_to(WORKSPACE)), "entries": entries}

    if name == "workspace_read":
        path = safe_path(str(args.get("path", "")))
        if not path.exists() or not path.is_file():
            raise ValueError("File does not exist in the workspace.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("File is larger than the 100 KB read limit.")
        return {"path": str(path.relative_to(WORKSPACE)), "content": path.read_text(encoding="utf-8")}

    if name == "workspace_search":
        query = str(args.get("query", "")).strip()
        if not query or len(query) > 300:
            raise ValueError("Search query must contain 1–300 characters.")
        matches = []
        root = safe_path(str(args.get("path", " "))) if str(args.get("path", "")).strip() else WORKSPACE
        files = [root] if root.is_file() else list(root.rglob("*"))[:1000]
        for file_path in files:
            if not file_path.is_file() or file_path.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                for line_no, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
                    if query.casefold() in line.casefold():
                        matches.append({"path": str(file_path.relative_to(WORKSPACE)), "line": line_no, "text": line[:400]})
                        if len(matches) >= 100:
                            return {"query": query, "matches": matches, "truncated": True}
            except (UnicodeDecodeError, OSError):
                continue
        return {"query": query, "matches": matches, "truncated": False}

    if name == "workspace_write":
        path = safe_path(str(args.get("path", "")))
        content = args.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("File content must be a non-empty string.")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError("Generated file exceeds the 100 KB write limit.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"path": str(path.relative_to(WORKSPACE)), "bytes_written": path.stat().st_size, "verified": path.exists()}

    raise ValueError("No executor is registered for this tool.")


async def make_plan(objective: str) -> list[dict[str, Any]]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        slug = re.sub(r"[^a-z0-9]+", "-", objective.lower()).strip("-")[:40] or "task"
        content = (
            "# NOX Autonomous Task Brief\n\n"
            f"## Objective\n{objective}\n\n"
            "## Execution status\nAI planning is unavailable because OPENROUTER_API_KEY is not configured. "
            "This file is a local task brief, not proof that the requested real-world objective was completed.\n\n"
            "## Safe next steps\n- Configure an AI provider to enable model-generated planning.\n"
            "- Add relevant input files to the NOX workspace if the task requires file analysis.\n"
            "- Review this brief before taking external or destructive actions.\n"
        )
        return [{"title": "Create a transparent task brief", "tool": "workspace_write",
                 "args": {"path": f"reports/{slug}-brief.md", "content": content}}]

    prompt = {
        "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content":
             "You are NOX's bounded task planner. Return ONLY valid JSON: "
             '{"steps":[{"title":"short action","tool":"workspace_list|workspace_read|workspace_search|workspace_write","args":{}}]}. '
             f"Use at most {MAX_STEPS} steps. Only these tools exist: workspace_list(path optional), "
             "workspace_read(path), workspace_search(query,path optional), workspace_write(path,content). "
             "All paths are relative to an isolated NOX workspace. Never request shell, network, credentials, "
             "system control, arbitrary filesystem access, or destructive actions. For objectives that cannot "
             "be completed with these tools, write a markdown report describing the bounded next steps and limitations "
             "using workspace_write. Use a new path under reports/ for generated reports. Do not claim a task is done "
             "before tools run. Return a non-empty steps array."},
            {"role": "user", "content": objective}
        ]
    }
    async with httpx.AsyncClient(timeout=35) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": os.getenv("APP_URL", "https://nox-ai.onrender.com"), "X-Title": "NOX AI"},
            json=prompt,
        )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"]
    raw = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw, flags=re.I)
    plan_data = json.loads(raw)
    steps = plan_data.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS:
        raise ValueError(f"Planner must return between 1 and {MAX_STEPS} steps.")
    validated = []
    for item in steps:
        if not isinstance(item, dict) or item.get("tool") not in ALLOWED_TOOLS:
            raise ValueError("Planner requested a tool that is not on the registered allowlist.")
        args = item.get("args", {})
        if not isinstance(args, dict):
            raise ValueError("Planner returned invalid tool arguments.")
        # Validate paths and limits before the plan is shown/executed.
        tool = item["tool"]
        if tool in {"workspace_read", "workspace_write"}:
            safe_path(str(args.get("path", "")))
        if tool == "workspace_search" and str(args.get("path", "")).strip():
            safe_path(str(args["path"]))
        if tool == "workspace_list" and str(args.get("path", "")).strip():
            safe_path(str(args["path"]))
        if tool == "workspace_write":
            if not isinstance(args.get("content"), str) or len(args["content"].encode("utf-8")) > MAX_FILE_BYTES:
                raise ValueError("Planner produced invalid or oversized file content.")
        validated.append({"id": str(uuid.uuid4()), "title": str(item.get("title", tool))[:180],
                          "tool": tool, "args": args, "status": "pending", "result": None, "error": None})
    return validated


async def run_task(task_id: str) -> None:
    task = TASKS.get(task_id)
    if not task:
        return
    try:
        task["status"] = "planning"
        activity(task, "Creating a bounded plan with the configured AI provider.")
        task["plan"] = await make_plan(task["objective"])
        activity(task, f"Plan validated: {len(task['plan'])} registered tool step(s).")
        if task.get("cancel_requested"):
            task["status"] = "cancelled"
            activity(task, "Task cancelled before execution.", "warning")
            return
        task["status"] = "running"
        for index, step in enumerate(task["plan"]):
            while task["status"] == "paused" and not task.get("cancel_requested") and not task.get("stop_requested"):
                await asyncio.sleep(0.25)
            if task.get("cancel_requested"):
                task["status"] = "cancelled"
                activity(task, "Cancellation confirmed at a safe checkpoint.", "warning")
                return
            if task.get("stop_requested"):
                task["status"] = "stopped"
                activity(task, "Stopped at a safe checkpoint; no further steps will be scheduled.", "warning")
                return
            task["current_step"] = index
            step["status"] = "running"
            activity(task, f"Executing step {index + 1}/{len(task['plan'])}: {step['title']}")
            try:
                result = await asyncio.wait_for(asyncio.to_thread(run_tool, step["tool"], step["args"]), timeout=20)
                step["result"] = result
                step["status"] = "completed"
                task["completed_steps"] += 1
                activity(task, f"Step verified: {step['title']}")
            except Exception as exc:
                step["status"] = "failed"
                step["error"] = str(exc)[:500]
                task["failed_steps"] += 1
                activity(task, f"Step failed: {step['title']} — {str(exc)[:250]}", "error")
                task["status"] = "failed"
                task["summary"] = f"Task stopped after step {index + 1} failed. Review the step error and activity log."
                return
        task["status"] = "completed"
        task["summary"] = f"Completed {task['completed_steps']} registered workspace tool step(s). Review each result and generated file path."
        activity(task, task["summary"], "success")
    except httpx.HTTPError:
        task["status"] = "failed"
        task["summary"] = "AI provider request failed. Check provider configuration and try again."
        activity(task, task["summary"], "error")
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        task["status"] = "failed"
        task["summary"] = f"Task planning failed: {str(exc)[:350]}"
        activity(task, task["summary"], "error")
    except Exception:
        task["status"] = "failed"
        task["summary"] = "Unexpected task error. Check the activity log and server logs."
        activity(task, task["summary"], "error")
    finally:
        task["updated_at"] = now()


class ModeRequest(BaseModel):
    enabled: bool


class TaskRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=4000)


class ControlRequest(BaseModel):
    action: Literal["pause", "resume", "stop", "cancel"]


@router.get("/state")
async def state():
    recent = sorted(TASKS.values(), key=lambda t: t["created_at"], reverse=True)[:20]
    return {"enabled": ENABLED, "capabilities": ["workspace_list", "workspace_read", "workspace_search", "workspace_write"],
            "workspace": "workspace/", "task_state_persistence": "process-local; resets on server restart",
            "tasks": [public_task(t) for t in recent]}


@router.put("/mode")
async def set_mode(payload: ModeRequest):
    global ENABLED
    ENABLED = payload.enabled
    return {"enabled": ENABLED, "message": "Autonomous Mode enabled." if ENABLED else "Autonomous Mode disabled. Running tasks are not automatically cancelled."}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found. In-memory task history may have reset after a server restart.")
    return public_task(task)


@router.post("/tasks")
async def create_task(payload: TaskRequest):
    if not ENABLED:
        raise HTTPException(status_code=409, detail="Enable Autonomous Mode before starting a task.")
    objective = payload.objective.strip()
    if not objective:
        raise HTTPException(status_code=400, detail="Task objective cannot be empty.")
    active = [t for t in TASKS.values() if t["status"] in {"queued", "planning", "running", "paused"} and t["objective"] == objective]
    if active:
        return public_task(active[0])
    task_id = str(uuid.uuid4())
    task = {"id": task_id, "objective": objective, "status": "queued", "created_at": now(), "updated_at": now(),
            "plan": [], "activity": [], "current_step": None, "completed_steps": 0, "failed_steps": 0,
            "summary": None, "cancel_requested": False, "stop_requested": False}
    TASKS[task_id] = task
    activity(task, "Task accepted and queued.")
    RUNNERS[task_id] = asyncio.create_task(run_task(task_id))
    return public_task(task)


@router.post("/tasks/{task_id}/control")
async def control_task(task_id: str, payload: ControlRequest):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    action = payload.action
    if action == "pause":
        if task["status"] != "running":
            raise HTTPException(status_code=409, detail="Only a running task can be paused.")
        task["status"] = "paused"
        activity(task, "Pause requested; execution will wait at the next safe checkpoint.")
    elif action == "resume":
        if task["status"] != "paused":
            raise HTTPException(status_code=409, detail="Only a paused task can be resumed.")
        task["status"] = "running"
        activity(task, "Task resumed.")
    elif action == "stop":
        if task["status"] not in {"queued", "planning", "running", "paused"}:
            raise HTTPException(status_code=409, detail="Task is already in a terminal state.")
        task["stop_requested"] = True
        if task["status"] == "paused":
            task["status"] = "running"
        activity(task, "Stop requested; the task will stop at a safe checkpoint.", "warning")
    elif action == "cancel":
        if task["status"] not in {"queued", "planning", "running", "paused"}:
            raise HTTPException(status_code=409, detail="Task is already in a terminal state.")
        task["cancel_requested"] = True
        if task["status"] == "paused":
            task["status"] = "running"
        activity(task, "Cancellation requested; no new steps will be scheduled.", "warning")
    return public_task(task)


def public_task(task: dict[str, Any]) -> dict[str, Any]:
    plan = []
    for step in task["plan"]:
        plan.append({key: value for key, value in step.items() if key != "args"})
    return {key: task[key] for key in ("id", "objective", "status", "created_at", "updated_at", "current_step",
            "completed_steps", "failed_steps", "summary", "activity")} | {"plan": plan}
