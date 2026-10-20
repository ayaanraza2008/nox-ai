(() => {
  "use strict";
  const style = document.createElement("style");
  style.textContent = '.nox-emergency-control{position:fixed;right:14px;bottom:14px;z-index:20000;display:flex;align-items:center;gap:8px;padding:9px;border:1px solid #ff516b88;border-radius:13px;background:#080d17f2;box-shadow:0 8px 32px #0009,0 0 24px #ff294522;backdrop-filter:blur(16px);max-width:calc(100vw - 24px)}\n' +
    '.nox-emergency-control button{border-radius:9px;padding:11px 13px;font:800 10px ui-monospace,monospace;letter-spacing:.08em;cursor:pointer}\n' +
    '.nox-emergency-stop{border:1px solid #ff7186;background:linear-gradient(135deg,#b91c3b,#7f102b);color:#fff;box-shadow:0 0 18px #ff29452c}\n' +
    '.nox-emergency-resume{border:1px solid #68e8bd;background:#103b35;color:#c9ffed}\n' +
    '.nox-emergency-status{min-width:76px;font:9px/1.5 ui-monospace,monospace;color:#a9c0d4}\n' +
    '.nox-emergency-status strong{display:block;color:#78f0c2;letter-spacing:.08em}\n' +
    'body[data-nox-emergency-state="stopping"] .nox-emergency-status strong,body[data-nox-emergency-state="stopped"] .nox-emergency-status strong{color:#ff7186}\n' +
    'body[data-nox-emergency-state="stopping"] #taskForm button[type="submit"],body[data-nox-emergency-state="stopped"] #taskForm button[type="submit"],body[data-nox-emergency-state="stopping"] #nsCreate,body[data-nox-emergency-state="stopped"] #nsCreate,body[data-nox-emergency-state="stopping"] #nbRun,body[data-nox-emergency-state="stopped"] #nbRun{pointer-events:none;opacity:.35}\n' +
    '@media(max-width:520px){.nox-emergency-control{right:8px;bottom:8px;gap:5px;padding:6px}.nox-emergency-control button{padding:10px 9px;font-size:9px}.nox-emergency-status{min-width:64px}}';
  document.head.appendChild(style);
  const dock = document.createElement("aside");
  dock.className = "nox-emergency-control";
  dock.setAttribute("aria-label", "NOX emergency execution controls");
  dock.innerHTML = '<div class="nox-emergency-status" aria-live="polite"><strong id="noxEmergencyPhase">CHECKING</strong><span id="noxEmergencyDetail">Task safety status</span></div><button type="button" class="nox-emergency-stop" id="noxEmergencyStop">EMERGENCY STOP</button><button type="button" class="nox-emergency-resume" id="noxEmergencyResume" hidden>RESUME</button>';
  document.body.appendChild(dock);
  const phase = document.getElementById("noxEmergencyPhase");
  const detail = document.getElementById("noxEmergencyDetail");
  const stopButton = document.getElementById("noxEmergencyStop");
  const resumeButton = document.getElementById("noxEmergencyResume");
  let state = "checking", busy = false, pollTimer = null;
  const launchSelectors = ['#taskForm button[type="submit"]', "#nsCreate", "#nbRun", "#nsToolRun", "#cognitiveRun", "#researchRun"];
  function setLaunchesBlocked(blocked) {
    launchSelectors.forEach(selector => document.querySelectorAll(selector).forEach(button => {
      if (!button.dataset.noxOriginalDisabled) button.dataset.noxOriginalDisabled = button.disabled ? "1" : "0";
      if (blocked) button.disabled = true;
      else if (button.dataset.noxOriginalDisabled === "0") button.disabled = false;
    }));
  }
  function apply(data) {
    state = data.state || (data.stopped ? "stopping" : "running");
    document.body.dataset.noxEmergencyState = state;
    phase.textContent = state.toUpperCase();
    const pending = Array.isArray(data.pending_operations) ? data.pending_operations : [];
    detail.textContent = state === "stopped" ? "No tracked work pending" :
      state === "stopping" ? pending.length + " operation(s) awaiting cleanup" :
      state === "unverified" ? "Safety state unavailable" : "New tasks permitted";
    resumeButton.hidden = !(data.stopped && state === "stopped");
    stopButton.disabled = busy;
    stopButton.textContent = state === "stopped" ? "STOPPED" : "EMERGENCY STOP";
    setLaunchesBlocked(state === "stopping" || state === "stopped" || state === "unverified");
    if (pending.length) detail.title = pending.map(item => item.type + ": " + item.id + " (" + item.status + ")").join("\n");
    else detail.removeAttribute("title");
  }
  async function api(path, method) {
    const response = await fetch(path, {method: method || "GET", credentials: "same-origin",
      cache: "no-store", headers: {"Accept": "application/json", "Content-Type": "application/json"}});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || ("NOX emergency endpoint returned HTTP " + response.status));
    return data;
  }
  async function refresh() {
    if (busy) return;
    try { apply(await api("/api/emergency-stop")); }
    catch (error) {
      phase.textContent = "UNVERIFIED";
      detail.textContent = error.message || "Safety state unavailable";
      document.body.dataset.noxEmergencyState = "unverified";
      setLaunchesBlocked(true);
      resumeButton.hidden = true;
    }
  }
  stopButton.addEventListener("click", async () => {
    if (busy) return;
    busy = true;
    state = "stopping";
    document.body.dataset.noxEmergencyState = "stopping";
    phase.textContent = "STOPPING";
    detail.textContent = "Cancelling queued and active work…";
    stopButton.disabled = true;
    resumeButton.hidden = true;
    setLaunchesBlocked(true);
    try {
      if (window.speechSynthesis && typeof window.speechSynthesis.cancel === "function") window.speechSynthesis.cancel();
      const voiceStop = document.getElementById("voiceStop");
      if (voiceStop && !voiceStop.disabled) voiceStop.click();
      window.dispatchEvent(new CustomEvent("nox:emergency-stop"));
      apply(await api("/api/emergency-stop", "POST"));
    } catch (error) {
      phase.textContent = "STOP UNVERIFIED";
      detail.textContent = error.message || "Could not confirm cancellation";
      document.body.dataset.noxEmergencyState = "unverified";
      setLaunchesBlocked(true);
    } finally {
      busy = false;
      stopButton.disabled = false;
      await refresh();
    }
  });
  resumeButton.addEventListener("click", async () => {
    if (busy || state !== "stopped") return;
    busy = true;
    resumeButton.disabled = true;
    try {
      const result = await api("/api/emergency-stop/resume", "POST");
      apply({state: "running", stopped: false, pending_operations: []});
      detail.textContent = result.message || "Resumed by user";
    } catch (error) {
      detail.textContent = error.message || "Resume rejected";
      await refresh();
    } finally {
      busy = false;
      resumeButton.disabled = false;
      await refresh();
    }
  });
  (async () => {
    try { await api("/api/session"); } catch (_) {}
    await refresh();
    pollTimer = window.setInterval(refresh, 2500);
  })();
  window.addEventListener("pagehide", () => { if (pollTimer) window.clearInterval(pollTimer); });
})();