"""Privacy-first operational brain for NOX AI.

This is a bounded, session-scoped memory and evaluation service, not model-weight
training. It stores only explicitly submitted candidates, never raw conversations.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("NOX_BRAIN_DB", str(ROOT / "nox_brain.sqlite3")))
MAX_MEMORIES = max(50, min(int(os.getenv("NOX_BRAIN_MAX_MEMORIES", "1000")), 10000))
MAX_SKILLS = 250
CATEGORIES = {"operational", "experience", "preference", "project", "temporary"}
SENSITIVE = re.compile(
    r"(?i)(api[_ -]?key\s*[:=]\s*\S+|bearer\s+[a-z0-9._-]{12,}|"
    r"password\s*[:=]\s*\S+|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:\d[ -]*?){13,19}\b)"
)
SECRET_WORDS = re.compile(r"(?i)\b(password|passphrase|private key|access token|refresh token|secret key)\b")
WORD = re.compile(r"[a-zA-Z0-9_]{2,}|[\u0900-\u097f]{2,}|[\u0600-\u06ff]{2,}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Connection:
    """SQLite context wrapper that always closes the connection after each unit of work."""
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
        return False


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS brain_settings (
      owner_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1,
      sync_mode TEXT NOT NULL DEFAULT 'local_only', retention_days INTEGER NOT NULL DEFAULT 365,
      categories_json TEXT NOT NULL DEFAULT '["operational","experience","preference","project","temporary"]',
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS brain_memories (
      id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, category TEXT NOT NULL,
      content TEXT NOT NULL, content_hash TEXT NOT NULL, source TEXT NOT NULL,
      source_ref TEXT, confidence REAL NOT NULL, verification TEXT NOT NULL,
      retention_days INTEGER NOT NULL, created_at TEXT NOT NULL,
      last_validated_at TEXT, expires_at TEXT, stale INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY(owner_id) REFERENCES brain_settings(owner_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_brain_memory_owner_created ON brain_memories(owner_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_brain_memory_owner_category ON brain_memories(owner_id, category);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_brain_memory_owner_hash ON brain_memories(owner_id, content_hash);
    CREATE TABLE IF NOT EXISTS brain_devices (
      id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, label TEXT NOT NULL,
      capabilities_json TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(owner_id, label)
    );
    CREATE TABLE IF NOT EXISTS brain_outcomes (
      id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, task_type TEXT NOT NULL,
      requested_outcome TEXT NOT NULL, result_summary TEXT NOT NULL,
      status TEXT NOT NULL, evidence TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS brain_skills (
      id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, name TEXT NOT NULL,
      purpose TEXT NOT NULL, definition_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
      status TEXT NOT NULL DEFAULT 'proposed', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(owner_id, name)
    );
    CREATE TABLE IF NOT EXISTS brain_proposals (
      id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, title TEXT NOT NULL,
      summary TEXT NOT NULL, proposal_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
      created_at TEXT NOT NULL, reviewed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS brain_audit (
      id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, action TEXT NOT NULL,
      item_type TEXT NOT NULL, item_id TEXT, detail_json TEXT NOT NULL, created_at TEXT NOT NULL
    );
    """)
    return _Connection(conn)


def _ensure_settings(conn, owner_id: str):
    conn.execute(
        "INSERT OR IGNORE INTO brain_settings(owner_id, enabled, sync_mode, retention_days, categories_json, updated_at) VALUES(?,1,'local_only',365,?,?)",
        (owner_id, json.dumps(["operational", "experience", "preference", "project", "temporary"]), now_iso()),
    )


def _audit(conn, owner_id: str, action: str, item_type: str, item_id: str | None = None, detail: dict | None = None):
    conn.execute(
        "INSERT INTO brain_audit(id,owner_id,action,item_type,item_id,detail_json,created_at) VALUES(?,?,?,?,?,?,?)",
        (uuid.uuid4().hex, owner_id, action, item_type, item_id, json.dumps(detail or {}, ensure_ascii=False), now_iso()),
    )


def _settings_dict(row) -> dict:
    return {
        "enabled": bool(row["enabled"]), "sync_mode": row["sync_mode"],
        "retention_days": int(row["retention_days"]),
        "categories": json.loads(row["categories_json"]), "updated_at": row["updated_at"],
    }


