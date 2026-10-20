(() => {
  "use strict";
  if (window.NOXCybersecurityCenter) return;
  const $ = (id) => document.getElementById(id);
  const style = document.createElement("style");
  style.textContent = `
    #noxCyberTrigger{border-color:#4c3c70;color:#d9caff}
    #noxCyberLayer{position:fixed;inset:0;z-index:12000;display:none;background:rgba(2,6,14,.76);backdrop-filter:blur(8px)}
    #noxCyberLayer.open{display:block}
    .nox-cyber-drawer{position:absolute;right:0;top:0;bottom:0;width:min(760px,100vw);display:flex;flex-direction:column;overflow:hidden;background:linear-gradient(155deg,#101a2c,#080d17 75%);border-left:1px solid #594b84;box-shadow:-25px 0 90px #0009;color:#e7f0ff}
    .nox-cyber-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 20px;border-bottom:1px solid #26334a}
    .nox-cyber-kicker{font-size:9px;letter-spacing:.2em;color:#bca5ff;font-weight:800}
    .nox-cyber-head h2{font-size:20px;margin:5px 0}.nox-cyber-head p{font-size:11px;color:#9aacc4;margin:0}
    .nox-cyber-close,.nox-cyber-btn{border:1px solid #3a4d68;border-radius:9px;background:#142238;color:#e9f5ff;padding:9px 12px;cursor:pointer}
    .nox-cyber-content{overflow:auto;padding:16px 18px 28px;display:grid;gap:13px}
    .nox-cyber-card{border:1px solid #263b56;border-radius:13px;background:linear-gradient(145deg,#101e31,#0b1422);padding:14px;min-width:0}
    .nox-cyber-card h3{font-size:12px;letter-spacing:.06em;margin:0 0 8px;color:#c4eaff}
    .nox-cyber-card p,.nox-cyber-help{font-size:11px;line-height:1.6;color:#9aacc4;margin:6px 0}
    .nox-cyber-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
    .nox-cyber-input,.nox-cyber-area{box-sizing:border-box;width:100%;border:1px solid #2a405b;border-radius:9px;background:#070f1b;color:#e6f2ff;padding:10px;font:12px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace}
    .nox-cyber-area{min-height:100px;resize:vertical}.nox-cyber-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
    .nox-cyber-primary{border-color:#7861b9;background:linear-gradient(135deg,#443277,#1d3a5b)}
    .nox-cyber-output{white-space:pre-wrap;overflow-wrap:anywhere;max-height:300px;overflow:auto;border:1px solid #26364d;border-radius:9px;background:#050a12;padding:10px;font:11px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;color:#cce5f5;margin-top:9px}
    .nox-cyber-chip{display:inline-block;border:1px solid #2c4b62;border-radius:999px;padding:4px 8px;margin:3px;font-size:10px;color:#aee8f8}
    .nox-cyber-chip.missing{border-color:#684d44;color:#ffc3a7}
    @media(max-width:560px){.nox-cyber-head{padding:14px}.nox-cyber-content{padding:12px}.nox-cyber-grid{grid-template-columns:1fr}}
  `;
  document.head.append(style);
  const layer = document.createElement("div");
  layer.id = "noxCyberLayer";
  layer.setAttribute("aria-hidden", "true");
  layer.innerHTML = `
    <section class="nox-cyber-drawer" role="dialog" aria-modal="true" aria-labelledby="noxCyberTitle">
      <header class="nox-cyber-head"><div><div class="nox-cyber-kicker">DEFENSIVE SECURITY / LAB MODE</div><h2 id="noxCyberTitle">Cybersecurity Center</h2><p>Read-only review, scope checks and tool readiness.</p></div><button type="button" class="nox-cyber-close" aria-label="Close Cybersecurity Center">×</button></header>
      <div class="nox-cyber-content">
        <section class="nox-cyber-card"><h3>Runtime & Tool Readiness</h3><p id="noxCyberStatusText">Checking server prerequisites…</p><div id="noxCyberTools"></div><p class="nox-cyber-help">This status describes the NOX API server, not your phone or PC. Active scans and local filesystem access require the local companion.</p><div class="nox-cyber-actions"><button id="noxCyberRefresh" class="nox-cyber-btn" type="button">Refresh status</button><button id="noxCyberExport" class="nox-cyber-btn" type="button">Export latest report</button><button id="noxCyberAskNOX" class="nox-cyber-btn" type="button">Ask NOX about report</button></div></section>
        <section class="nox-cyber-card"><h3>Source Code Security Review</h3><p>Paste source code for bounded heuristic checks. The code is not executed or sent to an AI provider.</p><input id="noxCyberFilename" class="nox-cyber-input" maxlength="160" value="pasted-source" aria-label="Filename" placeholder="Filename (optional)"><textarea id="noxCyberSource" class="nox-cyber-area" maxlength="50000" placeholder="Paste code here (up to 50,000 characters)"></textarea><div class="nox-cyber-actions"><button id="noxCyberReview" class="nox-cyber-btn nox-cyber-primary" type="button">Review code</button></div><pre id="noxCyberReviewOutput" class="nox-cyber-output" hidden></pre></section>
        <section class="nox-cyber-grid">
          <div class="nox-cyber-card"><h3>Server Log Triage</h3><p>Find common authentication and service-error patterns.</p><textarea id="noxCyberLogs" class="nox-cyber-area" maxlength="100000" placeholder="Paste sanitized logs"></textarea><div class="nox-cyber-actions"><button id="noxCyberLogReview" class="nox-cyber-btn" type="button">Analyze logs</button></div><pre id="noxCyberLogOutput" class="nox-cyber-output" hidden></pre></div>
          <div class="nox-cyber-card"><h3>Linux Command Explainer</h3><p>Explains a registered command; it never executes it.</p><input id="noxCyberCommand" class="nox-cyber-input" maxlength="300" placeholder="e.g. ss -lnt"><div class="nox-cyber-actions"><button id="noxCyberExplain" class="nox-cyber-btn" type="button">Explain command</button></div><pre id="noxCyberCommandOutput" class="nox-cyber-output" hidden></pre></div>
        </section>
        <section class="nox-cyber-card"><h3>Authorized Lab Scope</h3><p>Validate a local lab target before using a local security tool. This form does not start a scan or record legal authorization.</p><input id="noxCyberTarget" class="nox-cyber-input" maxlength="253" placeholder="127.0.0.1, 192.168.1.10, lab.test"><textarea id="noxCyberScopeNote" class="nox-cyber-area" maxlength="500" placeholder="Describe your authorization and permitted scope"></textarea><label class="nox-cyber-help"><input id="noxCyberAuthorized" type="checkbox"> I own this target or have explicit permission to test it.</label><div class="nox-cyber-actions"><button id="noxCyberValidateScope" class="nox-cyber-btn" type="button">Validate scope</button></div><pre id="noxCyberScopeOutput" class="nox-cyber-output" hidden></pre></section>
        <section class="nox-cyber-card"><h3>Local Companion · Active Lab Scan</h3><p>Optional local-only scan via your own NOX Companion at 127.0.0.1:8765. Requires Nmap installed locally, the companion token, an authorized lab target, and exact confirmation. HTTPS browser security may block local HTTP access; if so, use the companion API locally instead of weakening browser security.</p><input id="noxCyberLocalToken" class="nox-cyber-input" type="password" autocomplete="off" placeholder="Local NOX_COMPANION_TOKEN"><input id="noxCyberScanConfirm" class="nox-cyber-input" maxlength="80" placeholder="Type: I OWN OR AM AUTHORIZED TO TEST THIS TARGET"><div class="nox-cyber-actions"><button id="noxCyberLocalStatus" class="nox-cyber-btn" type="button">Check local companion</button><button id="noxCyberStartScan" class="nox-cyber-btn nox-cyber-primary" type="button">Start bounded Nmap scan</button><button id="noxCyberCancelScan" class="nox-cyber-btn" type="button">Cancel scan</button><button id="noxCyberPollScan" class="nox-cyber-btn" type="button">Refresh scan result</button></div><pre id="noxCyberLocalOutput" class="nox-cyber-output" hidden></pre></section><section class="nox-cyber-card"><h3>Integration & Safety Notes</h3><p>KaliGPT's upstream CLI has a generic Linux command tool and platform-specific installers. NOX does not call that arbitrary-command path from the hosted service. The local worker uses fixed argument lists, bounded Nmap service discovery, explicit confirmation, conservative timing, a timeout and cancellation checks.</p><p>Windows users need a local companion or WSL2 with tools installed; browser-only and Render deployments cannot scan the user's computer. No scanner is installed automatically.</p></section>
      </div>
    </section>`;
  document.body.append(layer);
  const trigger = document.createElement("button");
  trigger.id = "noxCyberTrigger";
  trigger.type = "button";
  trigger.className = "iconbtn";
  trigger.textContent = "⌁ Cybersecurity";
  trigger.setAttribute("aria-haspopup", "dialog");
  trigger.setAttribute("aria-expanded", "false");
  const topRight = document.querySelector(".topright");
  if (topRight) topRight.prepend(trigger);
  const closeButton = layer.querySelector(".nox-cyber-close");
  let previousFocus = null;
  let latestReport = null;
  const setOutput = (id, value) => {
    const node = $(id);
    node.hidden = false;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  };
  async function api(path, payload) {
    const response = await fetch("/api/cybersecurity/" + path, {
      method: payload ? "POST" : "GET",
      headers: payload ? { "Content-Type": "application/json" } : {},
      body: payload ? JSON.stringify(payload) : undefined,
      credentials: "same-origin"
    });
    const data = await response.json().catch(() => ({ detail: "The server returned a non-JSON response." }));
    if (!response.ok) throw new Error(data.detail || ("HTTP " + response.status));
    return data;
  }
  async function refreshStatus() {
    $("noxCyberStatusText").textContent = "Checking server prerequisites…";
    try {
      const data = await api("status");
      latestReport = { type: "runtime-status", data };
      $("noxCyberStatusText").textContent = data.execution_environment + " · " + data.system + " · local device access: " + (data.local_device_access ? "available" : "not available");
      const tools = $("noxCyberTools");
      tools.replaceChildren();
      data.tools.forEach(tool => {
        const chip = document.createElement("span");
        chip.className = "nox-cyber-chip" + (tool.available_on_server ? "" : " missing");
        chip.textContent = tool.id + ": " + (tool.available_on_server ? "detected on server" : "not installed on server");
        chip.title = tool.description;
        tools.append(chip);
      });
    } catch (error) {
      $("noxCyberStatusText").textContent = "Status unavailable: " + error.message;
    }
  }
  async function runAction(buttonId, outputId, fn, label) {
    const button = $(buttonId);
    button.disabled = true;
    const original = button.textContent;
    button.textContent = "Working…";
    try {
      const data = await fn();
      latestReport = { type: label, data };
      setOutput(outputId, data);
    } catch (error) {
      setOutput(outputId, { status: "error", message: error.message });
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }
  function open() {
    previousFocus = document.activeElement;
    layer.classList.add("open");
    layer.setAttribute("aria-hidden", "false");
    trigger.setAttribute("aria-expanded", "true");
    closeButton.focus();
    refreshStatus();
  }
  function close() {
    layer.classList.remove("open");
    layer.setAttribute("aria-hidden", "true");
    trigger.setAttribute("aria-expanded", "false");
    if (previousFocus && previousFocus.isConnected) previousFocus.focus();
  }
  trigger.addEventListener("click", open);
  closeButton.addEventListener("click", close);
  layer.addEventListener("click", event => { if (event.target === layer) close(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && layer.classList.contains("open")) close(); });
  $("noxCyberRefresh").addEventListener("click", refreshStatus);
  $("noxCyberReview").addEventListener("click", () => runAction("noxCyberReview", "noxCyberReviewOutput", () =>
    api("code-review", { source: $("noxCyberSource").value, filename: $("noxCyberFilename").value || "pasted-source", language: "auto" }), "code-review"));
  $("noxCyberLogReview").addEventListener("click", () => runAction("noxCyberLogReview", "noxCyberLogOutput", () =>
    api("log-review", { logs: $("noxCyberLogs").value }), "log-review"));
  $("noxCyberExplain").addEventListener("click", () => runAction("noxCyberExplain", "noxCyberCommandOutput", () =>
    api("explain-command", { command: $("noxCyberCommand").value }), "command-explanation"));
  $("noxCyberValidateScope").addEventListener("click", () => runAction("noxCyberValidateScope", "noxCyberScopeOutput", () =>
    api("validate-scope", { target: $("noxCyberTarget").value, authorized: $("noxCyberAuthorized").checked, scope_note: $("noxCyberScopeNote").value }), "scope-validation"));
  let localScanId = null;
  async function localApi(path, payload, method) {
    const token = $("noxCyberLocalToken").value.trim();
    if (!token) throw new Error("Enter the local NOX companion token first.");
    const response = await fetch("http://127.0.0.1:8765" + path, {
      method: method || (payload ? "POST" : "GET"),
      headers: Object.assign({ "X-NOX-Token": token }, payload ? { "Content-Type": "application/json" } : {}),
      body: payload ? JSON.stringify(payload) : undefined,
      mode: "cors",
      credentials: "omit"
    });
    const data = await response.json().catch(() => ({ detail: "Local companion returned a non-JSON response." }));
    if (!response.ok) throw new Error(data.detail || ("HTTP " + response.status));
    return data;
  }
  $("noxCyberLocalStatus").addEventListener("click", () => runAction("noxCyberLocalStatus", "noxCyberLocalOutput", () =>
    localApi("/v1/cybersecurity/status"), "local-companion-status"));
  $("noxCyberStartScan").addEventListener("click", () => runAction("noxCyberStartScan", "noxCyberLocalOutput", async () => {
    if (!$("noxCyberAuthorized").checked) throw new Error("Confirm ownership or explicit authorization first.");
    if ($("noxCyberScanConfirm").value.trim() !== "I OWN OR AM AUTHORIZED TO TEST THIS TARGET") throw new Error("Type the exact authorization confirmation.");
    const data = await localApi("/v1/cybersecurity/scans", {
      target: $("noxCyberTarget").value,
      authorized: $("noxCyberAuthorized").checked,
      scope_note: $("noxCyberScopeNote").value,
      confirmation: $("noxCyberScanConfirm").value.trim()
    });
    localScanId = data.task_id;
    return data;
  }, "local-scan-start"));
  $("noxCyberPollScan").addEventListener("click", () => runAction("noxCyberPollScan", "noxCyberLocalOutput", () => {
    if (!localScanId) throw new Error("Start a local scan first; no scan ID is stored.");
    return localApi("/v1/cybersecurity/scans/" + encodeURIComponent(localScanId));
  }, "local-scan-result"));
  $("noxCyberCancelScan").addEventListener("click", () => runAction("noxCyberCancelScan", "noxCyberLocalOutput", () => {
    if (!localScanId) throw new Error("There is no active local scan to cancel.");
    return localApi("/v1/cybersecurity/scans/cancel", { task_id: localScanId });
  }, "local-scan-cancel"));
  $("noxCyberAskNOX").addEventListener("click", () => {
    if (!latestReport) { $("noxCyberStatusText").textContent = "Run a review first; there is no report to discuss yet."; return; }
    const data = latestReport.data || {};
    const findings = Array.isArray(data.findings) ? data.findings.slice(0, 10).map(item =>
      (item.severity || "INFO") + " " + (item.rule || item.check || "finding") + ": " + (item.recommendation || item.detail || "")
    ) : [];
    const summary = "Help me interpret and prioritize this NOX cybersecurity report. Report type: " + latestReport.type +
      ". Findings: " + (data.finding_count ?? "not provided") + ". Severity counts: " +
      JSON.stringify(data.severity_counts || {}) + ". Top recommendations: " + (findings.join(" | ") || "Please explain the report summary and limitations.") +
      ". Treat results as heuristic leads, explain false-positive checks, and recommend defensive remediation. Do not run commands.";
    const input = $("messageInput");
    if (!input || !window.NOXMinimalHome || typeof window.NOXMinimalHome.openChat !== "function") {
      $("noxCyberStatusText").textContent = "NOX Text Chat is not available in this page session.";
      return;
    }
    window.NOXMinimalHome.openChat();
    input.value = summary;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus({ preventScroll: true });
  });
  $("noxCyberExport").addEventListener("click", () => {
    if (!latestReport) { $("noxCyberStatusText").textContent = "Run a review first; there is no report to export yet."; return; }
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), ...latestReport }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = "nox-cybersecurity-report.json";
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
  });
  window.NOXCybersecurityCenter = { open, close, refreshStatus };
})();