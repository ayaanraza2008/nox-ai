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
- Requests to the local HTTP API require the local token and explicit confirmation. Separately, a valid paired relay session can issue only the documented app-opening/search actions; pair only devices you trust, and disconnect them when no longer needed.
- Only shortcut files found in the user's/common Windows Start Menu are listed. Portable apps without shortcuts may not appear.
- The browser may block an HTTPS site from accessing a local HTTP service due to mixed-content or local-network access policy. If blocked, do not disable browser security; a secure local pairing/transport is needed.
- A launch response means Windows received the request, not that the app successfully opened. Verify the window.

## Mobile

The website currently uses Android intents for a small supported set (Instagram, YouTube, WhatsApp, Gmail, Maps, Spotify and Telegram). This is not all-app discovery: Android browsers cannot generally enumerate and launch every installed app. Broad installed-app access needs a native Android companion with appropriate package visibility and launch intents. iPhone/iOS only permits app opening through supported URL schemes/universal links and system-approved integrations; arbitrary apps cannot be force-opened.


## Pair this Windows companion to the NOX website

1. Open NOX in a browser and create a pairing code in **Device Pairing**. Use it within five minutes.
2. In PowerShell, from this folder, set the same code and start the companion:
   ```powershell
   $env:NOX_PAIR_CODE = "123456"
   $env:NOX_COMPANION_TOKEN = "choose-a-long-random-local-secret"
   $env:NOX_WEB_ORIGIN = "https://nox-ai-vcqx.onrender.com"
   python companion.py
   ```
3. The companion joins as **NOX Windows Companion** and saves its pairing token to `%USERPROFILE%\.nox-ai\paired-device.json`. Keep the terminal running. The website refreshes the device list automatically; choose this companion in **Send chat commands to**.
4. Send a command from NOX chat, for example `Open Chrome`, `Open Calculator`, `Open YouTube`, or `Google par latest gaming PC search karo`. The relay worker checks for queued commands every five seconds and retries after network errors.
5. On later starts, the saved pairing token is reused automatically. To revoke/re-pair, disconnect the device in NOX, delete the saved pairing file, and create a new code.

The relay never passes chat text to PowerShell or a shell. Without Home Assistant settings, it accepts only app-opening, fixed website, HTTP(S) URL, and web-search requests.

## Optional smart-home control with Home Assistant

NOX can control compatible home devices through [Home Assistant](https://www.home-assistant.io/), which acts as the local integration hub. This is an adapter, not automatic discovery of every device in the house.

1. Install Home Assistant on a device that stays on at home and add your TV, lights, plugs, fans, climate devices, or supported IP cameras through its official integrations. Matter, vendor integrations, and MQTT may be available depending on the device.
2. In Home Assistant, create a dedicated long-lived access token for NOX with the minimum permissions practical. Keep it private.
3. On the Windows PC that runs NOX Companion, set these PowerShell environment variables before launching `companion.py`:
   ```powershell
   $env:NOX_HOME_ASSISTANT_URL = "http://HOME-ASSISTANT-LAN-IP:8123"
   $env:NOX_HOME_ASSISTANT_TOKEN = "paste-the-private-token-here"
   python companion.py
   ```
   Replace the example URL with your Home Assistant address on your home network. Do not put the token in the website, source code, GitHub, or Render environment. For remote access, use a properly secured VPN or Home Assistant's secure remote-access option; do not expose an unauthenticated Home Assistant port to the public internet.
4. Keep the Windows companion running and pair it with the NOX website. Try commands such as `list lights`, `turn on living room lights`, `turn off all lights`, `TV on`, `TV off`, `list cameras`, or `set AC to 24 degrees`. Exact commands depend on Home Assistant entity names and device capabilities.

The current adapter supports a narrow allowlist of light, switch/plug, fan, media-player/TV, climate-temperature, and entity-status/list actions. Camera commands only list camera entities and status; they do not expose camera feeds. Door locks, alarms, and security devices are deliberately not controlled through free-form chat. Some TVs cannot power on unless their network standby/wake feature is enabled. A command can fail if the device is unsupported, offline, or not integrated into Home Assistant.
