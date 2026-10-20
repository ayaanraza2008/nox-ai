"""NOX connected-account and communication adapters.

Gmail is the first real provider. Other providers are explicitly reported as
unavailable until an official API or permitted integration is configured.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend import accounts

router = APIRouter(prefix="/api/connected", tags=["connected-apps"])
DB_PATH = Path(os.getenv("NOX_CONNECTED_APPS_DB", "/tmp/nox_connected_apps.sqlite3"))
ACCOUNT_COOKIE = "nox_account_session"
SESSION_COOKIE = "nox_session"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_MESSAGE_CHARS = 20000


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owner(request: Request) -> str:
    token = request.cookies.get(ACCOUNT_COOKIE, "")
    if token:
        try:
            account = accounts.resolve_session(token)
        except RuntimeError as exc:
            raise HTTPException(503, "Account storage is temporarily unavailable.") from exc
        if not account:
            raise HTTPException(401, "Your NOX account session expired. Sign in again.")
        return account["id"]
    value = request.cookies.get(SESSION_COOKIE, "")
    if not (32 <= len(value) <= 128 and all(c.isalnum() or c in "-_" for c in value)):
        raise HTTPException(401, "Refresh NOX to establish a browser session.")
    return value


def _fernet() -> Fernet:
    key = os.getenv("NOX_TOKEN_ENCRYPTION_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Connected apps are not configured: set NOX_TOKEN_ENCRYPTION_KEY.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(503, "NOX_TOKEN_ENCRYPTION_KEY must be a valid Fernet key.") from exc


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS connected_accounts (
            owner_id TEXT NOT NULL, provider TEXT NOT NULL, account_email TEXT NOT NULL,
            encrypted_tokens BLOB NOT NULL, scopes TEXT NOT NULL, connected_at TEXT NOT NULL,
            checked_at TEXT, PRIMARY KEY(owner_id, provider))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY, owner_id TEXT NOT NULL, provider TEXT NOT NULL,
            created_at REAL NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS communication_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id TEXT NOT NULL, provider TEXT NOT NULL,
            action TEXT NOT NULL, destination TEXT, status TEXT NOT NULL, detail TEXT,
            created_at TEXT NOT NULL)""")
        conn.commit()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _audit(owner: str, action: str, status: str, destination: str | None = None, detail: str | None = None):
    # Deliberately never persist message bodies, tokens, or attachment contents.
    with _db() as conn:
        conn.execute(
            "INSERT INTO communication_audit(owner_id,provider,action,destination,status,detail,created_at) VALUES(?,?,?,?,?,?,?)",
            (owner, "gmail", action, (destination or "")[:320] or None, status[:40], (detail or "")[:300] or None, utcnow()),
        )


def _google_config(request: Request) -> tuple[str, str, str]:
    _fernet()  # fail before redirecting to Google if secure token storage is not configured
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    if not redirect_uri:
        base = os.getenv("NOX_PUBLIC_BASE_URL", "").strip().rstrip("/")
        if base:
            redirect_uri = base + "/api/connected/gmail/callback"
    if not (client_id and client_secret and redirect_uri):
        raise HTTPException(503, "Gmail is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI.")
    if not redirect_uri.startswith("https://") and not redirect_uri.startswith("http://127.0.0.1"):
        raise HTTPException(503, "Google OAuth redirect must use HTTPS (loopback HTTP is allowed for local development).")
    return client_id, client_secret, redirect_uri