def get_settings(owner_id: str) -> dict:
    with _connect() as conn:
        _ensure_settings(conn, owner_id)
        row = conn.execute("SELECT * FROM brain_settings WHERE owner_id=?", (owner_id,)).fetchone()
        conn.commit()
        return _settings_dict(row)


def update_settings(owner_id: str, payload: dict) -> dict:
    allowed = {"operational", "experience", "preference", "project", "temporary"}
    with _connect() as conn:
        _ensure_settings(conn, owner_id)
        current = conn.execute("SELECT * FROM brain_settings WHERE owner_id=?", (owner_id,)).fetchone()
        enabled = bool(payload.get("enabled", current["enabled"]))
        sync_mode = payload.get("sync_mode", current["sync_mode"])
        if sync_mode not in {"local_only", "approved_sync"}:
            raise ValueError("sync_mode must be local_only or approved_sync")
        retention = int(payload.get("retention_days", current["retention_days"]))
        if not 1 <= retention <= 3650:
            raise ValueError("retention_days must be between 1 and 3650")
        categories = payload.get("categories", json.loads(current["categories_json"]))
        if not isinstance(categories, list) or not set(categories).issubset(allowed):
            raise ValueError("Invalid memory categories")
        conn.execute(
            "UPDATE brain_settings SET enabled=?,sync_mode=?,retention_days=?,categories_json=?,updated_at=? WHERE owner_id=?",
            (int(enabled), sync_mode, retention, json.dumps(sorted(set(categories))), now_iso(), owner_id),
        )
        _audit(conn, owner_id, "settings_updated", "settings", detail={"enabled": enabled, "sync_mode": sync_mode, "categories": sorted(set(categories))})
        conn.commit()
    return get_settings(owner_id)


def _digest(content: str) -> str:
    return hashlib.sha256(" ".join(content.casefold().split()).encode("utf-8")).hexdigest()


def _memory_payload(row) -> dict:
    return {
        "id": row["id"], "category": row["category"], "content": row["content"],
        "source": row["source"], "source_ref": row["source_ref"],
        "confidence": row["confidence"], "verification": row["verification"],
        "retention_days": row["retention_days"], "created_at": row["created_at"],
        "last_validated_at": row["last_validated_at"], "expires_at": row["expires_at"],
        "stale": bool(row["stale"]),
    }


def remember(owner_id: str, *, content: str, category: str, source: str = "user_explicit",
             source_ref: str | None = None, confidence: float = 0.8, verification: str = "user_confirmed",
             retention_days: int | None = None) -> dict:
    content = " ".join(content.split()).strip()
    if not content or len(content) > 2000:
        raise ValueError("Memory content must be between 1 and 2000 characters")
    if category not in CATEGORIES:
        raise ValueError("Unsupported memory category")
    if source not in {"user_explicit", "verified_lesson", "approved_import"}:
        raise ValueError("Memory source must be explicit or validated")
    if verification not in {"user_confirmed", "verified", "unverified"}:
        raise ValueError("Invalid verification status")
    if SENSITIVE.search(content) or SECRET_WORDS.search(content) or (source_ref and (SENSITIVE.search(source_ref) or SECRET_WORDS.search(source_ref))):
        raise ValueError("This looks like a secret or credential. NOX will not store it as a memory.")
    if category == "temporary":
        retention_days = min(max(int(retention_days or 1), 1), 7)
    else:
        retention_days = min(max(int(retention_days or get_settings(owner_id)["retention_days"]), 1), 3650)
    confidence = min(max(float(confidence), 0.0), 1.0)
    if source == "verified_lesson" and (verification != "verified" or confidence < 0.65):
        raise ValueError("Lessons require verified evidence and confidence of at least 0.65")
    if category not in get_settings(owner_id)["categories"]:
        raise ValueError("This memory category is disabled in Brain settings")
    digest = _digest(content)
    now = now_iso()
    expires = (datetime.now(timezone.utc) + timedelta(days=retention_days)).isoformat()
    with _connect() as conn:
        _ensure_settings(conn, owner_id)
        settings = conn.execute("SELECT enabled FROM brain_settings WHERE owner_id=?", (owner_id,)).fetchone()
        if not settings["enabled"]:
            raise ValueError("Memory is disabled in Brain settings")
        existing = conn.execute("SELECT * FROM brain_memories WHERE owner_id=? AND content_hash=?", (owner_id, digest)).fetchone()
        if existing:
            # A repeat may refresh provenance/validation, but never creates a duplicate.
            conn.execute(
                "UPDATE brain_memories SET confidence=MAX(confidence,?), verification=?, source=?, source_ref=COALESCE(?,source_ref), last_validated_at=?, stale=0, expires_at=? WHERE id=? AND owner_id=?",
                (confidence, verification, source, source_ref, now if verification == "verified" else existing["last_validated_at"], expires, existing["id"], owner_id),
            )
            _audit(conn, owner_id, "memory_merged", "memory", existing["id"], {"category": category})
            conn.commit()
            row = conn.execute("SELECT * FROM brain_memories WHERE id=?", (existing["id"],)).fetchone()
            return {"stored": True, "duplicate": True, "memory": _memory_payload(row)}
        count = conn.execute("SELECT COUNT(*) FROM brain_memories WHERE owner_id=?", (owner_id,)).fetchone()[0]
        if count >= MAX_MEMORIES:
            raise ValueError("Memory capacity reached. Delete or export older memories first.")
        memory_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO brain_memories(id,owner_id,category,content,content_hash,source,source_ref,confidence,verification,retention_days,created_at,last_validated_at,expires_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (memory_id, owner_id, category, content, digest, source, (source_ref or "")[:300] or None,
             confidence, verification, retention_days, now, now if verification == "verified" else None, expires),
        )
        _audit(conn, owner_id, "memory_stored", "memory", memory_id, {"category": category, "verification": verification})
        conn.commit()
        row = conn.execute("SELECT * FROM brain_memories WHERE id=?", (memory_id,)).fetchone()
        return {"stored": True, "duplicate": False, "memory": _memory_payload(row)}


