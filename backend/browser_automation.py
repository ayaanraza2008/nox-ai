"""Session-scoped, safety-gated Playwright browser automation for NOX AI."""
from __future__ import annotations
import asyncio, ipaddress, os, re, socket, time, uuid
from urllib.parse import quote_plus, urlsplit, urlunsplit
try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

MAX_SESSIONS = max(1, min(int(os.getenv("NOX_BROWSER_MAX_SESSIONS", "3")), 12))
TIMEOUT_MS = max(3000, min(int(os.getenv("NOX_BROWSER_ACTION_TIMEOUT_MS", "12000")), 30000))
NAV_TIMEOUT_MS = max(5000, min(int(os.getenv("NOX_BROWSER_NAVIGATION_TIMEOUT_MS", "20000")), 45000))
DANGEROUS = re.compile(r"\b(submit|send|publish|post|purchase|buy|pay|checkout|book|confirm|delete|remove|cancel subscription|transfer|place order|apply now)\b", re.I)
AUTH = re.compile(r"\b(sign in|log in|login|verify|two.factor|one.time password|captcha|passkey|authentication required)\b", re.I)

class BrowserAgentError(RuntimeError):
    pass

class BrowserAgent:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.sessions = {}
        self.lock = asyncio.Lock()

    @property
    def available(self):
        return async_playwright is not None

    async def _ensure_browser(self):
        if not self.available:
            raise BrowserAgentError("Playwright is not installed. Install backend requirements and Chromium.")
        if self.browser and self.browser.is_connected():
            return
        if self.playwright is None:
            self.playwright = await async_playwright().start()
        try:
            self.browser = await self.playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        except Exception as exc:
            raise BrowserAgentError("Chromium is unavailable. Install it on the server with playwright install chromium, then redeploy.") from exc

    async def _public_url(self, url):
        parsed = urlsplit((url or "").strip())
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise BrowserAgentError("Enter a complete public HTTP or HTTPS URL.")
        if parsed.username or parsed.password:
            raise BrowserAgentError("URLs containing embedded credentials are blocked.")
        host = parsed.hostname.rstrip(".").lower()
        if host in {"localhost", "localhost.localdomain", "metadata.google.internal"} or host.endswith((".localhost", ".local", ".internal")):
            raise BrowserAgentError("Private and local network destinations are blocked.")
        try:
            ip = ipaddress.ip_address(host)
            if not ip.is_global:
                raise BrowserAgentError("Private, loopback, and reserved IP addresses are blocked.")
        except ValueError:
            try:
                records = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM), timeout=3)
                addresses = {ipaddress.ip_address(r[4][0]) for r in records}
                if not addresses or any(not addr.is_global for addr in addresses):
                    raise BrowserAgentError("This host resolves to a private or reserved network address and is blocked.")
            except asyncio.TimeoutError as exc:
                raise BrowserAgentError("Could not safely resolve this hostname. Please try again.") from exc
            except socket.gaierror as exc:
                raise BrowserAgentError("The website hostname could not be resolved.") from exc
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))

    async def _route_guard(self, route):
        try:
            await self._public_url(route.request.url)
            await route.continue_()
        except Exception:
            await route.abort("blockedbyclient")

    def _event(self, s, message, status="info"):
        s["events"].append({"at": int(time.time()), "message": str(message)[:400], "status": status})
        s["events"] = s["events"][-40:]
        s["updated_at"] = int(time.time())

    async def _session(self, owner):
        async with self.lock:
            s = self.sessions.get(owner)
            if s and not s["closed"]:
                return s
            if sum(not x["closed"] for x in self.sessions.values()) >= MAX_SESSIONS:
                raise BrowserAgentError("All remote browser slots are busy. Stop an idle session and retry.")
            await self._ensure_browser()
            context = await self.browser.new_context(viewport={"width": 1365, "height": 850}, accept_downloads=True)
            context.set_default_timeout(TIMEOUT_MS)
            context.set_default_navigation_timeout(NAV_TIMEOUT_MS)
            await context.route("**/*", self._route_guard)
            page = await context.new_page()
            s = {"id": uuid.uuid4().hex, "owner": owner, "context": context, "page": page, "closed": False,
                 "status": "ready", "task": "No task running", "events": [], "pending": None, "downloads": [],
                 "created_at": int(time.time()), "updated_at": int(time.time()), "lock": asyncio.Lock()}
            page.on("download", lambda d: s["downloads"].append({"name": d.suggested_filename[:180], "url": d.url[:1000], "saved": False}))
            self.sessions[owner] = s
            self._event(s, "Remote Chromium session created.", "success")
            return s

    async def state(self, owner):
        s = self.sessions.get(owner)
        if not s or s["closed"]:
            return {"available": self.available, "active": False, "status": "idle", "task": "No task running", "events": [], "downloads": []}
        title, url = "", ""
        try:
            if not s["page"].is_closed():
                title, url = (await s["page"].title())[:300], s["page"].url[:1500]
        except Exception:
            pass
        return {"available": self.available, "active": True, "session_id": s["id"], "status": s["status"], "task": s["task"],
                "title": title, "url": url, "events": list(s["events"]), "pending_confirmation": bool(s["pending"]),
                "downloads": list(s["downloads"][-10:]), "updated_at": s["updated_at"], "remote": True}

    async def screenshot(self, owner):
        s = self.sessions.get(owner)
        if not s or s["closed"] or s["page"].is_closed():
            raise BrowserAgentError("Open a website first to see the remote browser preview.")
        try:
            return await s["page"].screenshot(type="png", full_page=False, animations="disabled", timeout=5000)
        except Exception as exc:
            raise BrowserAgentError("The current page preview is temporarily unavailable.") from exc

    def _safe_command_summary(self, command):
        # Never put literal field values into task state or the audit log.
        typed = re.search(r"(?is)\btype\s+(.+?)\s+into\s+(?:the\s+)?(.+?)\s+(?:field|box|input)\s*$", command)
        if typed:
            return "Type [value redacted] into " + typed.group(2).strip().strip("\"' .")[:100]
        return command[:180]

    async def run(self, owner, command, language="auto"):
        command = (command or "").strip()
        if not command or len(command) > 2000:
            raise BrowserAgentError("Enter a browser instruction (maximum 2,000 characters).")
        s = await self._session(owner)
        async with s["lock"]:
            summary = self._safe_command_summary(command)
            s["task"], s["status"] = summary[:300], "running"
            self._event(s, "Task started: " + summary)
            try:
                result = await self._execute(s, command)
                if s["status"] == "running":
                    s["status"] = "completed"
                self._event(s, result, "success" if s["status"] == "completed" else "attention")
            except BrowserAgentError as exc:
                s["status"] = "error"
                self._event(s, str(exc), "error")
                raise
            except Exception as exc:
                if s["status"] != "stopped":
                    s["status"] = "error"
                self._event(s, "Browser action interrupted." if s["status"] == "stopped" else "Browser action failed: " + type(exc).__name__, "attention" if s["status"] == "stopped" else "error")
                raise BrowserAgentError("That browser action failed. I rechecked the page; try a more specific instruction.") from exc
            return {"result": result, "state": await self.state(owner)}

    async def _execute(self, s, command):
        page, lower = s["page"], command.lower().strip()
        open_match = re.search(r"\b(?:open|go to|navigate to|visit)\s+(https?://\S+)", command, re.I)
        bare_url = re.fullmatch(r"https?://\S+", command, re.I)
        search_match = re.search(r"\b(?:search(?: the web)? for|google|look up)\s+(.+)", command, re.I)
        if open_match or bare_url:
            raw = (open_match.group(1) if open_match else command).rstrip(".,)")
            target = await self._public_url(raw)
            await page.goto(target, wait_until="domcontentloaded")
            await page.wait_for_timeout(400)
            title = (await page.title())[:200]
            return f"Opened {page.url}. Page title: {title or '(no title)'}."
        if search_match:
            query = search_match.group(1).strip().strip('"')
            if not query:
                raise BrowserAgentError("What should I search for?")
            await page.goto("https://html.duckduckgo.com/html/?q=" + quote_plus(query), wait_until="domcontentloaded")
            await page.wait_for_timeout(300)
            return "Search results for " + query + ":\n\n" + (await page.locator("body").inner_text())[:5000]
        if re.search(r"\b(inspect|read|summarize|what does this page|tell me about this page)\b", lower):
            if page.is_closed() or page.url == "about:blank":
                raise BrowserAgentError("Open a website first, or say: open https://example.com")
            text = re.sub(r"\n{3,}", "\n\n", (await page.locator("body").inner_text()).strip())
            return f"Page: {await page.title()}\nURL: {page.url}\n\n{text[:6500] or '(No readable page text found.)'}"
        click = re.search(r"\bclick\s+(?:the\s+)?(?:button|link|tab|menu item)?\s*[\"']?(.+?)[\"']?$", command, re.I)
        if click:
            label = click.group(1).strip().strip("\"' .")
            if not label:
                raise BrowserAgentError("Which visible button or link should I click?")
            loc = page.get_by_role("button", name=re.compile(re.escape(label), re.I)).or_(page.get_by_role("link", name=re.compile(re.escape(label), re.I)))
            if await loc.count() == 0:
                loc = page.get_by_text(re.compile(re.escape(label), re.I), exact=False)
            if await loc.count() == 0:
                raise BrowserAgentError(f"I couldn't find a visible control matching '{label}'. Inspect the page and retry.")
            info = await loc.first.evaluate("""el => {
                const form = el.closest('form');
                return {type:(el.getAttribute('type')||'').toLowerCase(), action:form ? (form.getAttribute('action')||'') : '',
                    context:form ? (form.innerText||'').slice(0,500) : ''};
            }""")
            sensitive_form = DANGEROUS.search(" ".join([label, info.get("action", ""), info.get("context", ""), page.url]))
            if DANGEROUS.search(label) or (info.get("type") == "submit" and sensitive_form):
                s["pending"] = {"action": "click", "label": label}
                s["status"] = "awaiting_confirmation"
                return f"'{label}' may submit or change information. Confirm before I click it."
            await loc.first.click()
            await page.wait_for_timeout(250)
            return f"Clicked '{label}'. Current page: {await page.title()} — {page.url}"
        type_match = re.search(r"\btype\s+(.+?)\s+into\s+(?:the\s+)?(.+?)\s+(?:field|box|input)\s*$", command, re.I)
        if type_match:
            value, label = type_match.group(1).strip().strip("\"'"), type_match.group(2).strip().strip("\"' .")
            if re.search(r"password|passcode|one.?time|\\botp\\b|verification code|security code|cvv|card number|social security|identity number|access token|secret", label, re.I):
                raise BrowserAgentError("For safety, NOX will not type passwords, one-time codes, payment-card details, identity numbers, or secrets. Enter those directly through the legitimate website flow.")
            loc = page.get_by_label(re.compile(re.escape(label), re.I)).or_(page.get_by_placeholder(re.compile(re.escape(label), re.I))).or_(page.get_by_role("textbox", name=re.compile(re.escape(label), re.I)))
            if not value or not label or await loc.count() == 0:
                raise BrowserAgentError(f"I couldn't find a field labelled '{label}'. Inspect the page and try its visible label.")
            await loc.first.fill(value)
            return f"Filled the '{label}' field. I have not submitted the form."
        if re.search(r"\b(scroll|scroll down|show more)\b", lower):
            direction = -1 if "up" in lower else 1
            await page.evaluate("(direction) => window.scrollBy(0, direction * Math.max(400, window.innerHeight * 0.75))", direction)
            return "Scrolled the current page."
        if re.search(r"\b(go back|back a page|previous page)\b", lower):
            await page.go_back(wait_until="domcontentloaded")
            return f"Navigated back to {page.url}."
        if re.search(r"\b(go forward|forward a page|next page)\b", lower):
            await page.go_forward(wait_until="domcontentloaded")
            return f"Navigated forward to {page.url}."
        if re.search(r"\b(download|save this file)\b", lower):
            loc = page.get_by_role("link", name=re.compile(r"download|report|export|csv|pdf", re.I))
            if await loc.count() == 0:
                raise BrowserAgentError("I couldn't identify a clear download link. Inspect the page and specify its label.")
            label = (await loc.first.inner_text())[:120]
            s["pending"] = {"action": "download", "label": label}
            s["status"] = "awaiting_confirmation"
            return "I found a possible download link. Confirm to activate it."
        if page.url != "about:blank" and AUTH.search((await page.locator("body").inner_text())[:2500]):
            s["status"] = "auth_required"
            return "This page may require authentication. Sign in only through the website's legitimate flow. This remote preview has no direct keyboard/mouse bridge for login; an authorized interactive companion is required to complete that step."
        raise BrowserAgentError("Try: open https://example.com; search the web for ...; inspect this page; click the link ...; type ... into the search field; scroll down; go back.")

    async def confirm(self, owner, approved):
        s = self.sessions.get(owner)
        if not s or s["closed"] or not s["pending"]:
            raise BrowserAgentError("There is no browser action waiting for confirmation.")
        async with s["lock"]:
            pending, s["pending"] = s["pending"], None
            if not approved:
                s["status"] = "paused"
                self._event(s, "User declined the pending browser action.", "attention")
                return {"result": "Action cancelled; nothing was clicked.", "state": await self.state(owner)}
            page, label = s["page"], pending["label"]
            if pending["action"] == "click":
                loc = page.get_by_role("button", name=re.compile(re.escape(label), re.I)).or_(page.get_by_role("link", name=re.compile(re.escape(label), re.I)))
                if await loc.count() == 0:
                    raise BrowserAgentError("The page changed; I couldn't find that control. Inspect it again before retrying.")
                await loc.first.click()
            else:
                loc = page.get_by_role("link", name=re.compile(re.escape(label), re.I))
                async with page.expect_download(timeout=15000) as info:
                    await loc.first.click()
                download = await info.value
                filename = re.sub(r"[^A-Za-z0-9._ -]", "_", download.suggested_filename)[:160] or "download"
                directory = os.path.abspath(os.getenv("NOX_BROWSER_DOWNLOAD_DIR", "/tmp/nox-browser-downloads"))
                os.makedirs(directory, exist_ok=True)
                path = os.path.join(directory, filename)
                await download.save_as(path)
                s["downloads"].append({"name": filename, "saved": True, "path": path})
            s["status"] = "completed"
            self._event(s, "Confirmed action completed: " + label, "success")
            return {"result": "Confirmed action completed: " + label, "state": await self.state(owner)}

    async def stop(self, owner):
        s = self.sessions.get(owner)
        if not s or s["closed"]:
            return {"status": "idle"}
        # Do not wait on the command lock: closing the context interrupts a stuck navigation/action.
        s["pending"] = None
        s["status"] = "stopped"
        self._event(s, "Browser session stopped by user.", "attention")
        try:
            await s["context"].close()
        finally:
            s["closed"] = True
        return {"status": "stopped", "message": "Remote browser session closed."}

    async def close(self):
        for s in list(self.sessions.values()):
            if not s["closed"]:
                try:
                    await s["context"].close()
                except Exception:
                    pass
        self.sessions.clear()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.browser = self.playwright = None

browser_agent = BrowserAgent()
