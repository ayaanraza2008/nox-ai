# Optional local RuView companion for NOX AI

This directory installs the official published @ruvnet/ruview CLI as an optional
local dependency. It is separate from the website runtime dependencies. The published
package is MIT-licensed and requires Node.js 20 or newer. It has no required runtime
dependencies; its optional @ruvnet/ruview-kernel peer can add local CSI processing
when separately installed and compatible.

## Windows PowerShell

From the NOX repository root:

    node --version
    npm --prefix .\ruview-companion install --ignore-scripts
    $env:NOX_RUVIEW_ENABLED = "1"
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000 on the same computer. Keep the NOX API bound to loopback.
Do not expose this local server through a router, tunnel, reverse proxy, or public host.

## Available operations

- Doctor runs the official CLI's local diagnostics.
- Devices runs the official CLI's device inventory command.
- Start capture runs the official bounded esp32 --seconds 45 --analyze command.
  Stop terminates that child process. Capture receives data; it does not scan nearby
  Wi-Fi networks or transmit packets to third-party devices.
- The structured capture summary is reduced to documented per-node CSI frame counts,
  mean RSSI, CSI frame rate, and packet-loss estimates. Remaining CLI output is
  truncated and displayed as untrusted diagnostic text. Device vitals, pose, breathing,
  and heart-rate fields are deliberately not surfaced as validated measurements.

The integration invokes the fixed CLI entry point using Node's process API, never a
shell, and only exposes allow-listed operations. It is disabled unless
NOX_RUVIEW_ENABLED=1 and only accepts requests from a loopback client with a
same-origin browser request and an authenticated NOX session.

## Hardware and accuracy

RuView documents several modes. Simulated mode can run without hardware, but is
synthetic. Full CSI capture requires a compatible and provisioned CSI source, typically
a supported ESP32 CSI node and local network transport. RSSI-only host Wi-Fi is not
full CSI and does not justify pose, breathing, heart-rate, or exact-location claims.
ESP32 hardware, wiring, compatible firmware, and setup may cost money; the software
package itself is free and open source.

The optional package was not installed as part of hosted deployment. Installing it
requires npm registry access. Hardware tests must be run locally with an actual
supported sensor. This adapter does not claim that the full Rust workspace, firmware,
pretrained models, or native UI have been vendored into NOX.
