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

## Natural-language terminal tasks and software installs

The paired Windows relay accepts these patterns without passing user text to a shell:

- `terminal python --version`, `terminal node --version`, `terminal npm --version`, `terminal git --version`, `terminal git status`, `terminal pip --version`, `terminal winget --version`, `terminal whoami`, `terminal systeminfo`, `terminal ipconfig`, `terminal tasklist`, `terminal hostname`, and selected `where` diagnostics.
- `terminal npm install`, `terminal npm run build`, `terminal npm run lint`, `terminal npm test`, `terminal git log -1 --oneline`, `terminal python -m compileall .`, `terminal dir`, and `terminal python -m pytest` only when `NOX_WORKSPACE_DIR` points to a configured project folder; npm tasks require a `package.json`, Git tasks require a repository, and pytest requires a test folder.
- `install vscode`, `install git`, `install python`, `install node`, `install 7zip`, `install vlc`, `install firefox`, `install chrome`, `install obs`, `install discord`, `install steam`, `install spotify`, `install zoom`, `install slack`, `install blender`, `install gimp`, `install libreoffice`, `install notepad++`, `install docker desktop`, `install android studio`, `install brave`, `install opera`, `install telegram`, `install github desktop`, `install powertoys`, `install audacity`, `install inkscape`, `install postman`, `install obsidian`, `install notion`, `install cursor`, `install intellij`, and `install pycharm` use exact package IDs from the WinGet source and run without a shell.
- Unknown software names return a Google search URL for review. NOX does **not** copy/paste and execute arbitrary commands found on web pages.

If an app-opening request does not match a Start Menu shortcut, the companion opens a web search for the official Windows download. This does not mean the app was installed. This is intentionally a reviewed command/package catalog, not unrestricted terminal access. Add new package IDs or command recipes only after reviewing them. Windows, WinGet, network access, package availability, and installation permissions are required. Some installers may still show OS/UAC prompts; NOX does not bypass them. Mobile operating systems have different app-launch/install restrictions and cannot use this Windows terminal feature.

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

If the network drops after a local command finishes, the companion retries reporting that command's result up to three times for transient network/server failures. It does **not** rerun the command to recover, avoiding duplicate installs or repeated side effects.

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

The current adapter supports an explicit allowlist: lights, switches/plugs, fans, TV/media players (on/off/play/pause), climate setpoints, blinds/covers (open/close), robot vacuums (start/stop/pause/dock), activating a uniquely matched named scene, and entity-status/list actions. Examples include `list devices`, `list blinds`, `list vacuums`, `turn on all lights`, `open living room blinds`, `start vacuum`, and `activate scene movie night`. Camera commands only list camera entities and status; they do not expose camera feeds or recordings. Door locks, alarms, and security devices are deliberately not controlled through free-form chat. Some TVs cannot power on unless their network standby/wake feature is enabled. A command can fail if the device is unsupported, offline, or not integrated into Home Assistant.


## Ethical hacking / passive website security checks

NOX includes an opt-in, low-impact website header checker in `ethical_hacking.py`. From a paired NOX chat, use it only for a website you own or are explicitly authorized to assess:

- `security check https://your-domain.example`
- `check headers for https://your-domain.example`

It makes one HTTPS request and reports whether common headers (HSTS, CSP, nosniff, Referrer-Policy, and Permissions-Policy) are present, while validating the TLS certificate. It blocks private/local IP addresses, non-standard ports, and redirects. It does **not** crawl, scan ports, brute-force, exploit vulnerabilities, attempt logins, or test cameras/devices. A missing header is only a review suggestion, not proof of a vulnerability. This is an initial passive checker, not a full penetration-testing suite.

For deeper authorized testing, use a dedicated lab or staging environment and review findings manually before making changes. Never test systems without the owner's permission.

### Read-only Python project audit

NOX also includes a heuristic static analyzer in `security_audit.py`. It reads Python source only and never executes inspected files or accesses the network.

1. Set the folder you own and want to review before starting the companion:
   ```powershell
   $env:NOX_SECURITY_PROJECT_DIR = "C:\\path\\to\\your\\project"
   python companion.py
   ```
2. Send the paired command: `audit project security` (also accepts `security audit project` or `scan my project code`).

It checks for suspicious dynamic execution, shell=True, unsafe pickle/YAML use, possible hard-coded secrets, weak hashes, disabled TLS verification, and debug mode. The report includes severity, file, line, evidence, and suggested fixes. It scans at most 500 Python files and skips common generated/dependency directories and oversized files. Findings are heuristic, can be false positives, and are not proof of exploitability. Configure the directory carefully: results may include short snippets from source lines. This source checker does not audit JavaScript, dependencies, live servers, or network services by itself.

### Dependency advisory checks and reports

NOX can check exact-pinned Python dependencies in `requirements.txt` and npm packages in `package-lock.json` against the public OSV vulnerability database. It sends package names and versions (not project source code or credentials) to OSV. It checks up to 80 unique packages and reports any network/database errors rather than treating incomplete results as clean.

- `audit project dependencies` — check dependency advisories.
- `generate security report` — run the Python static review and dependency check, then write `nox-security-reports/security-report.json` and `nox-security-reports/security-report.md` inside the configured project folder.
- `full project security audit` — alias for generating the combined report.

Review advisory matches before acting; they do not alone prove runtime exploitability. A clean report is not a guarantee of security. The report folder may contain source-line snippets from static findings, so keep the project folder private. These checks are read-only with respect to inspected code and do not install, upgrade, or modify packages.

### Regression tests