def list_memories(owner_id: str, query: str = "", category: str | None = None, limit: int = 100) -> dict:
    limit = min(max(int(limit), 1), 1000)
    with _connect() as conn:
        _ensure_settings(conn, owner_id)
        conn.execute("DELETE FROM brain_memories WHERE owner_id=? AND expires_at IS NOT NULL AND expires_at < ?", (owner_id, now_iso()))
        clauses = ["owner_id=?"]
        args: list[Any] = [owner_id]
        if category:
            if category not in CATEGORIES:
                raise ValueError("Unsupported memory category")
            clauses.append("category=?"); args.append(category)
        rows = conn.execute(
            "SELECT * FROM brain_memories WHERE " + " AND ".join(clauses) + " ORDER BY stale ASC, confidence DESC, created_at DESC LIMIT ?",
            (*args, limit),
        ).fetchall()
        conn.commit()
    terms = [t.casefold() for t in WORD.findall(query) if len(t) > 1]
    results = []
    for row in rows:
        item = _memory_payload(row)
        if terms:
            haystack = (item["content"] + " " + item["category"]).casefold()
            hits = sum(1 for term in terms if term in haystack)
            if not hits:
                continue
            item["relevance"] = hits / len(terms)
        results.append(item)
    if terms:
        results.sort(key=lambda item: (item.get("relevance", 0), item["confidence"], not item["stale"]), reverse=True)
    return {"count": len(results), "results": results[:limit]}


