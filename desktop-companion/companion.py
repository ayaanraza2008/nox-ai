"""Permissioned local Windows companion for NOX AI.

Only fixed, allow-listed applications and HTTPS destinations can be opened.
No arbitrary shell commands, file reads, or general remote-control endpoint.
"""
import hmac
import os
import shutil
import subprocess
import webbrowser
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

TOKEN = os.getenv("NOX_COMPANION_TOKEN", "").strip()
WEB_ORIGIN = os.getenv("NOX_WEB_ORIGIN", "https://nox-ai-vcqx.onrender.com").strip()
HOST = "127.0.0.1"
PORT = int(os.getenv("NOX_COMPANION_PORT", "8765"))

app = FastAPI(title="NOX Local Desktop Companion", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[WEB_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-NOX-Token"],
)

# Fixed commands only. Never accept an executable path or arguments from a request.
WINDOWS_APPS = {
    "calculator": ["calc.exe"],
    "notepad": ["notepad.exe"],
    "paint": ["mspaint.exe"],
    "file explorer": ["explorer.exe"],
    "task manager": ["taskmgr.exe"],
}
DESTINATIONS = {
    "instagram": "https://www.instagram.com/",
    "youtube": "https://www.youtube.com/",
    "google": "https://www.google.com/",
    "whatsapp web": "https://web.whatsapp.com/",
    "github": "https://github.com/",
    "chatgpt": "https://chatgpt.com/",
}

class OpenRequest(BaseModel):
    target: Literal[
        "calculator", "notepad", "paint", "file explorer", "task manager",
        "instagram", "youtube", "google", "whatsapp web", "github", "chatgpt"
    ]
    confirmed: bool = False


def authorize(token: str | None):
    if not TOKEN:
        raise HTTPException(status_code=503, detail="Set NOX_COMPANION_TOKEN before starting the companion.")
    if not token or not hmac.compare_digest(token, TOKEN):
        raise HTTPException(status_code=401, detail="Invalid companion token.")


@app.get("/health")
def health():
    return {
        "service": "NOX Local Desktop Companion",
        "status": "ok",
        "host": HOST,
        "actions": sorted([*WINDOWS_APPS.keys(), *DESTINATIONS.keys()]),
        "platform": os.name,
    }


@app.post("/v1/actions/open")
def open_target(payload: OpenRequest, x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="User confirmation is required before opening an app or website.")

    if payload.target in WINDOWS_APPS:
        if os.name != "nt":
            raise HTTPException(status_code=501, detail="Installed-app launching is currently supported on Windows only.")
        command = WINDOWS_APPS[payload.target]
        if not shutil.which(command[0]):
            raise HTTPException(status_code=404, detail=f"{payload.target} was not found on this PC.")
        try:
            subprocess.Popen(command, shell=False, close_fds=True)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Could not launch {payload.target}: {exc}") from exc
        return {"status": "launch_requested", "target": payload.target,
                "message": "Launch request sent. Verify the app window on this PC."}

    url = DESTINATIONS.get(payload.target)
    if not url:
        raise HTTPException(status_code=400, detail="Target is not on the allowlist.")
    try:
        opened = webbrowser.open(url, new=2, autoraise=True)
    except Exception:
        opened = False
    if not opened:
        raise HTTPException(status_code=500, detail="The default browser did not confirm opening the destination.")
    return {"status": "launch_requested", "target": payload.target, "url": url,
            "message": "Browser-open request sent. Verify the browser window on this PC."}


if __name__ == "__main__":
    import uvicorn
    if not TOKEN:
        raise SystemExit("Set NOX_COMPANION_TOKEN to a long random secret before running.")
    print(f"Starting NOX local companion on http://{HOST}:{PORT}")
    print("Loopback only; fixed allowlist; confirmation and token required.")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
