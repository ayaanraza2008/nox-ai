"""Guarded GitHub bridge: read-only inspection and approval-gated pull requests.

Credentials are server-side environment secrets. This module never writes directly to
the base branch; publishing creates a new branch and a pull request.
"""
import base64
import difflib
import os
import re
import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/github", tags=["github"])
API = "https://api.github.com"
MAX_FILES = 10
MAX_FILE_CHARS = 50000
MAX_TOTAL_CHARS = 150000
MAX_TREE_ITEMS = 5000
SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _owner(request: Request) -> str:
    value = request.cookies.get("nox_session", "")
    if not (32 <= len(value) <= 128 and all(ch.isalnum() or ch in "-_" for ch in value)):
        raise HTTPException(status_code=401, detail="Browser session required. Refresh NOX and retry.")
    return value


def _config():
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("NOX_GITHUB_REPOSITORY", "").strip()
    base = os.getenv("NOX_GITHUB_BASE_BRANCH", "main").strip() or "main"
    if not SAFE_REPO.fullmatch(repo):
        raise HTTPException(status_code=503, detail="Set NOX_GITHUB_REPOSITORY to owner/repository in the server environment.")
    if not token:
        raise HTTPException(status_code=503, detail="GitHub bridge needs a server-side GITHUB_TOKEN secret.")
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", base) or base.startswith("/") or ".." in base.split("/"):
        raise HTTPException(status_code=503, detail="NOX_GITHUB_BASE_BRANCH is invalid.")
    return token, repo, base


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _safe_path(path: str) -> str:
    path = path.strip()
    if (not path or len(path) > 240 or path.startswith("/") or "\\" in path
            or any(part in ("", ".", "..") for part in path.split("/"))
            or any(part.startswith(".") for part in path.split("/"))
            or path.lower().endswith((".pem", ".key", ".p12", ".pfx"))
            or path.split("/")[-1].lower() in {".env", "credentials", "secrets.json"}):
        raise HTTPException(status_code=400, detail="Unsafe path. Use a relative, non-hidden source/config file path.")
    return path


async def _request(client, method, url, **kwargs):
    try:
        response = await client.request(method, url, **kwargs)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="GitHub request timed out; retry.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not reach GitHub.")
    if response.status_code >= 400:
        if response.status_code == 404:
            detail = "GitHub resource not found or token lacks access."
        elif response.status_code in (401, 403):
            detail = "GitHub rejected the token or its permissions/rate limit."
        elif response.status_code == 422:
            detail = "GitHub rejected this operation; check branch/file conflicts and token permissions."
        else:
            detail = f"GitHub API returned HTTP {response.status_code}."
        raise HTTPException(status_code=502, detail=detail)
    if not response.content:
        return {}
    return response.json()


class PreviewChange(BaseModel):
    path: str = Field(min_length=1, max_length=240)
    content: str = Field(max_length=MAX_FILE_CHARS)
    expected_sha: Optional[str] = Field(default=None, max_length=100)


class PreviewRequest(BaseModel):
    changes: list[PreviewChange] = Field(min_length=1, max_length=MAX_FILES)


class PublishRequest(PreviewRequest):
    title: str = Field(min_length=5, max_length=120)
    body: str = Field(default="", max_length=4000)
    confirmed: bool = False


async def _get_file(client, repo, base, path):
    url = f"{API}/repos/{repo}/contents/{path}"
    data = await _request(client, "GET", url, params={"ref": base})
    if isinstance(data, list) or data.get("type") != "file":
        raise HTTPException(status_code=400, detail=f"{path} is not a regular file.")
    try:
        raw = base64.b64decode(data.get("content", "")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=415, detail=f"{path} is not a supported UTF-8 text file.")
    if len(raw) > MAX_FILE_CHARS:
        raise HTTPException(status_code=413, detail=f"{path} exceeds the text-file size limit.")
    return raw, data.get("sha")


def _validate_changes(changes):
    seen, total = set(), 0
    normalized = []
    for item in changes:
        path = _safe_path(item.path)
        if path in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate path: {path}")
        seen.add(path)
        total += len(item.content)
        normalized.append((path, item.content, item.expected_sha))
    if total > MAX_TOTAL_CHARS:
        raise HTTPException(status_code=413, detail="Combined proposal exceeds 150,000 characters.")
    return normalized


@router.get("/status")
async def github_status(request: Request):
    _owner(request)
    repo = os.getenv("NOX_GITHUB_REPOSITORY", "").strip()
    configured = bool(os.getenv("GITHUB_TOKEN", "").strip() and SAFE_REPO.fullmatch(repo))
    return {"configured": configured, "repository": repo if SAFE_REPO.fullmatch(repo) else None,
            "base_branch": os.getenv("NOX_GITHUB_BASE_BRANCH", "main"),
            "mode": "read-only + approval-gated pull requests" if configured else "setup_required",
            "direct_base_branch_writes": False}


