"""Defensive, bounded cybersecurity helpers for NOX.
This module intentionally never invokes KaliGPT's arbitrary-command tool from the hosted API.
"""
from __future__ import annotations
import ipaddress
import os
import platform
import re
import shutil
from collections import Counter
from typing import Any
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/cybersecurity", tags=["cybersecurity"])
MAX_SOURCE_CHARS = 50_000
MAX_LOG_CHARS = 100_000
MAX_LINES = 2_000
ALLOWED_TOOLS = {
    "nmap": ("nmap", "--version"),
    "owasp_zap": ("zaproxy", "--version"),
    "semgrep": ("semgrep", "--version"),
    "trivy": ("trivy", "--version"),
    "tshark": ("tshark", "--version"),
    "wireshark": ("wireshark", "--version"),
    "git": ("git", "--version"),
    "ollama": ("ollama", "--version"),
    "kaligpt": ("kaligpt", "--version"),
}
CODE_RULES = [
    ("HIGH", "dynamic-eval", re.compile(r"\b(?:eval|exec)\s*\("), "Avoid evaluating untrusted input; use a constrained parser or explicit dispatch."),
    ("HIGH", "shell-true", re.compile(r"\bshell\s*=\s*True\b"), "Use a fixed executable with an argument list; never pass model/user text to a shell."),
    ("HIGH", "unsafe-deserialization", re.compile(r"\bpickle\.(?:load|loads|Unpickler)\s*\("), "Do not deserialize untrusted pickle data."),
    ("HIGH", "tls-verification-disabled", re.compile(r"(?i)(?:verify\s*=\s*False|CERT_NONE)"), "Keep TLS certificate validation enabled."),
    ("MEDIUM", "hardcoded-secret", re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token|access[_-]?key)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"), "Move credentials to a secret manager/environment variable and rotate any exposed value."),
    ("MEDIUM", "weak-hash", re.compile(r"\bhashlib\.(?:md5|sha1)\s*\("), "Use a modern hash for integrity; use a password-hashing scheme for passwords."),
    ("MEDIUM", "unsafe-yaml", re.compile(r"\byaml\.load\s*\("), "Use yaml.safe_load for untrusted YAML where possible."),
    ("MEDIUM", "sql-string-format", re.compile(r"(?i)\b(?:execute|executemany)\s*\(\s*f['\"]"), "Use parameterized SQL queries instead of string interpolation."),
    ("LOW", "debug-mode", re.compile(r"\bdebug\s*=\s*True\b"), "Disable debug mode in production."),
]
LOG_PATTERNS = [
    ("HIGH", "repeated-auth-failure", re.compile(r"(?i)(?:failed|invalid|denied).{0,50}(?:login|password|authentication|credential)")),
    ("MEDIUM", "privilege-denied", re.compile(r"(?i)(?:permission denied|access denied|sudo:.*authentication failure)")),
    ("MEDIUM", "service-error", re.compile(r"(?i)\b(?:panic|fatal error|segmentation fault|traceback)\b")),
    ("LOW", "rate-limit", re.compile(r"(?i)(?:too many requests|rate.?limit|http.?429)")),
]

class CodeReviewRequest(BaseModel):
    source: str = Field(min_length=1, max_length=MAX_SOURCE_CHARS)
    filename: str = Field(default="pasted-source", max_length=160)
    language: str = Field(default="auto", max_length=32)

class LogReviewRequest(BaseModel):
    logs: str = Field(min_length=1, max_length=MAX_LOG_CHARS)

class CommandExplainRequest(BaseModel):
    command: str = Field(min_length=1, max_length=300)

class ScopeRequest(BaseModel):
    target: str = Field(min_length=1, max_length=253)
    authorized: bool = False
    scope_note: str = Field(min_length=10, max_length=500)

def _tool_inventory() -> list[dict[str, Any]]:
    descriptions = {
        "nmap": "Network discovery; active scans require the local companion and explicit scope.",
        "owasp_zap": "Web application testing proxy; active testing requires an isolated authorized target.",
        "semgrep": "Static code analysis.", "trivy": "Dependency, filesystem, and container vulnerability scanning.",
        "tshark": "Packet capture analysis; capture permissions and an authorized capture file are required.",
        "wireshark": "Packet analysis GUI; unavailable on most hosted workers.", "git": "Repository and change inspection.",
        "ollama": "Local model runtime; reachable only from the machine running it.",
        "kaligpt": "Optional upstream CLI; never invoked by this hosted API.",
    }
    return [{"id": name, "available_on_server": bool(shutil.which(binary)), "path": shutil.which(binary),
             "version": None, "version_probe": "not run", "description": descriptions[name]}
            for name, (binary, _version_arg) in ALLOWED_TOOLS.items()]

