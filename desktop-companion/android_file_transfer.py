"""Permissioned Android file listing and pull operations for the NOX local companion.

Only reads files from a small, explicit shared-storage allowlist. It never accepts
an arbitrary host destination, uses fixed ADB argv, and requires confirmation to pull.
"""
from __future__ import annotations

import hmac
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from device_control import _adb_executable, discover_adb_devices

router = APIRouter(prefix="/v1/devices/android", tags=["android-file-transfer"])
TOKEN = os.getenv("NOX_COMPANION_TOKEN", "").strip()
_SERIAL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_ALLOWED_DIRS = {
    "Download": "/sdcard/Download",
    "DCIM": "/sdcard/DCIM",
    "Pictures": "/sdcard/Pictures",
    "Documents": "/sdcard/Documents",
}
_ALLOWED_PATH_RE = re.compile(r"^/sdcard/(?:Download|DCIM|Pictures|Documents)/[A-Za-z0-9._/-]{1,240}$")


class PullRequest(BaseModel):
    serial: str = Field(min_length=1, max_length=128)
    remote_path: str = Field(min_length=1, max_length=256)
    confirmed: bool = False


def _authorize(token: str | None) -> None:
    if not TOKEN:
        raise HTTPException(status_code=503, detail="Set NOX_COMPANION_TOKEN before starting the companion.")
    if not token or not hmac.compare_digest(token, TOKEN):
        raise HTTPException(status_code=401, detail="Invalid companion token.")


def _require_authorized_device(serial: str) -> str:
    if not _SERIAL_RE.fullmatch(serial or ""):
        raise HTTPException(status_code=400, detail="Invalid ADB device identifier.")
    adb = _adb_executable()
    if not adb:
        raise HTTPException(status_code=503, detail="ADB was not found. Install Android Platform Tools or set NOX_ADB_PATH.")
    discovery = discover_adb_devices(adb)
    device = next((item for item in discovery.get("devices", []) if item.get("id") == serial), None)
    if not device:
        raise HTTPException(status_code=404, detail="The selected Android device is not connected.")
    if device.get("state") == "unauthorized":
        raise HTTPException(status_code=403, detail="Unlock the phone and approve its USB debugging prompt.")
    if device.get("state") != "device" or not device.get("authorized"):
        raise HTTPException(status_code=409, detail="Android device is not ready. Reconnect it and retry.")
    return adb


def _run_adb(adb: str, serial: str, args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [adb, "-s", serial, *args], shell=False, capture_output=True,
            text=True, timeout=timeout, check=False, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="ADB file operation timed out.") from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="ADB could not be started.") from exc


@router.get("/files")
def list_android_files(
    directory: Literal["Download", "DCIM", "Pictures", "Documents"] = Query(default="Download"),
    serial: str = Query(min_length=1, max_length=128),
    x_nox_token: str | None = Header(default=None),
):
    """List only regular files directly inside an allowlisted shared-storage directory."""
    _authorize(x_nox_token)
    adb = _require_authorized_device(serial)
    remote_dir = _ALLOWED_DIRS[directory]
    result = _run_adb(adb, serial, ["shell", "ls", "-1", remote_dir], timeout=10)
    if result.returncode != 0:
        raise HTTPException(status_code=502, detail="Android could not list that shared-storage folder.")
    names = []
    for line in (result.stdout or "").splitlines():
        name = line.strip()
        if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
            continue
        if name.startswith(".") or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,179}", name):
            continue
        names.append({"name": name, "path": remote_dir + "/" + name})
    return {
        "status": "ok",
        "serial": serial,
        "directory": directory,
        "files": names[:500],
        "truncated": len(names) > 500,
        "note": "Only top-level names from the selected shared-storage directory are listed; app-private data is not accessible.",
    }


@router.post("/pull")
def pull_android_file(payload: PullRequest, x_nox_token: str | None = Header(default=None)):
    """Copy one explicitly confirmed file into the current user's NOX transfer folder."""
    _authorize(x_nox_token)
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required before copying a phone file.")
    remote = payload.remote_path
    if (not _ALLOWED_PATH_RE.fullmatch(remote) or "/../" in remote or remote.endswith("/..")
            or remote.rsplit("/", 1)[-1] in {"", ".", ".."}):
        raise HTTPException(status_code=400, detail="Choose a file directly under Download, DCIM, Pictures, or Documents.")
    adb = _require_authorized_device(payload.serial)
    check = _run_adb(adb, payload.serial, ["shell", "test", "-f", remote], timeout=8)
    if check.returncode != 0:
        raise HTTPException(status_code=404, detail="The selected path is not a readable regular file.")
    transfer_dir = Path.home() / "Downloads" / "NOX-Device-Transfers"
    try:
        transfer_dir.mkdir(parents=True, exist_ok=True)
        # A timestamped name prevents silently overwriting an existing local file.
        name = remote.rsplit("/", 1)[-1]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = transfer_dir / f"{stamp}_{name}"
        result = _run_adb(adb, payload.serial, ["pull", remote, str(destination)], timeout=60)
        if result.returncode != 0 or not destination.is_file():
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
            raise HTTPException(status_code=502, detail="Android file transfer failed; no successful copy was confirmed.")
        size = destination.stat().st_size
    except HTTPException:
        raise
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not save the file in the NOX transfer folder.") from exc
    return {
        "status": "copied",
        "serial": payload.serial,
        "remote_path": remote,
        "local_path": str(destination),
        "size_bytes": size,
        "verified": True,
        "message": "File was copied to the Windows NOX-Device-Transfers folder.",
    }
