"""Durable email/password accounts for account-linked NOX Brain memory.

Accounts require PostgreSQL; the app deliberately refuses to create accounts on an
ephemeral SQLite filesystem. Passwords are PBKDF2 hashes and browser sessions are
opaque random tokens stored only as SHA-256 hashes.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

SESSION_DAYS = 30
PBKDF2_ITERATIONS = 310_000
_EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,253}\.[^\s@]{2,63}$")


def _database_url() -> str:
    value = (os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not value.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Account login requires a persistent PostgreSQL DATABASE_URL or SUPABASE_DB_URL.")
    return value


def _connect():
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(_database_url(), row_factory=dict_row, connect_timeout=10)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS nox_accounts (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS nox_account_sessions (
            token_hash TEXT PRIMARY KEY,
            account_id TEXT NOT NULL REFERENCES nox_accounts(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nox_account_sessions_account ON nox_account_sessions(account_id)")
        conn.commit()
        return conn
    except Exception:
        conn.rollback()
        conn.close()
        raise


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()


def _verify_password(password: str, salt_hex: str, expected: str) -> bool:
    try:
        actual = _hash_password(password, bytes.fromhex(salt_hex))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _new_session(conn, account_id: str) -> str:
    token = secrets.token_urlsafe(48)
    conn.execute(
        "INSERT INTO nox_account_sessions(token_hash,account_id,created_at,expires_at,revoked) VALUES(%s,%s,%s,%s,0)",
        (hashlib.sha256(token.encode()).hexdigest(), account_id, _iso(_now()), _iso(_now() + timedelta(days=SESSION_DAYS))),
    )
    return token


def register(email: str, password: str) -> dict:
    email = email.strip().casefold()
    if not _EMAIL.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    if len(password) < 10 or len(password) > 256:
        raise ValueError("Password must be 10–256 characters.")
    salt = secrets.token_bytes(16)
    account_id = uuid.uuid4().hex
    conn = _connect()
    try:
        existing = conn.execute("SELECT id FROM nox_accounts WHERE email=%s", (email,)).fetchone()
        if existing:
            raise ValueError("An account with this email already exists.")
        conn.execute(
            "INSERT INTO nox_accounts(id,email,password_salt,password_hash,created_at) VALUES(%s,%s,%s,%s,%s)",
            (account_id, email, salt.hex(), _hash_password(password, salt), _iso(_now())),
        )
        token = _new_session(conn, account_id)
        conn.commit()
        return {"account": {"id": account_id, "email": email}, "token": token}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def login(email: str, password: str) -> dict:
    email = email.strip().casefold()
    conn = _connect()
    try:
        account = conn.execute("SELECT * FROM nox_accounts WHERE email=%s", (email,)).fetchone()
        if not account or not _verify_password(password, account["password_salt"], account["password_hash"]):
            raise ValueError("Email or password is incorrect.")
        token = _new_session(conn, account["id"])
        conn.commit()
        return {"account": {"id": account["id"], "email": account["email"]}, "token": token}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def resolve_session(token: str) -> dict | None:
    if not token or len(token) > 256:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT a.id, a.email FROM nox_account_sessions s
               JOIN nox_accounts a ON a.id=s.account_id
               WHERE s.token_hash=%s AND s.revoked=0 AND s.expires_at>%s""",
            (hashlib.sha256(token.encode()).hexdigest(), _iso(_now())),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def logout(token: str) -> None:
    if not token:
        return
    conn = _connect()
    try:
        conn.execute("UPDATE nox_account_sessions SET revoked=1 WHERE token_hash=%s",
                     (hashlib.sha256(token.encode()).hexdigest(),))
        conn.commit()
    finally:
        conn.close()


def delete_account(token: str, password: str, confirmation: str) -> bool:
    if confirmation != "DELETE MY ACCOUNT":
        raise ValueError("Type DELETE MY ACCOUNT to confirm permanent deletion.")
    if not token:
        raise ValueError("Please log in again before deleting your account.")
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT a.* FROM nox_account_sessions s JOIN nox_accounts a ON a.id=s.account_id
               WHERE s.token_hash=%s AND s.revoked=0 AND s.expires_at>%s""",
            (hashlib.sha256(token.encode()).hexdigest(), _iso(_now())),
        ).fetchone()
        if not row or not _verify_password(password, row["password_salt"], row["password_hash"]):
            raise ValueError("Password confirmation failed.")
        account_id = row["id"]
        # Remove every Brain-owned record in the same PostgreSQL transaction.
        for table in ("brain_memories", "brain_devices", "brain_outcomes", "brain_skills", "brain_proposals", "brain_audit"):
            conn.execute(f"DELETE FROM {table} WHERE owner_id=%s", (account_id,))
        conn.execute("DELETE FROM brain_settings WHERE owner_id=%s", (account_id,))
        conn.execute("DELETE FROM nox_accounts WHERE id=%s", (account_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