def _tokens_for(owner: str) -> tuple[dict[str, Any], str]:
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM connected_accounts WHERE owner_id=? AND provider='gmail'", (owner,)
        ).fetchone()
    if not row:
        raise HTTPException(409, "Gmail is not connected. Open Connected Apps and connect Gmail first.")
    try:
        tokens = json.loads(_fernet().decrypt(bytes(row["encrypted_tokens"])).decode("utf-8"))
    except (InvalidToken, ValueError, TypeError) as exc:
        raise HTTPException(503, "Stored Gmail credentials cannot be decrypted. Check NOX_TOKEN_ENCRYPTION_KEY.") from exc
    if float(tokens.get("expires_at", 0)) <= time.time() + 60:
        _, client_secret, _ = _google_config_dummy()
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise HTTPException(401, "Gmail authorization expired. Reconnect the account.")
        try:
            response = httpx.post(GOOGLE_TOKEN, data={
                "client_id": os.getenv("GOOGLE_CLIENT_ID", "").strip(),
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }, timeout=20)
            response.raise_for_status()
            refreshed = response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, "Gmail token refresh failed. Reconnect Gmail if the problem continues.")
        tokens.update(refreshed)
        tokens["refresh_token"] = refresh_token
        tokens["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
        with _db() as conn:
            conn.execute("UPDATE connected_accounts SET encrypted_tokens=?,checked_at=? WHERE owner_id=? AND provider='gmail'",
                         (_fernet().encrypt(json.dumps(tokens).encode()), utcnow(), owner))
    return tokens, row["account_email"]


def _google_config_dummy() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise HTTPException(503, "Google OAuth client configuration is missing.")
    return client_id, client_secret, os.getenv("GOOGLE_REDIRECT_URI", "").strip()


def _gmail_request(owner: str, method: str, path: str, **kwargs) -> httpx.Response:
    tokens, _ = _tokens_for(owner)
    try:
        response = httpx.request(method, GMAIL_API + path, headers={
            "Authorization": "Bearer " + tokens["access_token"],
            "Accept": "application/json",
        }, timeout=25, **kwargs)
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach Gmail. No successful action was recorded.")
    if response.status_code == 401:
        raise HTTPException(401, "Gmail rejected the authorization. Reconnect the account.")
    if response.status_code == 403:
        raise HTTPException(403, "Gmail denied this operation. Check the granted OAuth permissions.")
    if response.is_error:
        # Do not pass provider response bodies to clients: they may contain private data.
        raise HTTPException(502, f"Gmail operation failed with provider HTTP {response.status_code}.")
    with _db() as conn:
        conn.execute("UPDATE connected_accounts SET checked_at=? WHERE owner_id=? AND provider='gmail'", (utcnow(), owner))
    return response


def _email_message(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> str:
    def validate_address(value: str, field: str, optional: bool = False):
        value = value.strip()
        if optional and not value:
            return ""
        if len(value) > 320 or not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", value):
            raise HTTPException(422, f"{field} must contain one valid email address.")
        return value
    to = validate_address(to, "To")
    cc = validate_address(cc, "CC", True)
    bcc = validate_address(bcc, "BCC", True)
    if not subject.strip() or len(subject) > 998:
        raise HTTPException(422, "Subject is required and must be at most 998 characters.")
    if not body.strip() or len(body) > MAX_MESSAGE_CHARS:
        raise HTTPException(422, f"Email body must be non-empty and no longer than {MAX_MESSAGE_CHARS} characters.")
    msg = EmailMessage()
    msg["To"] = to
    if cc: msg["Cc"] = cc
    if bcc: msg["Bcc"] = bcc
    msg["Subject"] = subject.strip()
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii").rstrip("=")


class EmailDraftRequest(BaseModel):
    to: str = Field(min_length=3, max_length=320)
    cc: str = Field(default="", max_length=320)
    bcc: str = Field(default="", max_length=320)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class EmailSendRequest(EmailDraftRequest):
    confirmed: bool = False


class EmailSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=25)


@router.get("/status")
async def connected_apps_status(request: Request):
    owner = _owner(request)
    with _db() as conn:
        rows = conn.execute("SELECT provider,account_email,scopes,connected_at,checked_at FROM connected_accounts WHERE owner_id=?", (owner,)).fetchall()
    by_provider = {r["provider"]: r for r in rows}
    apps = []
    for provider, name, capabilities, setup in [
        ("gmail", "Gmail", ["search_mail", "read_mail_metadata", "save_draft", "send_email"], "Google OAuth credentials required"),
        ("outlook", "Microsoft Outlook", [], "Official Microsoft Graph adapter not configured"),
        ("whatsapp", "WhatsApp", [], "Official WhatsApp Business API or supported integration required"),
        ("sms", "SMS", [], "Authorized SMS provider required"),
        ("calendar", "Calendar", [], "Calendar provider adapter not configured"),
        ("linkedin", "LinkedIn", [], "No automated messaging adapter configured"),
        ("phone", "Phone calls", [], "Telephony provider and explicit call authorization required"),
    ]:
        row = by_provider.get(provider)
        apps.append({
            "provider": provider, "name": name,
            "connected": bool(row), "account": row["account_email"] if row else None,
            "scopes": json.loads(row["scopes"]) if row else [],
            "capabilities": capabilities if row else [],
            "last_checked_at": row["checked_at"] if row else None,
            "connected_at": row["connected_at"] if row else None,
            "setup": setup if not row else None,
        })
    return {"apps": apps, "audit_enabled": True}


@router.get("/gmail/connect")
async def gmail_connect(request: Request):
    owner = _owner(request)
    client_id, _, redirect_uri = _google_config(request)
    state = secrets.token_urlsafe(32)
    with _db() as conn:
        conn.execute("DELETE FROM oauth_states WHERE created_at < ?", (time.time() - 900,))
        conn.execute("INSERT INTO oauth_states(state,owner_id,provider,created_at) VALUES(?,?,?,?)",
                     (state, owner, "gmail", time.time()))
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "code", "scope": "openid email https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.send",
        "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state,
    }
    return {"authorization_url": GOOGLE_AUTH + "?" + urlencode(params), "expires_in": 900}


