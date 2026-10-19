"""Session-scoped document and public-web knowledge indexing for NOX AI.

The first implementation deliberately uses SQLite FTS5 for dependable lexical retrieval.
It does not pretend to provide vector embeddings or OAuth connectors.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import sqlite3
import time
import uuid
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx
from fastapi import HTTPException, UploadFile

logger = logging.getLogger("nox.knowledge")
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("NOX_KNOWLEDGE_DB", str(ROOT / "nox_knowledge.sqlite3")))
MAX_UPLOAD_BYTES = int(os.getenv("NOX_KNOWLEDGE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MAX_TEXT_CHARS = int(os.getenv("NOX_KNOWLEDGE_MAX_TEXT_CHARS", "1000000"))
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 180
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".yaml", ".yml", ".xml", ".log", ".sql", ".toml", ".ini", ".pdf", ".docx", ".xlsx"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            source_url TEXT,
            filename TEXT,
            content_hash TEXT NOT NULL,
            content TEXT NOT NULL,
            byte_size INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'indexed',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_owner_updated
            ON knowledge_sources(owner_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_knowledge_owner_hash
            ON knowledge_sources(owner_id, content_hash);
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES knowledge_sources(id) ON DELETE CASCADE,
            UNIQUE(source_id, chunk_index)
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_owner
            ON knowledge_chunks(owner_id, source_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
            chunk_id UNINDEXED, source_id UNINDEXED, owner_id UNINDEXED,
            title, content, tokenize='unicode61'
        );
    """)
    return conn


class _ReadableHTML(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "canvas", "nav", "footer", "header", "form"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.parts = []
        self.title = []
        self.in_title = False
    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        if tag == "title":
            self.in_title = True
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        if tag == "title":
            self.in_title = False
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")
    def handle_data(self, data):
        if self.skip_depth:
            return
        text = data.strip()
        if not text:
            return
        self.parts.append(text + " ")
        if self.in_title:
            self.title.append(text)


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_TEXT_CHARS]


def _extract_docx(data: bytes) -> str:
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = ElementTree.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in xml.findall(".//w:p", ns):
        words = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        if words:
            paragraphs.append("".join(words))
    return "\n".join(paragraphs)


def _extract_xlsx(data: bytes) -> str:
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(n.text or "" for n in item.iter() if n.tag.endswith("}t")) for item in root]
        lines = []
        for name in sorted(n for n in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)):
            root = ElementTree.fromstring(archive.read(name))
            for row in (n for n in root.iter() if n.tag.endswith("}row")):
                cells = []
                for cell in (n for n in row if n.tag.endswith("}c")):
                    value = next((n.text or "" for n in cell if n.tag.endswith("}v")), "")
                    if cell.attrib.get("t") == "s" and value.isdigit():
                        value = shared[int(value)] if int(value) < len(shared) else value
                    elif cell.attrib.get("t") == "inlineStr":
                        value = "".join(n.text or "" for n in cell.iter() if n.tag.endswith("}t"))
                    if value:
                        cells.append(f"{cell.attrib.get('r', '')}: {value}")
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)


def extract_file_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{suffix or 'unknown'}'. Supported: PDF, DOCX, XLSX, TXT, Markdown, CSV, JSON, HTML, and common code/text files.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.")
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if not text.strip():
                raise HTTPException(status_code=422, detail="This PDF has no extractable text. Scanned PDF OCR is not configured yet.")
        elif suffix == ".docx":
            text = _extract_docx(data)
        elif suffix == ".xlsx":
            text = _extract_xlsx(data)
        elif suffix in {".html", ".htm"}:
            parser = _ReadableHTML()
            parser.feed(data.decode("utf-8", errors="replace"))
            text = " ".join(parser.parts)
        else:
            text = data.decode("utf-8-sig", errors="replace")
            if suffix == ".json":
                try:
                    text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
                except ValueError:
                    pass
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Knowledge extraction failed for %s (%s)", Path(filename).name[:100], type(exc).__name__)
        raise HTTPException(status_code=422, detail=f"Could not extract readable text from this file ({type(exc).__name__}).") from exc
    text = _clean_text(text)
    if not text:
        raise HTTPException(status_code=422, detail="No readable text was found in this file.")
    return text


