# NOX AI

A futuristic, multilingual personal AI assistant starter built with React, Vite, and FastAPI.

## Features
- Responsive dark interface with red accents
- Spatial holographic command deck with live canvas particles, draggable glass panels, real task/capability state, and adjustable/reduced motion
- Chat UI with Hindi, Urdu, English, and Hinglish language selection
- Browser speech input/output where supported
- Hands-free Voice Mode with automatic speech turn-taking, interruption, mute/end controls, browser voice selection, and speed/volume settings
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



## Spatial holographic command deck

The dashboard uses the existing `frontend/src/HolographicCore.jsx` canvas renderer and a new `frontend/src/SpatialDashboard.jsx` composition; it adds no rendering dependency. The central core uses a lightweight projected 3D particle field, orbiting arcs, proximity links, pointer parallax, and live application state. Microphone visuals use measured input levels where available; browser speech-synthesis output is labelled as estimated playback activity because the browser does not expose its rendered output stream to this UI.

Panels show existing NOX data only: saved conversation history, backend-reported capabilities, task queue state, pairing status, and browser voice-session state. The dashboard quick composer shares the same input/chat pipeline; Stop Reply aborts the active browser chat request, and task rows expose cancellation through the existing task API. Camera preview, OS telemetry, and a 3D model editor are intentionally not displayed because those integrations are not currently exposed by the web app. Panel position, pin state, minimized/hidden panels, motion intensity, and reduced-motion preference are saved locally in this browser. Use panel header controls to move, pin, minimize, expand, hide, or restore panels. On narrow screens the dashboard becomes a stacked layout.

The canvas lowers its particle count on smaller/low-core-count devices, caps rendering resolution/frame rate, and pauses its animation loop while the page is hidden. WebGL is not required; if a 2D canvas context is unavailable, the core drawing is omitted while the rest of NOX remains usable.

## Voice Mode: setup and limitations

Voice Mode is available from the Conversation panel. Select **Start Voice Mode** and grant microphone permission when the browser asks. Use the controls to mute/unmute, interrupt spoken playback, adjust supported voice/speed/volume settings, or end the session. Ending the session stops recognition, cancels playback, and releases the microphone stream. Text chat remains available if voice features are unsupported.

**Current implementation:** NOX uses the browser's Speech Recognition API for recognition and Speech Synthesis for spoken replies, then sends recognized text through the same existing `/api/chat` endpoint and conversation history. Voice-detected action commands continue through the existing task/command handler. No speech-provider API key is required by this implementation, and it does not silently configure a paid speech service.

**Important limitations:** this is a browser-native, turn-based voice conversation, not low-latency server-side full-duplex audio streaming. Speech recognition support and available voices vary by browser, OS, language, and device; some browsers send recognition audio to their own service, so review your browser vendor's privacy terms. Hindi/English/Hinglish recognition quality depends on the browser's language support. The current voice UI offers playback interruption by button; reliable voice-activity interruption while NOX is speaking is not guaranteed. A supported browser and HTTPS (or localhost for development) are required for microphone access. No local STT/TTS model is bundled, so there are no local model hardware requirements; standard microphone/audio hardware is sufficient. Browser/OS speech features may use data or platform services, and this app cannot promise unlimited or universally offline speech.

## Deploy on Render
Create a **Web Service** from this repository. The included `render.yaml` defines the build/start commands and checks `/api/health` for service health. Add `OPENROUTER_API_KEY` as a secret environment variable in Render to enable provider-backed AI replies. Free hosting and third-party AI free tiers may have usage limits or sleep.

### Persistent cross-device storage

