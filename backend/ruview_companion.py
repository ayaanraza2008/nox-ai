"""Opt-in, loopback-only adapter for the official RuView CLI.

Only fixed, allow-listed RuView operations are invoked. No HTTP input is treated as
shell text or executable arguments. Disabled by default; intended for a NOX instance
running on the same computer as the optional RuView installation.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(os.getenv("NOX_RUVIEW_PACKAGE_DIR", str(ROOT / "ruview-companion"))).resolve()
CLI_ENTRY = PACKAGE_DIR / "node_modules" / "@ruvnet" / "ruview" / "bin" / "cli.js"
MAX_OUTPUT = 8000
INSPECTION_TIMEOUT_SECONDS = 18
CAPTURE_SECONDS = 45


class RuViewUnavailable(RuntimeError):
    """RuView is disabled, not installed, or cannot be started."""


def enabled() -> bool:
    return os.getenv("NOX_RUVIEW_ENABLED", "").strip() == "1"


def status() -> dict[str, Any]:
    node = shutil.which("node")
    installed = bool(node and CLI_ENTRY.is_file())
    return {
        "enabled": enabled(),
        "installed": installed,
        "available": enabled() and installed,
        "package": "@ruvnet/ruview",
        "version": "0.9.2",
        "operations": ["doctor", "devices", "capture_start", "capture_stop"] if enabled() and installed else [],
        "message": (
            "RuView CLI is installed and locally enabled."
            if enabled() and installed else
            "Set NOX_RUVIEW_ENABLED=1 and install the pinned local RuView companion package."
            if not enabled() else
            "RuView CLI was not found at ruview-companion/node_modules/@ruvnet/ruview/bin/cli.js."
        ),
        "hardware_note": "Live CSI capture requires a compatible, configured RuView CSI source; ordinary browser Wi-Fi readings are not CSI.",
    }


class RuViewRunner:
    """Single bounded capture process plus bounded one-shot diagnostics."""

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._collector: asyncio.Task | None = None
        self._last_output = ""
        self._last_exit_code: int | None = None
        self._operation = "idle"

    def snapshot(self) -> dict[str, Any]:
        running = self._process is not None and self._process.returncode is None
        return {
            **status(),
            "running": running,
            "operation": self._operation if running else "idle",
            "last_output": self._last_output[-MAX_OUTPUT:],
            "last_exit_code": self._last_exit_code,
        }

    def _command(self, operation: str) -> list[str]:
        node = shutil.which("node")
        if not node or not CLI_ENTRY.is_file():
            raise RuViewUnavailable("RuView CLI is not installed. See the local companion installation instructions.")
        if operation == "doctor":
            args = ["doctor"]
        elif operation == "devices":
            args = ["devices"]
        elif operation == "capture":
            args = ["esp32", "--seconds", str(CAPTURE_SECONDS), "--analyze"]
        else:
            raise RuViewUnavailable("Unsupported RuView operation.")
        return [node, str(CLI_ENTRY), *args]

    async def inspect(self, operation: str) -> dict[str, Any]:
        if not enabled():
            raise RuViewUnavailable("RuView integration is disabled. Enable it only on a trusted local machine.")
        if operation not in {"doctor", "devices"}:
            raise RuViewUnavailable("Unsupported inspection operation.")
        command = self._command(operation)
        try:
            proc = await asyncio.create_subprocess_exec(
                *command, cwd=str(PACKAGE_DIR), stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                output, _ = await asyncio.wait_for(proc.communicate(), timeout=INSPECTION_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise RuViewUnavailable("RuView inspection timed out and was stopped.")
        except FileNotFoundError as exc:
            raise RuViewUnavailable("Node.js or the RuView CLI entry point could not be started.") from exc
        self._last_output = output.decode("utf-8", errors="replace")[-MAX_OUTPUT:]
        self._last_exit_code = proc.returncode
        self._operation = operation
        return {
            "operation": operation,
            "exit_code": proc.returncode,
            "success": proc.returncode == 0,
            "output": self._last_output,
            "evidence": "ruview_cli_output",
            "limitations": ["Diagnostics are local CLI output, not proof that sensing accuracy is validated."],
        }

    async def start_capture(self) -> dict[str, Any]:
        if not enabled():
            raise RuViewUnavailable("RuView integration is disabled. Enable it only on a trusted local machine.")
        if self._process is not None and self._process.returncode is None:
            return {"started": False, "running": True, "message": "A RuView capture is already running."}
        command = self._command("capture")
        try:
            self._process = await asyncio.create_subprocess_exec(
                *command, cwd=str(PACKAGE_DIR), stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError as exc:
            self._process = None
            raise RuViewUnavailable("Node.js or the RuView CLI entry point could not be started.") from exc
        self._last_output = ""
        self._last_exit_code = None
        self._operation = "capture"
        self._collector = asyncio.create_task(self._collect_output(self._process))
        return {
            "started": True,
            "running": True,
            "operation": "capture",
            "duration_seconds": CAPTURE_SECONDS,
            "message": "Started a bounded, receive-only RuView ESP32 CSI capture. Stop is available at any time.",
            "source": "RuView ESP32 CSI pipeline",
            "measurements": "Pending CLI output; no measurements are invented by NOX.",
        }

    async def _collect_output(self, proc: asyncio.subprocess.Process) -> None:
        try:
            output, _ = await proc.communicate()
            self._last_output = output.decode("utf-8", errors="replace")[-MAX_OUTPUT:]
            self._last_exit_code = proc.returncode
        except Exception as exc:
            self._last_output = ("Could not collect RuView output: " + str(exc))[-MAX_OUTPUT:]
        finally:
            if self._process is proc:
                self._process = None
            self._operation = "idle"

    async def stop_capture(self) -> dict[str, Any]:
        proc = self._process
        if proc is None or proc.returncode is not None:
            return {"stopped": False, "running": False, "message": "No RuView capture is running."}
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        if self._collector is not None:
            try:
                await asyncio.wait_for(self._collector, timeout=3)
            except asyncio.TimeoutError:
                self._collector.cancel()
        return {"stopped": True, "running": False, "message": "RuView capture process stopped."}


runner = RuViewRunner()