@router.get("/status")
def cybersecurity_status() -> dict[str, Any]:
    """Report server prerequisites only, never the user's device."""
    hosted = bool(os.getenv("RENDER") or os.getenv("K_SERVICE") or os.getenv("WEBSITE_INSTANCE_ID"))
    providers = {"openrouter": bool(os.getenv("OPENROUTER_API_KEY")), "gemini": bool(os.getenv("GEMINI_API_KEY")),
                 "groq": bool(os.getenv("GROQ_API_KEY")), "ollama_local_to_server": bool(os.getenv("OLLAMA_HOST"))}
    return {"status": "ok", "system": platform.system(), "python": platform.python_version(),
            "execution_environment": "hosted_server" if hosted else "local_server",
            "local_device_access": False, "active_scanning_available_here": False,
            "local_companion_required_for": ["Nmap scans", "local filesystem audits", "packet capture", "GUI tools"],
            "providers_configured": providers, "tools": _tool_inventory(),
            "notice": "Tool availability describes this API server, not the device running your browser. No shell commands are executed by this endpoint."}

@router.post("/code-review")
def review_code(request: CodeReviewRequest) -> dict[str, Any]:
    """Run bounded heuristic checks on source text supplied by the user; never execute it."""
    lines = request.source.splitlines()
    if len(lines) > MAX_LINES:
        raise HTTPException(status_code=413, detail=f"Source is limited to {MAX_LINES} lines.")
    findings: list[dict[str, Any]] = []
    for line_no, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        for severity, rule_id, pattern, recommendation in CODE_RULES:
            if pattern.search(line):
                evidence = "[redacted: possible credential]" if rule_id == "hardcoded-secret" else line.strip()[:180]
                findings.append({"severity": severity, "rule": rule_id,
                    "file": request.filename.replace("\\", "/").split("/")[-1], "line": line_no,
                    "evidence": evidence, "recommendation": recommendation})
                break
    counts = Counter(item["severity"] for item in findings)
    return {"status": "success", "mode": "read-only-heuristic-static-analysis",
        "filename": request.filename.replace("\\", "/").split("/")[-1], "language": request.language,
        "lines_reviewed": len(lines), "finding_count": len(findings),
        "severity_counts": {level: counts.get(level, 0) for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
        "findings": findings[:200],
        "limitations": "Heuristic checks only; false positives and missed issues are possible. Source is not executed, uploaded to an AI provider, or written to disk."}

@router.post("/log-review")
def review_logs(request: LogReviewRequest) -> dict[str, Any]:
    """Summarize suspicious patterns in user-supplied logs without network access."""
    lines = request.logs.splitlines()
    if len(lines) > MAX_LINES:
        raise HTTPException(status_code=413, detail=f"Logs are limited to {MAX_LINES} lines.")
    findings: list[dict[str, Any]] = []
    for line_no, line in enumerate(lines, 1):
        for severity, rule_id, pattern in LOG_PATTERNS:
            if pattern.search(line):
                findings.append({"severity": severity, "rule": rule_id, "line": line_no,
                    "evidence": line.strip()[:180],
                    "recommendation": "Correlate with surrounding timestamps and known-good activity before treating this as an incident."})
                break
    counts = Counter(item["severity"] for item in findings)
    return {"status": "success", "lines_reviewed": len(lines), "finding_count": len(findings),
        "severity_counts": {level: counts.get(level, 0) for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
        "findings": findings[:200],
        "limitations": "Pattern matching only. Findings are leads for human investigation, not proof of compromise."}

_COMMANDS = {
    "ip": "Displays network interfaces, addresses, and routes. Read-only examples include ip addr and ip route.",
    "ss": "Shows socket information. ss -lnt lists listening TCP ports without changing system state.",
    "nmap": "Network discovery and port/service scanning. Use only on systems you own or are explicitly authorized to assess; prefer a lab and conservative timing.",
    "semgrep": "Static analysis tool that matches code against security rules.",
    "trivy": "Scans dependencies, filesystems, and container images for known vulnerabilities.",
    "tshark": "Command-line packet analyzer. Capture only traffic you are authorized to inspect.",
    "git": "Tracks source changes. git diff --check checks whitespace without modifying files.",
    "curl": "Makes HTTP requests. Review destinations and avoid sending credentials to untrusted hosts.",
    "grep": "Searches text for patterns; avoid printing secrets into shared terminals or logs.",
    "find": "Searches directory trees. Use a narrow, known directory to avoid exposing private files.",
    "uname": "Displays kernel/system information.", "whoami": "Displays the current effective username.",
    "id": "Displays current user and group identifiers.", "pwd": "Displays the current working directory.",
    "ls": "Lists directory contents; filenames may reveal private information.",
    "rm": "Deletes files. NOX does not execute this command; inspect targets and backups before manual use.",
    "sudo": "Runs a command with elevated privileges. Avoid unless necessary and review the exact command first.",
    "chmod": "Changes file permissions and can weaken security if permissions are too broad.",
    "nc": "Network utility with potentially risky uses. NOX does not execute it.",
    "bash": "Shell interpreter capable of executing scripts. NOX does not execute model-generated shell commands.",
}
_BLOCKED_CONTROL = re.compile(r"[;&|$<>\\n\\r]")

@router.post("/explain-command")
def explain_command(request: CommandExplainRequest) -> dict[str, Any]:
    """Explain a command string without invoking a shell or executable."""
    command = request.command.strip()
    if _BLOCKED_CONTROL.search(command) or chr(96) in command or "\x00" in command:
        raise HTTPException(status_code=400, detail="Explain one command at a time; shell chaining, redirection, substitutions, and control operators are not accepted.")
    parts = command.split()
    if not parts:
        raise HTTPException(status_code=400, detail="Enter a command to explain.")
    key = parts[0].rsplit("/", 1)[-1]
    description = _COMMANDS.get(key)
    if description is None:
        raise HTTPException(status_code=400, detail="This command is not in the explanation registry. No command was executed.")
    risk = "high" if key in {"rm", "sudo", "chmod", "nc", "bash"} else ("medium" if key in {"nmap", "curl", "tshark"} else "low")
    return {"status": "success", "command": command, "program": key, "risk": risk,
            "explanation": description, "execution": "not executed",
            "note": "This endpoint explains text only. It never runs the command."}

def _allowed_hosts() -> set[str]:
    return {host.strip().casefold().rstrip(".") for host in os.getenv("NOX_CYBER_ALLOWED_HOSTS", "").split(",") if host.strip()}

@router.post("/validate-scope")
def validate_scope(request: ScopeRequest) -> dict[str, Any]:
    """Validate an explicit scope declaration. Does not scan or persist authorization."""
    if not request.authorized:
        raise HTTPException(status_code=403, detail="Confirm that you own the target or have explicit written authorization.")
    if len(request.scope_note.strip()) < 10:
        raise HTTPException(status_code=422, detail="Describe the permitted scope (at least 10 characters).")
    raw = request.target.strip()
    candidate = raw
    if "://" in raw:
        parsed = urlsplit(raw)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise HTTPException(status_code=400, detail="Use HTTPS on port 443 or a host/IP; no embedded credentials or alternate ports.")
        candidate = parsed.hostname or ""
    candidate = candidate.casefold().rstrip(".")
    if not candidate or any(ch.isspace() for ch in candidate) or "/" in candidate or len(candidate) > 253:
        raise HTTPException(status_code=400, detail="Enter a single host name or IP address.")
    local_lab = False
    try:
        address = ipaddress.ip_address(candidate)
        local_lab = bool(address.is_private or address.is_loopback or address.is_link_local)
        if not local_lab and candidate not in _allowed_hosts():
            raise HTTPException(status_code=403, detail="Public IP targets must be explicitly allowlisted in NOX_CYBER_ALLOWED_HOSTS; this hosted API does not scan public targets.")
    except ValueError:
        if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*", candidate):
            raise HTTPException(status_code=400, detail="Target host name is invalid.")
        local_suffix = candidate == "localhost" or candidate.endswith((".localhost", ".test", ".lab", ".invalid", ".example"))
        if not local_suffix and candidate not in _allowed_hosts():
            raise HTTPException(status_code=403, detail="Only local lab names or exact hosts configured in NOX_CYBER_ALLOWED_HOSTS are accepted.")
        local_lab = local_suffix
    return {"status": "scope_validated", "target": candidate, "scope_note_received": True,
        "target_class": "local_lab" if local_lab else "explicitly_allowlisted",
        "scan_started": False, "authorization_recorded": False,
        "next_step": "Use the local NOX companion to perform any approved assessment. This hosted endpoint does not initiate network traffic."}
