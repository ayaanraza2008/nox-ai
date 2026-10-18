# NOX Local Desktop Companion

This opt-in Windows helper discovers app shortcuts in the Windows Start Menu and can launch a selected shortcut after explicit confirmation. It is not general remote desktop access.

## What it supports

- Dynamic discovery of apps that have Windows Start Menu shortcuts; this covers many installed desktop apps, not literally every portable app or every executable.
- Launch selected apps after confirmation and token authentication.
- A small fixed set of websites can be opened in the default browser.
- No arbitrary shell commands, request-supplied executable paths, file reading, typing, or general window control.

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
   Keep the terminal running while using local app launches. Do not share or commit the token.
4. Test the helper in another PowerShell window:
   ```powershell
   Invoke-RestMethod http://127.0.0.1:8765/health
   ```
5. Open the NOX website on the same PC and submit a command such as `open chrome`, `open calculator`, or `open visual studio code`. The page asks for the token, finds matching Start Menu shortcuts, and asks for confirmation before launch.

## Security and known limitations

- The API binds to `127.0.0.1` only; it is not exposed to your LAN or the public internet.
- Every app launch requires the local token and explicit confirmation.
- Only shortcut files found in the user's/common Windows Start Menu are listed. Portable apps without shortcuts may not appear.
- The browser may block an HTTPS site from accessing a local HTTP service due to mixed-content or local-network access policy. If blocked, do not disable browser security; a secure local pairing/transport is needed.
- A launch response means Windows received the request, not that the app successfully opened. Verify the window.

## Mobile

The website currently uses Android intents for a small supported set (Instagram, YouTube, WhatsApp, Gmail, Maps, Spotify and Telegram). This is not all-app discovery: Android browsers cannot generally enumerate and launch every installed app. Broad installed-app access needs a native Android companion with appropriate package visibility and launch intents. iPhone/iOS only permits app opening through supported URL schemes/universal links and system-approved integrations; arbitrary apps cannot be force-opened.
