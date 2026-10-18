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

try:
    from home_assistant import execute_home_assistant_command
except ImportError:
    execute_home_assistant_command = None

try:
    from ethical_hacking import check_website_security
except ImportError:
    check_website_security = None

try:
    from security_audit import audit_project
except ImportError:
    audit_project = None

try:
    from dependency_audit import audit_dependencies, write_report
except ImportError:
    audit_dependencies = None
    write_report = None

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


def handle_security_command(raw: str):
    """Dispatch the supported defensive security commands without starting the relay."""
    command = raw.strip()
    if re.fullmatch(r"(?:security check|check security of|check headers for)\s+(https://\S+)", command, re.I):
        match = re.fullmatch(r"(?:security check|check security of|check headers for)\s+(https://\S+)", command, re.I)
        if check_website_security is None:
            return {"status": "unsupported", "message": "The NOX passive security module is unavailable in this installation."}
        return check_website_security(match.group(1))

    if re.fullmatch(r"(?:audit project security|security audit project|scan my project code)", command, re.I):
        if audit_project is None:
            return {"status": "unsupported", "message": "The NOX read-only project audit module is unavailable in this installation."}
        return audit_project()

    if re.fullmatch(r"(?:audit project dependencies|check dependency vulnerabilities|check dependencies)", command, re.I):
        if audit_dependencies is None:
            return {"status": "unsupported", "message": "The NOX dependency audit module is unavailable in this installation."}
        return audit_dependencies()

    if re.fullmatch(r"(?:generate security report|create security report|full project security audit)", command, re.I):
        if audit_project is None or audit_dependencies is None or write_report is None:
            return {"status": "unsupported", "message": "One or more NOX security audit modules are unavailable in this installation."}
        static_result = audit_project()
        dependency_result = audit_dependencies()
        report_result = write_report(static_result, dependency_result)
        return {
            "status": report_result.get("status", "error"),
            "static_analysis": static_result,
            "dependency_audit": dependency_result,
            "report_files": report_result,
        }
    return None


