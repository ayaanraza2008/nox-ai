# NOX AI

A futuristic, multilingual personal AI assistant with a responsive holographic command deck served by FastAPI.

## Features
- Responsive dark interface with red accents
- Spatial holographic command deck with a Three.js/WebGL particle core, draggable glass panels, real task/capability state, and reduced-motion support
- Chat UI with Hindi, Urdu, English, and Hinglish language selection
- Browser speech recognition plus neural TTS using Edge voices, with language-aware Hindi/Hinglish/Urdu/English routing
- Hands-free Voice Mode with sentence-level speech queued while the AI response is still streaming, interruption, mute/end controls, selectable compatible voices, and speaking-speed settings
- Optional voice timing diagnostics via `?debug=1`; timings are measured in the browser, while TTS generation duration is logged by the backend
- FastAPI backend with optional OpenRouter-compatible AI provider
- Bounded autonomous task worker with tool-calling public-web search and page reading
- Demo fallback when no AI API key is configured
- Render deployment configuration


## Knowledge Index (initial implementation)

NOX includes a session-scoped knowledge index for user-provided documents and individual public URLs.

- **Ingestion:** public HTML/plain-text/JSON URLs (only after checking the site's `robots.txt`) and uploaded TXT, Markdown, CSV, JSON, HTML, common source-code/text formats, PDF, DOCX, and XLSX.
- **Extraction and indexing:** normalized text, SHA-256 duplicate detection, bounded overlapping chunks, source metadata, and SQLite FTS5 lexical search.
- **RAG integration:** both normal and streaming chat retrieve up to four matching passages from the current browser session and pass them to the model as untrusted evidence. The model is instructed to cite the source title/location and not to follow instructions embedded in retrieved pages.
- **Privacy:** sources, chunks, searches, and deletion are scoped to the server-issued `nox_session` cookie. A source ID alone does not grant access to another session's indexed data.
- **Dashboard:** the Knowledge Index workspace shows actual source/chunk counts, stored bytes, source links, search passages, and per-source deletion.

### Knowledge Index configuration and limitations

- Install dependencies with `pip install -r backend/requirements.txt`; PDF extraction uses `pypdf`, and browser file uploads use `python-multipart`.
- The default database path is `nox_knowledge.sqlite3` at the repository root. Set `NOX_KNOWLEDGE_DB` to a path on a persistent mounted disk if the hosting platform provides one. **Render's default ephemeral filesystem can lose this index on redeploy/restart**, so configure durable storage before relying on it.
- Upload size defaults to 10 MiB per file (`NOX_KNOWLEDGE_MAX_UPLOAD_BYTES`); extracted text is capped at 1,000,000 characters per source (`NOX_KNOWLEDGE_MAX_TEXT_CHARS`).
- Search currently uses SQLite FTS5 and a keyword fallback. **Vector embeddings, semantic vector search, OCR for scanned PDFs, scheduled synchronization, multi-page crawling, and OAuth connectors (Drive/OneDrive/Notion/email/calendar/private GitHub) are not implemented or configured yet.** This release must not be described as indexing the entire internet or as a complete universal connector engine.
- URL ingestion refuses private/local IP ranges and redirects, and fails closed if it cannot verify `robots.txt`. Sites may still block requests or return content the extractor cannot read.
- Only index material you are authorized to access. Retrieved web/document content is treated as evidence, not instructions. No credentials are collected for third-party services by this initial implementation.

### Knowledge Index API

- `GET /api/knowledge` — source list and live index counts.
- `POST /api/knowledge/urls` with JSON `{"url":"https://example.org/docs"}` — index one permitted public URL.
- `POST /api/knowledge/upload` with multipart field `file` — index one supported document.
- `POST /api/knowledge/search` with JSON `{"query":"your question","limit":6}` — retrieve source passages.
- `DELETE /api/knowledge/sources/{source_id}` — remove the source, chunks, and searchable index entries.

Every endpoint requires the current browser session cookie. No counts in the UI are hardcoded.

## Run locally
1. Install Python 3.11+.
2. Install backend dependencies: `pip install -r backend/requirements.txt`
3. From the repository root run: `uvicorn backend.main:app --reload`
4. Open `http://127.0.0.1:8000`.

The frontend is a dependency-free static dashboard in `frontend/dist/index.html`. FastAPI serves it from the same origin as `/api/*`, so no separate frontend server or Node build is required.

## Voice quality and diagnostics

NOX keeps its existing neural TTS defaults (Madhur for Devanagari Hindi, Guy for US English, and Asad for Urdu) unless the user selects another voice in the Voice panel. The selectable list includes Hindi Madhur/Swara, Indian English Prabhat/Neerja, US English Guy, and Urdu Asad. Voice IDs are allowlisted server-side. The app cannot validate subjective voice quality without listening to generated audio on the target device; provider voice availability may change.

For Roman Hinglish sent to a Hindi neural voice, the backend transliterates a conservative set of common Hindi words to Devanagari while leaving technical/product words in Latin script. This is intentionally not advertised as full transliteration: uncommon spellings and names may still need better handling. For example, `Mera laptop slow chal raha hai` becomes a mixed-script TTS phrase rather than forcing every English technical word into Hindi.

Voice mode begins speaking each complete sentence as soon as it arrives from the AI stream, instead of waiting for the entire answer before starting TTS. The TTS endpoint still buffers each sentence's audio before browser playback, so this is overlapped AI/TTS generation rather than true chunked-audio playback. Browser SpeechRecognition controls its own endpointing and language model; this project does not claim custom VAD or a guaranteed 300–800 ms reply.

Open NOX with `?debug=1` to show per-turn browser timings for speech-end/final transcript, recognition completion, first AI token, first TTS audio ready, and first playback start (a proxy for audible onset). TTS generation duration and selected voice are logged server-side. Compare these timings on the actual deployment/device; automated CI cannot verify subjective pronunciation or physical speaker latency.

## AI provider and image input
Set `OPENROUTER_API_KEY` in your hosting environment to enable provider-backed responses. Optionally set `OPENROUTER_MODEL`. Without a key, the app uses a simple demo response; it is not a full AI model.

**Image understanding:** the Vision & Media panel accepts one PNG, JPEG, or WebP image up to 5 MB. After selecting it, send a chat message (or send the image without text) to submit it to the configured model. The image is not sent just by selecting it. OpenAI-compatible vision payloads are routed to `OPENROUTER_VISION_MODEL` when configured, or to the configured OpenRouter model as a fallback; Gemini uses `GEMINI_VISION_MODEL` or `GEMINI_MODEL`. Groq is skipped for image requests unless `GROQ_VISION_MODEL` is explicitly set. A model must actually support image input; a free-model router does not guarantee vision support, and provider quotas/availability still apply. No image-analysis success is reported when the provider is missing or the model rejects the payload. Uploaded image data is sent to the selected provider only when the user submits the chat request; review that provider's data policy before sending sensitive images.



## Spatial holographic command deck

The dashboard lives in `frontend/dist/index.html` and is served by the existing FastAPI static mount. It includes a responsive floating glass-panel layout, a Three.js/WebGL holographic core with orbital rings and particles (with a lightweight fallback if the library cannot initialize), real backend health/capability/task data, chat via `/api/chat`, task creation and cancellation, browser speech recognition and speech synthesis where supported, panel pin/minimize/hide controls, local motion and language preferences, and a reduced-motion mode. Core state is connected to real UI activity; visual animation does not claim that a task is running. The core pauses rendering while the page is hidden. Actual browser-level WebGL and microphone/TTS synchronization still need runtime testing on supported devices.

Camera preview, OS telemetry, a 3D model editor, and full desktop control are not shown because those integrations are not exposed by the web app.

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

## Security and browser-session isolation
Never commit API keys or passwords. Configure secrets in Render environment variables.

Task listing, task details/actions, and saved-chat endpoints are scoped to an opaque, server-issued `HttpOnly`, `SameSite=Lax` browser-session cookie (`nox_session`). The frontend requests `/api/session` before calling those endpoints. This prevents a caller from selecting another browser's task/history scope by changing a public `user_id` query parameter, and task ownership is persisted in the task database with a migration for existing SQLite/PostgreSQL tables. These anonymous sessions are **not** user accounts: they do not provide identity verification, cross-device login, or protection if the browser cookie is stolen. The public chat/TTS endpoints are still not an account-authenticated API and should receive additional abuse controls before broad production exposure. Legacy chat rows from the old client-supplied `user_id` scheme are not deleted, but they are not automatically migrated into a new session.


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


## Streaming chat and provider routing

NOX exposes `POST /api/chat/stream` using Server-Sent Events so assistant text appears while the provider is generating it. The existing `POST /api/chat` endpoint remains available for compatibility. Recent user/assistant turns are sent as bounded context (up to 12 turns at the provider), and image requests use the configured vision model.

Provider selection is configurable with `NOX_CHAT_PROVIDER=auto|openrouter|groq|gemini`. The default `auto` keeps the OpenRouter → Groq → Gemini fallback order; selecting a provider moves it to the front while other configured providers remain fallbacks. Model names remain configured separately with `OPENROUTER_MODEL`, `GROQ_MODEL`, and `GEMINI_MODEL`; vision models use `OPENROUTER_VISION_MODEL`, `GROQ_VISION_MODEL`, and `GEMINI_VISION_MODEL`. Keep API keys only in the hosting environment, never in frontend code. Streaming reduces perceived wait time but does not make a slow provider faster, and provider/model availability and quotas still apply.


## Response relevance and context handling

Streaming and non-streaming chat now share the same system prompt and context builder. The prompt prioritizes answering the current question directly, resolving follow-ups from recent turns, matching Hindi/Urdu/English/Hinglish naturally, avoiding unrelated filler, and acknowledging/correcting a reply when the user says it missed the point. The builder filters malformed turns and bounds history text so old messages are less likely to crowd out the current request. This improves behavior but cannot guarantee every model/provider will follow instructions perfectly; model quality and context limits still matter.


## Particle Transformation & Holographic Globe Lab (initial phase)

Open **3D LAB** from the command deck to explore the separate Three.js workspace. Built-in examples (sports car, motorcycle, heart, robot head, and Earth) use procedural Three.js geometry; the particle targets are sampled from mesh triangles, with curved interpolation between the previous and next formation. The viewer supports particle/solid display modes, rotation, zoom, pause/resume, density adjustment, reset, and return-to-core. Recognized commands typed or spoken through the existing chat pipeline can open the lab and trigger supported local actions.

### Geography and privacy boundaries

- The globe uses a sphere plus Natural Earth land-boundary GeoJSON from `nvkelso/natural-earth-vector` when that public source is reachable. This is not satellite imagery and is not live Earth data.
- Place lookup uses OpenStreetMap Nominatim and may be rate-limited or unavailable. Lookup markers are based on geocoder results or user-entered coordinates and are not live device positions.
- The phone field only validates international-format input and matches a small built-in set of calling-code prefixes. A phone number alone cannot reveal a subscriber's precise or live GPS location.
- Authorized live-device sharing, OBJ/GLB imports, and a text-to-3D provider adapter are not part of this initial phase.

### Realistic model generation limits

Solid mode displays the procedural mesh and its materials; it does not mean NOX has generated a photorealistic AI model. No text-to-3D API key or paid provider is required for the built-in examples. An actual AI model-generation provider and supported GLB/GLTF import can be added as a later phase after selecting a provider and reviewing its pricing, quotas, licensing, and key-storage requirements.


## Autonomous Agent Swarm (initial bounded implementation)

NOX includes a separate **Agent Swarm** workspace that accepts a complex objective, asks the configured AI provider for a structured plan, validates role assignments and dependency references, executes independent specialist tasks concurrently, passes completed dependency artifacts to downstream tasks, and asks an integration lead to produce one unified result. Job contracts, role/state, timestamps, events, results, and errors are stored in a separate SQLite database and scoped to the current browser session.

### API and controls

- `POST /api/swarm/jobs` with `{"goal":"...","language":"auto"}` creates a job (HTTP 202).
- `GET /api/swarm/jobs?limit=20` lists the current session's jobs.
- `GET /api/swarm/jobs/{job_id}` returns the plan, specialist statuses, event log, artifacts, and final result.
- `POST /api/swarm/jobs/{job_id}/cancel` cancels unfinished in-process work.
- The frontend's **AGENT SWARM** button opens the live node visualization; it polls actual job state rather than inventing progress percentages.

### Configuration and limitations

- Requires server-side `OPENROUTER_API_KEY`; optionally set `NOX_SWARM_MODEL` (defaults to `OPENROUTER_MODEL` or `openai/gpt-4o-mini`).
- `NOX_SWARM_MAX_AGENTS` defaults to 3 (bounded 1–5); `NOX_SWARM_MAX_TASKS` defaults to 5 (bounded 2–8); `NOX_SWARM_TASK_TIMEOUT` defaults to 90 seconds (bounded 15–180).
- Set `NOX_SWARM_DB` to a persistent disk path if swarm history must survive Render redeploys. Default is `/tmp/nox_swarm.sqlite3`, which may be ephemeral.
- Each specialist is a separate provider call with a scoped role and task contract. The current version generates plans and text artifacts; it does **not** grant agents shell, repository-write, arbitrary browsing, deployment, purchase, messaging, image/video generation, or desktop-control tools. Agent role labels do not imply those integrations exist.
- Independent tasks run concurrently up to the configured limit; dependency cycles are rejected. A failed dependency blocks dependent tasks, and a failed job does not claim a unified success. Cancellation is best-effort for in-flight provider requests. A server restart marks in-flight jobs failed rather than claiming they resumed.
- This first phase uses bounded asyncio work within one application process, not a distributed durable queue. For multi-instance production use, add a shared job broker/worker system and database-level claim/lease semantics.


## Safe Tool Bench (deterministic utilities)

The Agent Swarm workspace includes a **Safe Tool Bench** with three bounded, deterministic utilities:

- **Calculator:** parses arithmetic with Python's AST but only permits numeric literals, parentheses, unary signs, and basic arithmetic operators. It does not evaluate arbitrary Python expressions, function calls, names, or imports.
- **Text analyzer:** reports character/word/line counts, unique words, frequent terms, and a rough reading-time estimate.
- **JSON validate / format:** validates standard JSON and returns an indented representation plus top-level type and keys.

The tools are available through `POST /api/tools/execute` with `{"tool":"calculator","input":"(125 * 8) / 4"}`. Calls require the existing browser-session cookie. Input size and expression complexity are bounded. Tool execution is local and deterministic: it does not call an AI provider or access the shell, filesystem, or network. Results are returned to the requesting browser and are not saved as a separate history.


### Code Review Lab (safe preview tools)

The Safe Tool Bench also includes:

- **Python syntax check:** parses Python source into an AST and reports syntax errors with line/column details, or basic structural counts when parsing succeeds. It never executes the submitted code and cannot prove runtime correctness.
- **Code diff preview:** accepts a JSON object with string fields `original` and `proposed`, then shows a bounded unified diff with added/removed line counts. It is preview-only; NOX does not write files or apply patches.

Both utilities enforce input limits and are covered by automated tests. This is a review aid, not a sandbox or a repository editing/execution environment.


### Agent Swarm live updates

The Agent Swarm workspace subscribes to `GET /api/swarm/jobs/{job_id}/events`, a same-origin Server-Sent Events stream. It emits the latest persisted job snapshot when the job changes and closes when the job reaches a terminal state or the browser disconnects. The stream is scoped to the existing HttpOnly browser session; a missing or foreign job is rejected before streaming. Browsers without EventSource support, or where the stream disconnects, fall back to bounded status polling. This improves UI responsiveness without introducing a WebSocket server or claiming distributed-worker support.


## Project Workspace (approval-gated snapshots)

NOX includes a browser-session-scoped Project Workspace for reviewing user-supplied source snapshots. Create a project, paste/save relative-path files (maximum 100 files per project, 50,000 characters per file), draft replacement content, inspect the generated unified diff, and explicitly approve or reject the proposal. Approval updates only the saved SQLite workspace snapshot and increments its version; it never writes to the user's computer, a Git repository, or a deployed service. A patch is rejected as stale if the underlying file changed since the diff was created. Workspace project and patch APIs require the existing HttpOnly `nox_session` cookie and enforce per-session ownership.

The built-in validation endpoint parses Python syntax or standard JSON only; it does not execute code or claim runtime tests passed. Other file extensions are stored as text without an implied validator. Path traversal, absolute paths, hidden paths, oversized input, and excessive project/file counts are rejected. By default the workspace database is `/tmp/nox_workspace.sqlite3`; configure `NOX_WORKSPACE_DB` to a path on a mounted persistent disk if history must survive host restarts. This feature is a controlled snapshot/review workflow, not a live filesystem, repository connector, shell, sandbox, or deployment agent.


## GitHub Bridge (approval-gated draft PRs)

The **GITHUB BRIDGE** panel can browse visible repository files, load UTF-8 text, preview a unified diff, and—only after an explicit confirmation—create a new proposal branch and draft pull request. It rechecks each file's SHA before preview and again before publishing to detect stale edits. It never commits directly to the base branch, merges a pull request, or deploys the service.

### Server configuration

Set these in the hosting provider's **server-side environment/secrets**, never in frontend code or committed files:

- `GITHUB_TOKEN`: a fine-grained GitHub token restricted to this repository. Grant **Contents: Read and write** and **Pull requests: Read and write** only if you want draft PR publishing; keep the token private and rotate it if exposed.
- `NOX_GITHUB_REPOSITORY`: repository in `owner/repository` format, for example `ayaanraza2008/nox-ai`.
- `NOX_GITHUB_BASE_BRANCH`: optional base branch name; defaults to `main`.

If secrets are absent, NOX can still start; the panel reports setup required. The first version proposes one file per PR, limits each file to 50,000 characters and the overall request to 150,000 characters, filters hidden/sensitive paths, and opens a **draft** PR. GitHub permissions, branch rules, rate limits, and repository policies still apply. A multi-file operation can leave a proposal branch with partial commits if GitHub rejects a later file; inspect the branch and close it if needed. Review the PR on GitHub before merging. Creating a PR does not mean tests passed or the live Render site was updated.


## GitHub Actions CI dashboard

The **CI / TEST STATUS** panel uses the configured GitHub Bridge server-side token to show recent workflow runs for `NOX_GITHUB_BASE_BRANCH`, plus each run's jobs and step status. It displays actual GitHub Actions metadata and links to the canonical run page. The panel does not fetch or display secrets, environment values, or raw logs, and it does not start/cancel workflows.

The dashboard requires the same server-side `GITHUB_TOKEN` and `NOX_GITHUB_REPOSITORY` configuration as the GitHub Bridge. Grant **Actions: Read-only** on the configured repository in the fine-grained token for workflow run/job status access, in addition to the existing contents and pull-request permissions if those Bridge features are used. Missing permissions produce an error status rather than fabricated results.

A green workflow means the reported GitHub Actions run passed; it does **not** establish that Render deployed the same commit or that the live site is healthy. Check Render deploy logs and the live health endpoint separately.
