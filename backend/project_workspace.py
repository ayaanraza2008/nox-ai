"""Session-scoped, approval-gated project workspace snapshots.

This module stores user-supplied source text in SQLite. It never reads arbitrary
host paths, executes submitted code, writes to a repository, or deploys changes.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath


class WorkspaceError(ValueError):
    """Workspace operation is invalid or conflicts with current state."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> str:
    return os.environ.get("NOX_WORKSPACE_DB", "/tmp/nox_workspace.sqlite3")


def _connect():
    db = sqlite3.connect(_db_path(), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS workspace_projects (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, name TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_workspace_projects_owner
            ON workspace_projects(owner_id, updated_at DESC);
        CREATE TABLE IF NOT EXISTS workspace_files (
            project_id TEXT NOT NULL, path TEXT NOT NULL, content TEXT NOT NULL,
            version INTEGER NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(project_id, path),
            FOREIGN KEY(project_id) REFERENCES workspace_projects(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS workspace_patches (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner_id TEXT NOT NULL,
            path TEXT NOT NULL, summary TEXT NOT NULL, base_hash TEXT NOT NULL,
            proposed_content TEXT NOT NULL, status TEXT NOT NULL,
            diff TEXT NOT NULL, created_at TEXT NOT NULL, reviewed_at TEXT,
            FOREIGN KEY(project_id) REFERENCES workspace_projects(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_workspace_patches_project
            ON workspace_patches(project_id, created_at DESC);
    """)
    db.execute("PRAGMA foreign_keys=ON")
    return db


def validate_path(path: str) -> str:
    if not isinstance(path, str):
        raise WorkspaceError("File path must be text.")
    path = path.strip()
    if not path or len(path) > 240 or "\x00" in path or "\\" in path:
        raise WorkspaceError("Use a relative POSIX file path up to 240 characters.")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or any(part in ("", ".", "..") for part in path.split("/")):
        raise WorkspaceError("Absolute paths, '.' and '..' path segments are not allowed.")
    if any(part.startswith(".") for part in parsed.parts):
        raise WorkspaceError("Hidden file paths are not supported in this workspace.")
    if not re.fullmatch(r"[A-Za-z0-9._/@+ -]+", path):
        raise WorkspaceError("Path contains unsupported characters.")
    return path


def _project(db, project_id: str, owner_id: str):
    row = db.execute(
        "SELECT * FROM workspace_projects WHERE id=? AND owner_id=?",
        (project_id, owner_id),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["file_count"] = db.execute(
        "SELECT COUNT(*) FROM workspace_files WHERE project_id=?", (project_id,)
    ).fetchone()[0]
    result["pending_patches"] = db.execute(
        "SELECT COUNT(*) FROM workspace_patches WHERE project_id=? AND status='pending'",
        (project_id,),
    ).fetchone()[0]
    return result


def list_projects(owner_id: str) -> list[dict]:
    with _connect() as db:
        rows = db.execute(
            "SELECT id FROM workspace_projects WHERE owner_id=? ORDER BY updated_at DESC LIMIT 20",
            (owner_id,),
        ).fetchall()
        return [_project(db, row["id"], owner_id) for row in rows]


def create_project(name: str, owner_id: str) -> dict:
    name = " ".join(name.split()) if isinstance(name, str) else ""
    if not 1 <= len(name) <= 80:
        raise WorkspaceError("Project name must contain 1–80 characters.")
    with _connect() as db:
        count = db.execute("SELECT COUNT(*) FROM workspace_projects WHERE owner_id=?", (owner_id,)).fetchone()[0]
        if count >= 20:
            raise WorkspaceError("A browser session can keep at most 20 workspace projects.")
        project_id, stamp = uuid.uuid4().hex, _now()
        db.execute(
            "INSERT INTO workspace_projects(id,owner_id,name,created_at,updated_at) VALUES(?,?,?,?,?)",
            (project_id, owner_id, name, stamp, stamp),
        )
        return _project(db, project_id, owner_id)


def get_project(project_id: str, owner_id: str) -> dict | None:
    with _connect() as db:
        return _project(db, project_id, owner_id)


def list_files(project_id: str, owner_id: str) -> list[dict] | None:
    with _connect() as db:
        if not _project(db, project_id, owner_id):
            return None
        rows = db.execute(
            "SELECT path,version,updated_at,length(content) AS characters FROM workspace_files WHERE project_id=? ORDER BY path LIMIT 100",
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def save_file(project_id: str, path: str, content: str, owner_id: str) -> dict | None:
    path = validate_path(path)
    if not isinstance(content, str) or len(content) > 50000:
        raise WorkspaceError("File content must be text no larger than 50,000 characters.")
    with _connect() as db:
        project = _project(db, project_id, owner_id)
        if not project:
            return None
        row = db.execute(
            "SELECT version FROM workspace_files WHERE project_id=? AND path=?", (project_id, path)
        ).fetchone()
        if not row and project["file_count"] >= 100:
            raise WorkspaceError("A project can contain at most 100 workspace files.")
        version = (row["version"] + 1) if row else 1
        stamp = _now()
        db.execute(
            """INSERT INTO workspace_files(project_id,path,content,version,updated_at)
               VALUES(?,?,?,?,?) ON CONFLICT(project_id,path) DO UPDATE SET
               content=excluded.content,version=excluded.version,updated_at=excluded.updated_at""",
            (project_id, path, content, version, stamp),
        )
        db.execute("UPDATE workspace_projects SET updated_at=? WHERE id=?", (stamp, project_id))
        return {"path": path, "version": version, "characters": len(content), "updated_at": stamp}


def read_file(project_id: str, path: str, owner_id: str) -> dict | None:
    path = validate_path(path)
    with _connect() as db:
        if not _project(db, project_id, owner_id):
            return None
        row = db.execute(
            "SELECT path,content,version,updated_at FROM workspace_files WHERE project_id=? AND path=?",
            (project_id, path),
        ).fetchone()
        return dict(row) if row else None


def create_patch(project_id: str, path: str, proposed_content: str, summary: str, owner_id: str) -> dict | None:
    path = validate_path(path)
    if not isinstance(proposed_content, str) or len(proposed_content) > 50000:
        raise WorkspaceError("Proposed content must be text no larger than 50,000 characters.")
    summary = " ".join(summary.split()) if isinstance(summary, str) else ""
    if not 1 <= len(summary) <= 240:
        raise WorkspaceError("Patch summary must contain 1–240 characters.")
    with _connect() as db:
        project = _project(db, project_id, owner_id)
        if not project:
            return None
        row = db.execute(
            "SELECT content FROM workspace_files WHERE project_id=? AND path=?", (project_id, path)
        ).fetchone()
        if not row:
            raise WorkspaceError("Save the original file into this workspace before proposing a patch.")
        original = row["content"]
        diff = "\n".join(difflib.unified_diff(
            original.splitlines(), proposed_content.splitlines(),
            fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="", n=3,
        )) or "No changes detected."
        patch_id, stamp = uuid.uuid4().hex, _now()
        db.execute(
            """INSERT INTO workspace_patches
               (id,project_id,owner_id,path,summary,base_hash,proposed_content,status,diff,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (patch_id, project_id, owner_id, path, summary,
             hashlib.sha256(original.encode("utf-8")).hexdigest(), proposed_content,
             "pending", diff[:30000], stamp),
        )
        db.execute("UPDATE workspace_projects SET updated_at=? WHERE id=?", (stamp, project_id))
        return _patch_dict(db, patch_id)


def _patch_dict(db, patch_id: str):
    row = db.execute(
        "SELECT id,project_id,path,summary,status,diff,created_at,reviewed_at FROM workspace_patches WHERE id=?",
        (patch_id,),
    ).fetchone()
    return dict(row) if row else None


def list_patches(project_id: str, owner_id: str) -> list[dict] | None:
    with _connect() as db:
        if not _project(db, project_id, owner_id):
            return None
        rows = db.execute(
            "SELECT id FROM workspace_patches WHERE project_id=? AND owner_id=? ORDER BY created_at DESC LIMIT 50",
            (project_id, owner_id),
        ).fetchall()
        return [_patch_dict(db, row["id"]) for row in rows]


def review_patch(patch_id: str, decision: str, owner_id: str) -> dict | None:
    if decision not in ("approved", "rejected"):
        raise WorkspaceError("Decision must be approved or rejected.")
    with _connect() as db:
        patch = db.execute(
            "SELECT * FROM workspace_patches WHERE id=? AND owner_id=?", (patch_id, owner_id)
        ).fetchone()
        if not patch:
            return None
        if patch["status"] != "pending":
            raise WorkspaceError("This patch has already been reviewed.")
        stamp = _now()
        if decision == "approved":
            current = db.execute(
                "SELECT content,version FROM workspace_files WHERE project_id=? AND path=?",
                (patch["project_id"], patch["path"]),
            ).fetchone()
            if not current:
                raise WorkspaceError("The original workspace file no longer exists.")
            digest = hashlib.sha256(current["content"].encode("utf-8")).hexdigest()
            if digest != patch["base_hash"]:
                raise WorkspaceError("This patch is stale because the original file changed. Create a new patch against the latest version.")
            db.execute(
                "UPDATE workspace_files SET content=?,version=?,updated_at=? WHERE project_id=? AND path=?",
                (patch["proposed_content"], current["version"] + 1, stamp, patch["project_id"], patch["path"]),
            )
            db.execute("UPDATE workspace_projects SET updated_at=? WHERE id=?", (stamp, patch["project_id"]))
        db.execute(
            "UPDATE workspace_patches SET status=?,reviewed_at=? WHERE id=?",
            (decision, stamp, patch_id),
        )
        return _patch_dict(db, patch_id)


def validate_file(project_id: str, path: str, owner_id: str) -> dict | None:
    file = read_file(project_id, path, owner_id)
    if file is None:
        return None
    suffix = PurePosixPath(file["path"]).suffix.lower()
    if suffix == ".py":
        import ast
        try:
            tree = ast.parse(file["content"], mode="exec")
            return {"path": file["path"], "valid": True, "validator": "python AST", "top_level_statements": len(tree.body), "note": "Parsed only; code was not executed."}
        except SyntaxError as exc:
            return {"path": file["path"], "valid": False, "validator": "python AST", "error": exc.msg, "line": exc.lineno, "column": exc.offset, "note": "Code was not executed."}
    if suffix == ".json":
        import json
        try:
            json.loads(file["content"], parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid JSON constant: {value}")))
            return {"path": file["path"], "valid": True, "validator": "JSON parser", "note": "JSON parsed successfully."}
        except (ValueError, json.JSONDecodeError) as exc:
            return {"path": file["path"], "valid": False, "validator": "JSON parser", "error": str(exc)[:300]}
    return {"path": file["path"], "valid": None, "validator": "none", "note": "No built-in validator for this extension. No tests or code were executed."}
