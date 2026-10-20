(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const token = $("connectivityToken"), wifiButton = $("connectivityWifi"), ruButton = $("connectivityRuView");
  const wifiState = $("connectivityWifiState"), wifiDetails = $("connectivityWifiDetails");
  const ruState = $("ruviewState"), ruDetails = $("ruviewDetails"), canvas = $("wifiSignalCanvas");
  if (!token || !wifiButton || !ruButton || !canvas) return;
  let lastSignal = null;
  const companion = "http://127.0.0.1:8765";
  function drawSignal(value) {
    lastSignal = Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null;
    const ctx = canvas.getContext("2d"), w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(113,234,255,.16)"; ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 32) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
    for (let y = 0; y < h; y += 24) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
    const cx = w * .23, cy = h * .52, base = Math.min(w, h) * .38;
    ctx.strokeStyle = lastSignal === null ? "rgba(130,149,169,.55)" : "rgba(113,234,255,.75)";
    for (let i = 1; i <= 3; i++) {
      ctx.beginPath(); ctx.arc(cx, cy, base * i / 3, -Math.PI * .72, Math.PI * .72); ctx.stroke();
    }
    ctx.fillStyle = "#a18bff"; ctx.beginPath(); ctx.arc(cx, cy, 7, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#e7f4ff"; ctx.font = "bold 15px system-ui";
    ctx.fillText(lastSignal === null ? "NO LIVE MEASUREMENT" : "MEASURED WIFI SIGNAL", w * .48, h * .35);
    ctx.fillStyle = "#8295a9"; ctx.font = "13px system-ui";
    ctx.fillText(lastSignal === null ? "Press Inspect my Wi-Fi" : "Windows interface strength", w * .48, h * .52);
    if (lastSignal !== null) {
      ctx.fillStyle = "#71eaff"; ctx.font = "bold 24px system-ui"; ctx.fillText(lastSignal + "%", w * .48, h * .74);
      ctx.fillStyle = "#8295a9"; ctx.font = "11px system-ui"; ctx.fillText("Illustrative only · not an RF field map", w * .48, h * .88);
    }
  }
  function getToken() {
    const value = token.value.trim();
    if (!value) throw new Error("Enter your NOX_COMPANION_TOKEN first. The token is not saved by this page.");
    return value;
  }
  async function companionGet(path) {
    const response = await fetch(companion + path, {
      method: "GET", mode: "cors", cache: "no-store",
      headers: { "X-NOX-Token": getToken(), "Accept": "application/json" }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || ("Local companion HTTP " + response.status));
    return data;
  }
  wifiButton.addEventListener("click", async () => {
    wifiButton.disabled = true; wifiState.textContent = "CHECKING"; wifiDetails.textContent = "Requesting current Windows interface status…";
    try {
      const data = await companionGet("/v1/connectivity/wifi");
      wifiState.textContent = String(data.status || "UNKNOWN").toUpperCase();
      const fields = [
        ["SSID", data.ssid], ["Signal", data.signal_percent == null ? null : data.signal_percent + "%"],
        ["Channel", data.channel], ["Radio", data.radio_type],
        ["Receive", data.receive_mbps == null ? null : data.receive_mbps + " Mbps"],
        ["Transmit", data.transmit_mbps == null ? null : data.transmit_mbps + " Mbps"],
        ["Authentication", data.authentication], ["Cipher", data.cipher]
      ].filter(item => item[1] !== null && item[1] !== undefined && item[1] !== "");
      wifiDetails.textContent = fields.length
        ? fields.map(item => item[0] + ": " + item[1]).join(" · ") + "\nSource: " + data.source + "\nMeasured: " + data.measured_at
        : (data.note || "No connected Wi-Fi interface fields were available.");
      drawSignal(data.connected ? data.signal_percent : null);
    } catch (error) {
      wifiState.textContent = "UNAVAILABLE"; wifiDetails.textContent = error.message || "Unable to read local Wi-Fi.";
      drawSignal(null);
    } finally { wifiButton.disabled = false; }
  });
  ruButton.addEventListener("click", async () => {
    ruButton.disabled = true; ruState.textContent = "CONNECTING"; ruDetails.textContent = "Checking the local RuView API…";
    try {
      const [health, info, sensing] = await Promise.all([
        companionGet("/v1/connectivity/ruview?view=health"),
        companionGet("/v1/connectivity/ruview?view=info"),
        companionGet("/v1/connectivity/ruview?view=sensing")
      ]);
      const h = health.data || {}, inf = info.data || {}, sig = sensing.data || {};
      const source = String(h.source || sig.source || inf.source || "source not reported");
      const simulated = /simulat|demo|synthetic/i.test(source);
      ruState.textContent = simulated ? "SIMULATED SOURCE" : "API RESPONDING";
      const summary = [
        "Service: " + String(h.status || "reachable"),
        "Source: " + source,
        "Build: " + String(inf.version || inf.build || "not reported"),
        "Sensing payload: " + (sig && typeof sig === "object" ? Object.keys(sig).slice(0, 12).join(", ") : typeof sig),
        simulated ? "Simulation is not a real radio measurement." : "API responded; hardware data source still needs verification."
      ];
      ruDetails.textContent = summary.join("\n");
      if (h.status === "ok" || health.status === "ok") {
        const link = document.createElement("a"); link.href = "http://127.0.0.1:3000"; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = "Open RuView's actual local 3D workspace";
        link.style.cssText = "display:inline-block;margin-top:8px;color:var(--cyan)";
        ruDetails.appendChild(document.createElement("br")); ruDetails.appendChild(link);
      }
    } catch (error) {
      ruState.textContent = "NOT AVAILABLE";
      ruDetails.textContent = (error.message || "RuView unavailable") + "\nRequires local RuView running at 127.0.0.1:3000 and RUVIEW_API_TOKEN configured in the companion.";
    } finally { ruButton.disabled = false; }
  });
  drawSignal(null);
})();
