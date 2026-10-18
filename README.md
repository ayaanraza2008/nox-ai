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

## Security
Never commit API keys or passwords. Configure secrets in Render environment variables.


## Autonomous task worker and current limits

- Tasks submitted to the task panel now run through a bounded tool-using agent. With OPENROUTER_API_KEY configured, it can search the public web, read public HTML/text pages, use those results to reason, and return a result with source URLs.
- The agent has a maximum of five tool-call rounds per task. It blocks local/private IP targets and only reads public HTTP/HTTPS HTML or plain-text pages. Web page content is treated as untrusted input.
- The command panel can also open recognized websites (for example, YouTube, Google, GitHub, Instagram, WhatsApp Web, ChatGPT, and Render) or an explicit HTTP(S) URL in a new tab after asking for confirmation. That opens the page in the user's browser; it does not automate the page.
- The current web-research worker does not log in, submit forms, send messages, purchase items, execute shell commands, or perform general desktop control.
- An opt-in Windows companion now supports requesting launch of Calculator, Notepad, Paint, File Explorer, Task Manager, and a fixed set of websites. It binds to loopback, requires a token and explicit confirmation, and does not accept arbitrary commands. Setup: see `desktop-companion/README.md`.
- The frontend also attempts Android intents for Instagram, YouTube, WhatsApp, Gmail, Maps, Spotify, and Telegram. Android/browser policy determines whether an installed app opens or its official web fallback opens.
- The hosted HTTPS-to-local HTTP bridge may be blocked by browser local-network/mixed-content policy; this has not been verified on the user's browser. General desktop automation, arbitrary app launching, file access, and mobile device control are not implemented.
- Never store API keys in frontend code or commit them to Git. Configure provider credentials as Render environment secrets.
- A hosted AI provider key is required for provider-backed chat; free tiers and hosting quotas may change.