@router.get("/gmail/callback")
async def gmail_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        raise HTTPException(400, "Google authorization was cancelled or denied.")
    owner = _owner(request)
    if not code or not state:
        raise HTTPException(400, "Google OAuth callback is missing code or state.")
    with _db() as conn:
        row = conn.execute("SELECT * FROM oauth_states WHERE state=? AND provider='gmail'", (state,)).fetchone()
        conn.execute("DELETE FROM oauth_states WHERE state=?", (state,))
    if not row or row["owner_id"] != owner or time.time() - row["created_at"] > 900:
        raise HTTPException(400, "OAuth state is invalid, expired, or belongs to another NOX session.")
    client_id, client_secret, redirect_uri = _google_config(request)
    try:
        response = httpx.post(GOOGLE_TOKEN, data={
            "code": code, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        }, timeout=20)
        response.raise_for_status()
        tokens = response.json()
        user_response = httpx.get("https://www.googleapis.com/oauth2/v2/userinfo",
                                  headers={"Authorization": "Bearer " + tokens["access_token"]}, timeout=15)
        user_response.raise_for_status()
        user = user_response.json()
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(502, "Google OAuth exchange failed. Check Google Cloud OAuth configuration.")
    if not user.get("email"):
        raise HTTPException(502, "Google did not return the authorized account identity.")
    tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 3600))
    scopes = ["openid", "email", "https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.send"]
    with _db() as conn:
        existing = conn.execute("SELECT encrypted_tokens FROM connected_accounts WHERE owner_id=? AND provider='gmail'", (owner,)).fetchone()
        if existing and not tokens.get("refresh_token"):
            try:
                old = json.loads(_fernet().decrypt(bytes(existing["encrypted_tokens"])))
                tokens["refresh_token"] = old.get("refresh_token")
            except (InvalidToken, ValueError, TypeError):
                pass
        if not tokens.get("refresh_token"):
            raise HTTPException(400, "Google did not issue a refresh token. Disconnect Gmail in Google account settings and reconnect with consent.")
        conn.execute("""INSERT INTO connected_accounts(owner_id,provider,account_email,encrypted_tokens,scopes,connected_at,checked_at)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(owner_id,provider) DO UPDATE SET
            account_email=excluded.account_email,encrypted_tokens=excluded.encrypted_tokens,
            scopes=excluded.scopes,connected_at=excluded.connected_at,checked_at=excluded.checked_at""",
            (owner, "gmail", user["email"], _fernet().encrypt(json.dumps(tokens).encode()), json.dumps(scopes), utcnow(), utcnow()))
    _audit(owner, "connect", "connected", user["email"], "Google OAuth completed")
    # Redirect only to the configured NOX origin; never echo authorization codes or tokens.
    base = os.getenv("NOX_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base:
        base = str(request.base_url).rstrip("/")
    if not (base.startswith("https://") or base.startswith("http://127.0.0.1")):
        raise HTTPException(503, "Set NOX_PUBLIC_BASE_URL to the HTTPS NOX origin for the post-OAuth redirect.")
    return RedirectResponse(url=base + "/?connected=gmail", status_code=303)


@router.post("/gmail/disconnect")
async def gmail_disconnect(request: Request):
    owner = _owner(request)
    with _db() as conn:
        row = conn.execute("SELECT account_email FROM connected_accounts WHERE owner_id=? AND provider='gmail'", (owner,)).fetchone()
        conn.execute("DELETE FROM connected_accounts WHERE owner_id=? AND provider='gmail'", (owner,))
    if row:
        _audit(owner, "disconnect", "disconnected", row["account_email"])
    return {"disconnected": True, "provider": "gmail"}


@router.post("/gmail/search")
async def gmail_search(payload: EmailSearchRequest, request: Request):
    owner = _owner(request)
    response = _gmail_request(owner, "GET", "/messages", params={"q": payload.query, "maxResults": payload.limit})
    messages = response.json().get("messages", [])
    items = []
    for item in messages[:payload.limit]:
        detail = _gmail_request(owner, "GET", "/messages/" + item["id"], params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]}).json()
        headers = {h.get("name", "").lower(): h.get("value", "") for h in detail.get("payload", {}).get("headers", [])}
        items.append({"id": detail.get("id"), "thread_id": detail.get("threadId"),
                      "from": headers.get("from", ""), "to": headers.get("to", ""),
                      "subject": headers.get("subject", "(no subject)"), "date": headers.get("date", ""),
                      "snippet": detail.get("snippet", "")[:500]})
    _audit(owner, "search_mail", "succeeded", detail="Returned metadata only")
    return {"messages": items, "count": len(items), "provider_status": "succeeded"}


