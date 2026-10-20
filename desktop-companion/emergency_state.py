"""Persistent local Emergency Stop latch for the opt-in Windows companion."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.RLock()


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
                "state_file": str(path),
            }
        except FileNotFoundError:
            return {"stopped": False, "stopped_at": None, "updated_at": None,
                    "reason": "", "state_file": str(path)}
        except (OSError, ValueError, TypeError):
            # Fail closed if the latch file exists but cannot be trusted/read.
            return {"stopped": True, "stopped_at": None, "updated_at": None,
                    "reason": "state_unreadable_fail_closed", "state_file": str(path)}


def set_stopped(stopped: bool, reason: str = "user_action") -> dict:
    path = state_path()
    timestamp = _now()
    state = {
        "stopped": bool(stopped),
        "stopped_at": timestamp if stopped else None,
        "updated_at": timestamp,
        "reason": str(reason)[:120],
    }
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    return {**state, "state_file": str(path)}
