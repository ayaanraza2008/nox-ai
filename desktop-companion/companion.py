"""Minimal local NOX companion. Only opens allow-listed web destinations; no shell execution."""
import hmac
import os
import webbrowser
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

TOKEN = os.getenv("NOX_COMPANION_TOKEN", "").strip()
WEB_ORIGIN = os.getenv("NOX_WEB_ORIGIN", "https://nox-ai-vcqx.onrender.com").strip()
HOST = "127.0.0.1"
PORT = int(os.getenv("NOX_COMPANION_PORT", "8765"))

app = FastAPI(title="NOX Local Desktop Companion", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[WEB_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-NOX-Token"],
)

DESTINATIONS = {
    "instagram": "https://www.instagram.com/",
}


class OpenRequest(BaseModel):
    target: Literal["instagram"]
    confirmed: bool = False


def authorize(token: str | None):
    if not TOKEN:
        raise HTTPException(status_code=503, detail="Set NOX_COMPANION_TOKEN before starting the companion.")
    if not token or not hmac.compare_digest(token, TOKEN):
        raise HTTPException(status_code=401, detail="Invalid companion token.")


@app.get("/health")
def health():
    return {"service": "NOX Local Desktop Companion", "status": "ok", "host": HOST, "actions": ["open instagram website"]}


@app.post("/v1/actions/open")
def open_destination(payload: OpenRequest, x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="User confirmation is required before opening a destination.")
    url = DESTINATIONS[payload.target]
    try:
        opened = webbrowser.open(url, new=2, autoraise=True)
    except Exception:
        opened = False
    if not opened:
        raise HTTPException(status_code=500, detail="The default browser did not confirm opening the destination.")
    return {"status": "requested", "target": payload.target, "url": url, "message": "Open request sent to the default browser. Verify the browser window on this PC."}


if __name__ == "__main__":
    import uvicorn
    if not TOKEN:
        raise SystemExit("Set NOX_COMPANION_TOKEN to a long random secret before running.")
    print(f"Starting NOX local companion on http://{HOST}:{PORT}")
    print("This service binds to loopback only and exposes an allow-listed Instagram website action.")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