def retrieve_memories(owner_id: str, query: str, limit: int = 4) -> list[dict]:
    settings = get_settings(owner_id)
    if not settings["enabled"]:
        return []
    terms = [t.casefold() for t in WORD.findall(query) if len(t) > 1]
    if not terms:
        return []
    listed = list_memories(owner_id, query=query, limit=200)["results"]
    allowed = set(settings["categories"])
    ranked = []
    for item in listed:
        if item["category"] not in allowed or item["stale"] or item["verification"] == "unverified":
            continue
        text = item["content"].casefold()
        hits = sum(1 for term in terms if term in text)
        if not hits:
            continue
        freshness = 0.2 if item["last_validated_at"] else 0.0
        ranked.append((hits / len(terms) + item["confidence"] * 0.2 + freshness, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [{"title": f"NOX {item['category']} memory", "filename": item["source"], "text": item["content"],
             "memory_id": item["id"], "verification": item["verification"], "confidence": item["confidence"]}
            for _, item in ranked[:min(max(limit, 1), 8)]]


def review_memory(owner_id: str, memory_id: str, decision: str) -> dict | None:
    if decision not in {"revalidate", "mark_stale"}:
        raise ValueError("decision must be revalidate or mark_stale")
    now = now_iso()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM brain_memories WHERE owner_id=? AND id=?", (owner_id, memory_id)).fetchone()
        if not row:
            return None
        if decision == "revalidate":
            conn.execute("UPDATE brain_memories SET stale=0,verification='user_confirmed',last_validated_at=? WHERE owner_id=? AND id=?",
                         (now, owner_id, memory_id))
        else:
            conn.execute("UPDATE brain_memories SET stale=1 WHERE owner_id=? AND id=?", (owner_id, memory_id))
        _audit(conn, owner_id, "memory_" + decision, "memory", memory_id)
        conn.commit()
        updated = conn.execute("SELECT * FROM brain_memories WHERE owner_id=? AND id=?", (owner_id, memory_id)).fetchone()
        return _memory_payload(updated)


def delete_memory(owner_id: str, memory_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM brain_memories WHERE owner_id=? AND id=?", (owner_id, memory_id))
        if cur.rowcount:
            _audit(conn, owner_id, "memory_deleted", "memory", memory_id)
        conn.commit()
        return cur.rowcount > 0


def record_device(owner_id: str, label: str, capabilities: dict) -> dict:
    if not 1 <= len(label.strip()) <= 80:
        raise ValueError("Device label must be 1-80 characters")
    # Strict allowlist: no files, location, contacts, browsing, camera frames, or identifiers.
    allowed = {"platform", "browser", "language", "viewport", "webgl", "online", "hardware_threads",
               "approx_device_memory_gb", "microphone_available", "camera_available", "speech_recognition",
               "speech_synthesis", "reduced_motion"}
    clean = {}
    for key in allowed:
        value = capabilities.get(key)
        if key in {"platform", "browser", "language"} and isinstance(value, str):
            clean[key] = value[:80]
        elif key == "viewport" and isinstance(value, dict):
            clean[key] = {"width": max(0, min(int(value.get("width", 0)), 10000)),
                          "height": max(0, min(int(value.get("height", 0)), 10000))}
        elif key in {"webgl", "online", "microphone_available", "camera_available", "speech_recognition", "speech_synthesis", "reduced_motion"} and isinstance(value, bool):
            clean[key] = value
        elif key == "hardware_threads" and isinstance(value, int):
            clean[key] = max(0, min(value, 256))
        elif key == "approx_device_memory_gb" and isinstance(value, (int, float)):
            clean[key] = max(0, min(float(value), 1024))
    with _connect() as conn:
        _ensure_settings(conn, owner_id)
        device_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO brain_devices(id,owner_id,label,capabilities_json,updated_at) VALUES(?,?,?,?,?)
               ON CONFLICT(owner_id,label) DO UPDATE SET capabilities_json=excluded.capabilities_json,updated_at=excluded.updated_at""",
            (device_id, owner_id, label.strip(), json.dumps(clean), now_iso()),
        )
        _audit(conn, owner_id, "device_capabilities_updated", "device", detail={"label": label.strip(), "fields": sorted(clean)})
        conn.commit()
        row = conn.execute("SELECT * FROM brain_devices WHERE owner_id=? AND label=?", (owner_id, label.strip())).fetchone()
        return {"id": row["id"], "label": row["label"], "capabilities": json.loads(row["capabilities_json"]), "updated_at": row["updated_at"]}


def list_devices(owner_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM brain_devices WHERE owner_id=? ORDER BY updated_at DESC", (owner_id,)).fetchall()
    return [{"id": r["id"], "label": r["label"], "capabilities": json.loads(r["capabilities_json"]), "updated_at": r["updated_at"]} for r in rows]


def record_outcome(owner_id: str, task_type: str, requested_outcome: str, result_summary: str,
                   status: str, evidence: str | None = None) -> dict:
    if status not in {"succeeded", "failed", "partial"}:
        raise ValueError("status must be succeeded, failed, or partial")
    values = [task_type.strip(), requested_outcome.strip(), result_summary.strip()]
    if not all(values) or any(len(v) > 1500 for v in values):
        raise ValueError("Outcome fields must be non-empty and at most 1500 characters")
    if evidence and len(evidence) > 2000:
        raise ValueError("Evidence is too long")
    outcome_id = uuid.uuid4().hex
    with _connect() as conn:
        _ensure_settings(conn, owner_id)
        conn.execute(
            "INSERT INTO brain_outcomes(id,owner_id,task_type,requested_outcome,result_summary,status,evidence,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (outcome_id, owner_id, values[0], values[1], values[2], status, evidence, now_iso()),
        )
        _audit(conn, owner_id, "outcome_recorded", "outcome", outcome_id, {"status": status, "task_type": values[0]})
        conn.commit()
    return {"id": outcome_id, "task_type": values[0], "status": status, "created_at": now_iso(),
            "evidence_attached": bool(evidence and evidence.strip()), "requires_validation_before_memory": status == "succeeded" and bool(evidence and evidence.strip())}


BUILTIN_SKILLS = [
    {"name": "verified-memory-retrieval", "purpose": "Retrieve relevant non-stale verified memory before a task.", "inputs": ["task_query"], "outputs": ["ranked_memory_context"], "permissions": ["session_memory_read"], "validation": ["scope_check", "freshness_check"]},
    {"name": "safe-device-capability-summary", "purpose": "Use only an explicit allowlist of browser capability metadata.", "inputs": ["approved_capabilities"], "outputs": ["capability_summary"], "permissions": ["explicit_browser_submission"], "validation": ["allowlist_validation"]},
    {"name": "task-outcome-review", "purpose": "Record a concise result and evidence-backed evaluation of a completed task.", "inputs": ["requested_outcome", "result_summary", "status", "evidence"], "outputs": ["outcome_record"], "permissions": ["session_outcome_write"], "validation": ["schema_validation"]},
]


def list_skills(owner_id: str) -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM brain_skills WHERE owner_id=? ORDER BY updated_at DESC", (owner_id,)).fetchall()
    custom = [{"id": r["id"], "name": r["name"], "purpose": r["purpose"], "definition": json.loads(r["definition_json"]),
               "version": r["version"], "status": r["status"], "created_at": r["created_at"], "updated_at": r["updated_at"]} for r in rows]
    builtins = [{"id": "builtin:" + item["name"], **item, "version": 1, "status": "validated"} for item in BUILTIN_SKILLS]
    return {"count": len(builtins) + len(custom), "skills": builtins + custom}


def propose_skill(owner_id: str, name: str, purpose: str, definition: dict) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,59}", name):
        raise ValueError("Skill name must be 3-60 lowercase letters, numbers, or hyphens")
    if len(purpose.strip()) > 500 or not purpose.strip():
        raise ValueError("Skill purpose must be 1-500 characters")
    safe_definition = {key: definition[key] for key in ("inputs", "outputs", "permissions", "steps", "validation", "limitations") if key in definition}
    if len(json.dumps(safe_definition)) > 6000:
        raise ValueError("Skill definition is too large")
    now = now_iso()
    with _connect() as conn:
        _ensure_settings(conn, owner_id)
        existing = conn.execute("SELECT * FROM brain_skills WHERE owner_id=? AND name=?", (owner_id, name)).fetchone()
        skill_id = existing["id"] if existing else uuid.uuid4().hex
        version = int(existing["version"]) + 1 if existing else 1
        conn.execute(
            """INSERT INTO brain_skills(id,owner_id,name,purpose,definition_json,version,status,created_at,updated_at)
               VALUES(?,?,?,?,?,?, 'proposed',?,?) ON CONFLICT(owner_id,name) DO UPDATE SET
               purpose=excluded.purpose,definition_json=excluded.definition_json,version=excluded.version,status='proposed',updated_at=excluded.updated_at""",
            (skill_id, owner_id, name, purpose.strip(), json.dumps(safe_definition, ensure_ascii=False), version, existing["created_at"] if existing else now, now),
        )
        _audit(conn, owner_id, "skill_proposed", "skill", skill_id, {"name": name, "version": version})
        conn.commit()
        row = conn.execute("SELECT * FROM brain_skills WHERE id=?", (skill_id,)).fetchone()
    return {"id": row["id"], "name": row["name"], "purpose": row["purpose"], "definition": json.loads(row["definition_json"]), "version": row["version"], "status": row["status"]}


def review_skill(owner_id: str, skill_id: str, decision: str) -> dict | None:
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")
    with _connect() as conn:
        row = conn.execute("SELECT * FROM brain_skills WHERE owner_id=? AND id=?", (owner_id, skill_id)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE brain_skills SET status=?,updated_at=? WHERE owner_id=? AND id=?", (decision, now_iso(), owner_id, skill_id))
        _audit(conn, owner_id, "skill_" + decision, "skill", skill_id, {"version": row["version"]})
        conn.commit()
        return {"id": row["id"], "name": row["name"], "version": row["version"], "status": decision}


def create_proposal(owner_id: str, title: str, summary: str, proposal: dict) -> dict:
    if not title.strip() or not summary.strip() or len(title) > 120 or len(summary) > 1500:
        raise ValueError("Proposal title/summary is invalid")
    safe = {key: proposal[key] for key in ("kind", "target", "rationale", "validation_plan", "rollback_plan") if key in proposal}
    proposal_id = uuid.uuid4().hex
    with _connect() as conn:
        _ensure_settings(conn, owner_id)
        conn.execute("INSERT INTO brain_proposals(id,owner_id,title,summary,proposal_json,status,created_at) VALUES(?,?,?,?,?,'pending',?)",
                     (proposal_id, owner_id, title.strip(), summary.strip(), json.dumps(safe, ensure_ascii=False), now_iso()))
        _audit(conn, owner_id, "improvement_proposed", "proposal", proposal_id)
        conn.commit()
    return {"id": proposal_id, "title": title.strip(), "summary": summary.strip(), "proposal": safe, "status": "pending"}


def list_proposals(owner_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM brain_proposals WHERE owner_id=? ORDER BY created_at DESC LIMIT 100", (owner_id,)).fetchall()
    return [{"id": r["id"], "title": r["title"], "summary": r["summary"], "proposal": json.loads(r["proposal_json"]),
             "status": r["status"], "created_at": r["created_at"], "reviewed_at": r["reviewed_at"]} for r in rows]


def review_proposal(owner_id: str, proposal_id: str, decision: str) -> dict | None:
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")
    with _connect() as conn:
        row = conn.execute("SELECT * FROM brain_proposals WHERE owner_id=? AND id=?", (owner_id, proposal_id)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE brain_proposals SET status=?,reviewed_at=? WHERE owner_id=? AND id=?", (decision, now_iso(), owner_id, proposal_id))
        _audit(conn, owner_id, "proposal_" + decision, "proposal", proposal_id)
        conn.commit()
        return {"id": row["id"], "title": row["title"], "status": decision}


def audit_log(owner_id: str, limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM brain_audit WHERE owner_id=? ORDER BY created_at DESC LIMIT ?", (owner_id, min(max(limit, 1), 200))).fetchall()
    return [{"id": r["id"], "action": r["action"], "item_type": r["item_type"], "item_id": r["item_id"],
             "detail": json.loads(r["detail_json"]), "created_at": r["created_at"]} for r in rows]


def overview(owner_id: str) -> dict:
    settings = get_settings(owner_id)
    with _connect() as conn:
        _ensure_settings(conn, owner_id)
        conn.execute("DELETE FROM brain_memories WHERE owner_id=? AND expires_at IS NOT NULL AND expires_at < ?", (owner_id, now_iso()))
        counts = {
            "memories": conn.execute("SELECT COUNT(*) FROM brain_memories WHERE owner_id=?", (owner_id,)).fetchone()[0],
            "verified_memories": conn.execute("SELECT COUNT(*) FROM brain_memories WHERE owner_id=? AND verification IN ('verified','user_confirmed') AND stale=0", (owner_id,)).fetchone()[0],
            "outcomes": conn.execute("SELECT COUNT(*) FROM brain_outcomes WHERE owner_id=?", (owner_id,)).fetchone()[0],
            "skills": conn.execute("SELECT COUNT(*) FROM brain_skills WHERE owner_id=?", (owner_id,)).fetchone()[0] + len(BUILTIN_SKILLS),
            "pending_proposals": conn.execute("SELECT COUNT(*) FROM brain_proposals WHERE owner_id=? AND status='pending'", (owner_id,)).fetchone()[0],
            "devices": conn.execute("SELECT COUNT(*) FROM brain_devices WHERE owner_id=?", (owner_id,)).fetchone()[0],
            "storage_bytes": conn.execute("SELECT COALESCE(SUM(LENGTH(content)),0) FROM brain_memories WHERE owner_id=?", (owner_id,)).fetchone()[0],
        }
        conn.commit()
    return {"service": "NOX Brain", "status": "ready" if settings["enabled"] else "disabled",
            "settings": settings, "counts": counts,
            "capabilities": {"persistent_memory": True, "keyword_retrieval": True, "semantic_vectors": False,
                             "automatic_model_weight_training": False, "automatic_code_mutation": False,
                             "cross_device_sync": False, "device_data_scope": "explicit allowlisted capability metadata only"}}
