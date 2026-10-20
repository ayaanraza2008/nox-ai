"""Consent-based NOX location sharing backed by PostgreSQL.

Location is only uploaded by an enrolled device while its owner has explicitly
enabled sharing and the consent window has not expired. Phone numbers are not
used to infer coordinates.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

_RETENTION_DAYS = max(1, min(int(os.getenv("NOX_LOCATION_RETENTION_DAYS", "7")), 90))
_RATE_BUCKETS: dict[str, list[float]] = {}


def _db_url() -> str:
    value = (os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not value.startswith(("postgres://", "postgresql://")):
        raise HTTPException(status_code=503, detail="Location sharing requires a persistent PostgreSQL database.")
    return value


def _connect():
    try:
        return psycopg.connect(_db_url(), row_factory=dict_row, connect_timeout=8)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Location database is unavailable; no location was changed.") from exc


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _context(conn, owner_id: str | None = None, *, ingest: bool = False,
             enroll: bool = False, accept_invite: bool = False):
    conn.execute("SELECT set_config('app.nox_user_id', %s, true)", (owner_id or "",))
    conn.execute("SELECT set_config('app.nox_ingest', %s, true)", ("true" if ingest else "false",))
    conn.execute("SELECT set_config('app.nox_enroll', %s, true)", ("true" if enroll else "false",))
    conn.execute("SELECT set_config('app.nox_invite_accept', %s, true)", ("true" if accept_invite else "false",))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat() if value else None


def rate_limit(key: str, limit: int = 12, window_seconds: int = 60) -> None:
    """Small per-process abuse guard; use a shared gateway limiter for multi-instance production."""
    now = time.monotonic()
    bucket = [stamp for stamp in _RATE_BUCKETS.get(key, []) if now - stamp < window_seconds]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Too many location setup requests. Wait briefly and retry.")
    bucket.append(now)
    _RATE_BUCKETS[key] = bucket


def create_enrollment_code(owner_id: str, label: str = "NOX device") -> dict:
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = _now() + timedelta(minutes=5)
    with _connect() as conn:
        _context(conn, owner_id)
        conn.execute("DELETE FROM nox_location_enrollment_codes WHERE expires_at < now() OR used_at IS NOT NULL")
        conn.execute(
            "INSERT INTO nox_location_enrollment_codes(id, owner_id, code_hash, label, expires_at) VALUES(%s,%s,%s,%s,%s)",
            (str(uuid.uuid4()), owner_id, _hash(code), label[:80], expires),
        )
    return {"code": code, "expires_at": _iso(expires), "expires_in_seconds": 300}


def enroll_mobile_device(code: str, label: str, platform: str) -> dict:
    if platform not in {"android", "ios"}:
        raise HTTPException(status_code=422, detail="Platform must be android or ios.")
    token = secrets.token_urlsafe(40)
    with _connect() as conn:
        _context(conn, enroll=True)
        enrollment = conn.execute(
            """SELECT * FROM nox_location_enrollment_codes
               WHERE code_hash=%s AND used_at IS NULL AND expires_at > now()
               FOR UPDATE""",
            (_hash(code),),
        ).fetchone()
        if not enrollment:
            raise HTTPException(status_code=400, detail="Enrollment code is invalid, expired, or already used.")
        owner_id = enrollment["owner_id"]
        _context(conn, owner_id)
        device_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO nox_location_devices
               (id, owner_id, label, platform, token_hash, sharing_enabled, created_at, updated_at)
               VALUES(%s,%s,%s,%s,%s,false,now(),now())""",
            (device_id, owner_id, label.strip()[:80] or "NOX device", platform, _hash(token)),
        )
        conn.execute("UPDATE nox_location_enrollment_codes SET used_at=now() WHERE id=%s", (enrollment["id"],))
    return {"device_id": device_id, "device_token": token, "sharing_enabled": False,
            "message": "Device enrolled. The owner must explicitly enable sharing in NOX."}


