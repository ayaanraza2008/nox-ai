(() => {
  if (window.__noxLiveBrowserMounted) return;
  window.__noxLiveBrowserMounted = true;
  const style = document.createElement("style");
  style.textContent = `
    #noxBrowserOpen{border-color:#71eaff66;color:#9fefff}
    #noxBrowserModal{position:fixed;inset:0;z-index:120;background:#02060bdc;backdrop-filter:blur(12px);display:none;align-items:center;justify-content:center;padding:12px}
    #noxBrowserModal .nb-shell{width:min(1100px,100%);max-height:94vh;overflow:auto;border:1px solid #71eaff55;border-radius:15px;background:linear-gradient(145deg,#0b1725f7,#070c14f7);box-shadow:0 24px 100px #000b;color:#e7f4ff}
    #noxBrowserModal .nb-head{display:flex;align-items:center;gap:10px;padding:13px;border-bottom:1px solid #71eaff22;position:sticky;top:0;background:#0a1422f5;z-index:2}
    #noxBrowserModal .nb-head strong{font-size:12px;letter-spacing:.14em}
    #noxBrowserModal .nb-head small{display:block;font:9px monospace;color:#8aa0b4;margin-top:4px}
    #noxBrowserModal .nb-close{margin-left:auto}
    #noxBrowserModal .nb-body{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(260px,.8fr);gap:12px;padding:12px}
    #noxBrowserModal .nb-preview{border:1px solid #71eaff24;border-radius:10px;overflow:hidden;background:#050a10;min-height:180px}
    #noxBrowserModal .nb-previewbar{padding:8px 10px;font:10px monospace;color:#91a8ba;border-bottom:1px solid #71eaff20;overflow-wrap:anywhere}
    #noxBrowserModal .nb-shot{display:block;width:100%;min-height:180px;object-fit:contain;background:#060b12}
    #noxBrowserModal .nb-side{display:flex;flex-direction:column;gap:9px;min-width:0}
    #noxBrowserModal .nb-card{border:1px solid #71eaff20;border-radius:10px;padding:10px;background:#09131f}
    #noxBrowserModal .nb-label{font:9px monospace;color:#7deaff;letter-spacing:.1em;text-transform:uppercase;margin-bottom:7px}
    #noxBrowserModal .nb-muted{font-size:10px;line-height:1.5;color:#8da1b3}
    #noxBrowserModal .nb-field{width:100%;min-width:0;background:#060d17;border:1px solid #71eaff28;border-radius:8px;padding:10px;color:#e7f4ff;font:12px system-ui}
    #noxBrowserModal .nb-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}
    #noxBrowserModal .nb-btn{border:1px solid #71eaff36;background:#102033;color:#ccefff;border-radius:8px;padding:8px 10px;font-size:10px}
    #noxBrowserModal .nb-btn.main{background:linear-gradient(135deg,#17657b,#423b7a);color:#fff}
    #noxBrowserModal .nb-btn.warn{border-color:#ffca7255;color:#ffda91}
    #noxBrowserModal .nb-events{display:flex;flex-direction:column;gap:6px;max-height:230px;overflow:auto}
    #noxBrowserModal .nb-event{padding:7px 8px;border-radius:7px;background:#060e18;font-size:10px;line-height:1.45;overflow-wrap:anywhere;border-left:2px solid #54748d}
    #noxBrowserModal .nb-event[data-status="error"]{border-color:#ff7f9b}
    #noxBrowserModal .nb-event[data-status="success"]{border-color:#78f0c2}
    #noxBrowserModal .nb-event[data-status="attention"]{border-color:#ffd27b}
    #noxBrowserModal .nb-pending{padding:9px;border:1px solid #ffd27b66;background:#241d10;border-radius:8px;font-size:11px;line-height:1.5}
    #noxBrowserModal .nb-results{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px;line-height:1.55;max-height:260px;overflow:auto;color:#c7dce9}
    #noxBrowserModal .nb-download a{display:block;color:#83e9ff;font-size:10px;margin-top:6px;overflow-wrap:anywhere}
    @media(max-width:760px){#noxBrowserModal .nb-body{grid-template-columns:1fr;padding:8px}#noxBrowserModal .nb-shell{max-height:96vh}#noxBrowserModal .nb-shot{min-height:150px}}
  `;
  document.head.appendChild(style);
  const addButton = () => {
    const top = document.querySelector(".topright");
    if (!top || document.getElementById("noxBrowserOpen")) return false;
    const button = document.createElement("button");
    button.id = "noxBrowserOpen"; button.className = "secondary"; button.type = "button";
    button.textContent = "🌐 LIVE BROWSER"; button.addEventListener("click", openPanel); top.prepend(button);
    return true;
  };
  document.body.insertAdjacentHTML("beforeend", `
    <div id="noxBrowserModal" role="dialog" aria-modal="true" aria-label="NOX Live Browser">
      <section class="nb-shell">
        <header class="nb-head"><span style="font-size:20px">◉</span><div><strong>NOX LIVE BROWSER</strong><small id="nbRemoteLabel">REMOTE CHROMIUM · CONNECTING</small></div><button class="nb-btn nb-close" id="nbClose">Close ✕</button></header>
        <div class="nb-body">
          <div style="display:flex;flex-direction:column;gap:9px;min-width:0">
            <div class="nb-preview"><div class="nb-previewbar"><span id="nbPageTitle">No page open</span><br><span id="nbPageUrl">Remote browser is idle</span></div><img class="nb-shot" id="nbScreenshot" alt="Remote Chromium screenshot preview" src="" /></div>
            <div class="nb-card"><div class="nb-label">Task result</div><div class="nb-results" id="nbResult">Type or speak a browser command to begin. The preview is a screenshot of the actual remote browser.</div></div>
            <div class="nb-card"><div class="nb-label">Task history</div><div class="nb-events" id="nbEvents"><div class="nb-muted">No browser actions yet.</div></div></div>
          </div>
          <div class="nb-side">
            <div class="nb-card"><div class="nb-label">Command</div><textarea id="nbCommand" class="nb-field" rows="3" maxlength="2000" placeholder="Research quantum computing breakthroughs&#10;Open https://example.com&#10;Search the web for ...&#10;Inspect this page"></textarea><div class="nb-actions"><button class="nb-btn main" id="nbRun">Run command</button><button class="nb-btn" id="nbSpeak">🎙 Speak</button><button class="nb-btn warn" id="nbStop">Stop session</button></div><div class="nb-muted" style="margin-top:8px">Try: research [topic] to read up to three public sources and save a Markdown report; open a URL, search, inspect, click a visible label, fill a labelled field, scroll, or go back. High-impact actions wait for your approval.</div></div>
            <div class="nb-card"><div class="nb-label">Execution status</div><div id="nbStatus" style="font-size:12px">Idle</div><div class="nb-muted" id="nbTask" style="margin-top:5px">No task running</div><div class="nb-actions"><button class="nb-btn" id="nbRefresh">Refresh preview</button><button class="nb-btn" id="nbBack">← Back</button><button class="nb-btn" id="nbForward">Forward →</button></div></div>
            <div class="nb-card" id="nbApprovalCard" hidden><div class="nb-label">Your approval required</div><div class="nb-pending" id="nbPendingText">A consequential action is waiting.</div><div class="nb-actions"><button class="nb-btn main" id="nbApprove">Approve action</button><button class="nb-btn warn" id="nbDecline">Decline</button></div><div class="nb-muted" style="margin-top:7px">Review the target and effect before approving. Silence never counts as consent.</div></div>
            <div class="nb-card"><div class="nb-label">Downloads</div><div id="nbDownloads" class="nb-download nb-muted">No downloaded files.</div></div>
            <div class="nb-muted">Remote session: the page is running on NOX's server. This panel shows a screenshot preview, not an interactive local browser. Authentication/CAPTCHA may require a separately paired interactive browser companion.</div>
          </div>
        </div>
      </section>
    </div>`);
  const $ = id => document.getElementById(id);
  const modal = $("noxBrowserModal");
  let poller = null, busy = false;
  function showResult(text) { $("nbResult").textContent = text || ""; }
  async function api(path, options={}) {
    const response = await fetch(path, {credentials:"same-origin", ...options, headers:{"Content-Type":"application/json", ...(options.headers||{})}});
    const type = response.headers.get("content-type") || "";
    const data = type.includes("application/json") ? await response.json() : null;
    if (!response.ok) throw new Error(data?.detail || data?.message || ("Request failed (" + response.status + ")"));
    return data;
  }
  async function refreshState(withShot=true) {
    try {
      const s = await api("/api/browser/state");
      $("nbRemoteLabel").textContent = s.active ? "REMOTE CHROMIUM · SESSION ACTIVE" : (s.available ? "REMOTE CHROMIUM · READY" : "PLAYWRIGHT NOT INSTALLED");
      $("nbStatus").textContent = (s.status || "idle").replaceAll("_"," ").toUpperCase();
      $("nbTask").textContent = s.task || "No task running";
      $("nbPageTitle").textContent = s.title || "No page open";
      $("nbPageUrl").textContent = s.url || "Remote browser is idle";
      $("nbApprovalCard").hidden = !s.pending_confirmation;
      if (s.pending_confirmation) $("nbPendingText").textContent = "NOX paused before a consequential action. Inspect the page and choose Approve or Decline.";
      $("nbEvents").replaceChildren();
      (s.events || []).slice().reverse().forEach(e => {
        const node = document.createElement("div"); node.className="nb-event"; node.dataset.status=e.status||"info";
        node.textContent = new Date((e.at||0)*1000).toLocaleTimeString()+" · "+e.message; $("nbEvents").appendChild(node);
      });
      if (!(s.events||[]).length) $("nbEvents").textContent = "No browser actions yet.";
      $("nbDownloads").replaceChildren();
      if (!(s.downloads||[]).length) $("nbDownloads").textContent = "No downloaded files.";
      (s.downloads||[]).forEach((d,i) => {
        const a=document.createElement("a"); a.textContent=d.name+(d.saved?" · saved on remote server":" · detected");
        if(d.saved) { a.href="/api/browser/download/"+(d.index ?? i); a.target="_blank"; a.rel="noopener"; } else a.href="#";
        $("nbDownloads").appendChild(a);
      });
      if(withShot && s.active) {
        const response = await fetch("/api/browser/screenshot?t="+Date.now(), {credentials:"same-origin"});
        if(response.ok) {
          const blob=await response.blob(), next=URL.createObjectURL(blob), old=$("nbScreenshot").dataset.objectUrl;
          $("nbScreenshot").src=next; $("nbScreenshot").dataset.objectUrl=next; if(old) URL.revokeObjectURL(old);
        }
      }
      return s;
    } catch (err) { $("nbStatus").textContent="ERROR"; showResult(err.message); }
  }
  async function openPanel() {
    modal.style.display="flex"; try { await api("/api/session"); } catch {}
    await refreshState(true); if(poller) clearInterval(poller);
    poller=setInterval(()=>{if(modal.style.display==="flex"&&!busy)refreshState(true)},4000);
  }
  function closePanel(){modal.style.display="none";if(poller)clearInterval(poller);poller=null}
  async function run(command) {
    command=(command||$("nbCommand").value).trim(); if(!command||busy)return;
    busy=true; $("nbRun").disabled=true; showResult("NOX is operating the remote browser…");
    try {
      const data=await api("/api/browser/command",{method:"POST",body:JSON.stringify({command,language:document.querySelector("#language")?.value||"auto"})});
      showResult(data.result||"Command finished."); await refreshState(true);
    } catch(err){showResult(err.message);await refreshState(false)}
    finally{busy=false;$("nbRun").disabled=false}
  }
  async function confirmAction(approved){
    try{const data=await api("/api/browser/confirm",{method:"POST",body:JSON.stringify({approved})});showResult(data.result||"Updated.");await refreshState(true)}
    catch(err){showResult(err.message)}
  }
  $("nbClose").onclick=closePanel; modal.addEventListener("click",e=>{if(e.target===modal)closePanel()});
  $("nbRun").onclick=()=>run(); $("nbCommand").addEventListener("keydown",e=>{if(e.key==="Enter"&&(e.ctrlKey||e.metaKey)){e.preventDefault();run()}});
  $("nbRefresh").onclick=()=>refreshState(true); $("nbBack").onclick=()=>run("go back a page"); $("nbForward").onclick=()=>run("go forward a page");
  $("nbStop").onclick=async()=>{try{const r=await api("/api/browser/stop",{method:"POST",body:"{}"});showResult(r.message||"Stopped.");await refreshState(false)}catch(e){showResult(e.message)}};
  $("nbApprove").onclick=()=>confirmAction(true); $("nbDecline").onclick=()=>confirmAction(false);
  $("nbSpeak").onclick=()=>{
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR){showResult("Voice input is not supported in this browser. Type your command instead.");return}
    const rec=new SR(); rec.lang=({"hi":"hi-IN","ur":"ur-PK","en":"en-IN","hinglish":"en-IN","auto":"en-IN"})[document.querySelector("#language")?.value||"auto"]||"en-IN";
    rec.interimResults=false;rec.maxAlternatives=1;
    rec.onresult=e=>{$("nbCommand").value=e.results[0][0].transcript;run($("nbCommand").value)};
    rec.onerror=()=>showResult("Voice input failed or permission was denied. Type your command instead.");
    try{rec.start();showResult("Listening for a browser command…")}catch{showResult("Voice input could not start. Type your command instead.")}
  };
  const observer=new MutationObserver(()=>addButton()); observer.observe(document.body,{childList:true,subtree:true});
  if(!addButton()) setTimeout(addButton,500);
})();