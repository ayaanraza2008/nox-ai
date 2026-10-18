"""Local, read-only static security review for an explicitly configured project.

This scanner never executes inspected code, installs packages, or accesses the network.
Set NOX_SECURITY_PROJECT_DIR to the project directory before starting the companion.
"""
import os
import re
from pathlib import Path

MAX_FILES = 500
MAX_FILE_BYTES = 1_000_000
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}

RULES = [
    ("HIGH", "dynamic-code", re.compile(r"\b(?:eval|exec)\s*\("), "Dynamic code execution: validate input and avoid evaluating untrusted text."),
    ("HIGH", "shell-true", re.compile(r"\bshell\s*=\s*True\b"), "Shell execution enabled: prefer argument lists and avoid untrusted command strings."),
    ("HIGH", "pickle-load", re.compile(r"\bpickle\.(?:loads?|Unpickler)\s*\("), "Deserializing pickle can execute code; never load untrusted pickle data."),
    ("MEDIUM", "hardcoded-secret", re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"), "Possible hard-coded credential: move secrets to environment variables and rotate exposed credentials."),
    ("MEDIUM", "weak-hash", re.compile(r"\bhashlib\.(?:md5|sha1)\s*\("), "Legacy hash detected; use SHA-256 or a modern password-hashing algorithm as appropriate."),
    ("MEDIUM", "unsafe-yaml", re.compile(r"\byaml\.load\s*\("), "YAML load may be unsafe with untrusted input; use yaml.safe_load where appropriate."),
    ("MEDIUM", "disabled-tls-validation", re.compile(r"(?i)\b(?:verify\s*=\s*False|CERT_NONE)\b"), "TLS certificate verification may be disabled; keep certificate validation enabled."),
    ("LOW", "debug-mode", re.compile(r"\bdebug\s*=\s*True\b"), "Debug mode may expose diagnostics; disable it in production."),
]


def _project_root():
    configured = os.getenv("NOX_SECURITY_PROJECT_DIR", "").strip()
    if not configured:
        raise ValueError("Set NOX_SECURITY_PROJECT_DIR to the project folder you own, then restart NOX Companion.")
    root = Path(configured).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("NOX_SECURITY_PROJECT_DIR must point to a directory.")
    return root


def audit_project():
    """Scan Python source files under the configured project root without executing them."""
    try:
        root = _project_root()
    except (OSError, ValueError) as exc:
        return {"status": "error", "message": str(exc)}

    findings, scanned, skipped = [], 0, 0
    try:
        for current, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not (Path(current) / name).is_symlink()]
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                path = Path(current) / filename
                try:
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(root) or path.is_symlink():
                        skipped += 1
                        continue
                    if resolved.stat().st_size > MAX_FILE_BYTES:
                        skipped += 1
                        continue
                    source = resolved.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    skipped += 1
                    continue
                scanned += 1
                for line_no, line in enumerate(source.splitlines(), 1):
                    stripped = line.lstrip()
                    if stripped.startswith("#"):
                        continue
                    for severity, rule_id, pattern, recommendation in RULES:
                        if pattern.search(line):
                            findings.append({
                                "severity": severity,
                                "rule": rule_id,
                                "file": resolved.relative_to(root).as_posix(),
                                "line": line_no,
                                "evidence": line.strip()[:220],
                                "recommendation": recommendation,
                            })
                            break
                if scanned >= MAX_FILES:
                    skipped += 1
                    break
            if scanned >= MAX_FILES:
                break
    except OSError as exc:
        return {"status": "error", "message": "Could not traverse configured project: " + str(exc)}

    counts = {level: sum(1 for item in findings if item["severity"] == level) for level in ("HIGH", "MEDIUM", "LOW")}
    return {
        "status": "success",
        "mode": "read-only-static-analysis",
        "project": root.name,
        "files_scanned": scanned,
        "files_skipped": skipped,
        "finding_count": len(findings),
        "severity_counts": counts,
        "findings": findings[:200],
        "limitations": "Heuristic Python source scan only; may produce false positives and miss issues. It does not execute code, scan networks, audit dependencies, or prove exploitability.",
    }