@router.get("/tree")
async def github_tree(request: Request, path: str = ""):
    _owner(request)
    token, repo, base = _config()
    path = path.strip("/")
    if path:
        path = _safe_path(path)
    async with httpx.AsyncClient(headers=_headers(token), timeout=15.0) as client:
        data = await _request(client, "GET", f"{API}/repos/{repo}/contents/{path}" if path else f"{API}/repos/{repo}/contents",
                              params={"ref": base})
    if isinstance(data, dict):
        data = [data]
    entries = []
    for item in data[:MAX_TREE_ITEMS]:
        if item.get("type") not in ("file", "dir"):
            continue
        name = str(item.get("name", ""))[:180]
        if name.startswith(".") or name.lower() in {"node_modules", "__pycache__", ".git"}:
            continue
        entries.append({"name": name, "path": item.get("path", ""), "type": item["type"],
                        "size": item.get("size", 0), "sha": item.get("sha")})
    return {"repository": repo, "base_branch": base, "path": path, "entries": entries}


@router.get("/file")
async def github_read_file(request: Request, path: str):
    _owner(request)
    token, repo, base = _config()
    path = _safe_path(path)
    async with httpx.AsyncClient(headers=_headers(token), timeout=15.0) as client:
        content, sha = await _get_file(client, repo, base, path)
    return {"repository": repo, "base_branch": base, "path": path, "content": content, "sha": sha}


@router.post("/preview")
async def github_preview(payload: PreviewRequest, request: Request):
    _owner(request)
    token, repo, base = _config()
    changes = _validate_changes(payload.changes)
    results = []
    async with httpx.AsyncClient(headers=_headers(token), timeout=20.0) as client:
        for path, proposed, expected_sha in changes:
            try:
                original, current_sha = await _get_file(client, repo, base, path)
                exists = True
            except HTTPException as exc:
                if exc.status_code != 502 or "not found" not in str(exc.detail).lower():
                    raise
                original, current_sha, exists = "", None, False
            if current_sha != expected_sha:
                raise HTTPException(status_code=409, detail=f"{path} changed in GitHub or its expected SHA is missing. Reload it before previewing.")
            diff = "".join(difflib.unified_diff(original.splitlines(keepends=True), proposed.splitlines(keepends=True),
                                                fromfile=f"a/{path}" if exists else "/dev/null",
                                                tofile=f"b/{path}", n=3))
            results.append({"path": path, "exists": exists, "expected_sha": current_sha,
                            "added": sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")),
                            "removed": sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")),
                            "diff": diff[:20000]})
    return {"repository": repo, "base_branch": base, "changes": results,
            "note": "Preview only. Nothing has been written to GitHub."}


@router.post("/publish")
async def github_publish(payload: PublishRequest, request: Request):
    _owner(request)
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required after reviewing the diff.")
    token, repo, base = _config()
    changes = _validate_changes(payload.changes)
    async with httpx.AsyncClient(headers=_headers(token), timeout=25.0) as client:
        # Re-check every base file before making any remote writes.
        checked = []
        for path, proposed, expected_sha in changes:
            try:
                original, current_sha = await _get_file(client, repo, base, path)
                exists = True
            except HTTPException as exc:
                if exc.status_code != 502 or "not found" not in str(exc.detail).lower():
                    raise
                original, current_sha, exists = "", None, False
            if current_sha != expected_sha:
                raise HTTPException(status_code=409, detail=f"{path} changed since preview. Refresh and review the diff again.")
            if original == proposed:
                raise HTTPException(status_code=400, detail=f"{path} has no changes.")
            checked.append((path, proposed, current_sha, exists))

        base_ref = await _request(client, "GET", f"{API}/repos/{repo}/git/ref/heads/{base}")
        base_sha = base_ref["object"]["sha"]
        branch = "nox/proposal-" + secrets.token_hex(5)
        await _request(client, "POST", f"{API}/repos/{repo}/git/refs",
                       json={"ref": f"refs/heads/{branch}", "sha": base_sha})
        # All commits are made to the new proposal branch, never the base branch.
        for path, content, sha, exists in checked:
            import json as jsonlib
            body = {"message": f"NOX proposal: update {path}", "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    "branch": branch}
            if exists:
                body["sha"] = sha
            await _request(client, "PUT", f"{API}/repos/{repo}/contents/{path}", json=body)
        pr = await _request(client, "POST", f"{API}/repos/{repo}/pulls",
                            json={"title": payload.title, "body": payload.body + "\n\nCreated by NOX after explicit user approval. Review all changes before merging.",
                                  "head": branch, "base": base, "draft": True})
    return {"published": True, "branch": branch, "pull_request": pr.get("html_url"),
            "number": pr.get("number"), "state": pr.get("state"), "draft": pr.get("draft", True),
            "note": "Draft PR created. NOX did not merge it or deploy the application."}
