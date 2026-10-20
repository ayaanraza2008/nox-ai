"""Persistent NOX account authentication, verification, and recovery.

Requires PostgreSQL. Passwords use Argon2id for new accounts; legacy PBKDF2
hashes are upgraded after a successful login. OTPs and session tokens are never
stored in plaintext.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

SESSION_DAYS = 30
OTP_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
PBKDF2_ITERATIONS = 310_000
_EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,253}\.[^\s@]{2,63}$")
_USERNAME = re.compile(r"^[a-z0-9](?:[a-z0-9_]{1,18}[a-z0-9])?$")
_PHONE = re.compile(r"^[0-9]{10}$")
_PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)


def _database_url() -> str:
    value = (os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not value.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Account login requires a persistent PostgreSQL DATABASE_URL or SUPABASE_DB_URL.")
    return value


def _raw_connect():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(_database_url(), row_factory=dict_row, connect_timeout=10)


def _connect():
    conn = _raw_connect()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS nox_accounts (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_salt TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        # Additive migration: existing accounts and sessions are retained.
        migrations = (
            "ALTER TABLE nox_accounts ADD COLUMN IF NOT EXISTS full_name TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE nox_accounts ADD COLUMN IF NOT EXISTS username TEXT",
            "ALTER TABLE nox_accounts ADD COLUMN IF NOT EXISTS country_code TEXT NOT NULL DEFAULT '+91'",
            "ALTER TABLE nox_accounts ADD COLUMN IF NOT EXISTS phone_number TEXT",
            "ALTER TABLE nox_accounts ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE nox_accounts ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE nox_accounts ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending_verification'",
            "ALTER TABLE nox_accounts ADD COLUMN IF NOT EXISTS password_scheme TEXT NOT NULL DEFAULT 'pbkdf2'",
            "ALTER TABLE nox_accounts ADD COLUMN IF NOT EXISTS updated_at TEXT",
        )
        for statement in migrations:
            conn.execute(statement)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_nox_accounts_username ON nox_accounts(username) WHERE username IS NOT NULL")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_nox_accounts_phone ON nox_accounts(country_code, phone_number) WHERE phone_number IS NOT NULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS nox_account_sessions (
            token_hash TEXT PRIMARY KEY,
            account_id TEXT NOT NULL REFERENCES nox_accounts(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nox_account_sessions_account ON nox_account_sessions(account_id)")
        conn.execute("""CREATE TABLE IF NOT EXISTS nox_account_challenges (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL REFERENCES nox_accounts(id) ON DELETE CASCADE,
            purpose TEXT NOT NULL,
            destination TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            consumed_at TEXT
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nox_challenges_account ON nox_account_challenges(account_id, purpose, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nox_challenges_created ON nox_account_challenges(created_at)")
        conn.execute("""CREATE TABLE IF NOT EXISTS nox_account_rate_limits (
            action TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            window_start TEXT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY(action, key_hash)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nox_account_rate_limits_window ON nox_account_rate_limits(window_start)")
        # Reconcile only inconsistent rows; do not take a full-table write lock
        # on every authenticated request.
        conn.execute("""UPDATE nox_accounts SET status=CASE
            WHEN email_verified AND phone_verified THEN 'active'
            WHEN email_verified THEN 'email_verified'
            WHEN phone_verified THEN 'phone_verified'
            ELSE 'pending_verification' END
            WHERE status NOT IN ('suspended','deleted') AND status<>CASE
            WHEN email_verified AND phone_verified THEN 'active'
            WHEN email_verified THEN 'email_verified'
            WHEN phone_verified THEN 'phone_verified'
            ELSE 'pending_verification' END""")
        challenge_cutoff = _iso(datetime.now(timezone.utc) - timedelta(days=30))
        conn.execute("DELETE FROM nox_account_challenges WHERE created_at < %s", (challenge_cutoff,))
        conn.execute("DELETE FROM nox_account_rate_limits WHERE window_start < %s", (challenge_cutoff,))
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


def _public_account(row) -> dict:
    email_verified = bool(row.get("email_verified", False))
    phone_verified = bool(row.get("phone_verified", False))
    status = row.get("status") or _status(email_verified, phone_verified)
    return {
        "id": row["id"], "email": row["email"], "full_name": row.get("full_name") or "",
        "username": row.get("username") or "", "country_code": row.get("country_code") or "+91",
        "phone_number": row.get("phone_number") or "", "email_verified": email_verified,
        "phone_verified": phone_verified, "status": status,
        "profile_complete": bool(row.get("full_name") and row.get("username") and row.get("phone_number")),
        "verification_providers": {"email": _email_configured(), "sms": _sms_configured()},
    }


def _status(email_verified: bool, phone_verified: bool) -> str:
    if email_verified and phone_verified:
        return "active"
    if email_verified:
        return "email_verified"
    if phone_verified:
        return "phone_verified"
    return "pending_verification"


def _validate_profile(full_name: str, username: str, country_code: str, phone_number: str) -> tuple[str, str, str, str]:
    full_name = " ".join((full_name or "").split())
    username = (username or "").strip().lower()
    country_code = (country_code or "").strip()
    phone_number = (phone_number or "").strip()
    if not 2 <= len(full_name) <= 100:
        raise ValueError("Full name must be 2–100 characters.")
    if not _USERNAME.fullmatch(username) or len(username) > 20:
        raise ValueError("Username must be 3–20 lowercase letters, numbers, or underscores; it must start and end with a letter or number.")
    if not re.fullmatch(r"\+[1-9][0-9]{0,3}", country_code):
        raise ValueError("Select a valid country calling code.")
    if not _PHONE.fullmatch(phone_number):
        raise ValueError("Mobile number must contain exactly 10 digits.")
    return full_name, username, country_code, phone_number


def _hash_password(password: str, salt: bytes | None = None) -> str:
    """Legacy PBKDF2 helper retained for compatibility tests and old account hashes."""
    if salt is None:
        salt = secrets.token_bytes(16)
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()


def _verify_password(password: str, salt_hex: str, expected: str) -> bool:
    try:
        actual = _hash_password(password, bytes.fromhex(salt_hex))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _password_matches(account, password: str) -> bool:
    scheme = account.get("password_scheme") or "pbkdf2"
    if scheme == "argon2id" or str(account.get("password_hash", "")).startswith("$argon2id$"):
        try:
            return _PASSWORDS.verify(account["password_hash"], password)
        except (VerifyMismatchError, InvalidHashError, TypeError, ValueError):
            return False
    return _verify_password(password, account.get("password_salt") or "", account.get("password_hash") or "")


def _set_password(conn, account_id: str, password: str) -> None:
    conn.execute(
        "UPDATE nox_accounts SET password_salt='', password_hash=%s, password_scheme='argon2id', updated_at=%s WHERE id=%s",
        (_PASSWORDS.hash(password), _iso(_now()), account_id),
    )


def _new_session(conn, account_id: str, remember_me: bool = True) -> tuple[str, int]:
    token = secrets.token_urlsafe(48)
    days = SESSION_DAYS if remember_me else 1
    conn.execute(
        "INSERT INTO nox_account_sessions(token_hash,account_id,created_at,expires_at,revoked) VALUES(%s,%s,%s,%s,0)",
        (hashlib.sha256(token.encode()).hexdigest(), account_id, _iso(_now()), _iso(_now() + timedelta(days=days))),
    )
    return token, days * 86400


def _rate_limit(conn, action: str, key: str, max_count: int, window_seconds: int) -> None:
    """Persist rate-limit counters independently of the caller's rollback transaction."""
    key_hash = hashlib.sha256((action + ":" + (key or "unknown").casefold()).encode()).hexdigest()
    now = _now()
    cutoff = _iso(now - timedelta(seconds=window_seconds))
    rate_conn = _raw_connect()
    try:
        row = rate_conn.execute("""INSERT INTO nox_account_rate_limits(action,key_hash,window_start,count)
            VALUES(%s,%s,%s,1)
            ON CONFLICT(action,key_hash) DO UPDATE SET
              window_start=CASE WHEN nox_account_rate_limits.window_start <= %s
                                THEN EXCLUDED.window_start ELSE nox_account_rate_limits.window_start END,
              count=CASE WHEN nox_account_rate_limits.window_start <= %s
                         THEN 1 ELSE nox_account_rate_limits.count+1 END
            RETURNING count""",
            (action, key_hash, _iso(now), cutoff, cutoff)).fetchone()
        rate_conn.commit()
        if row and int(row["count"]) > max_count:
            raise ValueError("Too many attempts. Please wait before trying again.")
    except Exception:
        rate_conn.rollback()
        raise
    finally:
        rate_conn.close()


def _verification_secret() -> str:
    return os.getenv("NOX_VERIFICATION_SECRET") or _database_url()


def _code_hash(code: str) -> str:
    return hmac.new(_verification_secret().encode(), code.encode(), hashlib.sha256).hexdigest()


def _email_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM") and
                ((not os.getenv("SMTP_USER") and not os.getenv("SMTP_PASSWORD")) or
                 (os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))))


def _sms_configured() -> bool:
    return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN") and os.getenv("TWILIO_FROM_NUMBER"))


def provider_configured(channel: str) -> bool:
    if channel == "email":
        return _email_configured()
    if channel == "sms":
        return _sms_configured()
    return False


def _send_email(destination: str, subject: str, body: str) -> bool:
    if not _email_configured():
        return False
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = destination
    message["Subject"] = subject
    message.set_content(body)
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) as server:
            if user and password:
                server.login(user, password)
            server.send_message(message)
    else:
        if os.getenv("SMTP_STARTTLS", "true").lower() not in {"1", "true", "yes"}:
            raise RuntimeError("SMTP_STARTTLS must be enabled for secure email delivery.")
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls(context=ssl.create_default_context())
            if user and password:
                server.login(user, password)
            server.send_message(message)
    return True


