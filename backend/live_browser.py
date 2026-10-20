"""Consent-based local Playwright browser automation for NOX AI.

Optional dependency: install backend/requirements-browser.txt and Playwright Chromium.
This service is deliberately local-only at the API layer and supports allow-listed
browser actions rather than arbitrary code or shell execution.
"""
from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import socket
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlparse

MAX_TASKS_PER_SESSION = 20
MAX_STEPS_PER_TASK = 12
NAVIGATION_TIMEOUT_MS = 20000
ACTION_TIMEOUT_MS = 8000
MAX_PAGE_TEXT = 12000
MAX_SCREENSHOT_BYTES = 2_000_000
RISKY_ACTION = re.compile(r"\b(submit|send|publish|post|buy|purchase|pay|checkout|book|reserve|delete|remove|cancel|transfer|confirm|save changes|change password)\b", re.I)
AUTH_MARKERS = ("captcha", "verify you are human", "one-time password", "two-factor authentication", "security check")


class BrowserUnavailable(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_http_url(raw_url: str) -> str:
    """Validate a public HTTP(S) URL and reject local/private destinations."""
    value = (raw_url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only complete http:// or https:// website URLs are supported.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    allow_local_tests = os.getenv("NOX_BROWSER_ALLOW_LOCAL_TESTS", "").strip() == "1"
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or host.endswith(".local"):
        if allow_local_tests and host in {"localhost", "localhost.localdomain"}:
            return value
        raise ValueError("Local and private network destinations are blocked by the browser safety policy.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        except (OSError, ValueError) as exc:
            raise ValueError("The website host could not be resolved.") from exc
    if allow_local_tests and addresses and all(addr.is_loopback for addr in addresses):
        return value
    if not addresses or any(not addr.is_global for addr in addresses):
        raise ValueError("Local, private, reserved, or non-public IP destinations are blocked.")
    return value


def plan_instruction(instruction: str) -> list[dict[str, str]]:
    """Convert a small, explicit command grammar into allow-listed browser steps."""
    text = (instruction or "").strip()
    if not text:
        return []
    if len(text) > 2000:
        raise ValueError("Browser instruction must be 2,000 characters or fewer.")
    chained = re.split(r"\s+then\s+", text, flags=re.I)
    if len(chained) > 1:
        steps: list[dict[str, str]] = []
        for part in chained:
            if part.strip():
                steps.extend(plan_instruction(part.strip()))
        return steps[:MAX_STEPS_PER_TASK]

    # Common site aliases avoid asking for a URL when the destination is unambiguous.
    alias = re.fullmatch(
        r"\s*(?:nox[, ]*)?(?:open|visit|go to|navigate to)\s+"
        r"(youtube|google|wikipedia|github|reddit|stackoverflow|amazon|instagram|facebook|tiktok)"
        r"(?:\s+(?:and\s+)?(?:search|find)\s+(?:for\s+)?(.+?))?\s*",
        text, re.I,
    )
    if alias:
        site = alias.group(1).lower()
        query = (alias.group(2) or "").strip().strip(" .?!")
        base_urls = {
            "youtube": "https://www.youtube.com/",
            "google": "https://www.google.com/",
            "wikipedia": "https://en.wikipedia.org/",
            "github": "https://github.com/",
            "reddit": "https://www.reddit.com/",
            "stackoverflow": "https://stackoverflow.com/",
            "amazon": "https://www.amazon.com/",
            "instagram": "https://www.instagram.com/",
            "facebook": "https://www.facebook.com/",
            "tiktok": "https://www.tiktok.com/",
        }
        url = base_urls[site]
        if query and site == "youtube":
            url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
        elif query and site == "google":
            url = "https://www.google.com/search?q=" + quote_plus(query)
        elif query and site == "wikipedia":
            url = "https://en.wikipedia.org/w/index.php?search=" + quote_plus(query)
        elif query:
            return [{"action": "clarify", "value": f"I can open {site.title()}, but I cannot safely assume its search interface. Open the site first, then tell me the exact search control label."}]
        return [{"action": "navigate", "value": url}, {"action": "inspect", "value": ""}]

    # Explicit URL is the least ambiguous start point.
    urls = re.findall(r"https?://[^\s<>\"']+", text, re.I)
    if urls:
        url = urls[0].rstrip(".,);]")
        return [{"action": "navigate", "value": url}, {"action": "inspect", "value": ""}]

    search = re.search(r"\b(?:search(?: the web)?(?: for)?|google|look up|find online)\s+(.+)", text, re.I)
    if search:
        query = search.group(1).strip().strip(" .?!")
        if query:
            return [
                {"action": "navigate", "value": "https://www.google.com/search?q=" + quote_plus(query)},
                {"action": "inspect", "value": ""},
            ]

    click = re.fullmatch(r"\s*click\s+(?:on\s+)?(?:the\s+)?[\"']?(.+?)[\"']?\s*", text, re.I)
    if click:
        return [{"action": "click", "value": click.group(1).strip()}]

    fill = re.fullmatch(r"\s*(?:type|enter|fill)\s+[\"'](.+?)[\"']\s+into\s+[\"']?(.+?)[\"']?\s*", text, re.I)
    if fill:
        return [{"action": "fill", "value": fill.group(2).strip(), "text": fill.group(1)}]

    select = re.fullmatch(r"\s*select\s+[\"']?(.+?)[\"']?\s+(?:in|from)\s+[\"']?(.+?)[\"']?\s*", text, re.I)
    if select:
        return [{"action": "select", "value": select.group(2).strip(), "text": select.group(1).strip()}]

    if re.search(r"\b(scroll|go down|page down)\b", text, re.I):
        return [{"action": "scroll", "value": "down"}]
    if re.search(r"\b(go back|back to previous page)\b", text, re.I):
        return [{"action": "back", "value": ""}]
    if re.search(r"\b(go forward|next page)\b", text, re.I):
        return [{"action": "forward", "value": ""}]
    if re.search(r"\b(inspect|read this page|summari[sz]e this page|what is on this page|tell me what this site does)\b", text, re.I):
        return [{"action": "inspect", "value": ""}]
    if re.search(r"\b(open|visit|go to|navigate to)\b", text, re.I):
        return [{"action": "clarify", "value": "Which exact website URL should I open? You can paste the full https:// address."}]
    return [{"action": "clarify", "value": "I can currently open a URL, search the web, inspect a page, click a named control, fill a clearly named field, select an option, scroll, or navigate back/forward. Which action should I perform first?"}]


class BrowserSession:
    def __init__(self, owner: str):
        self.owner = owner
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.task: asyncio.Task | None = None
        self.task_id: str | None = None
        self.instruction = ""
        self.state = "idle"
        self.current_step = 0
        self.steps: list[dict[str, Any]] = []
        self.result = ""
        self.error = ""
        self.pending_question: str | None = None
        self.pending_confirmation: dict[str, str] | None = None
        self.created_at: str | None = None
        self.updated_at = utc_now()
        self.history: list[dict[str, Any]] = []
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.stop_event = asyncio.Event()
        self.decision: asyncio.Future | None = None
        self._lock = asyncio.Lock()

    async def launch(self) -> None:
        if self.page is not None and not self.page.is_closed():
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserUnavailable(
                "Playwright is not installed. From the repository root run: "
                "pip install -r backend/requirements-browser.txt; python -m playwright install chromium"
            ) from exc
        self.playwright = await async_playwright().start()
        headless = os.getenv("NOX_BROWSER_HEADLESS", "1").strip().lower() not in {"0", "false", "no"}
        try:
            self.browser = await self.playwright.chromium.launch(headless=headless)
            self.context = await self.browser.new_context(accept_downloads=True, viewport={"width": 1365, "height": 850})
            self.page = await self.context.new_page()
            self.page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
            self.page.set_default_timeout(ACTION_TIMEOUT_MS)
            await self.page.route("**/*", self._guard_route)
        except Exception:
            await self.close()
            raise

    async def _guard_route(self, route) -> None:
        try:
            _public_http_url(route.request.url)
        except ValueError:
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    async def close(self) -> None:
        for obj in (self.context, self.browser):
            if obj is not None:
                try:
                    await obj.close()
                except Exception:
                    pass
        if self.playwright is not None:
            try:
                await self.playwright.stop()
            except Exception:
                pass
        self.page = self.context = self.browser = self.playwright = None

    async def _await_permission(self) -> None:
        await self.pause_event.wait()
        if self.stop_event.is_set():
            raise asyncio.CancelledError()

    async def _page_summary(self) -> str:
        if self.page is None or self.page.is_closed():
            return "No active page is available."
        title = (await self.page.title())[:300]
        url = self.page.url[:1500]
        try:
            body = await self.page.locator("body").inner_text(timeout=3000)
        except Exception:
            body = ""
        body = re.sub(r"\n{3,}", "\n\n", body).strip()[:MAX_PAGE_TEXT]
        return f"Title: {title}\nURL: {url}\n\nPage text (untrusted website content):\n{body}"

    async def _needs_auth(self) -> bool:
        if self.page is None:
            return False
        url = self.page.url.lower()
        try:
            body = (await self.page.locator("body").inner_text(timeout=1200)).lower()[:8000]
        except Exception:
            body = ""
        return any(word in url for word in ("/login", "/signin", "/sign-in", "/auth/")) or any(mark in body for mark in AUTH_MARKERS)

    async def _perform(self, step: dict[str, str]) -> str:
        await self._await_permission()
        action = step["action"]
        value = step.get("value", "")
        if action == "navigate":
            url = _public_http_url(value)
            await self.page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            try:
                await self.page.wait_for_load_state("networkidle", timeout=2500)
            except Exception:
                pass
            if await self._needs_auth():
                self.state = "awaiting_auth"
                self.pending_question = (
                    "This page appears to require sign-in or an additional security check. Complete it in the visible browser window, then press Resume. NOX will not bypass it."
                    if os.getenv("NOX_BROWSER_HEADLESS", "1").strip().lower() in {"0", "false", "no"}
                    else "This page requires sign-in or a security check, but the browser is headless. Stop NOX, set NOX_BROWSER_HEADLESS=0, restart locally, and retry so you can complete the legitimate website flow."
                )
                self.pause_event.clear()
                return "Paused for user authentication."
            return f"Opened {self.page.url}"
        if action == "inspect":
            self.result = await self._page_summary()
            return self.result[:4000]
        if action == "click":
            if RISKY_ACTION.search(value):
                self.pending_confirmation = {"action": "click", "target": value, "page": self.page.url[:1500]}
                self.state = "awaiting_confirmation"
                self.pending_question = f"Confirm before clicking “{value}” on {self.page.url}. This may submit or change information."
                self.decision = asyncio.get_running_loop().create_future()
                approved = await self.decision
                self.pending_confirmation = None
                self.pending_question = None
                if not approved:
                    raise PermissionError("User declined the consequential action.")
            matches = []
            for locator in (
                self.page.get_by_role("button", name=value, exact=True),
                self.page.get_by_role("link", name=value, exact=True),
                self.page.get_by_text(value, exact=True),
            ):
                try:
                    count = await locator.count()
                    if count:
                        matches.append(locator)
                except Exception:
                    continue
            if not matches:
                raise ValueError(f"No accessible element exactly matching “{value}” was found.")
            chosen = matches[0]
            count = await chosen.count()
            if count > 1:
                self.pending_question = f"I found {count} matching elements named “{value}”. Please use a more specific button or link label."
                self.state = "awaiting_input"
                raise LookupError(self.pending_question)
            await chosen.first.click()
            await self.page.wait_for_timeout(350)
            if await self._needs_auth():
                self.state = "awaiting_auth"
                self.pending_question = (
                    "A login or security check is required. Complete it in the visible browser window and press Resume."
                    if os.getenv("NOX_BROWSER_HEADLESS", "1").strip().lower() in {"0", "false", "no"}
                    else "A login or security check is required, but the browser is headless. Restart locally with NOX_BROWSER_HEADLESS=0 to complete the legitimate website flow."
                )
                self.pause_event.clear()
            return f"Clicked “{value}”"
        if action == "fill":
            field = value
            text = step.get("text", "")
            candidates = [
                self.page.get_by_label(field, exact=True),
                self.page.get_by_placeholder(field, exact=True),
                self.page.get_by_role("textbox", name=field, exact=True),
            ]
            matches = []
            for locator in candidates:
                try:
                    if await locator.count():
                        matches.append(locator)
                except Exception:
                    pass
            if not matches:
                raise ValueError(f"No form field labelled or described as “{field}” was found.")
            if await matches[0].count() > 1:
                raise LookupError(f"More than one field matches “{field}”. Please specify a unique label.")
            await matches[0].fill(text)
            return f"Filled the field “{field}”. The value is not included in task history."
        if action == "select":
            field = value
            option = step.get("text", "")
            locator = self.page.get_by_label(field, exact=True)
            if await locator.count() != 1:
                raise ValueError(f"Expected one dropdown labelled “{field}”; found {await locator.count()}.")
            await locator.select_option(label=option)
            return f"Selected “{option}” in “{field}”."
        if action == "scroll":
            await self.page.evaluate("window.scrollBy(0, Math.max(450, Math.floor(window.innerHeight * 0.75)))")
            return "Scrolled down."
        if action == "back":
            await self.page.go_back(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            return f"Navigated back to {self.page.url}"
        if action == "forward":
            await self.page.go_forward(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            return f"Navigated forward to {self.page.url}"
        if action == "clarify":
            self.pending_question = value
            self.state = "awaiting_input"
            return value
        raise ValueError("Unsupported browser action.")

    async def start_task(self, instruction: str) -> dict[str, Any]:
        async with self._lock:
            if self.task and not self.task.done():
                raise ValueError("A browser task is already active. Stop or finish it before starting another.")
            plan = plan_instruction(instruction)
            self.task_id = uuid.uuid4().hex
            self.instruction = instruction[:2000]
            self.created_at = utc_now()
            self.updated_at = self.created_at
            self.steps = [{"index": i + 1, "action": s["action"], "label": self._step_label(s), "status": "pending"} for i, s in enumerate(plan[:MAX_STEPS_PER_TASK])]
            self.current_step = 0
            self.result = ""
            self.error = ""
            self.pending_question = None
            self.pending_confirmation = None
            self.stop_event = asyncio.Event()
            self.pause_event = asyncio.Event()
            self.pause_event.set()
            self.state = "running"
            self.task = asyncio.create_task(self._run_plan(plan[:MAX_STEPS_PER_TASK]))
            return self.snapshot()

    @staticmethod
    def _step_label(step: dict[str, str]) -> str:
        action = step.get("action", "")
        labels = {"navigate": "Open website", "inspect": "Inspect current page", "click": "Click a named control", "fill": "Fill a named field", "select": "Choose a dropdown option", "scroll": "Scroll page", "back": "Go back", "forward": "Go forward", "clarify": "Ask for missing details"}
        return labels.get(action, action)

    async def _run_plan(self, plan: list[dict[str, str]]) -> None:
        try:
            if any(step["action"] != "clarify" for step in plan):
                await self.launch()
            for index, step in enumerate(plan):
                await self._await_permission()
                self.current_step = index + 1
                self.steps[index]["status"] = "running"
                self.updated_at = utc_now()
                try:
                    result = await self._perform(step)
                    self.steps[index]["status"] = "completed"
                    self.steps[index]["result"] = result[:4000]
                    if self.state in {"awaiting_auth", "awaiting_confirmation", "awaiting_input"}:
                        self.pause_event.clear()
                        await self.pause_event.wait()
                        if self.stop_event.is_set():
                            raise asyncio.CancelledError()
                        if self.state == "running":
                            self.pending_question = None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if isinstance(exc, PermissionError) and self.stop_event.is_set():
                        self.steps[index]["status"] = "cancelled"
                        self.state = "cancelled"
                        return
                    self.steps[index]["status"] = "failed"
                    self.steps[index]["error"] = str(exc)[:500]
                    self.error = str(exc)[:500]
                    self.state = "failed"
                    return
            self.state = "completed"
            self.result = self.result or (await self._page_summary() if self.page else "Clarification required before any browser action.")
        except asyncio.CancelledError:
            self.state = "cancelled"
        except Exception as exc:
            self.state = "failed"
            self.error = str(exc)[:500]
        finally:
            self.updated_at = utc_now()
            self.history.append({"task_id": self.task_id, "created_at": self.created_at, "status": self.state, "step_count": len(self.steps), "url": self.page.url[:1500] if self.page and not self.page.is_closed() else "", "error": self.error[:300]})
            self.history = self.history[-MAX_TASKS_PER_SESSION:]

    async def run_action(self, action: str, value: str = "", text: str = "") -> dict[str, Any]:
        if self.task and not self.task.done():
            raise ValueError("A task is active. Stop or pause it before manual browser control.")
        if action not in {"navigate", "inspect", "click", "fill", "select", "scroll", "back", "forward", "reload"}:
            raise ValueError("Unsupported browser action.")
        if action == "click" and RISKY_ACTION.search(value):
            return await self.start_task("click " + value)
        if self.page is None or self.page.is_closed():
            if action != "navigate":
                raise BrowserUnavailable("Open a website first.")
            await self.launch()
        if action == "reload":
            await self.page.reload(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            result = f"Reloaded {self.page.url}"
        else:
            result = await self._perform({"action": action, "value": value, "text": text})
        self.updated_at = utc_now()
        self.result = result[:MAX_PAGE_TEXT]
        return self.snapshot()

    async def answer(self, answer: str) -> dict[str, Any]:
        if self.state != "awaiting_input" or not self.pending_question:
            raise ValueError("NOX is not waiting for a clarification.")
        original = self.instruction
        combined = f"{original}. User clarification: {answer[:1000]}"
        if self.task and not self.task.done():
            self.stop_event.set()
            self.pause_event.set()
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.pending_question = None
        self.state = "idle"
        return await self.start_task(combined)

    async def confirm(self, approved: bool) -> dict[str, Any]:
        if self.state != "awaiting_confirmation" or self.decision is None or self.decision.done():
            raise ValueError("There is no consequential browser action awaiting confirmation.")
        self.decision.set_result(bool(approved))
        if approved:
            self.state = "running"
            self.pending_question = None
            self.pause_event.set()
        else:
            self.state = "cancelled"
            self.stop_event.set()
            self.pause_event.set()
        return self.snapshot()

    async def pause(self) -> dict[str, Any]:
        if self.state == "running":
            self.pause_event.clear()
            self.state = "paused"
        return self.snapshot()

    async def resume(self) -> dict[str, Any]:
        if self.state in {"paused", "awaiting_auth"}:
            self.pending_question = None
            self.state = "running"
            self.pause_event.set()
        return self.snapshot()

    async def stop(self) -> dict[str, Any]:
        self.stop_event.set()
        self.pause_event.set()
        if self.decision is not None and not self.decision.done():
            self.decision.set_result(False)
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await asyncio.wait_for(self.task, timeout=2)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        self.state = "cancelled"
        self.pending_question = None
        self.pending_confirmation = None
        self.updated_at = utc_now()
        return self.snapshot()

    async def screenshot(self) -> bytes:
        if self.page is None or self.page.is_closed():
            raise BrowserUnavailable("No browser page is open yet.")
        data = await self.page.screenshot(type="png", full_page=False, animations="disabled")
        if len(data) > MAX_SCREENSHOT_BYTES:
            raise BrowserUnavailable("Browser screenshot exceeded the safety size limit.")
        return data

    def snapshot(self) -> dict[str, Any]:
        page = self.page
        return {
            "enabled": os.getenv("NOX_BROWSER_ENABLED", "").strip() == "1",
            "available": self.page is not None and page is not None and not page.is_closed(),
            "task_id": self.task_id,
            "instruction": self.instruction[:300],
            "state": self.state,
            "current_url": page.url[:1500] if page and not page.is_closed() else "",
            "page_title": "",
            "current_step": self.current_step,
            "steps": self.steps,
            "pending_question": self.pending_question,
            "pending_confirmation": self.pending_confirmation,
            "result": self.result[:MAX_PAGE_TEXT],
            "error": self.error[:500],
            "updated_at": self.updated_at,
            "history": self.history[-10:],
            "headless": os.getenv("NOX_BROWSER_HEADLESS", "1").strip().lower() not in {"0", "false", "no"},
        }


class BrowserManager:
    def __init__(self):
        self.sessions: dict[str, BrowserSession] = {}

    def get(self, owner: str) -> BrowserSession:
        if owner not in self.sessions:
            self.sessions[owner] = BrowserSession(owner)
        return self.sessions[owner]

    async def close_all(self) -> None:
        for session in list(self.sessions.values()):
            await session.stop()
            await session.close()


manager = BrowserManager()
