"""Permissioned local Windows companion for NOX AI.

Discovers apps from Windows Start Menu shortcuts. Only an explicit, confirmed,
token-authenticated request can launch one discovered shortcut. No arbitrary shell.
"""
import hashlib
import hmac
import os
import re
import subprocess

import httpx
import webbrowser
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from device_control import discover_adb_devices, launch_android_app
from emergency_state import get_state as get_emergency_state, set_stopped as set_emergency_stopped

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
RUVIEW_API_TOKEN = os.getenv("RUVIEW_API_TOKEN", "").strip()
RUVIEW_LOCAL_URL = "http://127.0.0.1:3000"

app = FastAPI(title="NOX Local Desktop Companion", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[WEB_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-NOX-Token"],
)

@app.middleware("http")
async def enforce_local_emergency_stop(request: Request, call_next):
    """Fail closed for every mutating companion endpoint while locally stopped."""
    exempt = {"/v1/emergency/stop", "/v1/emergency/resume"}
    if request.method == "POST" and request.url.path not in exempt:
        supplied = request.headers.get("X-NOX-Token", "")
        if not TOKEN or not hmac.compare_digest(supplied, TOKEN):
            return JSONResponse(status_code=401, content={"detail": "Invalid companion token."})
        if get_emergency_state()["stopped"]:
            return JSONResponse(status_code=423, content={
                "detail": "Local NOX Emergency Stop is latched. Explicitly resume the companion first."
            })
    return await call_next(request)


@app.on_event("startup")
async def start_optional_windows_tray():
    try:
        from tray_controller import start_tray
        start_tray()
    except Exception as exc:
        # The API remains usable if the optional Windows tray dependencies are absent.
        import logging
        logging.getLogger("nox.companion").warning("Tray controller unavailable (%s)", type(exc).__name__)


@app.get("/v1/emergency/status")
def local_emergency_status(x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    return get_emergency_state()


@app.post("/v1/emergency/stop")
def local_emergency_stop(x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    return {"state": "stopped", **set_emergency_stopped(True, "local_emergency_stop")}


@app.post("/v1/emergency/resume")
def local_emergency_resume(x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    return {"state": "running", **set_emergency_stopped(False, "explicit_local_resume")}


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


class AndroidLaunchRequest(BaseModel):
    serial: str = Field(min_length=1, max_length=128)
    package_name: str = Field(min_length=3, max_length=255)
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


def read_windows_wifi_status():
    """Read current Windows Wi-Fi interface status using a fixed, read-only command."""
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="Wi-Fi inspection is currently supported on Windows only.")
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            shell=False, capture_output=True, text=True, timeout=8,
            check=False, stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=501, detail="Windows netsh is unavailable.") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Windows Wi-Fi status query timed out.") from exc
    if result.returncode != 0:
        raise HTTPException(status_code=503, detail="Windows could not read Wi-Fi interface status.")
    raw = result.stdout or ""
    # Localized Windows output may not match these English field labels; unknown stays null.
    patterns = {
        "state": r"^\s*State\s*:\s*(.+?)\s*$",
        "ssid": r"^\s*SSID\s*:\s*(.*?)\s*$",
        "bssid": r"^\s*BSSID\s*:\s*([0-9a-fA-F:.-]+)\s*$",
        "radio_type": r"^\s*Radio type\s*:\s*(.*?)\s*$",
        "channel": r"^\s*Channel\s*:\s*(\d+)\s*$",
        "signal_percent": r"^\s*Signal\s*:\s*(\d+)\s*%\s*$",
        "receive_mbps": r"^\s*Receive rate \(Mbps\)\s*:\s*([0-9.]+)\s*$",
        "transmit_mbps": r"^\s*Transmit rate \(Mbps\)\s*:\s*([0-9.]+)\s*$",
        "authentication": r"^\s*Authentication\s*:\s*(.*?)\s*$",
        "cipher": r"^\s*Cipher\s*:\s*(.*?)\s*$",
    }
    parsed = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, raw, re.MULTILINE | re.IGNORECASE)
        parsed[key] = match.group(1).strip() if match else None
    state = (parsed.get("state") or "").casefold()
    connected = state == "connected"
    if parsed.get("signal_percent") is not None:
        parsed["signal_percent"] = int(parsed["signal_percent"])
    if parsed.get("channel") is not None:
        parsed["channel"] = int(parsed["channel"])
    for key in ("receive_mbps", "transmit_mbps"):
        if parsed.get(key) is not None:
            parsed[key] = float(parsed[key])
    return {
        "platform": "windows",
        "status": "connected" if connected else ("disconnected" if state else "unknown"),
        "connected": connected,
        "ssid": parsed.get("ssid") if connected else None,
        "bssid": parsed.get("bssid") if connected else None,
        "radio_type": parsed.get("radio_type") if connected else None,
        "channel": parsed.get("channel") if connected else None,
        "signal_percent": parsed.get("signal_percent") if connected else None,
        "receive_mbps": parsed.get("receive_mbps") if connected else None,
        "transmit_mbps": parsed.get("transmit_mbps") if connected else None,
        "authentication": parsed.get("authentication") if connected else None,
        "cipher": parsed.get("cipher") if connected else None,
        "source": "Windows netsh wlan show interfaces",
        "measured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "raw_output_exposed": False,
        "note": "Interface metrics only; not CSI sensing or a security certification.",
    }


@app.get("/v1/connectivity/capabilities")
def connectivity_capabilities(x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    return {
        "platform": "windows" if os.name == "nt" else os.name,
        "wifi_status": os.name == "nt",
        "wifi_method": "netsh wlan show interfaces" if os.name == "nt" else None,
        "ruview_proxy": bool(RUVIEW_API_TOKEN),
        "bluetooth_discovery": False,
        "note": "Capabilities are conservative; Wi-Fi CSI requires a separately installed and configured RuView service and compatible data source.",
    }


@app.get("/v1/connectivity/wifi")
def connectivity_wifi(x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    return read_windows_wifi_status()


RUVIEW_PATHS = {
    "health": "/health",
    "info": "/api/v1/info",
    "sensing": "/api/v1/sensing/latest",
    "vitals": "/api/v1/vital-signs",
    "pose": "/api/v1/pose/current",
}


@app.get("/v1/connectivity/ruview")
async def connectivity_ruview(view: Literal["health", "info", "sensing", "vitals", "pose"] = "health",
                              x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    if not RUVIEW_API_TOKEN:
        raise HTTPException(status_code=503, detail="Set RUVIEW_API_TOKEN in the local companion environment to connect RuView.")
    url = RUVIEW_LOCAL_URL + RUVIEW_PATHS[view]
    try:
        async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
            response = await client.get(url, headers={"Authorization": "Bearer " + RUVIEW_API_TOKEN})
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            raise HTTPException(status_code=502, detail="RuView returned a non-JSON response.")
        return {"status": "ok", "view": view, "source": "local RuView API", "data": payload}
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Local RuView request timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"RuView returned HTTP {exc.response.status_code}.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Local RuView is not reachable at 127.0.0.1:3000.") from exc


@app.get("/v1/devices")
def list_connected_devices(x_nox_token: str | None = Header(default=None)):
    """Discover local ADB devices; never scans the LAN or pairs devices silently."""
    authorize(x_nox_token)
    result = discover_adb_devices()
    return {
        **result,
        "host_platform": "windows" if os.name == "nt" else os.name,
        "wifi_interface": "available" if os.name == "nt" else "unsupported",
        "bluetooth": {"status": "not_implemented", "reason": "No Bluetooth adapter is wired into this companion yet."},
        "ios": {"status": "not_implemented", "reason": "iOS does not expose unrestricted device control to this companion."},
    }


@app.get("/v1/devices/capabilities")
def device_control_capabilities(x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    discovered = discover_adb_devices()
    return {
        "platform": "windows" if os.name == "nt" else os.name,
        "adapters": [
            {
                "id": "android_adb",
                "status": "implemented_with_setup" if discovered.get("status") == "ok" else discovered.get("status", "setup_required"),
                "transports": ["USB", "ADB-over-network-if-the-owner-configured-it"],
                "actions": ["discover_devices", "inspect_authorization_state", "launch_installed_app"],
                "requires": ["Android Platform Tools", "USB debugging enabled by the owner", "owner approval of this computer's debugging key"],
                "limitations": ["App launch is reported as requested, not verified", "File transfer, screen capture, and general UI automation are not exposed by this prototype"],
            },
            {
                "id": "windows_wifi_status",
                "status": "implemented_with_setup" if os.name == "nt" else "unsupported",
                "actions": ["read_current_wifi_interface_status"],
                "limitations": ["Read-only interface status; not general LAN discovery"],
            },
            {"id": "bluetooth_ble", "status": "not_implemented", "actions": [], "limitations": ["No Bluetooth scanning or GATT adapter is wired in."]},
            {"id": "ios", "status": "not_implemented", "actions": [], "limitations": ["Use approved Shortcuts/App Intents integrations; no unrestricted control."]},
        ],
        "adb": discovered.get("capabilities", {}),
        "note": "All local companion routes require X-NOX-Token. No unauthenticated control port is opened.",
    }


@app.post("/v1/devices/android/launch")
def launch_android_device_app(payload: AndroidLaunchRequest, x_nox_token: str | None = Header(default=None)):
    authorize(x_nox_token)
    try:
        return launch_android_app(payload.serial, payload.package_name, payload.confirmed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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


# Commands are deliberately mapped to fixed argument lists; user text is never passed to a shell.
SAFE_TERMINAL_COMMANDS = {
    "python --version": ["python", "--version"],
    "py --version": ["py", "--version"],
    "node --version": ["node", "--version"],
    "npm --version": ["npm", "--version"],
    "git --version": ["git", "--version"],
    "git status": ["git", "status", "--short"],
    "pip --version": ["python", "-m", "pip", "--version"],
    "winget --version": ["winget", "--version"],
    "whoami": ["whoami"],
    "systeminfo": ["systeminfo"],
    "ipconfig": ["ipconfig"],
    "tasklist": ["tasklist"],
    "hostname": ["hostname"],
    "where python": ["where", "python"],
    "where node": ["where", "node"],
    "where git": ["where", "git"],
}
# Stable WinGet package IDs only; no package names or commands are interpolated into a shell.
WINGET_PACKAGES = {
    "vscode": ("Microsoft.VisualStudioCode", "Visual Studio Code"),
    "visual studio code": ("Microsoft.VisualStudioCode", "Visual Studio Code"),
    "git": ("Git.Git", "Git"),
    "python": ("Python.Python.3.12", "Python 3.12"),
    "node": ("OpenJS.NodeJS.LTS", "Node.js LTS"),
    "nodejs": ("OpenJS.NodeJS.LTS", "Node.js LTS"),
    "7zip": ("7zip.7zip", "7-Zip"),
    "7-zip": ("7zip.7zip", "7-Zip"),
    "vlc": ("VideoLAN.VLC", "VLC media player"),
    "firefox": ("Mozilla.Firefox", "Mozilla Firefox"),
    "chrome": ("Google.Chrome", "Google Chrome"),
    "obs": ("OBSProject.OBSStudio", "OBS Studio"),
    "obs studio": ("OBSProject.OBSStudio", "OBS Studio"),
    "discord": ("Discord.Discord", "Discord"),
    "steam": ("Valve.Steam", "Steam"),
    "spotify": ("Spotify.Spotify", "Spotify"),
    "zoom": ("Zoom.Zoom", "Zoom Workplace"),
    "slack": ("SlackTechnologies.Slack", "Slack"),
    "blender": ("BlenderFoundation.Blender", "Blender"),
    "gimp": ("GIMP.GIMP.3", "GIMP"),
    "libreoffice": ("TheDocumentFoundation.LibreOffice", "LibreOffice"),
    "notepad++": ("Notepad++.Notepad++", "Notepad++"),
    "docker desktop": ("Docker.DockerDesktop", "Docker Desktop"),
    "android studio": ("Google.AndroidStudio", "Android Studio"),
    "brave": ("Brave.Brave", "Brave Browser"),
    "opera": ("Opera.Opera", "Opera Browser"),
    "telegram": ("Telegram.TelegramDesktop", "Telegram Desktop"),
    "github desktop": ("GitHub.GitHubDesktop", "GitHub Desktop"),
    "powertoys": ("Microsoft.PowerToys", "Microsoft PowerToys"),
    "audacity": ("Audacity.Audacity", "Audacity"),
    "inkscape": ("Inkscape.Inkscape", "Inkscape"),
    "postman": ("Postman.Postman", "Postman"),
    "obsidian": ("Obsidian.Obsidian", "Obsidian"),
    "notion": ("Notion.Notion", "Notion"),
    "cursor": ("Anysphere.Cursor", "Cursor"),
    "intellij": ("JetBrains.IntelliJIDEA.Community", "IntelliJ IDEA Community"),
    "pycharm": ("JetBrains.PyCharm.Community", "PyCharm Community"),
}


def execute_safe_terminal_command(raw: str):
    """Run a small, fixed set of diagnostic/build commands; never invoke a shell."""
    command = raw.strip().casefold()
    args = SAFE_TERMINAL_COMMANDS.get(command)
    workspace_commands = {
        "npm install": ["npm", "install", "--no-audit", "--no-fund"],
        "npm run build": ["npm", "run", "build"],
        "npm test": ["npm", "test"],
        "python -m pytest": ["python", "-m", "pytest"],
        "npm run lint": ["npm", "run", "lint"],
        "git log -1 --oneline": ["git", "log", "-1", "--oneline"],
        "python -m compileall .": ["python", "-m", "compileall", "."],
        "dir": ["cmd", "/c", "dir"],
    }
    if args is None and command in workspace_commands:
        workspace = os.getenv("NOX_WORKSPACE_DIR", "").strip()
        if not workspace:
            return {"status": "setup_required", "message": "Set NOX_WORKSPACE_DIR to the specific project folder before running project commands."}
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir():
            return {"status": "error", "message": "Configured NOX_WORKSPACE_DIR is not an existing directory."}
        if command.startswith("npm ") and not (root / "package.json").is_file():
            return {"status": "rejected", "message": "The configured workspace has no package.json; npm command was not run."}
        if command.startswith("git ") and not (root / ".git").exists():
            return {"status": "rejected", "message": "The configured workspace is not a Git repository; git command was not run."}
        if command.startswith("python -m pytest") and not any((root / name).exists() for name in ("tests", "test")):
            return {"status": "rejected", "message": "No tests/ or test/ folder was found in the configured workspace."}
        args = workspace_commands[command]
        cwd = str(root)
    else:
        cwd = None
    if args is None:
        return None
    if os.name != "nt":
        return {"status": "unsupported", "message": "Local terminal commands are supported only on Windows in this companion."}
    try:
        completed = subprocess.run(
            args, cwd=cwd, shell=False, capture_output=True, text=True,
            timeout=180, check=False, stdin=subprocess.DEVNULL,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return {
            "status": "success" if completed.returncode == 0 else "error",
            "command": command,
            "returncode": completed.returncode,
            "output": output[-5000:] or "(no output)",
        }
    except FileNotFoundError:
        return {"status": "not_found", "message": "Required program is not installed or is not available on PATH: " + args[0]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": "Command exceeded the 180-second time limit."}
    except OSError as exc:
        return {"status": "error", "message": "Could not run approved command: " + str(exc)[:300]}


def install_known_software(raw: str):
    """Install only a known package ID through WinGet; never execute internet snippets."""
    match = re.fullmatch(r"(?:install|download and install|install software)\s+(.+)", raw.strip(), re.I)
    if not match:
        return None
    query = match.group(1).strip().casefold()
    package = WINGET_PACKAGES.get(query)
    if not package:
        search_url = "https://www.google.com/search?q=" + __import__("urllib.parse", fromlist=["quote_plus"]).quote_plus(query + " official download winget package id")
        opened = False
        try:
            opened = webbrowser.open(search_url, new=2, autoraise=True)
        except Exception:
            pass
        return {
            "status": "needs_review",
            "message": "Opened a search for the official download/package details. This package is not in NOX's verified package-ID allowlist, so NOX will not blindly execute a command copied from a web page.",
            "search_url": search_url,
            "search_opened": bool(opened),
        }
    if os.name != "nt":
        return {"status": "unsupported", "message": "Automatic software installation is currently supported on Windows only."}
    package_id, display_name = package
    try:
        completed = subprocess.run(
            ["winget", "install", "--id", package_id, "--exact", "--source", "winget",
             "--accept-source-agreements", "--accept-package-agreements"],
            shell=False, capture_output=True, text=True, timeout=900, check=False,
            stdin=subprocess.DEVNULL,
        )
        output = ((completed.stdout or "") + (completed.stderr or ""))[-5000:]
        return {
            "status": "success" if completed.returncode == 0 else "error",
            "software": display_name, "package_id": package_id,
            "returncode": completed.returncode, "output": output or "(no output)",
        }
    except FileNotFoundError:
        return {"status": "setup_required", "message": "WinGet is not installed or unavailable. Install/update Microsoft's App Installer from Microsoft Store, then retry."}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": "Installation exceeded the 15-minute time limit."}
    except OSError as exc:
        return {"status": "error", "message": "Installer could not start: " + str(exc)[:300]}


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

    def deliver_result(command_id, result, token):
        """Retry result delivery only; never rerun the user's side-effecting command."""
        encoded_id = urllib.parse.quote(command_id, safe="")
        encoded_result = urllib.parse.quote(json.dumps(result), safe="")
        path = "/api/pairing/commands/" + encoded_id + "/result?result=" + encoded_result
        for attempt in range(3):
            try:
                return request(path, "POST", token=token)
            except urllib.error.HTTPError as exc:
                # Client errors require correction/re-pairing; retry only server-side failures.
                if exc.code < 500 or attempt == 2:
                    raise
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError("Could not deliver command result after bounded retries")

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

        install_result = install_known_software(raw)
        if install_result is not None:
            return install_result

        terminal_match = re.fullmatch(r"(?:run terminal|terminal|run command)\s*:?\s*(.+)", raw, re.I)
        if terminal_match:
            terminal_result = execute_safe_terminal_command(terminal_match.group(1))
            if terminal_result is not None:
                return terminal_result
            return {"status": "rejected", "message": "That terminal command is not in NOX's safe command allowlist. Arbitrary shell commands are disabled."}

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
        if len(matches) > 1:
            return {"status":"needs_choice","message":"Multiple apps match; use a more specific name.","matches":[x["name"] for x in matches[:10]]}
        if not matches:
            from urllib.parse import quote_plus
            search_url = "https://www.google.com/search?q=" + quote_plus(target + " official Windows app download")
            try:
                opened = webbrowser.open(search_url, new=2, autoraise=True)
            except Exception:
                opened = False
            return {
                "status": "not_found",
                "message": "No matching Start Menu app was found. Opened a search for the official download so you can check whether it needs installing.",
                "search_url": search_url,
                "search_opened": bool(opened),
            }
        shortcut = find_shortcut(matches[0]["id"])
        if not shortcut:
            return {"status":"not_found","message":"App shortcut not found; retry after refreshing."}
        try:
            os.startfile(str(shortcut))
        except OSError as exc:
            return {"status":"error","message":"Windows could not launch app: " + str(exc)}
        return {"status":"launch_requested","message":"Launch requested for " + shortcut.stem}

    while True:
        if get_emergency_state()["stopped"]:
            time.sleep(1)
            continue
        try:
            active = join()
            if active:
                sid = urllib.parse.quote(active["session_id"], safe="")
                token = active["device_token"]
                request("/api/pairing/status?session_id=" + sid, token=token)
                item = request("/api/pairing/commands/next?session_id=" + sid, token=token).get("command")
                if item:
                    if get_emergency_state()["stopped"]:
                        deliver_result(item["command_id"], {
                            "status": "cancelled",
                            "message": "Emergency Stop latched before command execution."
                        }, token)
                        continue
                    result = run_command(item.get("command", ""))
                    # The command has already run. Retry only reporting its result; never re-execute it
                    # if the network fails, since installs and other actions may have side effects.
                    deliver_result(item["command_id"], result, token)
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