def status_fields(item: dict, now: datetime | None = None) -> dict:
    """Derive honest online/stale state without treating old coordinates as live."""
    now = now or _now()
    seen = item.get("last_seen_at")
    location_at = item.get("last_location_at")
    consent_end = item.get("consent_expires_at")
    item["online"] = bool(seen and now - seen <= timedelta(minutes=2))
    item["location_stale"] = not location_at or now - location_at > timedelta(minutes=2)
    item["sharing_active"] = bool(item.get("sharing_enabled") and consent_end and consent_end > now)
    if not item["sharing_active"] and not item.get("is_owner"):
        item["latitude"] = item["longitude"] = item["accuracy_m"] = None
        item["location_stale"] = True
    return item


def list_devices(owner_id: str) -> dict:
    with _connect() as conn:
        _context(conn, owner_id)
        rows = conn.execute(
            """SELECT d.id, d.owner_id, d.label, d.platform, d.sharing_enabled,
                      d.consent_expires_at, d.last_seen_at, d.last_location_at,
                      d.latitude, d.longitude, d.accuracy_m, d.created_at,
                      CASE WHEN d.owner_id=%s THEN true ELSE false END AS is_owner,
                      CASE WHEN d.owner_id=%s THEN NULL ELSE (
                        SELECT sh.id FROM nox_location_shares sh
                        WHERE sh.owner_id=d.owner_id AND sh.viewer_id=%s
                          AND sh.status='active' AND sh.expires_at>now() LIMIT 1
                      ) END AS share_id
               FROM nox_location_devices d
               WHERE d.revoked_at IS NULL AND (
                   d.owner_id=%s OR EXISTS (
                     SELECT 1 FROM nox_location_shares sh
                     WHERE sh.owner_id=d.owner_id AND sh.viewer_id=%s AND sh.status='active'
                       AND sh.expires_at > now()
                   )
               )
               ORDER BY d.updated_at DESC LIMIT 100""",
            (owner_id, owner_id, owner_id, owner_id, owner_id),
        ).fetchall()
    now = _now()
    devices = []
    for row in rows:
        item = dict(row)
        seen = item.get("last_seen_at")
        location_at = item.get("last_location_at")
        consent_end = item.get("consent_expires_at")
        item["last_seen_at"] = _iso(seen)
        item["last_location_at"] = _iso(location_at)
        item["consent_expires_at"] = _iso(consent_end)
        item["created_at"] = _iso(item.get("created_at"))
        devices.append(status_fields(item, now))
    return {"devices": devices, "retention_days": _RETENTION_DAYS,
            "freshness_threshold_seconds": 120}