def _chunks(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):
            boundary = max(text.rfind("\n", start + CHUNK_CHARS // 2, end), text.rfind(". ", start + CHUNK_CHARS // 2, end), text.rfind(" ", start + CHUNK_CHARS // 2, end))
            if boundary > start:
                end = boundary + 1
        part = text[start:end].strip()
        if part:
            chunks.append(part)
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks


def _source_payload(row, include_content=False):
    item = {
        "id": row["id"], "source_type": row["source_type"], "title": row["title"],
        "url": row["source_url"], "filename": row["filename"],
        "bytes": row["byte_size"], "status": row["status"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "content_hash": row["content_hash"],
    }
    if include_content:
        item["content"] = row["content"]
    return item


def index_text(owner_id: str, *, title: str, text: str, source_type: str,
               source_url: str | None = None, filename: str | None = None,
               byte_size: int = 0) -> dict:
    text = _clean_text(text)
    if not text:
        raise HTTPException(status_code=422, detail="No readable text to index.")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    stamp = now_iso()
    conn = _connect()
    try:
        duplicate = conn.execute(
            "SELECT * FROM knowledge_sources WHERE owner_id=? AND content_hash=? LIMIT 1",
            (owner_id, digest),
        ).fetchone()
        if duplicate:
            return {"source": _source_payload(duplicate), "duplicate": True, "chunks": conn.execute(
                "SELECT COUNT(*) FROM knowledge_chunks WHERE source_id=?", (duplicate["id"],)
            ).fetchone()[0]}
        existing = None
        if source_url:
            existing = conn.execute(
                "SELECT * FROM knowledge_sources WHERE owner_id=? AND source_url=? LIMIT 1",
                (owner_id, source_url),
            ).fetchone()
        source_id = existing["id"] if existing else uuid.uuid4().hex
        chunks = _chunks(text)
        if existing:
            conn.execute("DELETE FROM knowledge_fts WHERE source_id=?", (source_id,))
            conn.execute("DELETE FROM knowledge_chunks WHERE source_id=?", (source_id,))
            conn.execute("""UPDATE knowledge_sources SET source_type=?,title=?,content_hash=?,content=?,
                byte_size=?,status='indexed',updated_at=? WHERE id=? AND owner_id=?""",
                (source_type, title[:300], digest, text, byte_size or len(text.encode()), stamp, source_id, owner_id))
        else:
            conn.execute("""INSERT INTO knowledge_sources
                (id,owner_id,source_type,title,source_url,filename,content_hash,content,byte_size,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,'indexed',?,?)""",
                (source_id, owner_id, source_type, title[:300], source_url, filename, digest, text,
                 byte_size or len(text.encode()), stamp, stamp))
        for i, chunk in enumerate(chunks):
            chunk_id = uuid.uuid4().hex
            conn.execute("INSERT INTO knowledge_chunks(id,source_id,owner_id,chunk_index,content) VALUES(?,?,?,?,?)",
                         (chunk_id, source_id, owner_id, i, chunk))
            conn.execute("INSERT INTO knowledge_fts(chunk_id,source_id,owner_id,title,content) VALUES(?,?,?,?,?)",
                         (chunk_id, source_id, owner_id, title[:300], chunk))
        conn.commit()
        row = conn.execute("SELECT * FROM knowledge_sources WHERE id=? AND owner_id=?", (source_id, owner_id)).fetchone()
        return {"source": _source_payload(row), "duplicate": False, "chunks": len(chunks)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_sources(owner_id: str) -> dict:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM knowledge_sources WHERE owner_id=? ORDER BY updated_at DESC LIMIT 200", (owner_id,)).fetchall()
        chunk_count = conn.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE owner_id=?", (owner_id,)).fetchone()[0]
        byte_count = conn.execute("SELECT COALESCE(SUM(byte_size),0) FROM knowledge_sources WHERE owner_id=?", (owner_id,)).fetchone()[0]
        return {"sources": [_source_payload(row) for row in rows], "source_count": len(rows),
                "chunk_count": chunk_count, "storage_bytes": byte_count,
                "search_engine": "SQLite FTS5 lexical search", "semantic_embeddings": "not_configured"}
    finally:
        conn.close()


def search_knowledge(owner_id: str, query: str, limit: int = 6) -> dict:
    query = query.strip()[:500]
    if not query:
        return {"results": [], "query": query}
    terms = re.findall(r"[\w\u0900-\u097f\u0600-\u06ff]+", query, flags=re.UNICODE)[:16]
    if not terms:
        return {"results": [], "query": query}
    fts_query = " OR ".join('"' + term.replace('"', '""') + '"*' for term in terms if len(term) > 1)
    conn = _connect()
    try:
        rows = []
        if fts_query:
            try:
                rows = conn.execute("""SELECT f.chunk_id,f.source_id,f.title,f.content,
                    bm25(knowledge_fts,0,0,0,2.0,1.0) AS rank,
                    s.source_url,s.filename,s.updated_at,s.source_type,c.chunk_index
                    FROM knowledge_fts f
                    JOIN knowledge_sources s ON s.id=f.source_id AND s.owner_id=f.owner_id
                    JOIN knowledge_chunks c ON c.id=f.chunk_id AND c.owner_id=f.owner_id
                    WHERE f.owner_id=? AND knowledge_fts MATCH ?
                    ORDER BY rank LIMIT ?""", (owner_id, fts_query, max(1, min(limit, 10)))).fetchall()
            except sqlite3.OperationalError as exc:
                logger.info("FTS query fallback (%s)", type(exc).__name__)
        if not rows:
            candidates = conn.execute("""SELECT c.id AS chunk_id,c.source_id,s.title,c.content,
                s.source_url,s.filename,s.updated_at,s.source_type,c.chunk_index
                FROM knowledge_chunks c JOIN knowledge_sources s ON s.id=c.source_id AND s.owner_id=c.owner_id
                WHERE c.owner_id=? ORDER BY s.updated_at DESC LIMIT 1500""", (owner_id,)).fetchall()
            scored = []
            lower_query = query.casefold()
            for row in candidates:
                body = row["content"].casefold()
                score = sum(body.count(term.casefold()) * (2 if len(term) > 4 else 1) for term in terms)
                if lower_query in body:
                    score += 8
                if score:
                    scored.append((score, row))
            scored.sort(key=lambda pair: (pair[0], pair[1]["updated_at"]), reverse=True)
            rows = [row for _, row in scored[:max(1, min(limit, 10))]]
        results = []
        for row in rows:
            results.append({
                "chunk_id": row["chunk_id"], "source_id": row["source_id"], "title": row["title"],
                "text": row["content"], "url": row["source_url"], "filename": row["filename"],
                "source_type": row["source_type"], "updated_at": row["updated_at"],
                "chunk_index": row["chunk_index"],
            })
        return {"query": query, "results": results, "retrieval": "lexical", "count": len(results)}
    finally:
        conn.close()


def delete_source(owner_id: str, source_id: str) -> bool:
    conn = _connect()
    try:
        row = conn.execute("SELECT id FROM knowledge_sources WHERE id=? AND owner_id=?", (source_id, owner_id)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM knowledge_fts WHERE source_id=? AND owner_id=?", (source_id, owner_id))
        conn.execute("DELETE FROM knowledge_chunks WHERE source_id=? AND owner_id=?", (source_id, owner_id))
        conn.execute("DELETE FROM knowledge_sources WHERE id=? AND owner_id=?", (source_id, owner_id))
        conn.commit()
        return True
    finally:
        conn.close()


def _validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Enter a public http:// or https:// URL without embedded credentials.")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
        raise HTTPException(status_code=400, detail="Private and local network URLs cannot be indexed.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise HTTPException(status_code=400, detail="The website hostname could not be resolved.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global:
            raise HTTPException(status_code=400, detail="Private, loopback, and non-public network addresses cannot be indexed.")
    return url.strip()


async def ingest_public_url(owner_id: str, url: str) -> dict:
    url = _validate_public_url(url)
    parsed = urlparse(url)
    headers = {"User-Agent": "NOXKnowledgeBot/1.0 (+public-page indexing; respects robots.txt)"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(18, connect=6), follow_redirects=False, headers=headers, trust_env=True) as client:
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            _validate_public_url(robots_url)
            robots = await client.get(robots_url)
            if robots.status_code < 400:
                from urllib.robotparser import RobotFileParser
                parser = RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(robots.text.splitlines())
                if not parser.can_fetch(headers["User-Agent"], url):
                    raise HTTPException(status_code=403, detail="This website's robots.txt disallows indexing this URL.")
        except HTTPException:
            raise
        except Exception:
            # If robots.txt cannot be checked, fail closed rather than crawl blindly.
            raise HTTPException(status_code=502, detail="Could not verify robots.txt for this site; indexing was not started.")
        try:
            response = await client.get(url, headers={"Accept": "text/html,text/plain,application/pdf;q=0.7"})
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Could not fetch this public page.") from exc
        if response.is_redirect:
            raise HTTPException(status_code=400, detail="This URL redirects. Add the final public URL directly.")
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"The website returned HTTP {response.status_code}.")
        if len(response.content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="The website response exceeds the configured size limit.")
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type:
            parser = _ReadableHTML()
            parser.feed(response.text)
            text = _clean_text(" ".join(parser.parts))
            title = " ".join(parser.title).strip() or parsed.netloc
        elif "text/plain" in content_type or "application/json" in content_type:
            text = _clean_text(response.text)
            title = parsed.path.rstrip("/").split("/")[-1] or parsed.netloc
        else:
            raise HTTPException(status_code=415, detail="This URL did not return HTML, plain text, or JSON. Upload supported documents directly.")
    if not text:
        raise HTTPException(status_code=422, detail="No readable page text was found.")
    return index_text(owner_id, title=title, text=text, source_type="web", source_url=url, byte_size=len(response.content))


async def ingest_upload(owner_id: str, upload: UploadFile) -> dict:
    filename = Path(upload.filename or "upload.txt").name[:180]
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.")
    text = extract_file_text(filename, data)
    return index_text(owner_id, title=filename, text=text, source_type="upload", filename=filename, byte_size=len(data))
