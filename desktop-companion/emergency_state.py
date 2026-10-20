"""Persistent fail-closed stop latch and managed child-process cancellation."""
from __future__ import annotations

import json
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.RLock()
_ACTIVE_PROCESSES: dict[int, subprocess.Popen] = {}
MAX_MANAGED_PROCESSES = 16


class EmergencyStopActive(RuntimeError):
    """Raised when a new local process is attempted while NOX is stopped."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_path() -> Path:
    configured = os.getenv("NOX_COMPANION_STATE_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    base = os.getenv("LOCALAPPDATA", "").strip()
    root = Path(base) / "NOX AI" if base else Path.home() / ".nox-ai"
    return root / "emergency-state.json"


def get_state() -> dict:
    path = state_path()
    with _LOCK:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("state must be an object")
            return {
                "stopped": bool(value.get("stopped", False)),
                "stopped_at": value.get("stopped_at"),
                "updated_at": value.get("updated_at"),
                "reason": str(value.get("reason", ""))[:120],
                "process_cleanup": value.get("process_cleanup", []),
                "state_file": str(path),
            }
        except FileNotFoundError:
            return {"stopped": False, "stopped_at": None, "updated_at": None,
                    "reason": "", "process_cleanup": [], "state_file": str(path)}
        except (OSError, ValueError, TypeError):
            # Fail closed if the latch file exists but cannot be trusted/read.
            return {"stopped": True, "stopped_at": None, "updated_at": None,
                    "reason": "state_unreadable_fail_closed", "process_cleanup": [],
                    "state_file": str(path)}


def register_process(process: subprocess.Popen) -> bool:
    """Register only a process launched by NOX; reject it if stop already latched."""
    with _LOCK:
        if get_state()["stopped"]:
            _terminate_process(process)
            return False
        if len(_ACTIVE_PROCESSES) >= MAX_MANAGED_PROCESSES:
            _terminate_process(process)
            raise RuntimeError("NOX managed-process limit reached.")
        _ACTIVE_PROCESSES[process.pid] = process
        return True


def unregister_process(process: subprocess.Popen) -> None:
    with _LOCK:
        _ACTIVE_PROCESSES.pop(process.pid, None)


def _terminate_process(process: subprocess.Popen) -> dict:
    pid = process.pid
    if process.poll() is not None:
        return {"pid": pid, "status": "already_exited"}
    try:
        if os.name == "nt" and hasattr(subprocess, "CTRL_BREAK_EVENT"):
            try:
                process.send_signal(subprocess.CTRL_BREAK_EVENT)
                process.wait(timeout=0.8)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if process.poll() is None:
                # The PID is from a process explicitly created and tracked by NOX.
                # /T limits force termination to that managed process tree.
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        shell=False, capture_output=True, timeout=3, check=False,
                        stdin=subprocess.DEVNULL,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                    except OSError:
                        pass
        else:
            process.terminate()
            try:
                process.wait(timeout=0.8)
            except subprocess.TimeoutExpired:
                process.kill()
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            return {"pid": pid, "status": "cleanup_pending"}
        return {"pid": pid, "status": "terminated_managed_process"}
    except OSError:
        return {"pid": pid, "status": "cleanup_pending"}


def terminate_managed_processes() -> list[dict]:
    with _LOCK:
        processes = list(_ACTIVE_PROCESSES.values())
    results = []
    for process in processes:
        results.append(_terminate_process(process))
        if process.poll() is not None:
            unregister_process(process)
    return results


def run_managed_process(args: list[str], *, cwd: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run an allowlisted argv command while tracking its owned process for stop."""
    if get_state()["stopped"]:
        raise EmergencyStopActive("NOX Emergency Stop is latched.")
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    process = subprocess.Popen(
        args, cwd=cwd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, stdin=subprocess.DEVNULL, creationflags=creationflags,
    )
    if not register_process(process):
        raise EmergencyStopActive("NOX Emergency Stop latched before process execution.")
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _terminate_process(process)
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(args, timeout, output=stdout, stderr=stderr) from exc
        if get_state()["stopped"]:
            raise EmergencyStopActive("NOX Emergency Stop terminated this managed process.")
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
    finally:
        unregister_process(process)


def set_stopped(stopped: bool, reason: str = "user_action") -> dict:
    current = get_state()
    if not stopped and current["stopped"]:
        pending_pids = {
            item.get("pid") for item in current.get("process_cleanup", [])
            if isinstance(item, dict) and item.get("status") == "cleanup_pending"
        }
        with _LOCK:
            still_running = any(
                pid in _ACTIVE_PROCESSES and _ACTIVE_PROCESSES[pid].poll() is None
                for pid in pending_pids
            )
        if still_running:
            raise RuntimeError("Cannot resume while a NOX-managed process still requires cleanup.")
    path = state_path()
    timestamp = _now()
    state = {
        "stopped": bool(stopped),
        "stopped_at": timestamp if stopped else None,
        "updated_at": timestamp,
        "reason": str(reason)[:120],
        "process_cleanup": [],
    }
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    if stopped:
        state["process_cleanup"] = terminate_managed_processes()
        state["updated_at"] = _now()
        with _LOCK:
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, path)
    return {**state, "state_file": str(path)}