@router.post("/gmail/drafts")
async def gmail_save_draft(payload: EmailDraftRequest, request: Request):
    owner = _owner(request)
    raw = _email_message(payload.to, payload.subject, payload.body, payload.cc, payload.bcc)
    response = _gmail_request(owner, "POST", "/drafts", json={"message": {"raw": raw}})
    result = response.json()
    _audit(owner, "save_draft", "succeeded", payload.to, "Gmail draft created")
    return {"status": "draft_saved", "draft_id": result.get("id"), "thread_id": result.get("message", {}).get("threadId"),
            "recipient": payload.to, "subject": payload.subject, "provider": "gmail"}


@router.post("/gmail/send")
async def gmail_send(payload: EmailSendRequest, request: Request):
    owner = _owner(request)
    if not payload.confirmed:
        raise HTTPException(428, "Review the recipient, subject, and body, then explicitly confirm sending.")
    raw = _email_message(payload.to, payload.subject, payload.body, payload.cc, payload.bcc)
    try:
        result = _gmail_request(owner, "POST", "/messages/send", json={"raw": raw}).json()
    except HTTPException as exc:
        _audit(owner, "send_email", "failed", payload.to, f"HTTP {exc.status_code}")
        raise
    _audit(owner, "send_email", "accepted_by_provider", payload.to, "Gmail accepted send request; delivery not confirmed")
    return {"status": "send_accepted", "provider": "gmail", "message_id": result.get("id"),
            "thread_id": result.get("threadId"), "recipient": payload.to,
            "delivery_status": "unknown", "message": "Gmail accepted the send request; this does not prove recipient delivery."}


@router.get("/audit")
async def communication_audit(request: Request, limit: int = 50):
    owner = _owner(request)
    limit = max(1, min(limit, 100))
    with _db() as conn:
        rows = conn.execute("SELECT provider,action,destination,status,detail,created_at FROM communication_audit WHERE owner_id=? ORDER BY id DESC LIMIT ?", (owner, limit)).fetchall()
    return {"events": [dict(row) for row in rows]}


@router.delete("/audit")
async def clear_communication_audit(request: Request):
    owner = _owner(request)
    with _db() as conn:
        conn.execute("DELETE FROM communication_audit WHERE owner_id=?", (owner,))
    return {"deleted": True}


def provider_registry() -> dict[str, dict[str, Any]]:
    """Machine-readable adapter registry; only configured providers advertise actions."""
    return {
        "gmail": {"adapter": "Gmail REST API", "official_api": True, "actions": ["search_mail", "save_draft", "send_email"]},
        "outlook": {"adapter": None, "official_api": True, "actions": [], "reason": "Microsoft Graph OAuth adapter not implemented"},
        "whatsapp": {"adapter": None, "official_api": True, "actions": [], "reason": "Requires eligible WhatsApp Business API account or permitted provider"},
        "linkedin": {"adapter": None, "official_api": True, "actions": [], "reason": "No messaging adapter configured"},
        "sms": {"adapter": None, "official_api": True, "actions": [], "reason": "No SMS provider configured"},
        "phone": {"adapter": None, "official_api": True, "actions": [], "reason": "No telephony provider configured"},
        "calendar": {"adapter": None, "official_api": True, "actions": [], "reason": "No calendar adapter configured"},
    }
