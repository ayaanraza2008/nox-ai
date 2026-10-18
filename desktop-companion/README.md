# NOX Local Desktop Companion (preview)

This is a small, opt-in Windows/Python companion for testing one safe action: opening the Instagram website in the PC's default browser. It does **not** control the Instagram desktop/mobile app, execute shell commands, or provide general remote desktop access.

## Run on the PC you want NOX to control

1. Install Python 3.11+.
2. Open PowerShell in this folder.
3. Create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
4. Set a long random token in this PowerShell window (replace the sample):
   ```powershell
   $env:NOX_COMPANION_TOKEN = "replace-with-a-long-random-secret"
   $env:NOX_WEB_ORIGIN = "https://nox-ai-vcqx.onrender.com"
   python companion.py
   ```
5. In another PowerShell window, test health:
   ```powershell
   Invoke-RestMethod http://127.0.0.1:8765/health
   ```

## Safety model

- Binds to `127.0.0.1` only; it is not exposed to your LAN or the public internet.
- Requires the secret `X-NOX-Token` header for actions.
- Requires an explicit `confirmed: true` field.
- Only accepts the fixed `instagram` destination; no arbitrary URL, shell, file, or process execution.
- The action response means the browser-open request was sent, not that page load or login succeeded. Verify it visually.

## Current limitation

This companion is **not yet connected to the hosted Task Orchestrator UI**. It is a first local component; a later integration must use a deliberate pairing flow and keep the token out of frontend code. Never paste the token into public chats or commit it to Git.
