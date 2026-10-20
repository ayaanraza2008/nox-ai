(() => {
  "use strict";
  if (document.getElementById("noxLiveBrowserPanel")) return;
  const css = document.createElement("style");
  css.textContent = `
    #noxLiveBrowserLauncher{position:fixed;right:18px;bottom:92px;z-index:9000;border:1px solid #38bdf8;background:linear-gradient(135deg,#101a31,#17102d);color:#e8f8ff;border-radius:999px;padding:11px 16px;font:600 12px system-ui;letter-spacing:.08em;box-shadow:0 0 24px #38bdf833;cursor:pointer}
    #noxLiveBrowserPanel{position:fixed;inset:5vh 3vw 5vh auto;width:min(720px,94vw);z-index:9001;display:none;flex-direction:column;gap:10px;padding:16px;border:1px solid #4f7db6;border-radius:18px;background:rgba(5,10,23,.97);color:#e6f5ff;box-shadow:0 20px 80px #000b;backdrop-filter:blur(18px);font:13px system-ui}
    #noxLiveBrowserPanel.open{display:flex}#noxLiveBrowserPanel *{box-sizing:border-box}
    #noxLiveBrowserPanel .nox-lb-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
    #noxLiveBrowserPanel .nox-lb-sub{font-size:11px;color:#9fb5d2}
    #noxLiveBrowserPanel .nox-lb-row{display:flex;gap:7px;flex-wrap:wrap}
    #noxLiveBrowserPanel input,#noxLiveBrowserPanel textarea{min-width:0;flex:1;background:#0b1427;color:#e6f5ff;border:1px solid #314865;border-radius:9px;padding:10px;font:inherit}
    #noxLiveBrowserPanel button{background:#12243c;color:#dff7ff;border:1px solid #365a7b;border-radius:9px;padding:9px 11px;cursor:pointer;font:inherit}
    #noxLiveBrowserPanel button.primary{background:#153b59;border-color:#31b7ec}#noxLiveBrowserPanel button.danger{border-color:#ad536b}
    #noxLiveBrowserPanel .nox-lb-preview{min-height:160px;max-height:38vh;overflow:auto;background:#02050b;border:1px solid #253850;border-radius:12px;display:flex;align-items:center;justify-content:center}
    #noxLiveBrowserPanel .nox-lb-preview img{max-width:100%;max-height:38vh;object-fit:contain}
    #noxLiveBrowserPanel .nox-lb-status{padding:9px 11px;background:#0a1728;border:1px solid #243d5a;border-radius:9px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:130px;overflow:auto}
    #noxLiveBrowserPanel .nox-lb-steps{max-height:100px;overflow:auto;font-size:11px;color:#b6c8df}
    #noxLiveBrowserPanel .nox-lb-steps div{padding:3px 0}#noxLiveBrowserPanel .nox-lb-question{border:1px solid #eab30866;background:#2b220b;padding:10px;border-radius:10px;white-space:pre-wrap}
    @media(max-width:600px){#noxLiveBrowserPanel{inset:2vh 2vw;width:96vw;padding:11px}#noxLiveBrowserLauncher{right:12px;bottom:84px}}
  `;
  document.head.appendChild(css);
  const launcher = document.createElement("button");
  launcher.id = "noxLiveBrowserLauncher";
  launcher.type = "button";
  launcher.textContent = "◉ LIVE BROWSER";
  launcher.setAttribute("aria-label", "Open NOX Live Browser");
  const panel = document.createElement("section");
  panel.id = "noxLiveBrowserPanel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "false");
  panel.setAttribute("aria-label", "NOX Live Browser");
  panel.innerHTML = `
    <div class="nox-lb-head"><div><strong style="letter-spacing:.13em">NOX / LIVE BROWSER</strong><div class="nox-lb-sub" id="noxLbMode">LOCAL AUTOMATION · STATUS UNKNOWN</div></div><button id="noxLbClose" aria-label="Close panel">✕</button></div>
    <div class="nox-lb-row"><input id="noxLbCommand" maxlength="2000" placeholder="Open https://example.com · search web for …" aria-label="Browser task or command"><button class="primary" id="noxLbRun">Run</button></div>
    <div class="nox-lb-row"><button id="noxLbInspect">Inspect page</button><button id="noxLbBack">Back</button><button id="noxLbForward">Forward</button><button id="noxLbScroll">Scroll down</button><button id="noxLbPause">Pause</button><button id="noxLbResume">Resume</button><button class="danger" id="noxLbStop">Stop task</button></div>
    <div class="nox-lb-sub" id="noxLbUrl">No page open</div>
    <div class="nox-lb-preview"><img id="noxLbScreenshot" alt="Screenshot of the actual locally controlled browser page" hidden><span id="noxLbEmpty" class="nox-lb-sub">A real browser screenshot appears here after opening a page.</span></div>
    <div class="nox-lb-status" id="noxLbResult">Ready. Browser control requires local setup and explicit opt-in.</div>
    <div class="nox-lb-steps" id="noxLbSteps"></div>
    <div class="nox-lb-sub">RECENT LOCAL TASKS</div><div class="nox-lb-steps" id="noxLbHistory"></div>
    <div class="nox-lb-question" id="noxLbQuestion" hidden></div>
    <div class="nox-lb-row" id="noxLbAnswerRow" hidden><input id="noxLbAnswer" maxlength="1000" placeholder="Answer NOX's question"><button class="primary" id="noxLbAnswerSend">Send answer</button></div>
    <div class="nox-lb-row" id="noxLbConfirmRow" hidden><button class="primary" id="noxLbConfirm">Confirm this action</button><button class="danger" id="noxLbDecline">Decline</button></div>
    <div class="nox-lb-sub">Website text is treated as untrusted data. Payments, submissions, publishing, deletion and similar actions require explicit confirmation. Login/CAPTCHA must be completed by you in the visible local browser.</div>
  `;
  document.body.append(launcher, panel);
  const $ = (id) => document.getElementById(id);
  let poller = null;
  let lastState = "";
  let lastSnapshot = null;
  let speakQuestionsForTask = false;
  let spokenQuestion = "";
  async function api(path, options = {}) {
    const response = await fetch(path, {credentials:"same-origin", cache:"no-store", ...options, headers:{"Content-Type":"application/json", ...(options.headers || {})}});
    const data = response.headers.get("content-type")?.includes("application/json") ? await response.json() : null;
    if (!response.ok) throw new Error(data?.detail || ("HTTP " + response.status));
    return data;
  }
  function render(data) {
    if (!data) return;
    lastSnapshot = data;
    lastState = data.state || "idle";
    $("noxLbMode").textContent = data.enabled
      ? (data.headless ? "LOCAL BROWSER · HEADLESS PREVIEW" : "LOCAL BROWSER · VISIBLE WINDOW")
      : "DISABLED · SET NOX_BROWSER_ENABLED=1";
    $("noxLbUrl").textContent = data.current_url ? data.page_title + " · " + data.current_url : "No page open";
    $("noxLbResult").textContent = [data.state ? "State: " + data.state : "", data.result || "", data.error ? "Error: " + data.error : ""].filter(Boolean).join("\n") || "Ready.";
    $("noxLbSteps").replaceChildren(...(data.steps || []).map(step => {
      const row = document.createElement("div");
      row.textContent = (step.status === "completed" ? "✓ " : step.status === "failed" ? "× " : step.status === "running" ? "◌ " : "· ") + step.index + ". " + step.label + (step.error ? " — " + step.error : "");
      return row;
    }));
    $("noxLbHistory").replaceChildren(...(data.history || []).slice().reverse().map(task => {
      const row = document.createElement("div");
      row.textContent = new Date(task.created_at || Date.now()).toLocaleTimeString() + " · " + task.status + " · " + (task.step_count || 0) + " steps" + (task.url ? " · " + task.url : "") + (task.error ? " · " + task.error : "");
      return row;
    }));
    const question = $("noxLbQuestion");
    question.hidden = !data.pending_question;
    question.textContent = data.pending_question || "";
    if (speakQuestionsForTask && data.pending_question && data.pending_question !== spokenQuestion && "speechSynthesis" in window) {
      spokenQuestion = data.pending_question;
      if (typeof window.NOXSpeakBrowserQuestion === "function") {
        window.NOXSpeakBrowserQuestion(data.pending_question);
      } else {
        const language = document.getElementById("language")?.value || "auto";
        const utterance = new SpeechSynthesisUtterance(data.pending_question);
        utterance.lang = language === "hi" || language === "hinglish" ? "hi-IN" : language === "ur" ? "ur-PK" : "en-US";
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      }
    }
    $("noxLbAnswerRow").hidden = data.state !== "awaiting_input";
    $("noxLbConfirmRow").hidden = data.state !== "awaiting_confirmation";
    $("noxLbPause").disabled = !["running"].includes(data.state);
    $("noxLbResume").disabled = !["paused","awaiting_auth"].includes(data.state);
    if (data.available && panel.classList.contains("open")) refreshScreenshot().catch(() => {});
  }
  async function status() { try { await api("/api/session"); render(await api("/api/browser/status")); } catch (e) { $("noxLbResult").textContent = e.message + "\nStart NOX locally with the optional Playwright setup."; } }
  async function refreshScreenshot() {
    const response = await fetch("/api/browser/screenshot?ts=" + Date.now(), {credentials:"same-origin", cache:"no-store"});
    if (!response.ok) { $("noxLbScreenshot").hidden = true; $("noxLbEmpty").hidden = false; return; }
    const blob = await response.blob();
    const old = $("noxLbScreenshot").dataset.objectUrl;
    if (old) URL.revokeObjectURL(old);
    const url = URL.createObjectURL(blob);
    $("noxLbScreenshot").src = url;
    $("noxLbScreenshot").dataset.objectUrl = url;
    $("noxLbScreenshot").hidden = false;
    $("noxLbEmpty").hidden = true;
  }
  async function act(path, body) { try { const data = await api(path, {method:"POST", body:JSON.stringify(body || {})}); render(data); await status(); } catch (e) { $("noxLbResult").textContent = e.message; } }
  launcher.onclick = () => { panel.classList.add("open"); status(); if (!poller) poller = setInterval(status, 1200); };
  $("noxLbClose").onclick = () => { panel.classList.remove("open"); if (poller) clearInterval(poller); poller = null; };
  $("noxLbRun").onclick = () => { const instruction = $("noxLbCommand").value.trim(); if (instruction) act("/api/browser/task", {instruction}); };
  $("noxLbCommand").addEventListener("keydown", e => { if (e.key === "Enter") $("noxLbRun").click(); });
  $("noxLbInspect").onclick = () => act("/api/browser/action", {action:"inspect"});
  $("noxLbBack").onclick = () => act("/api/browser/action", {action:"back"});
  $("noxLbForward").onclick = () => act("/api/browser/action", {action:"forward"});
  $("noxLbScroll").onclick = () => act("/api/browser/action", {action:"scroll"});
  $("noxLbPause").onclick = () => act("/api/browser/pause");
  $("noxLbResume").onclick = () => act("/api/browser/resume");
  $("noxLbStop").onclick = () => act("/api/browser/stop");
  $("noxLbAnswerSend").onclick = () => { const answer = $("noxLbAnswer").value.trim(); if (answer) { act("/api/browser/answer", {answer}); $("noxLbAnswer").value = ""; } };
  $("noxLbConfirm").onclick = () => act("/api/browser/confirm", {approved:true});
  $("noxLbDecline").onclick = () => act("/api/browser/confirm", {approved:false});
  const browserControl = /^(?:nox[, ]*)?(?:stop browser(?: task)?|pause browser(?: task)?|resume browser(?: task)?|continue browser(?: task)?|cancel browser(?: task)?)$/i;
  const yesAnswer = /^(?:yes|yes confirm|confirm|approve|go ahead|proceed)$/i;
  const noAnswer = /^(?:no|no cancel|decline|don't|do not|cancel)$/i;
  window.NOXLiveBrowser = {
    shouldHandle(text) {
      const value = String(text || "").trim();
      if (!value) return false;
      if (lastSnapshot?.state === "awaiting_input" || lastSnapshot?.state === "awaiting_confirmation") return true;
      if (browserControl.test(value)) return true;
      return /https?:\/\//i.test(value) ||
        /\b(?:search the web for|search for|look up online|inspect this page|read this page|scroll down|go back|go forward)\b/i.test(value) ||
        /^\s*(?:nox[, ]*)?(?:open|visit|go to|navigate to|click|type|enter|fill|select)\b/i.test(value);
    },
    async handleCommand(text, options = {}) {
      panel.classList.add("open");
      if (!poller) poller = setInterval(status, 1200);
      speakQuestionsForTask = !!options.voiceTurn;
      spokenQuestion = ["awaiting_input", "awaiting_confirmation"].includes(lastSnapshot?.state) ? (lastSnapshot?.pending_question || "") : "";
      $("noxLbCommand").value = String(text || "").slice(0, 2000);
      await status();
      const value = String(text || "").trim();
      if (/\b(?:stop|cancel) browser(?: task)?\b/i.test(value)) return act("/api/browser/stop");
      if (/\bpause browser(?: task)?\b/i.test(value)) return act("/api/browser/pause");
      if (/\b(?:resume|continue) browser(?: task)?\b/i.test(value)) return act("/api/browser/resume");
      if (lastSnapshot?.state === "awaiting_confirmation") {
        if (yesAnswer.test(value)) return act("/api/browser/confirm", {approved:true});
        if (noAnswer.test(value)) return act("/api/browser/confirm", {approved:false});
        $("noxLbResult").textContent = "Please say “yes” to confirm or “no” to decline this consequential action.";
        return;
      }
      if (lastSnapshot?.state === "awaiting_input") {
        $("noxLbAnswer").value = value;
        await act("/api/browser/answer", {answer:value});
        $("noxLbAnswer").value = "";
        return;
      }
      await act("/api/browser/task", {instruction:value});
    }
  };
})();