def set_sharing(owner_id: str, device_id: str, enabled: bool, expires_hours: int = 24) -> dict:
    if enabled and not 1 <= expires_hours <= 168:
        raise HTTPException(status_code=422, detail="Sharing expiry must be between 1 and 168 hours.")
    with _connect() as conn:
        _context(conn, owner_id)
        row = conn.execute(
            "SELECT id FROM nox_location_devices WHERE id=%s AND owner_id=%s AND revoked_at IS NULL FOR UPDATE",
            (device_id, owner_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Device not found for this account.")
        expiry = _now() + timedelta(hours=expires_hours) if enabled else _now()
        conn.execute(
            "UPDATE nox_location_devices SET sharing_enabled=%s, consent_expires_at=%s, updated_at=now() WHERE id=%s AND owner_id=%s",
            (enabled, expiry, device_id, owner_id),
        )
    return {"device_id": device_id, "sharing_enabled": enabled, "consent_expires_at": _iso(expiry)}


def revoke_device(owner_id: str, device_id: str) -> dict:
    with _connect() as conn:
        _context(conn, owner_id)
        result = conn.execute(
            """UPDATE nox_location_devices SET sharing_enabled=false, revoked_at=now(),
                      token_hash=%s, updated_at=now()
               WHERE id=%s AND owner_id=%s AND revoked_at IS NULL""",
            (_hash(secrets.token_urlsafe(40)), device_id, owner_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Device not found for this account.")
    return {"device_id": device_id, "revoked": True}


def create_invitation(inviter_id: str) -> dict:
    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(hours=24)
    invitation_id = str(uuid.uuid4())
    with _connect() as conn:
        _context(conn, inviter_id)
        conn.execute(
            """INSERT INTO nox_location_invites(id, inviter_id, token_hash, status, created_at, expires_at)
               VALUES(%s,%s,%s,'pending',now(),%s)""",
            (invitation_id, inviter_id, _hash(token), expires),
        )
    base = os.getenv("NOX_PUBLIC_BASE_URL", "https://nox-ai-vcqx.onrender.com").rstrip("/")
    return {"invitation_id": invitation_id, "invite_url": f"{base}/?location_invite={token}",
            "expires_at": _iso(expires), "note": "Share this link with the recipient. They must sign in and explicitly accept."}


def accept_invitation(recipient_id: str, token: str) -> dict:
    with _connect() as conn:
        _context(conn, recipient_id, accept_invite=True)
        invite = conn.execute(
            """SELECT * FROM nox_location_invites WHERE token_hash=%s AND status='pending'
               AND expires_at > now() FOR UPDATE""",
            (_hash(token),),
        ).fetchone()
        if not invite:
            raise HTTPException(status_code=400, detail="Invitation is invalid, expired, or already used.")
        if invite["inviter_id"] == recipient_id:
            raise HTTPException(status_code=400, detail="You cannot accept your own invitation.")
        # Keep invite-accept context enabled so RLS permits marking this invite accepted.
        share_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO nox_location_shares(id, owner_id, viewer_id, status, created_at, expires_at)
               VALUES(%s,%s,%s,'active',now(),%s)
               ON CONFLICT(owner_id, viewer_id) DO UPDATE SET status='active', expires_at=EXCLUDED.expires_at, revoked_at=NULL""",
            (share_id, recipient_id, invite["inviter_id"], _now() + timedelta(days=30)),
        )
        conn.execute("UPDATE nox_location_invites SET status='accepted', accepted_by=%s, accepted_at=now() WHERE id=%s",
                     (recipient_id, invite["id"]))
    return {"accepted": True, "sharing_enabled": False,
            "message": "Invitation accepted. Select a device and explicitly enable location sharing to share coordinates."}


def revoke_share(owner_id: str, share_id: str) -> dict:
    with _connect() as conn:
        _context(conn, owner_id)
        result = conn.execute(
            """UPDATE nox_location_shares SET status='revoked', revoked_at=now()
               WHERE id=%s AND (owner_id=%s OR viewer_id=%s) AND status='active'""",
            (share_id, owner_id, owner_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Active location share not found.")
    return {"share_id": share_id, "revoked": True}


def mobile_status(token: str) -> dict:
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Device location token required.")
    with _connect() as conn:
        _context(conn, ingest=True)
        row = conn.execute(
            "SELECT id, sharing_enabled, consent_expires_at, revoked_at FROM nox_location_devices WHERE token_hash=%s",
            (_hash(token),),
        ).fetchone()
        if not row or row.get("revoked_at"):
            raise HTTPException(status_code=401, detail="Device token is invalid or revoked.")
    now = _now()
    active = bool(row["sharing_enabled"] and row["consent_expires_at"] and row["consent_expires_at"] > now)
    return {"device_id": row["id"], "sharing_enabled": active,
            "consent_expires_at": _iso(row["consent_expires_at"]),
            "poll_after_seconds": 30}


def update_location(token: str, latitude: float, longitude: float, accuracy_m: float,
                    captured_at: datetime | None = None) -> dict:
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Device location token required.")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=422, detail="Latitude or longitude is outside valid bounds.")
    if not (0 <= accuracy_m <= 10000):
        raise HTTPException(status_code=422, detail="Accuracy must be between 0 and 10000 metres.")
    now = _now()
    captured = captured_at or now
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    if abs((now - captured).total_seconds()) > 300:
        raise HTTPException(status_code=422, detail="Location timestamp is too old or too far in the future.")
    with _connect() as conn:
        _context(conn, ingest=True)
        device = conn.execute(
            "SELECT * FROM nox_location_devices WHERE token_hash=%s AND revoked_at IS NULL FOR UPDATE",
            (_hash(token),),
        ).fetchone()
        if not device:
            raise HTTPException(status_code=401, detail="Invalid or revoked device token.")
        owner_id = device["owner_id"]
        _context(conn, owner_id, ingest=True)
        if not device["sharing_enabled"] or not device["consent_expires_at"] or device["consent_expires_at"] <= now:
            raise HTTPException(status_code=403, detail="Location sharing is paused or consent has expired.")
        last = device.get("last_location_at")
        if last and (now - last).total_seconds() < 5:
            raise HTTPException(status_code=429, detail="Location updates are limited to one every five seconds.")
        conn.execute(
            """UPDATE nox_location_devices SET latitude=%s, longitude=%s, accuracy_m=%s,
                   last_location_at=%s, last_seen_at=now(), updated_at=now() WHERE id=%s""",
            (latitude, longitude, accuracy_m, captured, device["id"]),
        )
        conn.execute(
            """INSERT INTO nox_location_history(id, device_id, owner_id, latitude, longitude, accuracy_m, captured_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            (str(uuid.uuid4()), device["id"], owner_id, latitude, longitude, accuracy_m, captured),
        )
        conn.execute("DELETE FROM nox_location_history WHERE captured_at < now() - (%s * interval '1 day')", (_RETENTION_DAYS,))
    return {"accepted": True, "captured_at": _iso(captured), "server_received_at": _iso(now)}


def get_history(owner_id: str, device_id: str, limit: int = 100) -> dict:
    limit = max(1, min(int(limit), 500))
    with _connect() as conn:
        _context(conn, owner_id)
        device = conn.execute(
            """SELECT d.id, d.owner_id FROM nox_location_devices d
               WHERE d.id=%s AND d.revoked_at IS NULL AND (
                 d.owner_id=%s OR EXISTS (SELECT 1 FROM nox_location_shares s
                   WHERE s.owner_id=d.owner_id AND s.viewer_id=%s AND s.status='active' AND s.expires_at>now())
               )""",
            (device_id, owner_id, owner_id),
        ).fetchone()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found or sharing access is not active.")
        if device["owner_id"] != owner_id:
            share = conn.execute("SELECT 1 FROM nox_location_shares WHERE owner_id=%s AND viewer_id=%s AND status='active' AND expires_at>now()",
                                 (device["owner_id"], owner_id)).fetchone()
            if not share:
                raise HTTPException(status_code=403, detail="Location access has been revoked.")
        rows = conn.execute(
            """SELECT latitude, longitude, accuracy_m, captured_at FROM nox_location_history
               WHERE device_id=%s AND owner_id=%s AND captured_at >= now() - (%s * interval '1 day')
               ORDER BY captured_at DESC LIMIT %s""",
            (device_id, device["owner_id"], _RETENTION_DAYS, limit),
        ).fetchall()
    return {"device_id": device_id, "retention_days": _RETENTION_DAYS,
            "points": [{"latitude": x["latitude"], "longitude": x["longitude"],
                        "accuracy_m": x["accuracy_m"], "captured_at": _iso(x["captured_at"])} for x in rows]}


def map_config() -> dict:
    raw = os.getenv("NOX_MAP_STYLE_URL", "").strip()
    parsed = urlsplit(raw) if raw else None
    valid = bool(parsed and parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password)
    return {"map_style_url": raw if valid else None, "configured": valid,
            "message": None if valid else "Set NOX_MAP_STYLE_URL to an HTTPS MapLibre-compatible style URL and configure its tile provider."}
