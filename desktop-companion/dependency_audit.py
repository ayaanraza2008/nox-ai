"""Dependency vulnerability audit using the public OSV database.

Only dependency names and pinned versions are sent to https://api.osv.dev.
No source code, credentials, or arbitrary URLs are sent. No packages are installed.
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
MAX_DEPENDENCIES = 80
TIMEOUT_SECONDS = 7
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


def _root():
    configured = os.getenv("NOX_SECURITY_PROJECT_DIR", "").strip()
    if not configured:
        raise ValueError("Set NOX_SECURITY_PROJECT_DIR to the project folder you own, then restart NOX Companion.")
    root = Path(configured).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("NOX_SECURITY_PROJECT_DIR must point to a directory.")
    return root


def _read_dependencies(root):
    deps = {}
    skipped = []
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (Path(current) / d).is_symlink()]
        base = Path(current)
        if "requirements.txt" in files:
            path = base / "requirements.txt"
            try:
                if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > 250_000:
                    skipped.append(str(path.relative_to(root)))
                else:
                    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                        line = raw.strip()
                        if not line or line.startswith("#") or line.startswith(("-", "git+", "http:", "https:")):
                            continue
                        match = re.match(r"^([A-Za-z0-9_.-]+)\s*==\s*([A-Za-z0-9_.+!-]+)(?:\s*;.*)?$", line)
                        if match:
                            deps[(match.group(1).lower().replace("_", "-"), match.group(2), "PyPI")] = {
                                "name": match.group(1), "version": match.group(2), "ecosystem": "PyPI",
                                "manifest": str(path.relative_to(root))
                            }
            except OSError:
                skipped.append(str(path.relative_to(root)))
        if "package-lock.json" in files:
            path = base / "package-lock.json"
            try:
                if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > 2_000_000:
                    skipped.append(str(path.relative_to(root)))
                else:
                    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                    packages = data.get("packages", {})
                    for package_path, item in packages.items():
                        if not package_path:
                            continue
                        version = item.get("version")
                        if not version:
                            continue
                        name = item.get("name")
                        if not name and package_path.startswith("node_modules/"):
                            name = package_path[len("node_modules/"):]
                        if name and re.fullmatch(r"[A-Za-z0-9@/_.+-]+", name) and re.fullmatch(r"[A-Za-z0-9_.+-]+", version):
                            deps[(name.lower(), version, "npm")] = {
                                "name": name, "version": version, "ecosystem": "npm",
                                "manifest": str(path.relative_to(root))
                            }
            except (OSError, ValueError, AttributeError):
                skipped.append(str(path.relative_to(root)))
    return list(deps.values())[:MAX_DEPENDENCIES], skipped, len(deps)


def _query_osv(dep):
    body = json.dumps({
        "package": {"name": dep["name"], "ecosystem": dep["ecosystem"]},
        "version": dep["version"]
    }).encode("utf-8")
    request = urllib.request.Request(
        OSV_QUERY_URL, data=body, headers={"Content-Type": "application/json", "User-Agent": "NOX-Defensive-Audit/1.0"},
        method="POST"
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise RuntimeError("OSV returned HTTP " + str(response.status))
        result = json.loads(response.read(1_000_000).decode("utf-8"))
    advisories = []
    for vuln in result.get("vulns", []):
        refs = [ref.get("url") for ref in vuln.get("references", []) if isinstance(ref, dict) and ref.get("url", "").startswith("https://")]
        advisories.append({
            "id": vuln.get("id", "Unknown advisory"),
            "summary": (vuln.get("summary") or vuln.get("details") or "No summary provided")[:350],
            "references": refs[:3],
            "modified": vuln.get("modified")
        })
    return advisories


def audit_dependencies():
    try:
        root = _root()
    except (OSError, ValueError) as exc:
        return {"status": "error", "message": str(exc)}
    dependencies, skipped, total = _read_dependencies(root)
    findings, checked, errors = [], 0, []
    for dep in dependencies:
        try:
            advisories = _query_osv(dep)
            checked += 1
            for advisory in advisories:
                findings.append({
                    "severity": "REVIEW",
                    "package": dep["name"],
                    "version": dep["version"],
                    "ecosystem": dep["ecosystem"],
                    "manifest": dep["manifest"],
                    "advisory": advisory
                })
        except (OSError, ValueError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            errors.append({"package": dep["name"], "version": dep["version"], "error": str(exc)[:180]})
    return {
        "status": "success" if not errors else "partial",
        "mode": "pinned-dependency-advisory-check",
        "project": root.name,
        "database": "OSV.dev",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "dependencies_discovered": total,
        "dependencies_checked": checked,
        "dependencies_capped_or_skipped": max(0, total - len(dependencies)) + len(skipped),
        "advisory_matches": len(findings),
        "findings": findings,
        "query_errors": errors[:30],
        "manifests_skipped": skipped[:30],
        "limitations": "Only exact-pinned requirements.txt dependencies and package-lock.json entries are checked, up to 80 unique packages. Network/database failures can leave gaps. Advisory matches require human review and do not alone prove runtime exploitability. Only package names and versions are sent to OSV."
    }


def write_report(static_result=None, dependency_result=None):
    try:
        root = _root()
    except (OSError, ValueError) as exc:
        return {"status": "error", "message": str(exc)}
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": root.name,
        "static_analysis": static_result or {"status": "not_run"},
        "dependency_audit": dependency_result or {"status": "not_run"},
    }
    out_dir = root / "nox-security-reports"
    try:
        out_dir.mkdir(mode=0o700, exist_ok=True)
        json_path = out_dir / "security-report.json"
        md_path = out_dir / "security-report.md"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [
            "# NOX Security Report", "",
            f"- Project: {root.name}",
            f"- Generated (UTC): {report['generated_at']}", "",
            "## Static source analysis", "",
        ]
        static = report["static_analysis"]
        lines += [f"- Status: {static.get('status', 'unknown')}",
                  f"- Python files scanned: {static.get('files_scanned', 0)}",
                  f"- Findings: {static.get('finding_count', 0)}", ""]
        for item in static.get("findings", []):
            lines += [f"### [{item.get('severity')}] {item.get('rule')}",
                      f"- File: {item.get('file')}:{item.get('line')}",
                      f"- Evidence: {item.get('evidence', '')}",
                      f"- Recommendation: {item.get('recommendation', '')}", ""]
        dep = report["dependency_audit"]
        lines += ["## Dependency advisory check", "",
                  f"- Status: {dep.get('status', 'unknown')}",
                  f"- Dependencies checked: {dep.get('dependencies_checked', 0)}",
                  f"- Advisory matches: {dep.get('advisory_matches', 0)}", ""]
        for item in dep.get("findings", []):
            adv = item.get("advisory", {})
            lines += [f"### {item.get('package')} {item.get('version')} — {adv.get('id')}",
                      f"- Manifest: {item.get('manifest')}",
                      f"- Summary: {adv.get('summary', '')}"]
            lines += [f"- Reference: {url}" for url in adv.get("references", [])]
            lines.append("")
        lines += ["## Limitations", "",
                  "Automated heuristic checks can miss issues and produce false positives. Review results before taking action. A missing finding is not proof that the project is secure.", ""]
        md_path.write_text("\n".join(lines), encoding="utf-8")
        try:
            os.chmod(out_dir, 0o700)
            os.chmod(json_path, 0o600)
            os.chmod(md_path, 0o600)
        except OSError:
            pass
    except OSError as exc:
        return {"status": "error", "message": "Could not write report: " + str(exc)}
    return {"status": "success", "json_report": str(json_path), "markdown_report": str(md_path)}
