"""Authorized local device discovery and Android ADB actions for the NOX Windows companion.

Only invokes ADB through fixed argument arrays (never a shell). Android must have
USB debugging enabled and the device owner must approve this computer's RSA key.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Callable, Any

from emergency_state import EmergencyStopActive, run_managed_process

_SERIAL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$")


def _adb_executable(adb_path: str | None = None) -> str | None:
    candidate = (adb_path or os.getenv("NOX_ADB_PATH", "")).strip()
    if candidate:
        return candidate
    return shutil.which("adb")


def _managed_adb_runner(args, **kwargs):
    return run_managed_process(args, timeout=int(kwargs.get("timeout", 15)))


def discover_adb_devices(
    adb_path: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict:
    """Enumerate ADB devices and report authorization state without changing them."""
    adb = _adb_executable(adb_path)
    if not adb:
        return {
            "status": "setup_required",
            "devices": [],
            "error": "Android Platform Tools (adb) were not found. Install them or set NOX_ADB_PATH.",
            "capabilities": {"adb_usb_discovery": False, "android_app_launch": False, "file_transfer": False},
        }
    try:
        result = runner(
            [adb, "devices", "-l"], shell=False, capture_output=True, text=True,
            timeout=8, check=False, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "devices": [], "error": "ADB device discovery timed out.",
                "capabilities": {"adb_usb_discovery": True, "android_app_launch": False, "file_transfer": False}}
    except OSError:
        return {"status": "error", "devices": [], "error": "ADB could not be started. Check the installation and permissions.",
                "capabilities": {"adb_usb_discovery": False, "android_app_launch": False, "file_transfer": False}}
    if result.returncode != 0:
        return {"status": "error", "devices": [], "error": "ADB returned an error while listing devices.",
                "capabilities": {"adb_usb_discovery": True, "android_app_launch": False, "file_transfer": False}}
    devices = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of devices attached"):
            continue
        parts = line.split()
        if len(parts) < 2 or not _SERIAL_RE.fullmatch(parts[0]):
            continue
        serial, state = parts[0], parts[1]
        metadata = {}
        for item in parts[2:]:
            if ":" in item:
                key, value = item.split(":", 1)
                metadata[key] = value.replace("_", " ")
        authorized = state == "device"
        devices.append({
            "id": serial,
            "name": metadata.get("model") or metadata.get("product") or "Android device",
            "type": "android",
            "os": "Android",
            "connection": "adb_usb" if ":" not in serial else "adb_network",
            "state": state,
            "authorized": authorized,
            "capabilities": {
                "diagnostics": authorized,
                "app_launch": authorized,
                "file_transfer": authorized,
                "screen_capture": authorized,
                "general_ui_automation": False,
            },
            "limitations": [] if authorized else [
                "On the phone, unlock it and approve the USB debugging authorization prompt.",
                "If state is offline, reconnect the cable and check the ADB driver."
            ],
        })
    return {
        "status": "ok",
        "devices": devices,
        "count": len(devices),
        "capabilities": {
            "adb_usb_discovery": True,
            "android_app_launch": any(d["authorized"] for d in devices),
            "file_transfer": False,
            "screen_capture": False,
            "bluetooth_discovery": False,
            "ios_control": False,
        },
        "note": "Only ADB-authorized Android devices are controllable. Capability flags describe implemented endpoints, not hardware guarantees.",
    }


def launch_android_app(
    serial: str,
    package_name: str,
    confirmed: bool,
    adb_path: str | None = None,
    runner: Callable[..., Any] | None = None,
) -> dict:
    """Launch an installed Android app via an authorized ADB connection."""
    if not confirmed:
        raise ValueError("User confirmation is required before launching an app.")
    if not _SERIAL_RE.fullmatch(serial or ""):
        raise ValueError("Invalid ADB device identifier.")
    if not _PACKAGE_RE.fullmatch(package_name or ""):
        raise ValueError("Provide a valid Android package name, such as com.example.app.")
    adb = _adb_executable(adb_path)
    if not adb:
        raise RuntimeError("ADB was not found. Install Android Platform Tools or set NOX_ADB_PATH.")
    # Keep the read-only discovery probe separate; only the mutating launch
    # process is registered for Emergency Stop cancellation by default.
    discovery = discover_adb_devices(adb, runner=runner or subprocess.run)
    device = next((item for item in discovery.get("devices", []) if item["id"] == serial), None)
    if device is None:
        raise RuntimeError("The selected Android device is not connected. Refresh device discovery.")
    if device["state"] == "unauthorized":
        raise PermissionError("Android debugging is unauthorized. Unlock the phone and approve this computer.")
    if device["state"] != "device" or not device["authorized"]:
        raise RuntimeError(f"Android device is not ready (ADB state: {device['state']}). Reconnect it and retry.")
    try:
        launch_runner = runner or _managed_adb_runner
        if runner is None:
            result = launch_runner(
                [adb, "-s", serial, "shell", "monkey", "-p", package_name,
                 "-c", "android.intent.category.LAUNCHER", "1"], timeout=15,
            )
        else:
            result = launch_runner(
                [adb, "-s", serial, "shell", "monkey", "-p", package_name,
                 "-c", "android.intent.category.LAUNCHER", "1"],
                shell=False, capture_output=True, text=True, timeout=15, check=False,
                stdin=subprocess.DEVNULL,
            )
    except EmergencyStopActive:
        raise
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("Android app launch timed out; check the phone before retrying.") from exc
    except OSError as exc:
        raise RuntimeError("ADB could not execute the launch request.") from exc
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).lower()
    if result.returncode != 0 or "no activities found" in output or "error:" in output:
        raise RuntimeError("Android did not accept the app launch. Check the package name and whether the app is installed.")
    # A successful monkey exit only confirms that Android accepted the request; it does not prove
    # the app is foreground. Never report a verified launch based on that alone.
    return {
        "status": "launch_requested_not_verified",
        "device_id": serial,
        "package_name": package_name,
        "message": "Android accepted the launch request. Verify the app is open on the phone.",
        "verified": False,
    }