**Supabase setup (PostgreSQL):** Supabase is compatible with NOX's PostgreSQL storage. Create a Supabase project, open **Connect** in its dashboard, and copy the PostgreSQL connection string (prefer the Session pooler/connection option recommended for your hosting environment). In Render → your NOX service → **Environment**, add `SUPABASE_DB_URL` with that full connection string, including the password and any required SSL parameters. Use the server-side database connection string, **not** the publishable/anon key or service-role API key. Never put the database URL in frontend code or commit it to GitHub. Save and redeploy, then check `/api/health` for `"storage_backend": "postgresql"`. If `SUPABASE_DB_URL` is unset, NOX continues to use `DATABASE_URL` for existing PostgreSQL deployments.
The backend supports PostgreSQL for pairing sessions, device registrations, command relay records, and shared chat history. To enable it:

1. Create a PostgreSQL database with a provider you choose. Check its price, expiry, storage, and connection limits first; do not assume a free tier is permanent.
2. Copy its **internal** connection URL if the database and web service are on the same hosting provider; otherwise use the provider's recommended external URL.
3. In the Render web service, open **Environment** and set `DATABASE_URL` to that connection URL. Keep it private; never commit it to GitHub or share it in chat.
4. Save the environment change and redeploy the web service.
5. Open `https://YOUR-SERVICE.onrender.com/api/health`. Confirm `"storage_backend": "postgresql"` and `"durable_storage_configured": true`.

If `DATABASE_URL` is absent, NOX falls back to SQLite. On an ephemeral host filesystem, SQLite pairing data can disappear after a restart or redeploy. The health endpoint reports which storage mode is configured, but PostgreSQL must be provisioned and the URL added by the owner; the repository cannot create a database or configure secret values automatically.

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
- The opt-in Windows companion discovers apps with shortcuts in the Windows Start Menu and can launch a selected shortcut. It supports a small fixed list of terminal diagnostics/build commands and exact-ID WinGet installs for common software; unknown install requests open a search for official package details instead of executing web commands. Terminal tasks require a configured workspace where applicable. Portable apps without shortcuts may not appear. It can optionally connect to Home Assistant running on the home network to control a limited set of supported smart-home entities. See `desktop-companion/README.md`.
- The Windows companion also includes an opt-in passive website security checker for authorized public HTTPS sites. It checks common response security headers with a single request; it does not scan ports, crawl, brute-force, or exploit. See `desktop-companion/README.md`.
- A native Android companion source project is in `android-companion/`. It can open launchable installed apps and route `install <app name>` requests to Google Play search; Android still requires the user to choose and install the app. Build/install it separately. Its broad package-visibility permission is subject to Google Play policy.
- The frontend routes Android app-open commands to the native companion through `nox://launch?query=...`. The companion must be installed on that phone. iOS arbitrary app launch is not supported.
- The hosted HTTPS-to-local HTTP bridge may be blocked by browser local-network/mixed-content policy; this has not been verified on the user's browser. General desktop automation, file access, and silent/unconfirmed app control are not implemented.
- Never store API keys in frontend code or commit them to Git. Configure provider credentials as Render environment secrets.
- A hosted AI provider key is required for provider-backed chat; free tiers and hosting quotas may change.


## Cross-device chat history (paired devices)

The latest frontend/backend adds an authenticated shared conversation store for devices in the same NOX pairing session. The browser requests history using its paired-device token; the API checks that the token belongs to the requested session. It supports listing, saving, and deleting conversations and keeps up to 30 conversations per session. Unpaired devices cannot read that session's history through these endpoints.

**Persistence note:** the current default uses SQLite at `nox_pairing.sqlite3`. On hosting platforms with an ephemeral filesystem, stored pairings, commands, and shared chat history can be lost when the service restarts or redeploys. For durable production use, configure a persistent disk or migrate the store to a managed database. Cross-device sync also requires the same active pairing session on each device.

## What “from anywhere” requires

NOX is a growing, permissioned assistant, not yet a universal remote-control layer. The hosted web app can chat and route supported commands; local app/device actions require the appropriate companion to be installed, paired, running, and granted OS permissions. Browsers and mobile operating systems intentionally block unrestricted background access. Purchases, sending messages, destructive edits, and other consequential actions should keep explicit confirmation. Do not put API keys or device tokens in public repositories.
