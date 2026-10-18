# NOX AI

A futuristic, multilingual personal AI assistant starter built with React, Vite, and FastAPI.

## Features
- Responsive dark interface with red accents
- Chat UI with Hindi, Urdu, English, and Hinglish language selection
- Browser speech input/output where supported
- FastAPI backend with optional OpenRouter-compatible AI provider
- Bounded autonomous task worker with tool-calling public-web search and page reading
- Demo fallback when no AI API key is configured
- Render deployment configuration

## Run locally
1. Install Node.js 20+ and Python 3.11+.
2. Install backend dependencies: `pip install -r backend/requirements.txt`
3. Install frontend dependencies: `cd frontend && npm install`
4. Build frontend: `npm run build`
5. From the repository root run: `uvicorn backend.main:app --reload`
6. Open `http://127.0.0.1:8000`.

## AI provider
Set `OPENROUTER_API_KEY` in your hosting environment to enable provider-backed responses. Optionally set `OPENROUTER_MODEL`. Without a key, the app uses a simple demo response; it is not a full AI model.

## Deploy on Render
Create a **Web Service** from this repository. The included `render.yaml` defines the build and start commands. Add `OPENROUTER_API_KEY` as a secret environment variable in Render if you have one. Free hosting and third-party AI free tiers may have usage limits or sleep.

## NOX device pairing (early implementation)

The UI now includes **Pair devices**. On the first browser, create a pairing code; on the second browser, enter that code within five minutes. The pairing API stores per-device bearer tokens, lists devices in the same session, supports explicit per-device disconnect, and exposes an authenticated command queue for companion clients. The browser saves its token in local storage and retries the status check while the page is open.

**Current scope:** Windows and Android companions can join a six-digit pairing session and poll queued commands. Windows supports Start Menu app shortcuts, known websites, explicit HTTP(S) URLs, and web search. With the optional local Home Assistant adapter configured, Windows can also control supported lights, plugs/switches, fans, TVs/media players, and climate setpoints and list supported entity statuses. See `desktop-companion/README.md`. It does not automatically connect every household device; devices must be supported by and integrated into Home Assistant. The Android companion runs as a foreground service and may show a notification that must be tapped when Android blocks background app launches. Keep companions running and their OS services/notifications enabled. Browser-only pairing does not grant OS-level control. Do not share pairing codes or device tokens. The SQLite database defaults to `nox_pairing.sqlite3` in the service directory; on hosting platforms with ephemeral filesystems, pairing records can be lost after redeploy/restart unless `NOX_PAIRING_DB` points to persistent storage.

## Security
Never commit API keys or passwords. Configure secrets in Render environment variables.


## Command execution behavior

- NOX should execute clear, allowed, low-risk commands immediately and should not repeat the user's request or ask for redundant confirmation.
- It should infer sensible defaults for routine tasks and ask a concise follow-up only when a missing detail is essential or materially different choices exist.
- Confirmation remains required for consequential actions such as sending/posting messages, purchases/payments, deleting or overwriting data, sharing private information, or changing security settings. Authentication and operating-system/browser permission prompts are not bypassed.
- Website-opening commands no longer show a redundant confirmation dialog. On Windows, app launch still requires the user's configured local companion token; if multiple apps match, NOX asks which app to open.

## Autonomous task worker and current limits

- Tasks submitted to the task panel now run through a bounded tool-using agent. With OPENROUTER_API_KEY configured, it can search the public web, read public HTML/text pages, use those results to reason, and return a result with source URLs.
- The agent has a maximum of five tool-call rounds per task. It blocks local/private IP targets and only reads public HTTP/HTTPS HTML or plain-text pages. Web page content is treated as untrusted input.
- The command panel opens recognized websites (for example, YouTube, Google, GitHub, Instagram, WhatsApp Web, ChatGPT, and Render) or an explicit HTTP(S) URL in a new tab directly when the user clearly asks. This opens the page in the user's browser; it does not automate the page.
- The current web-research worker does not log in, submit forms, send messages, purchase items, execute shell commands, or perform general desktop control.
- The opt-in Windows companion discovers apps with shortcuts in the Windows Start Menu and can launch a selected shortcut after token authentication and confirmation. Portable apps without shortcuts may not appear. It can optionally connect to Home Assistant running on the home network to control a limited set of supported smart-home entities. See `desktop-companion/README.md`.
- The Windows companion also includes an opt-in passive website security checker for authorized public HTTPS sites. It checks common response security headers with a single request; it does not scan ports, crawl, brute-force, or exploit. See `desktop-companion/README.md`.
- A native Android companion source project is in `android-companion/`. It can list launchable apps visible to Android and lets the user choose an app matching the requested name. Build/install it separately; no APK has been built or installed in this session. Its broad package-visibility permission is subject to Google Play policy.
- The frontend routes Android app-open commands to the native companion through `nox://launch?query=...`. The companion must be installed on that phone. iOS arbitrary app launch is not supported.
- The hosted HTTPS-to-local HTTP bridge may be blocked by browser local-network/mixed-content policy; this has not been verified on the user's browser. General desktop automation, file access, and silent/unconfirmed app control are not implemented.
- Never store API keys in frontend code or commit them to Git. Configure provider credentials as Render environment secrets.
- A hosted AI provider key is required for provider-backed chat; free tiers and hosting quotas may change.
