"""Permissioned local Windows companion for NOX AI.

Discovers apps from Windows Start Menu shortcuts. Only an explicit, confirmed,
token-authenticated request can launch one discovered shortcut. No arbitrary shell.
"""
import hashlib
import hmac
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

TOKEN = os.getenv("NOX_COMPANION_TOKEN", "").strip()
WEB_ORIGIN = os.getenv("NOX_WEB_ORIGIN", "https://nox-ai-vcqx.onrender.com").strip()
HOST = "127.0.0.1"
PORT = int(os.getenv("NOX_COMPANION_PORT", "8765"))

app = FastAPI(title="NOX Local Desktop Companion", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[WEB_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-NOX-Token"],
)

DESTINATIONS = {
    "instagram": "https://www.instagram.com/",
    "youtube": "https://www.youtube.com/",
    "google": "https://www.google.com/",
    "whatsapp web": "https://web.whatsapp.com/",
    "github": "https://github.com/",
    "chatgpt": "https://chatgpt.com/",
}

class OpenRequest(BaseModel):
    target: str
    confirmed: bool = False


def authorize(token: str | None):
    if not TOKEN:
        raise HTTPException(status_code=503, detail="Set NOX_COMPANION_TOKEN before starting the companion.")
    if not token or not hmac.compare_digest(token, TOKEN):
        raise HTTPException(status_code=401, detail="Invalid companion token.")


def shortcut_roots():
    roots = []
    appdata = os.getenv("APPDATA")
    programdata = os.getenv("PROGRAMDATA")
    if appdata:
        roots.append(Path(appdata) / "Microsoft/Windows/Start Menu/Programs")
    if programdata:
        roots.append(Path(programdata) / "Microsoft/Windows/Start Menu/Programs")
    return [p for p in roots if p.is_dir()]


def discover_apps():
    """Return only Start Menu .lnk shortcuts, with opaque IDs instead of paths."""
    if os.name != "nt":
        return []
    found = {}
    for root in shortcut_roots():
        try:
            shortcuts = root.rglob("*.lnk")
            for path in shortcuts:
                try:
                    if not path.is_file():
                        continue
                    label = path.stem.strip()
                    if not label:
                        continue
                    app_id = hashlib.sha256(str(path.resolve()).casefold().encode("utf-8")).hexdigest()[:20]
                    found[app_id] = {"id": app_id, "name": label}
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            continue
    return sorted(found.values(), key=lambda x: x["name"].casefold())


def find_shortcut(app_id: str):
    if len(app_id) != 20 or any(c not in "0123456789abcdef" for c in app_id):
        return None
    for root in shortcut_roots():
        try:
            for path in root.rglob("*.lnk"):
                try:
                    expected = hashlib.sha256(str(path.resolve()).casefold().encode("utf-8")).hexdigest()[:20]
                    if hmac.compare_digest(expected, app_id) and path.is_file():
                        return path
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            continue
    return None


@app.get("/health")
def health():
    return {
        "service": "NOX Local Desktop Companion",
        "status": "ok",
        "host": HOST,
        "platform": os.name,
        "dynamic_start_menu_discovery": os.name == "nt",
    }


@app.get("/v1/apps")
def list_apps(x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="Start Menu app discovery is currently supported on Windows only.")
    apps = discover_apps()
    return {"apps": apps, "count": len(apps), "source": "Windows Start Menu shortcuts"}


@app.post("/v1/actions/open")
def open_target(payload: OpenRequest, x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="User confirmation is required before opening an app or website.")

    # Website targets are fixed and never accept arbitrary URLs.
    if payload.target in DESTINATIONS:
        try:
            opened = webbrowser.open(DESTINATIONS[payload.target], new=2, autoraise=True)
        except Exception:
            opened = False
        if not opened:
            raise HTTPException(status_code=500, detail="The default browser did not confirm opening the destination.")
        return {"status": "launch_requested", "target": payload.target, "url": DESTINATIONS[payload.target]}

    if os.name != "nt":
        raise HTTPException(status_code=501, detail="Installed-app launch is currently supported on Windows only.")
    shortcut = find_shortcut(payload.target)
    if shortcut is None:
        raise HTTPException(status_code=404, detail="App shortcut was not found. Refresh the app list and try again.")
    try:
        # Launch the user's selected Start Menu shortcut; no request-supplied command or path.
        os.startfile(str(shortcut))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Windows could not launch this app shortcut: {exc}") from exc
    return {"status": "launch_requested", "target": shortcut.stem,
            "message": "Launch request sent. Verify the app window on this PC."}


if __name__ == "__main__":
    import uvicorn
    if not TOKEN:
        raise SystemExit("Set NOX_COMPANION_TOKEN to a long random secret before running.")
    print(f"Starting NOX local companion on http://{HOST}:{PORT}")
    print("Loopback only; discovered Start Menu shortcuts; confirmation and token required.")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
