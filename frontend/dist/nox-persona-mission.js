(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const STORAGE = { mode: "nox_operating_mode", gender: "nox_voice_gender", volume: "nox_voice_volume" };
  let missionTimer = 0;
  let previewAudio = null;
  let busy = false;

  const css = document.createElement("style");
  css.textContent = `
    .nox-mode-switch{display:flex;align-items:center;gap:5px;margin-right:4px}
    .nox-mode-switch button{white-space:nowrap;font-size:10px;letter-spacing:.06em}
    .nox-mode-switch .selected{border-color:var(--cyan);color:var(--text);box-shadow:0 0 16px color-mix(in srgb,var(--cyan) 18%,transparent)}
    body.nox-autonomous-mode{--bg:#100608;--panel:rgba(28,8,12,.9);--panel2:rgba(38,8,14,.82);--line:rgba(255,65,78,.3);--line2:rgba(255,25,45,.26);--cyan:#ff4d5d;--violet:#ff8a72;--muted:#b78e94;--text:#fff0f1;--green:#ffb1b6;--amber:#ff9a78;--red:#ff334f;background-color:#100608}
    body.nox-autonomous-mode{background-image:radial-gradient(ellipse at 50% 5%,rgba(155,9,29,.18),transparent 44%)}
    body.nox-autonomous-mode .topbar{border-bottom-color:rgba(255,60,80,.3);box-shadow:0 8px 35px rgba(120,0,16,.12)}
    body.nox-autonomous-mode .panel{border-color:rgba(255,60,78,.28);box-shadow:0 10px 34px rgba(95,0,12,.12),inset 0 0 24px rgba(255,35,55,.025)}
    body.nox-autonomous-mode .brandmark{border-color:#ff4058;color:#ff7c89;box-shadow:0 0 20px rgba(255,45,65,.2)}
    body.nox-autonomous-mode #corePanel{border-color:#ff445c;box-shadow:0 0 0 1px rgba(255,35,60,.1),0 0 35px rgba(255,20,45,.17),inset 0 0 35px rgba(255,25,45,.08)}
    body.nox-autonomous-mode #corePanel:before{content:"";position:absolute;inset:0;z-index:1;pointer-events:none;background:radial-gradient(ellipse at center,rgba(255,20,40,.12),rgba(100,0,8,.03) 58%,transparent 78%);mix-blend-mode:screen}
    body.nox-autonomous-mode #corePanel .nox-particle-canvas{filter:hue-rotate(128deg) saturate(1.45)}
    body.nox-autonomous-mode .primary,body.nox-autonomous-mode .nox-mode-switch .selected{border-color:#ff4058;background:linear-gradient(135deg,rgba(140,12,30,.8),rgba(65,8,16,.95));color:#fff1f2}
    body.nox-autonomous-mode .nox-mission{border-color:rgba(255,60,78,.45);background:linear-gradient(120deg,rgba(90,6,18,.28),rgba(20,5,9,.72))}
    .nox-mission{display:none;border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:12px;background:linear-gradient(120deg,rgba(99,208,238,.06),rgba(12,18,30,.4))}
    body.nox-autonomous-mode .nox-mission{display:block}
    .nox-mission-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
    .nox-mission-title{font:700 10px/1.3 var(--mono);letter-spacing:.13em}
    .nox-mission-state{font:700 10px var(--mono);color:var(--cyan)}
    .nox-mission-objective{font-size:12px;line-height:1.45;margin-top:9px;overflow-wrap:anywhere;color:var(--text)}
    .nox-mission-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:10px}
    .nox-mission-metric{border:1px solid var(--line);border-radius:8px;padding:7px}
    .nox-mission-metric strong{display:block;font:700 17px var(--mono);color:var(--text)}
    .nox-mission-metric span{font:9px var(--mono);color:var(--muted);letter-spacing:.08em}
    .nox-mission-note{font-size:10px;line-height:1.45;color:var(--muted);margin-top:9px}
    .nox-mode-controls{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:10px}
    .nox-mode-controls button{font-size:10px;padding:7px 10px}
    .nox-voice-profiles{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:9px 0 5px}
    .nox-voice-profiles .profile{flex:1 1 105px;display:flex;align-items:center;justify-content:center;gap:7px}
    .nox-voice-profiles .profile[aria-pressed="true"]{border-color:var(--cyan);color:var(--text);box-shadow:0 0 14px color-mix(in srgb,var(--cyan) 15%,transparent)}
    .nox-volume{display:flex;align-items:center;gap:8px;font-size:10px;color:var(--muted);flex:1 1 160px}
    .nox-volume input{width:100%;min-width:70px}
    .nox-preview-status{font-size:10px;color:var(--muted);min-height:14px;flex:1 1 100%}
    @media(max-width:760px){.nox-mode-switch{order:3;width:100%;margin:5px 0 0}.nox-mode-switch button{flex:1}.nox-mission-metrics{gap:5px}.nox-mission-metric{padding:6px}}
    @media(prefers-reduced-motion:reduce){body.nox-autonomous-mode #corePanel .nox-particle-canvas{filter:none}}
  `;
  document.head.appendChild(css);

  function el(tag, attrs = {}, text = "") {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (key === "class") node.className = value;
      else if (key.startsWith("aria-") || key === "type" || key === "title" || key === "min" || key === "max" || key === "step" || key === "value" || key === "id") node.setAttribute(key, value);
      else node[key] = value;
    });
    if (text) node.textContent = text;
    return node;
  }

  function modeFromStorage() {
    try { return localStorage.getItem(STORAGE.mode) === "autonomous" ? "autonomous" : "normal"; }
    catch { return "normal"; }
  }
  function voiceGender() {
    try { return localStorage.getItem(STORAGE.gender) === "female" ? "female" : "male"; }
    catch { return "male"; }
  }
  function volumeValue() {
    try { const n = Number(localStorage.getItem(STORAGE.volume)); return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) : 0.85; }
    catch { return 0.85; }
  }

  function buildModeSwitch() {
    const host = document.querySelector(".topright");
    if (!host || $("noxModeSwitch")) return;
    const group = el("div", { id: "noxModeSwitch", class: "nox-mode-switch", role: "group", "aria-label": "NOX operating mode" });
    const normal = el("button", { id: "noxNormalMode", class: "iconbtn", type: "button" }, "◈ NORMAL");
    const autonomous = el("button", { id: "noxAutonomousMode", class: "iconbtn", type: "button" }, "⬡ AUTONOMOUS");
    normal.addEventListener("click", () => setOperatingMode("normal"));
    autonomous.addEventListener("click", () => setOperatingMode("autonomous"));
    group.append(normal, autonomous);
    host.prepend(group);
  }

  function buildMissionPanel() {
    const panel = $("taskPanel");
    const body = panel?.querySelector(".panelbody");
    if (!body || $("noxMission")) return;
    const card = el("section", { id: "noxMission", class: "nox-mission", "aria-live": "polite" });
    const top = el("div", { class: "nox-mission-top" });
    top.append(el("div", { class: "nox-mission-title" }, "NOX / MISSION CONTROL"), el("div", { id: "noxMissionState", class: "nox-mission-state" }, "STANDBY"));
    const objective = el("div", { id: "noxMissionObjective", class: "nox-mission-objective" }, "No active objective. Submit a task below to begin.");
    const metrics = el("div", { class: "nox-mission-metrics" });
    [["noxMissionActive", "0", "ACTIVE"], ["noxMissionDone", "0", "COMPLETED"], ["noxMissionBlocked", "0", "BLOCKED / ERROR"]].forEach(([id, value, label]) => {
      const metric = el("div", { class: "nox-mission-metric" });
      metric.append(el("strong", { id }, value), el("span", {}, label));
      metrics.append(metric);
    });
    const note = el("div", { class: "nox-mission-note" }, "Live status from NOX's session-scoped backend task queue. Available tools and permissions remain bounded; this mode does not grant local computer control.");
    card.append(top, objective, metrics, note);
    body.prepend(card);
  }

  function buildVoiceControls() {
    const body = $("voicePanel")?.querySelector(".panelbody");
    const controls = document.querySelector(".voicecontrols");
    if (!body || !controls || $("noxVoiceModeControls")) return;
    const modeRow = el("div", { id: "noxVoiceModeControls", class: "nox-mode-controls", role: "group", "aria-label": "Voice or text interaction" });
    const voice = el("button", { id: "noxVoiceMode", class: "secondary", type: "button" }, "◖ Voice Mode");
    const text = el("button", { id: "noxTextMode", class: "secondary", type: "button" }, "▤ Text Mode");
    voice.addEventListener("click", () => {
      if ($("voiceStatus")?.textContent === "LISTENING" || $("voiceStatus")?.textContent === "SPEAKING" || $("voiceStatus")?.textContent === "THINKING") return;
      $("voiceStart")?.click();
    });
    text.addEventListener("click", () => {
      if ($("voiceStop") && !$("voiceStop").disabled) $("voiceStop").click();
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      if (previewAudio) { previewAudio.pause(); previewAudio = null; }
      if ($("chatStatus")) $("chatStatus").textContent = "Text mode · spoken replies stopped";
      updateVoiceModeButtons(false);
    });
    modeRow.append(voice, text);
    body.prepend(modeRow);

    const row = el("div", { id: "noxVoiceProfiles", class: "nox-voice-profiles" });
    const male = el("button", { id: "noxMaleVoice", class: "secondary profile", type: "button", "aria-pressed": "false" }, "♂ Male · Rich");
    const female = el("button", { id: "noxFemaleVoice", class: "secondary profile", type: "button", "aria-pressed": "false" }, "♀ Female · Warm");
    const preview = el("button", { id: "noxVoicePreview", class: "secondary", type: "button" }, "▶ Preview");
    const volume = el("label", { class: "nox-volume" }, "Volume");
    const slider = el("input", { id: "noxVoiceVolume", type: "range", min: "0", max: "1", step: "0.05", value: String(volumeValue()) });
    slider.setAttribute("aria-label", "Voice output volume");
    volume.append(slider);
    const status = el("div", { id: "noxVoicePreviewStatus", class: "nox-preview-status", role: "status", "aria-live": "polite" });
    male.addEventListener("click", () => setVoiceGender("male"));
    female.addEventListener("click", () => setVoiceGender("female"));
    preview.addEventListener("click", previewVoice);
    slider.addEventListener("input", () => {
      const value = String(Math.max(0, Math.min(1, Number(slider.value))));
      try { localStorage.setItem(STORAGE.volume, value); } catch {}
      if (previewAudio) previewAudio.volume = Number(value);
    });
    row.append(male, female, preview, volume, status);
    controls.insertAdjacentElement("afterend", row);
    setVoiceGender(voiceGender(), false);
    updateVoiceModeButtons(null);
  }

  function updateVoiceModeButtons(active) {
    const voice = $("noxVoiceMode"), text = $("noxTextMode");
    if (voice) voice.setAttribute("aria-pressed", active === true ? "true" : "false");
    if (text) text.setAttribute("aria-pressed", active === false ? "true" : "false");
    if (voice) voice.classList.toggle("primary", active === true);
    if (text) text.classList.toggle("primary", active === false);
  }

  function setVoiceGender(gender, persist = true) {
    gender = gender === "female" ? "female" : "male";
    if (persist) { try { localStorage.setItem(STORAGE.gender, gender); } catch {} }
    const male = $("noxMaleVoice"), female = $("noxFemaleVoice");
    if (male) male.setAttribute("aria-pressed", gender === "male" ? "true" : "false");
    if (female) female.setAttribute("aria-pressed", gender === "female" ? "true" : "false");
    // Auto lets the active voice profile select a provider-supported voice for each speech language.
    const selector = $("voiceChoice");
    if (selector && persist) selector.value = "auto";
    const status = $("noxVoicePreviewStatus");
    if (status) status.textContent = gender === "female" ? "Female profile selected. Urdu currently uses the provider's available Asad voice." : "Male profile selected.";
  }

  function voiceFor(gender, language) {
    if (language === "hi-IN") return gender === "female" ? "hi-IN-SwaraNeural" : "hi-IN-MadhurNeural";
    if (language === "ur-PK") return "ur-PK-AsadNeural";
    return gender === "female" ? "en-IN-NeerjaNeural" : "en-IN-PrabhatNeural";
  }

  async function previewVoice() {
    const button = $("noxVoicePreview"), status = $("noxVoicePreviewStatus");
    if (busy) return;
    busy = true;
    if (button) button.disabled = true;
    if (status) status.textContent = "Requesting a real provider voice preview…";
    try {
      if (previewAudio) { previewAudio.pause(); previewAudio = null; }
      const selectedLanguage = $("language")?.value || "auto";
      const language = selectedLanguage === "hi" || selectedLanguage === "hinglish" ? "hi-IN" : selectedLanguage === "ur" ? "ur-PK" : "en-IN";
      const gender = voiceGender();
      const payload = { text: language === "hi-IN" ? "नमस्ते, मैं NOX हूँ। बताइए, आज क्या करना है?" : language === "ur-PK" ? "السلام علیکم، میں NOX ہوں۔ بتائیے، آج کیا کرنا ہے؟" : "Hello, I'm NOX. Ready when you are.", language, voice: voiceFor(gender, language), rate: Number($("voiceRate")?.value || 1) };
      const response = await fetch("/api/tts", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error("Voice provider returned HTTP " + response.status);
      const audio = new Audio(URL.createObjectURL(await response.blob()));
      previewAudio = audio;
      audio.volume = volumeValue();
      audio.onended = () => { URL.revokeObjectURL(audio.src); if (previewAudio === audio) previewAudio = null; };
      await audio.play();
      if (status) status.textContent = gender === "female" && language === "ur-PK" ? "Preview playing · Urdu voice falls back to the available Asad voice." : "Preview playing · " + (gender === "female" ? "Female" : "Male") + " profile.";
    } catch (error) {
      if (status) status.textContent = "Preview unavailable: " + String(error?.message || error);
    } finally {
      busy = false;
      if (button) button.disabled = false;
    }
  }

  function setOperatingMode(mode) {
    mode = mode === "autonomous" ? "autonomous" : "normal";
    document.body.classList.toggle("nox-autonomous-mode", mode === "autonomous");
    try { localStorage.setItem(STORAGE.mode, mode); } catch {}
    const normal = $("noxNormalMode"), autonomous = $("noxAutonomousMode");
    if (normal) { normal.classList.toggle("selected", mode === "normal"); normal.setAttribute("aria-pressed", mode === "normal" ? "true" : "false"); }
    if (autonomous) { autonomous.classList.toggle("selected", mode === "autonomous"); autonomous.setAttribute("aria-pressed", mode === "autonomous" ? "true" : "false"); }
    const status = $("noxMissionState");
    if (status && mode === "normal") status.textContent = "STANDBY";
    const taskPanel = $("taskPanel");
    if (taskPanel && mode === "autonomous") taskPanel.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
    if (mode === "autonomous") {
      refreshMission();
      if (!missionTimer) missionTimer = window.setInterval(refreshMission, 3000);
    } else if (missionTimer) {
      clearInterval(missionTimer); missionTimer = 0;
    }
  }

  async function refreshMission() {
    const state = $("noxMissionState");
    if (!state || !document.body.classList.contains("nox-autonomous-mode") || document.hidden) return;
    try {
      await fetch("/api/session", { credentials: "same-origin", cache: "no-store" }).then((r) => { if (!r.ok) throw new Error("Session unavailable"); });
      const response = await fetch("/api/tasks?limit=20", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("Task service HTTP " + response.status);
      const data = await response.json();
      const tasks = Array.isArray(data.tasks) ? data.tasks : [];
      const active = tasks.filter((t) => ["queued", "pending", "planning", "running", "in_progress", "paused", "verifying"].includes(String(t.status || "").toLowerCase()));
      const done = tasks.filter((t) => ["completed", "success", "succeeded"].includes(String(t.status || "").toLowerCase()));
      const blocked = tasks.filter((t) => ["failed", "error", "blocked", "cancelled", "canceled"].includes(String(t.status || "").toLowerCase()));
      $("noxMissionActive").textContent = String(active.length);
      $("noxMissionDone").textContent = String(done.length);
      $("noxMissionBlocked").textContent = String(blocked.length);
      const latest = tasks[0];
      const labels = { queued: "OBJECTIVE RECEIVED", pending: "STANDBY", planning: "PLANNING", running: "EXECUTING", in_progress: "EXECUTING", verifying: "VERIFYING", paused: "PAUSED", completed: "COMPLETED", success: "COMPLETED", succeeded: "COMPLETED", failed: "ERROR", error: "ERROR", blocked: "BLOCKED", cancelled: "CANCELLED", canceled: "CANCELLED" };
      state.textContent = latest ? (labels[String(latest.status || "").toLowerCase()] || String(latest.status || "STANDBY").toUpperCase()) : "STANDBY";
      $("noxMissionObjective").textContent = latest ? String(latest.goal || latest.title || "Task objective unavailable") : "No active objective. Submit a task below to begin.";
    } catch (error) {
      state.textContent = "STATUS UNAVAILABLE";
      $("noxMissionObjective").textContent = "Could not read live task state: " + String(error?.message || error) + ". Check the backend connection.";
    }
  }

  function boot() {
    buildModeSwitch();
    buildMissionPanel();
    buildVoiceControls();
    setOperatingMode(modeFromStorage());
    const stop = $("voiceStop");
    if (stop) stop.addEventListener("click", () => updateVoiceModeButtons(false));
    const start = $("voiceStart");
    if (start) start.addEventListener("click", () => window.setTimeout(() => {
      const active = $("voiceStatus") && ["LISTENING", "SPEAKING", "THINKING"].includes($("voiceStatus").textContent);
      updateVoiceModeButtons(Boolean(active));
    }, 250));
    const toggle = $("voiceToggle");
    if (toggle) toggle.addEventListener("click", () => window.setTimeout(() => updateVoiceModeButtons(Boolean($("voiceStatus") && ["LISTENING", "SPEAKING", "THINKING"].includes($("voiceStatus").textContent))), 250));
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && missionTimer) { clearInterval(missionTimer); missionTimer = 0; }
      else if (!document.hidden && document.body.classList.contains("nox-autonomous-mode") && !missionTimer) { refreshMission(); missionTimer = window.setInterval(refreshMission, 3000); }
    });
    window.addEventListener("pagehide", () => {
      if (missionTimer) clearInterval(missionTimer);
      if (previewAudio) { previewAudio.pause(); previewAudio = null; }
    }, { once: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();