From the repository root, run `python -m unittest discover -s desktop-companion/tests -v`. GitHub Actions now runs these tests on pushes along with Python syntax validation. The tests mock the external OSV call and DNS lookup so they do not scan a live target or require the vulnerability database to be reachable.

### Authorized lab workflow

For hands-on learning, use an intentionally vulnerable local training app or a lab you control. Keep the target inventory, permission, test window, and allowed test types written down; isolate the lab from production and real user data; take a backup; and stop if the target differs from the approved scope. NOX's current feature set does not automatically exploit targets or perform active penetration tests.


### Authorized Android USB device control (prototype)

The Windows companion now exposes authenticated ADB device discovery and a confirmation-gated installed-app launch endpoint. It does not unlock phones, approve debugging prompts, or bypass Android permissions.

1. Install **Android SDK Platform-Tools** from the official Android developer site and ensure `adb` is on Windows `PATH`. If needed, set `NOX_ADB_PATH` to the full path of `adb.exe`.
2. On your own Android phone, enable Developer options and USB debugging, connect the USB cable, unlock the phone, and explicitly approve the RSA debugging prompt for this computer. On Windows, install the phone manufacturer's USB driver if ADB does not list it.
3. Start this companion with a private `NOX_COMPANION_TOKEN` configured. Keep the service bound to `127.0.0.1`; do not expose it to the public internet.
4. Send the token in the `X-NOX-Token` header:
   - `GET http://127.0.0.1:8765/v1/devices` — enumerates ADB devices and clearly reports `device`, `unauthorized`, and `offline` states.
   - `GET http://127.0.0.1:8765/v1/devices/capabilities` — returns the truthful local adapter capability matrix.
   - `POST http://127.0.0.1:8765/v1/devices/android/launch` with JSON `{"serial":"YOUR_ADB_SERIAL","package_name":"com.example.app","confirmed":true}` — requests launch of an installed package on the selected authorized device. Replace both example values with values from your own device/app.
5. A launch response is explicitly marked `launch_requested_not_verified`; verify the app on the phone. A successful ADB process exit alone does not prove the app reached the foreground.

If ADB is missing, install Platform-Tools or set `NOX_ADB_PATH`. If the device is `unauthorized`, approve the on-device prompt; if `offline`, reconnect the cable and check the driver. The companion never runs request text through a shell and validates serial/package identifiers before invoking ADB.

**Implemented now:** Windows-side ADB enumeration, authorization-state reporting, and confirmation-gated app launch; read-only Windows Wi-Fi interface status.

**Not implemented yet:** USB file push/pull endpoints, screen capture, generic screen tap/type automation, Bluetooth Classic/BLE scanning or GATT, automatic LAN discovery, one-tap ADB-over-Wi-Fi pairing, iOS control, and a dedicated NOX dashboard UI for these new local endpoints. The hosted Render backend cannot directly see a USB device attached to your PC; the local Windows companion must be installed and running.


## Local cybersecurity scan endpoints

The companion includes a token-authenticated local security adapter. It binds to loopback only and does not make these endpoints available through the hosted Render API.

- `GET http://127.0.0.1:8765/v1/cybersecurity/status` — detects local tool paths and probes selected fixed --version flags with a two-second timeout; it does not start scans.
- `POST http://127.0.0.1:8765/v1/cybersecurity/scans` — starts bounded Nmap service discovery. Requires JSON fields `target`, `authorized: true`, a `scope_note` of at least 10 characters, and the exact confirmation `I OWN OR AM AUTHORIZED TO TEST THIS TARGET`.
- `GET http://127.0.0.1:8765/v1/cybersecurity/scans/TASK_ID` — polls a scan's actual result.
- `POST http://127.0.0.1:8765/v1/cybersecurity/scans/cancel` with JSON `{"task_id":"TASK_ID"}` — requests cancellation.

Every request requires `X-NOX-Token`. Nmap must already be installed. The adapter scans at most the top 100 ports with service detection, conservative timing, a 45-second hard limit, and bounded output. By default it accepts private/local lab IPs and local lab names; other hosts require an exact comma-separated `NOX_CYBER_ALLOWED_HOSTS` entry. Configure only assets you administer and have explicit permission to assess. This is not a vulnerability exploit engine. Emergency Stop blocks starting new scans, but authenticated cancellation remains available.

## Emergency Stop and Windows tray controls

Install the current optional tray dependencies with the companion requirements:

```powershell
pip install -r requirements.txt
```

On Windows, the companion attempts to add a notification-area icon with **EMERGENCY STOP**, **Resume NOX**, and **Open NOX Dashboard** menu items. If tray dependencies or the desktop notification area are unavailable, the loopback API remains available and logs a warning.

The local companion stores its own fail-closed latch in `%LOCALAPPDATA%\NOX AI\emergency-state.json` (override with `NOX_COMPANION_STATE_PATH`). Its authenticated endpoints are:

- `GET /v1/emergency/status`
- `POST /v1/emergency/stop`
- `POST /v1/emergency/resume`

All mutating local companion HTTP endpoints require the existing `X-NOX-Token` and return HTTP 423 while locally stopped, except the explicit stop/resume controls. The paired relay loop also pauses command polling while stopped and checks the latch again before executing a fetched command. If a fetched command was not executed because the latch engaged, it reports cancellation instead of executing it later.

**Important scope boundary:** the local Windows latch and hosted NOX dashboard latch are separate stores today. A local tray stop blocks the local companion and its relay, while the hosted dashboard stop cancels the current account/session's backend task queue, swarm jobs, and remote browser session. Do not assume a stop in one process has reached the other process unless the UI explicitly confirms it. No unrelated Windows process is killed. The tray is an interactive user-session helper, not a Windows service; it does not guarantee startup before login or run while Windows is powered off.
