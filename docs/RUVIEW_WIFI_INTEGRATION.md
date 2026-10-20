# NOX AI — Local Wi-Fi and RuView integration

## What is actually integrated

NOX's existing Network & Privacy panel now has explicit buttons for:
- Reading the current Windows Wi-Fi interface through the authenticated local desktop companion.
- Querying a locally running RuView service through a fixed-path proxy, returning actual API payloads for health, build info, latest sensing frame, vitals and pose.
- Showing the source status reported by RuView. Synthetic/demo output must remain labelled as simulated; an API response alone does not prove hardware sensing is active.

The companion only binds to `127.0.0.1`, requires `X-NOX-Token`, uses fixed `netsh wlan show interfaces` arguments (no shell), and never returns raw command output or saved Wi-Fi credentials. The RuView proxy only targets `http://127.0.0.1:3000` and an allowlist of fixed endpoints. Its API token stays in the companion process environment, not in the browser.

## Upstream inspection and clone status

Upstream repository: https://github.com/ruvnet/RuView
- Public repository; root license is MIT. Preserve its copyright/license notices when redistributing upstream code.
- Inspected upstream README, Python project metadata, user guide, Docker Compose, and ESP32 CSI firmware documentation through the public GitHub repository API.
- The upstream repository documents a Rust sensing server, Three.js workspace, Windows Wi-Fi RSSI-only source, simulated CSI source, and ESP32-S3 / ESP32-C6 CSI firmware.
- RSSI-only Windows mode is not equivalent to CSI. Pose estimation and advanced spatial outputs depend on supported CSI input and processing/model/hardware prerequisites. Upstream describes vital-sign outputs as experimental and not medical measurements.
- A complete clone and dependency install could not be performed in this execution environment: `git clone https://github.com/ruvnet/RuView.git` failed with `Could not resolve host: github.com`. GitHub API inspection succeeded, but this is **not** a successful local installation or build. The adapter deliberately does not pretend otherwise.

## Run RuView locally on Windows (no paid API)

Requirements: Docker Desktop running, a Windows PC, Python 3.11+ for the NOX companion, and a local Wi-Fi interface. The simulated source needs no CSI hardware; live CSI sensing needs a compatible ESP32 CSI node and correct network/UDP setup.

In PowerShell, from the NOX repository root:

```powershell
# Generate a temporary local API token. Do not commit or share it.
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$env:RUVIEW_API_TOKEN = ([Convert]::ToHexString($bytes)).ToLowerInvariant()
$env:CSI_SOURCE = "simulated"
docker compose -f deploy/ruview-local.compose.yml up -d
```

Then, in the **same PowerShell session** so the token is inherited, start the companion:

```powershell
cd desktop-companion
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:NOX_COMPANION_TOKEN = "choose-a-separate-long-random-token"
$env:NOX_WEB_ORIGIN = "https://nox-ai-vcqx.onrender.com"
$env:RUVIEW_API_TOKEN = $env:RUVIEW_API_TOKEN
python companion.py
```

Open NOX on the same Windows PC, expand **Network & Privacy**, enter `NOX_COMPANION_TOKEN`, then press **Check RuView**. Use **Inspect my Wi-Fi** for interface metrics. The browser never stores either token. Localhost requests may be subject to browser local-network permission or mixed-content restrictions; if blocked, use the companion's documented local health URL and check the browser console. Do not expose the local ports to the public internet.

To stop the local RuView container:

```powershell
docker compose -f deploy/ruview-local.compose.yml down
```

## Data source and limitations

- The supplied Compose file explicitly selects `CSI_SOURCE=simulated`; its data is synthetic and must not be interpreted as real sensing.
- Windows Wi-Fi status uses `netsh wlan show interfaces` and reports the connected interface's SSID, BSSID, signal percentage, channel, radio type, link rates and authentication/cipher fields only when Windows exposes them. Windows localization can make some fields unavailable.
- This adapter does not yet flash firmware, collect CSI itself, launch/stop the RuView process through NOX, or enable Bluetooth/hotspot control. Start/stop the container with the explicit local commands above.
- The NOX signal rings are illustrative, based on a measured signal percentage when available; they are not a calibrated RF heatmap or room reconstruction.
- RuView's API is queried from the local companion so the RuView bearer token is not exposed to the browser. Only fixed endpoints are proxied. The existing NOX hosted Render backend cannot directly access your PC's Wi-Fi adapter.
- Do not use Wi-Fi sensing outputs as medical measurements or as proof that a person is present. Validate hardware and signal source before relying on any estimate.

## Upstream license

RuView's root `LICENSE` declares the MIT License (copyright rUv). Firmware directories may carry additional license terms; review the license files in any upstream subdirectory before copying or redistributing its contents. This NOX integration currently calls the separately installed service and does not vendor upstream source files.