def _send_sms(destination: str, body: str) -> bool:
    if not _sms_configured():
        return False
    sid = os.environ["TWILIO_ACCOUNT_SID"]
    url = "https://api.twilio.com/2010-04-01/Accounts/" + sid + "/Messages.json"
    response = httpx.post(url, data={"To": destination, "From": os.environ["TWILIO_FROM_NUMBER"], "Body": body},
                          auth=(sid, os.environ["TWILIO_AUTH_TOKEN"]), timeout=15)
    response.raise_for_status()
    return True


def _send_challenge(conn, account, purpose: str, channel: str, client_key: str = "") -> str:
    if channel == "email":
        if not _email_configured():
            return "setup_required"
        destination = account["email"]
    elif channel == "sms":
        if not account.get("phone_number"):
            return "profile_required"
        if not _sms_configured():
            return "setup_required"
        destination = (account.get("country_code") or "") + account["phone_number"]
    else:
        raise ValueError("Unsupported verification channel.")

    _rate_limit(conn, "send_" + purpose, (account["id"] + ":" + channel + ":" + client_key), 5, 3600)
    # Serialize sends for this account so concurrent requests cannot bypass cooldown.
    conn.execute("SELECT id FROM nox_accounts WHERE id=%s FOR UPDATE", (account["id"],))
    recent = conn.execute("""SELECT created_at FROM nox_account_challenges
        WHERE account_id=%s AND purpose=%s ORDER BY created_at DESC LIMIT 1""",
        (account["id"], purpose)).fetchone()
    if recent and datetime.fromisoformat(recent["created_at"]) > _now() - timedelta(seconds=RESEND_COOLDOWN_SECONDS):
        raise ValueError("Please wait before requesting another code.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge_id = uuid.uuid4().hex
    now = _now()
    conn.execute("""INSERT INTO nox_account_challenges
        (id,account_id,purpose,destination,code_hash,created_at,expires_at,attempts,consumed_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s,0,NULL)""",
        (challenge_id, account["id"], purpose, destination, _code_hash(code), _iso(now),
         _iso(now + timedelta(minutes=OTP_MINUTES))))
    try:
        if channel == "email":
            _send_email(destination, "Your NOX AI verification code",
                        f"Your NOX AI code is {code}. It expires in {OTP_MINUTES} minutes and can be used once. If you did not request it, ignore this email.")
        else:
            _send_sms(destination, f"Your NOX AI verification code is {code}. It expires in {OTP_MINUTES} minutes.")
    except Exception:
        conn.execute("UPDATE nox_account_challenges SET consumed_at=%s WHERE id=%s", (_iso(_now()), challenge_id))
        return "delivery_failed"
    return "sent"


def register(full_name: str, username: str, email: str, country_code: str, phone_number: str,
             password: str, client_key: str = "") -> dict:
    full_name, username, country_code, phone_number = _validate_profile(full_name, username, country_code, phone_number)
    email = (email or "").strip().casefold()
    if not _EMAIL.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    if len(password) < 10 or len(password) > 256:
        raise ValueError("Password must be 10–256 characters.")
    conn = _connect()
    try:
        _rate_limit(conn, "register", client_key or email, 5, 3600)
        existing = conn.execute("""SELECT id FROM nox_accounts
            WHERE email=%s OR username=%s OR (country_code=%s AND phone_number=%s)""",
            (email, username, country_code, phone_number)).fetchone()
        if existing:
            raise ValueError("An account already exists with one of those details.")
        account_id = uuid.uuid4().hex
        now = _iso(_now())
        conn.execute("""INSERT INTO nox_accounts
            (id,email,password_salt,password_hash,created_at,full_name,username,country_code,phone_number,
             email_verified,phone_verified,status,password_scheme,updated_at)
            VALUES(%s,%s,'',%s,%s,%s,%s,%s,%s,FALSE,FALSE,'pending_verification','argon2id',%s)""",
            (account_id, email, _PASSWORDS.hash(password), now, full_name, username, country_code, phone_number, now))
        token, max_age = _new_session(conn, account_id, True)
        account = conn.execute("SELECT * FROM nox_accounts WHERE id=%s", (account_id,)).fetchone()
        email_delivery = _send_challenge(conn, account, "email_verify", "email", client_key)
        phone_delivery = _send_challenge(conn, account, "phone_verify", "sms", client_key)
        conn.commit()
        return {"account": _public_account(account), "token": token, "max_age": max_age,
                "delivery": {"email": email_delivery, "phone": phone_delivery}}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def login(identifier: str, password: str, country_code: str = "+91", client_key: str = "",
          remember_me: bool = True) -> dict:
    identifier = (identifier or "").strip()
    if not identifier or len(identifier) > 320 or not password or len(password) > 256:
        raise ValueError("Username/email/mobile or password is incorrect.")
    conn = _connect()
    try:
        _rate_limit(conn, "login", (client_key + ":" + identifier.casefold()), 10, 900)
        if "@" in identifier:
            row = conn.execute("SELECT * FROM nox_accounts WHERE email=%s", (identifier.casefold(),)).fetchone()
        elif identifier.isdigit():
            if not re.fullmatch(r"[0-9]{10}", identifier) or not re.fullmatch(r"\+[1-9][0-9]{0,3}", country_code or ""):
                row = None
            else:
                row = conn.execute("SELECT * FROM nox_accounts WHERE country_code=%s AND phone_number=%s",
                                   (country_code, identifier)).fetchone()
        else:
            row = conn.execute("SELECT * FROM nox_accounts WHERE username=%s", (identifier.lower(),)).fetchone()
        if not row or row.get("status") == "suspended" or not _password_matches(row, password):
            raise ValueError("Username/email/mobile or password is incorrect.")
        if row.get("status") == "deleted":
            raise ValueError("This account is unavailable.")
        if row.get("password_scheme") != "argon2id" or not str(row.get("password_hash", "")).startswith("$argon2id$"):
            _set_password(conn, row["id"], password)
        token, max_age = _new_session(conn, row["id"], remember_me)
        conn.commit()
        fresh = dict(row)
        fresh["password_hash"] = ""
        fresh["password_salt"] = ""
        fresh["password_scheme"] = "argon2id"
        return {"account": _public_account(fresh), "token": token, "max_age": max_age}
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
        row = conn.execute("""SELECT a.id,a.email,a.full_name,a.username,a.country_code,a.phone_number,
            a.email_verified,a.phone_verified,a.status
            FROM nox_account_sessions s JOIN nox_accounts a ON a.id=s.account_id
            WHERE s.token_hash=%s AND s.revoked=0 AND s.expires_at>%s""",
            (hashlib.sha256(token.encode()).hexdigest(), _iso(_now()))).fetchone()
        return _public_account(row) if row else None
    finally:
        conn.close()


def verify_code(token: str, purpose: str, channel: str, code: str) -> dict:
    if not re.fullmatch(r"[0-9]{6}", code or ""):
        raise ValueError("Enter the six-digit code.")
    if purpose not in {"email_verify", "phone_verify", "password_reset_email", "password_reset_phone"}:
        raise ValueError("Unsupported verification purpose.")
    conn = _connect()
    try:
        session = conn.execute("""SELECT a.* FROM nox_account_sessions s JOIN nox_accounts a ON a.id=s.account_id
            WHERE s.token_hash=%s AND s.revoked=0 AND s.expires_at>%s""",
            (hashlib.sha256((token or "").encode()).hexdigest(), _iso(_now()))).fetchone()
        if not session:
            raise ValueError("Please sign in again.")
        expected_purpose = ("email_verify" if channel == "email" else "phone_verify") if purpose.endswith("_verify") else purpose
        challenge = conn.execute("""SELECT * FROM nox_account_challenges
            WHERE account_id=%s AND purpose=%s AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1 FOR UPDATE""",
            (session["id"], expected_purpose)).fetchone()
        if not challenge:
            raise ValueError("No active code found. Request a new code.")
        if datetime.fromisoformat(challenge["expires_at"]) <= _now():
            conn.execute("UPDATE nox_account_challenges SET consumed_at=%s WHERE id=%s", (_iso(_now()), challenge["id"]))
            conn.commit()
            raise ValueError("This code has expired. Request a new one.")
        if int(challenge["attempts"]) >= OTP_MAX_ATTEMPTS:
            raise ValueError("Too many incorrect attempts. Request a new code.")
        if not hmac.compare_digest(challenge["code_hash"], _code_hash(code)):
            conn.execute("UPDATE nox_account_challenges SET attempts=attempts+1 WHERE id=%s", (challenge["id"],))
            conn.commit()
            raise ValueError("Incorrect code. Check it and try again.")
        now = _iso(_now())
        conn.execute("UPDATE nox_account_challenges SET consumed_at=%s WHERE id=%s", (now, challenge["id"]))
        if purpose.endswith("_verify"):
            column = "email_verified" if channel == "email" else "phone_verified"
            conn.execute(f"UPDATE nox_accounts SET {column}=TRUE,updated_at=%s WHERE id=%s", (now, session["id"]))
            conn.execute("""UPDATE nox_accounts SET status=CASE
                WHEN email_verified AND phone_verified THEN 'active'
                WHEN email_verified THEN 'email_verified'
                WHEN phone_verified THEN 'phone_verified'
                ELSE 'pending_verification' END WHERE id=%s AND status<>'suspended'""", (session["id"],))
        conn.commit()
        updated = conn.execute("SELECT * FROM nox_accounts WHERE id=%s", (session["id"],)).fetchone()
        return _public_account(updated)
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        conn.close()


def resend_verification(token: str, channel: str, client_key: str = "") -> str:
    if channel not in {"email", "sms"}:
        raise ValueError("Choose email or mobile verification.")
    conn = _connect()
    try:
        row = conn.execute("""SELECT a.* FROM nox_account_sessions s JOIN nox_accounts a ON a.id=s.account_id
            WHERE s.token_hash=%s AND s.revoked=0 AND s.expires_at>%s""",
            (hashlib.sha256((token or "").encode()).hexdigest(), _iso(_now()))).fetchone()
        if not row:
            raise ValueError("Please sign in again.")
        if row.get("status") == "suspended":
            raise ValueError("This account is suspended. Contact NOX support.")
        if channel == "email" and row["email_verified"]:
            return "already_verified"
        if channel == "sms" and row["phone_verified"]:
            return "already_verified"
        purpose = "email_verify" if channel == "email" else "phone_verify"
        result = _send_challenge(conn, row, purpose, channel, client_key)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def request_recovery(identifier: str, channel: str, country_code: str = "+91", client_key: str = "") -> str:
    """Always returns the same public response to avoid account enumeration."""
    conn = None
    try:
        conn = _connect()
        _rate_limit(conn, "recovery", (client_key + ":" + (identifier or "").casefold()), 5, 3600)
        row = None
        value = (identifier or "").strip()
        if channel == "email" and _EMAIL.fullmatch(value.casefold()):
            row = conn.execute("SELECT * FROM nox_accounts WHERE email=%s", (value.casefold(),)).fetchone()
        elif channel == "sms" and _PHONE.fullmatch(value) and re.fullmatch(r"\+[1-9][0-9]{0,3}", country_code or ""):
            row = conn.execute("SELECT * FROM nox_accounts WHERE country_code=%s AND phone_number=%s",
                               (country_code, value)).fetchone()
        if row and row.get("status") not in {"suspended", "deleted"}:
            _send_challenge(conn, row, "password_reset_email" if channel == "email" else "password_reset_phone",
                            channel, client_key)
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        # Do not reveal existence, delivery configuration, or provider failures.
    finally:
        if conn:
            conn.close()
    return "If a matching account exists and this channel is configured, a recovery code will be sent."


def reset_password(identifier: str, channel: str, country_code: str, code: str, new_password: str,
                   client_key: str = "") -> bool:
    if len(new_password) < 10 or len(new_password) > 256:
        raise ValueError("Password must be 10–256 characters.")
    if channel not in {"email", "sms"} or not re.fullmatch(r"[0-9]{6}", code or ""):
        raise ValueError("Enter a valid recovery code.")
    value = (identifier or "").strip()
    conn = _connect()
    try:
        _rate_limit(conn, "reset_password", (client_key + ":" + value.casefold()), 8, 900)
        if channel == "email":
            row = conn.execute("SELECT * FROM nox_accounts WHERE email=%s", (value.casefold(),)).fetchone()
            purpose = "password_reset_email"
        else:
            row = conn.execute("SELECT * FROM nox_accounts WHERE country_code=%s AND phone_number=%s",
                               (country_code, value)).fetchone()
            purpose = "password_reset_phone"
        if not row:
            raise ValueError("The code or account details are invalid or expired. Request a new code.")
        challenge = conn.execute("""SELECT * FROM nox_account_challenges WHERE account_id=%s AND purpose=%s
            AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1 FOR UPDATE""", (row["id"], purpose)).fetchone()
        if not challenge or datetime.fromisoformat(challenge["expires_at"]) <= _now() or int(challenge["attempts"]) >= OTP_MAX_ATTEMPTS:
            raise ValueError("The code or account details are invalid or expired. Request a new code.")
        if not hmac.compare_digest(challenge["code_hash"], _code_hash(code)):
            conn.execute("UPDATE nox_account_challenges SET attempts=attempts+1 WHERE id=%s", (challenge["id"],))
            conn.commit()
            raise ValueError("The code or account details are invalid or expired. Request a new code.")
        _set_password(conn, row["id"], new_password)
        conn.execute("UPDATE nox_account_challenges SET consumed_at=%s WHERE id=%s", (_iso(_now()), challenge["id"]))
        conn.execute("UPDATE nox_account_sessions SET revoked=1 WHERE account_id=%s", (row["id"],))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_profile(token: str, full_name: str, username: str, country_code: str, phone_number: str,
                   password: str, client_key: str = "") -> dict:
    full_name, username, country_code, phone_number = _validate_profile(full_name, username, country_code, phone_number)
    conn = _connect()
    try:
        row = conn.execute("""SELECT a.* FROM nox_account_sessions s JOIN nox_accounts a ON a.id=s.account_id
            WHERE s.token_hash=%s AND s.revoked=0 AND s.expires_at>%s""",
            (hashlib.sha256((token or "").encode()).hexdigest(), _iso(_now()))).fetchone()
        if not row or not _password_matches(row, password):
            raise ValueError("Password confirmation failed.")
        if row.get("status") == "suspended":
            raise ValueError("This account is suspended. Contact NOX support.")
        _rate_limit(conn, "profile_update", row["id"] + ":" + client_key, 5, 3600)
        if username != row.get("username") or country_code != row.get("country_code") or phone_number != row.get("phone_number"):
            collision = conn.execute("""SELECT id FROM nox_accounts WHERE id<>%s AND
                (username=%s OR (country_code=%s AND phone_number=%s))""",
                (row["id"], username, country_code, phone_number)).fetchone()
            if collision:
                raise ValueError("That username or mobile number is already in use.")
        phone_changed = country_code != row.get("country_code") or phone_number != row.get("phone_number")
        conn.execute("""UPDATE nox_accounts SET full_name=%s,username=%s,country_code=%s,phone_number=%s,
            phone_verified=CASE WHEN %s THEN FALSE ELSE phone_verified END,updated_at=%s WHERE id=%s""",
            (full_name, username, country_code, phone_number, phone_changed, _iso(_now()), row["id"]))
        if phone_changed:
            conn.execute("UPDATE nox_accounts SET status=CASE WHEN email_verified THEN 'email_verified' ELSE 'pending_verification' END WHERE id=%s",
                         (row["id"],))
            # Revoke other sessions after a sensitive contact change; keep current for onboarding.
            conn.execute("UPDATE nox_account_sessions SET revoked=1 WHERE account_id=%s AND token_hash<>%s",
                         (row["id"], hashlib.sha256(token.encode()).hexdigest()))
        fresh = conn.execute("SELECT * FROM nox_accounts WHERE id=%s", (row["id"],)).fetchone()
        delivery = _send_challenge(conn, fresh, "phone_verify", "sms", client_key) if phone_changed else "unchanged"
        conn.commit()
        return {"account": _public_account(fresh), "phone_delivery": delivery}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



def update_email(token: str, email: str, password: str, client_key: str = "") -> dict:
    email = (email or "").strip().casefold()
    if not _EMAIL.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    conn = _connect()
    try:
        row = conn.execute("""SELECT a.* FROM nox_account_sessions s JOIN nox_accounts a ON a.id=s.account_id
            WHERE s.token_hash=%s AND s.revoked=0 AND s.expires_at>%s""",
            (hashlib.sha256((token or "").encode()).hexdigest(), _iso(_now()))).fetchone()
        if not row or not _password_matches(row, password):
            raise ValueError("Password confirmation failed.")
        if row.get("status") == "suspended":
            raise ValueError("This account is suspended. Contact NOX support.")
        if email == row["email"]:
            return {"account": _public_account(row), "email_delivery": "unchanged"}
        collision = conn.execute("SELECT id FROM nox_accounts WHERE email=%s AND id<>%s", (email, row["id"])).fetchone()
        if collision:
            raise ValueError("That email address is already in use.")
        _rate_limit(conn, "email_update", row["id"] + ":" + client_key, 3, 3600)
        now = _iso(_now())
        conn.execute("UPDATE nox_accounts SET email=%s,email_verified=FALSE,status=CASE WHEN phone_verified THEN 'phone_verified' ELSE 'pending_verification' END,updated_at=%s WHERE id=%s",
                     (email, now, row["id"]))
        conn.execute("UPDATE nox_account_challenges SET consumed_at=%s WHERE account_id=%s AND purpose='email_verify' AND consumed_at IS NULL",
                     (now, row["id"]))
        conn.execute("UPDATE nox_account_sessions SET revoked=1 WHERE account_id=%s AND token_hash<>%s",
                     (row["id"], hashlib.sha256(token.encode()).hexdigest()))
        fresh = conn.execute("SELECT * FROM nox_accounts WHERE id=%s", (row["id"],)).fetchone()
        delivery = _send_challenge(conn, fresh, "email_verify", "email", client_key)
        conn.commit()
        return {"account": _public_account(fresh), "email_delivery": delivery}
    except Exception:
        conn.rollback()
        raise
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


def logout_other_sessions(token: str) -> int:
    if not token or len(token) > 256:
        raise ValueError("Please sign in again before managing sessions.")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = _connect()
    try:
        row = conn.execute("""SELECT s.account_id FROM nox_account_sessions s
            JOIN nox_accounts a ON a.id=s.account_id
            WHERE s.token_hash=%s AND s.revoked=0 AND s.expires_at>%s""",
            (token_hash, _iso(_now()))).fetchone()
        if not row:
            raise ValueError("Account session expired. Please sign in again.")
        cursor = conn.execute("""UPDATE nox_account_sessions SET revoked=1
            WHERE account_id=%s AND token_hash<>%s AND revoked=0 AND expires_at>%s""",
            (row["account_id"], token_hash, _iso(_now())))
        revoked = max(0, int(cursor.rowcount or 0))
        conn.commit()
        return revoked
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_account(token: str, password: str, confirmation: str) -> bool:
    from backend import brain
    schema_conn = brain._connect()
    schema_conn.close()
    if confirmation != "DELETE MY ACCOUNT":
        raise ValueError("Type DELETE MY ACCOUNT to confirm permanent deletion.")
    if not token:
        raise ValueError("Please log in again before deleting your account.")
    conn = _connect()
    try:
        row = conn.execute("""SELECT a.* FROM nox_account_sessions s JOIN nox_accounts a ON a.id=s.account_id
            WHERE s.token_hash=%s AND s.revoked=0 AND s.expires_at>%s""",
            (hashlib.sha256(token.encode()).hexdigest(), _iso(_now()))).fetchone()
        if not row or not _password_matches(row, password):
            raise ValueError("Password confirmation failed.")
        account_id = row["id"]
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
