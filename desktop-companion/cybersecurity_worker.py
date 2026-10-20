"""Local-only defensive security tool adapters for NOX Companion.
No arbitrary shell is exposed. Active scans require explicit confirmation, a scope
note, and a private/local lab target or exact allowlist entry.
"""
from __future__ import annotations
import ipaddress
import os
import re
import shutil
import subprocess
import time
from typing import Any

MAX_OUTPUT_CHARS = 12_000
SCAN_TIMEOUT_SECONDS = 45
CONFIRMATION = "I OWN OR AM AUTHORIZED TO TEST THIS TARGET"
TOOLS = {
    "nmap": {"binary": "nmap", "version_args": ["--version"], "purpose": "Conservative lab service discovery"},
    "semgrep": {"binary": "semgrep", "version_args": ["--version"], "purpose": "Static code analysis"},
    "trivy": {"binary": "trivy", "version_args": ["--version"], "purpose": "Dependency and container vulnerability scanning"},
    "tshark": {"binary": "tshark", "version_args": ["--version"], "purpose": "Authorized packet-capture analysis"},
    "zaproxy": {"binary": "zaproxy", "version_args": None, "purpose": "Web security testing proxy"},
    "ollama": {"binary": "ollama", "version_args": ["--version"], "purpose": "Local model runtime"},
    "kaligpt": {"binary": "kaligpt", "version_args": ["--version"], "purpose": "Optional upstream CLI; arbitrary-command mode is never called by this adapter"},
}
class CybersecurityError(ValueError):
    pass

def _is_local_lab_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    ranges = (
        ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16")
        if address.version == 4 else ("fc00::/7", "::1/128", "fe80::/10")
    )
    return any(address in ipaddress.ip_network(network) for network in ranges)

def discover_tools() -> list[dict[str, Any]]:
    """Detect tools and probe versions only with fixed, bounded version arguments."""
    results = []
    for name, spec in TOOLS.items():
        path = shutil.which(spec["binary"])
        version = None
        version_status = "not installed"
        if path and spec.get("version_args"):
            try:
                probe = subprocess.run(
                    [path, *spec["version_args"]],
                    shell=False, stdin=subprocess.DEVNULL, capture_output=True,
                    text=True, timeout=2, check=False,
                )
                output = (probe.stdout or probe.stderr or "").strip().splitlines()
                version = output[0][:160] if output else None
                version_status = "probed" if probe.returncode == 0 and version else "probe failed"
            except subprocess.TimeoutExpired:
                version_status = "probe timed out"
            except OSError:
                version_status = "probe failed"
        elif path:
            version_status = "not probed; version flag may launch a GUI or interactive process"
        results.append({
            "name": name, "available": bool(path), "path": path, "purpose": spec["purpose"],
            "version": version, "version_status": version_status,
        })
    return results

def validate_target(target: str, authorized: bool, scope_note: str) -> tuple[str, str]:
    if not authorized:
        raise CybersecurityError("Explicit authorization confirmation is required.")
    if not isinstance(scope_note, str) or len(scope_note.strip()) < 10:
        raise CybersecurityError("Describe the authorized scope in at least 10 characters.")
    if not isinstance(target, str) or not target.strip() or len(target) > 253:
        raise CybersecurityError("Enter one host or IP address.")
    host = target.strip().casefold().rstrip(".")
    if "://" in host or "/" in host or any(ch.isspace() for ch in host):
        raise CybersecurityError("Use a single host/IP, not a URL, path, or command.")
    try:
        address = ipaddress.ip_address(host)
        if not _is_local_lab_ip(address):
            allowed = {v.strip().casefold().rstrip(".") for v in os.getenv("NOX_CYBER_ALLOWED_HOSTS", "").split(",") if v.strip()}
            if host not in allowed:
                raise CybersecurityError("Public IP targets require an exact NOX_CYBER_ALLOWED_HOSTS entry.")
        return host, "private_or_local_ip" if _is_local_lab_ip(address) else "explicit_allowlist"
    except ValueError as exc:
        if isinstance(exc, CybersecurityError):
            raise
    if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*", host):
        raise CybersecurityError("Target hostname is invalid.")
    local_lab = host == "localhost" or host.endswith((".localhost", ".test", ".lab", ".invalid", ".example"))
    allowed = {v.strip().casefold().rstrip(".") for v in os.getenv("NOX_CYBER_ALLOWED_HOSTS", "").split(",") if v.strip()}
    if not local_lab and host not in allowed:
        raise CybersecurityError("Only local lab names or exact NOX_CYBER_ALLOWED_HOSTS entries are allowed.")
    return host, "local_lab" if local_lab else "explicit_allowlist"

def scan_services(target: str, *, authorized: bool, scope_note: str, confirmation: str, cancel_event=None) -> dict[str, Any]:
    """Run bounded Nmap service discovery with shell disabled."""
    host, target_class = validate_target(target, authorized, scope_note)
    if confirmation != CONFIRMATION:
        raise CybersecurityError("Type the exact authorization confirmation before starting a scan.")
    binary = shutil.which("nmap")
    if not binary:
        return {"status": "unavailable", "tool": "nmap",
                "message": "Nmap is not installed on this local companion. Install it from its official distribution source, then restart NOX Companion."}
    command = [binary, "-sV", "--top-ports", "100", "-T2", "--host-timeout", "35s", host]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, shell=False)
    started = time.monotonic()
    try:
        while process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
                return {"status": "cancelled", "tool": "nmap", "target": host, "message": "Scan cancelled by user."}
            if time.monotonic() - started > SCAN_TIMEOUT_SECONDS:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
                return {"status": "timeout", "tool": "nmap", "target": host, "message": "Scan exceeded the 45-second limit."}
            time.sleep(0.1)
        stdout, stderr = process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return {"status": "timeout", "tool": "nmap", "target": host, "message": "Scan exceeded the output collection timeout."}
    stdout = stdout or ""
    stderr = stderr or ""
    return {"status": "success" if process.returncode == 0 else "error", "tool": "nmap",
            "target": host, "target_class": target_class,
            "command": ["nmap", "-sV", "--top-ports", "100", "-T2", "--host-timeout", "35s", "<validated-target>"],
            "return_code": process.returncode, "stdout": stdout[:MAX_OUTPUT_CHARS], "stderr": stderr[:2000],
            "output_truncated": len(stdout) > MAX_OUTPUT_CHARS, "duration_limit_seconds": SCAN_TIMEOUT_SECONDS,
            "scope_note": scope_note.strip()[:500],
            "warning": "Service discovery is active network traffic. Run only on the explicitly authorized target."}
