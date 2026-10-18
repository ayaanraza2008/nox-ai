# NOX Local Desktop Companion

This opt-in Windows/Python helper lets the hosted NOX UI request a small set of approved local actions. It is not general remote desktop access.

## Supported actions

- Windows apps: Calculator, Notepad, Paint, File Explorer, Task Manager.
- Default browser: Instagram, YouTube, Google, WhatsApp Web, GitHub, ChatGPT.
- Every launch requires a browser confirmation and the local companion token.
- It does not run arbitrary commands, accept executable paths, read files, or type into apps.

## Setup on the Windows PC

1. Install Python 3.11+.
2. Open PowerShell in this folder and run:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Choose a long random token and start the helper:
   ```powershell
   $env:NOX_COMPANION_TOKEN = "paste-a-long-random-secret-here"
   $env:NOX_WEB_ORIGIN = "https://nox-ai-vcqx.onrender.com"
   python companion.py
   ```
   Keep this terminal running while you use local actions. Use the exact same token when the NOX web UI asks for it. Do not share or commit the token.
4. Test the helper in another PowerShell window:
   ```powershell
   Invoke-RestMethod http://127.0.0.1:8765/health
   ```
5. Open the deployed NOX website on the same Windows PC and enter a supported command such as `open calculator` or `open notepad`.

## Security

- The API binds to `127.0.0.1` only; it is not exposed to your LAN or the public internet.
- Actions require the `X-NOX-Token` header and `confirmed: true`.
- CORS is restricted to `NOX_WEB_ORIGIN`.
- The browser may block a hosted HTTPS page from reaching a local HTTP service because of browser local-network/mixed-content policy. If that happens, the web-to-companion bridge will not work in that browser until a secure local pairing/transport is implemented. Do not disable browser security to work around it.
- A launch response means the operating system received the request, not that the app finished opening successfully. Verify on the PC.

## Mobile

Android browser intents are supported for selected apps (Instagram, YouTube, WhatsApp, Gmail, Maps, Spotify and Telegram). Android/browser settings and app-link handling determine whether the installed app opens or the official website fallback opens. This is not a native Android companion and cannot launch arbitrary apps or control the phone.