def pairing_worker():
    """Poll the paired command queue; reconnect automatically after transient network failures."""
    import json
    import re
    import time
    import threading
    import urllib.parse
    import urllib.request
    import urllib.error

    api = os.getenv("NOX_PAIRING_API", "https://nox-ai-vcqx.onrender.com").rstrip("/")
    code = os.getenv("NOX_PAIR_CODE", "").strip()
    config = Path(os.getenv("NOX_PAIRING_FILE", str(Path.home() / ".nox-ai" / "paired-device.json")))
    pairing = None

    def request(path, method="GET", payload=None, token=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["X-NOX-Device-Token"] = token
        req = urllib.request.Request(api + path, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def join():
        nonlocal pairing
        if pairing and pairing.get("session_id") and pairing.get("device_token"):
            return pairing
        try:
            saved = json.loads(config.read_text(encoding="utf-8"))
            if saved.get("session_id") and saved.get("device_token"):
                pairing = saved
                return pairing
        except (OSError, ValueError):
            pass
        if not code:
            return None
        pairing = request("/api/pairing/join", "POST", {
            "code": code, "device_name": "NOX Windows Companion"
        })
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps(pairing), encoding="utf-8")
        try:
            os.chmod(config, 0o600)
        except OSError:
            pass
        print("NOX pairing complete; credentials saved locally.")
        return pairing

    def run_command(command):
        raw = command.strip()
        if not raw or len(raw) > 1000:
            return {"status": "rejected", "message": "Empty or oversized command."}
        if execute_home_assistant_command is not None:
            ha_result = execute_home_assistant_command(raw)
            if ha_result is not None:
                return ha_result

        security_result = handle_security_command(raw)
        if security_result is not None:
            return security_result

        search = re.match(r"^(?:please\s+)?(?:search(?:\s+the\s+web)?(?:\s+for)?|google par|google|find online|internet par)\s+(.+?)(?:\s+(?:on|using)\s+(google|youtube|bing))?$", raw, re.I)
        if search:
            query = re.sub(r"^(?:par|for)\s+", "", search.group(1).strip(), flags=re.I)
            query = re.sub(r"\s+(?:search\s*)?(?:karo|kar do|please)$", "", query, flags=re.I).strip()
            engine = (search.group(2) or "google").lower()
            base = {"google":"https://www.google.com/search?q=", "youtube":"https://www.youtube.com/results?search_query=", "bing":"https://www.bing.com/search?q="}[engine]
            opened = webbrowser.open(base + urllib.parse.quote_plus(query), new=2)
            return {"status":"launch_requested" if opened else "error","message":"Search opened for " + query if opened else "Could not open search"}
        target = re.sub(r"^(?:please\s+)?(?:open|launch|start|visit|go to|khol|kholo|khul|chalao|chalu karo|खोलो|खोल|चलाओ)\s+", "", raw, flags=re.I).strip()
        target = re.sub(r"\s+(?:please|khol|kholo|open|launch|खोलो|खोल)$", "", target, flags=re.I).strip()
        target = re.sub(r"^(?:app|application)\s+", "", target, flags=re.I).strip()
        key = target.casefold()
        if key in DESTINATIONS:
            opened = webbrowser.open(DESTINATIONS[key], new=2, autoraise=True)
            return {"status":"launch_requested" if opened else "error","message":"Opened " + target if opened else "Browser did not open " + target}
        if re.match(r"^https?://", target, re.I):
            from urllib.parse import urlsplit
            parsed = urlsplit(target)
            if parsed.scheme not in ("http","https") or not parsed.hostname or parsed.username or parsed.password:
                return {"status":"rejected","message":"Only valid HTTP(S) URLs are supported."}
            opened = webbrowser.open(target, new=2, autoraise=True)
            return {"status":"launch_requested" if opened else "error","message":"Opened " + parsed.hostname if opened else "Browser did not open URL"}
        if os.name != "nt":
            return {"status":"unsupported","message":"Installed-app launch is supported on Windows only."}
        q = re.sub(r"[^a-z0-9]", "", target.casefold())
        q = {"vscode":"visualstudiocode","code":"visualstudiocode","chrome":"googlechrome","edge":"microsoftedge","explorer":"fileexplorer","calc":"calculator"}.get(q,q)
        matches = [app for app in discover_apps() if (lambda name: name == q or name.startswith(q) or q.startswith(name))(re.sub(r"[^a-z0-9]", "", app["name"].casefold()))]
        if len(matches) != 1:
            return {"status":"needs_choice" if matches else "not_found","message":("Multiple apps match; use a more specific name. " if matches else "No Start Menu shortcut matched: ") + target,"matches":[x["name"] for x in matches[:10]]}
        shortcut = find_shortcut(matches[0]["id"])
        if not shortcut:
            return {"status":"not_found","message":"App shortcut not found; retry after refreshing."}
        try:
            os.startfile(str(shortcut))
        except OSError as exc:
            return {"status":"error","message":"Windows could not launch app: " + str(exc)}
        return {"status":"launch_requested","message":"Launch requested for " + shortcut.stem}

    while True:
        try:
            active = join()
            if active:
                sid = urllib.parse.quote(active["session_id"], safe="")
                token = active["device_token"]
                request("/api/pairing/status?session_id=" + sid, token=token)
                item = request("/api/pairing/commands/next?session_id=" + sid, token=token).get("command")
                if item:
                    result = run_command(item.get("command", ""))
                    request("/api/pairing/commands/" + urllib.parse.quote(item["command_id"], safe="") + "/result?result=" + urllib.parse.quote(json.dumps(result), safe=""), "POST", token=token)
                    print("NOX paired command:", result.get("status"), result.get("message"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401,403,404):
                print("NOX pairing requires attention; re-pair if the token/session was revoked:", exc)
                pairing = None
            else:
                print("NOX relay temporarily unavailable; reconnecting:", exc)
        except Exception as exc:
            print("NOX relay temporarily unavailable; reconnecting:", exc)
        time.sleep(5)




if __name__ == "__main__":
    import threading
    import uvicorn
    if not TOKEN:
        raise SystemExit("Set NOX_COMPANION_TOKEN to a long random secret before running.")
    print(f"Starting NOX local companion on http://{HOST}:{PORT}")
    print("Loopback-only local API. The paired relay supports only app opening and web search.")
    threading.Thread(target=pairing_worker, daemon=True, name="nox-pairing-relay").start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
