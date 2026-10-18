# NOX AI

A futuristic, multilingual personal AI assistant starter built with React, Vite, and FastAPI.

## Features
- Responsive dark interface with red accents
- Chat UI with Hindi, Urdu, English, and Hinglish language selection
- Browser speech input/output where supported
- FastAPI backend with optional OpenRouter-compatible AI provider
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


## Single-command agent roadmap and current limits

- The command panel can open recognized websites (for example, YouTube, Google, GitHub, Instagram, WhatsApp Web, ChatGPT, and Render) or an explicit HTTP(S) URL in a new tab after asking for confirmation.
- This is navigation only. It does not claim to have logged in, clicked buttons, sent messages, purchased anything, or completed other site actions.
- Multi-step website automation needs a browser automation worker with per-task permissions, confirmation before consequential actions, timeouts, and an auditable action log.
- Opening installed apps, controlling windows, and accessing files on the user's own phone/PC requires a separately installed local companion with narrowly scoped permissions. A Render-hosted backend cannot directly operate the user's device.
- Never store API keys in frontend code or commit them to Git. Configure provider credentials as Render environment secrets.
- A hosted AI provider key is required for provider-backed chat; free tiers and hosting quotas may change.
