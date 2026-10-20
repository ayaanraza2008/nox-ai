(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  async function api(path, options = {}) {
    const res = await fetch(path, {credentials:"same-origin", ...options, headers:{"Content-Type":"application/json", ...(options.headers||{})}});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || ("Request failed: HTTP " + res.status));
    return data;
  }
  const root = document.createElement("section");
  root.id = "noxCommunicationsPanel";
  root.className = "panel";
  root.style.cssText = "position:fixed;z-index:70;right:16px;top:78px;width:min(480px,calc(100vw - 24px));max-height:calc(100vh - 96px);overflow:auto;box-shadow:0 20px 80px #000b;display:none";
  root.innerHTML = `
    <div class="panelhead"><div><div class="ptitle">CONNECTED APPS / COMMUNICATIONS</div><div class="pmeta">AUTHORIZED PROVIDERS ONLY</div></div><button class="iconbtn" id="noxCommClose" aria-label="Close">✕</button></div>
    <div class="panelbody">
      <div id="noxCommNotice" class="footnote" role="status">Checking connected providers…</div>
      <div id="noxCommProviders" style="display:grid;gap:7px;margin:10px 0"></div>
      <div class="divider"></div>
      <div class="ptitle" style="margin-bottom:8px">GMAIL COMPOSE</div>
      <label class="brain-label" for="noxCommTo">To</label><input id="noxCommTo" class="field" type="email" autocomplete="email" placeholder="recipient@example.com">
      <label class="brain-label" for="noxCommCc">CC (optional)</label><input id="noxCommCc" class="field" type="email" placeholder="cc@example.com">
      <label class="brain-label" for="noxCommSubject">Subject</label><input id="noxCommSubject" class="field" maxlength="998" placeholder="Email subject">
      <label class="brain-label" for="noxCommBody">Message</label><textarea id="noxCommBody" class="field" rows="5" maxlength="20000" placeholder="Write the message. Review before sending."></textarea>
      <div class="footnote" style="margin:8px 0">Send requires an explicit review/confirmation. A successful Gmail send request is not proof of delivery. Attachments are not yet supported in this release.</div>
      <div class="brain-form-row"><button class="secondary" id="noxCommDraft">Save draft</button><button class="primary" id="noxCommSend">Review &amp; send</button></div>
      <div class="divider"></div>
      <div class="ptitle">SEARCH INBOX</div>
      <div class="brain-form-row"><input id="noxCommSearch" class="field" placeholder="from:, subject:, newer_than:7d"><button class="secondary" id="noxCommSearchBtn">Search</button></div>
      <div id="noxCommResults" style="display:grid;gap:7px;margin-top:8px"></div>
      <div class="divider"></div>
      <div class="row" style="display:flex;gap:8px;align-items:center;justify-content:space-between"><button class="secondary" id="noxCommAudit">Task audit</button><button class="secondary" id="noxCommClearAudit">Clear audit</button></div>
      <div id="noxCommAuditResults" class="footnote" style="margin-top:8px"></div>
    </div>`;
  document.body.appendChild(root);
  const toggle = document.createElement("button");
  toggle.type = "button"; toggle.id = "noxConnectedAppsToggle"; toggle.className = "primary";
  toggle.textContent = "CONNECTED APPS";
  toggle.style.cssText = "position:fixed;right:16px;bottom:18px;z-index:65;box-shadow:0 5px 28px #0008";
  toggle.setAttribute("aria-expanded","false");
  document.body.appendChild(toggle);
  function openPanel() { root.style.display="block"; toggle.setAttribute("aria-expanded","true"); refresh(); }
  function closePanel() { root.style.display="none"; toggle.setAttribute("aria-expanded","false"); }
  toggle.addEventListener("click", () => root.style.display === "block" ? closePanel() : openPanel());
  $("noxCommClose").onclick = closePanel;
  async function refresh() {
    try {
      const d = await api("/api/connected/status");
      $("noxCommProviders").innerHTML = d.apps.map(p => `<div class="taskrow"><div class="taskrowhead"><strong>${esc(p.name)}</strong><span class="tag ${p.connected?"done":"pending"}">${p.connected?"CONNECTED":"NOT CONNECTED"}</span></div><p>${esc(p.account || p.setup || "No account")}</p><div class="footnote">${esc((p.capabilities||[]).join(" · ") || "No automated actions configured")}</div><div class="taskactions" style="margin-top:7px">${p.provider==="gmail" ? (p.connected?'<button class="secondary" data-disconnect-gmail>Disconnect</button>':'<button class="primary" data-connect-gmail>Connect Gmail</button>') : ""}</div></div>`).join("");
      $("noxCommNotice").textContent = "Provider status loaded from the backend. Only Gmail is implemented in this build; other providers are not connected.";
      root.querySelectorAll("[data-connect-gmail]").forEach(b => b.onclick = connectGmail);
      root.querySelectorAll("[data-disconnect-gmail]").forEach(b => b.onclick = disconnectGmail);
    } catch (e) { $("noxCommNotice").textContent = e.message; }
  }
  async function connectGmail() {
    try {
      $("noxCommNotice").textContent = "Preparing Google OAuth…";
      const d = await api("/api/connected/gmail/connect");
      if (!d.authorization_url || !d.authorization_url.startsWith("https://accounts.google.com/")) throw new Error("Google returned an invalid authorization URL.");
      window.location.assign(d.authorization_url);
    } catch (e) { $("noxCommNotice").textContent = e.message; }
  }
  async function disconnectGmail() {
    if (!window.confirm("Disconnect Gmail from NOX on this account?")) return;
    try { await api("/api/connected/gmail/disconnect",{method:"POST",body:"{}"}); $("noxCommNotice").textContent="Gmail disconnected."; refresh(); }
    catch(e) { $("noxCommNotice").textContent=e.message; }
  }
  function emailPayload() { return {to:$("noxCommTo").value.trim(),cc:$("noxCommCc").value.trim(),subject:$("noxCommSubject").value.trim(),body:$("noxCommBody").value}; }
  $("noxCommDraft").onclick = async () => {
    try {
      const d = await api("/api/connected/gmail/drafts",{method:"POST",body:JSON.stringify(emailPayload())});
      $("noxCommNotice").textContent = "Draft saved in Gmail. Draft ID: " + (d.draft_id || "returned by provider");
    } catch(e) { $("noxCommNotice").textContent=e.message; }
  };
  $("noxCommSend").onclick = async () => {
    const p = emailPayload();
    if (!p.to || !p.subject || !p.body.trim()) { $("noxCommNotice").textContent="Enter the recipient, subject, and message first."; return; }
    const summary = "Send this email through the connected Gmail account?\n\nTo: "+p.to+"\nCC: "+(p.cc||"—")+"\nSubject: "+p.subject+"\n\n"+p.body;
    if (!window.confirm(summary)) return;
    try {
      const d = await api("/api/connected/gmail/send",{method:"POST",body:JSON.stringify({...p,confirmed:true})});
      $("noxCommNotice").textContent = "Provider result: "+d.status+". Delivery status: "+d.delivery_status+". "+d.message;
    } catch(e) { $("noxCommNotice").textContent=e.message; }
  };
  $("noxCommSearchBtn").onclick = async () => {
    const q = $("noxCommSearch").value.trim(); if (!q) return;
    $("noxCommResults").textContent="Searching Gmail…";
    try {
      const d=await api("/api/connected/gmail/search",{method:"POST",body:JSON.stringify({query:q,limit:10})});
      $("noxCommResults").innerHTML=d.messages.map(m=>`<div class="taskrow"><div class="taskrowhead"><strong>${esc(m.subject)}</strong><span class="tiny">${esc(m.date)}</span></div><p>From: ${esc(m.from)}<br>To: ${esc(m.to)}</p><div class="footnote">${esc(m.snippet)}</div><button class="secondary" data-use-sender="${esc(m.from)}" data-subject="${esc(/^re:/i.test(m.subject)?"":"Re: ")+esc(m.subject)}">Use sender</button></div>`).join("") || "No messages matched.";
      root.querySelectorAll("[data-use-sender]").forEach(b=>b.onclick=()=>{$("noxCommTo").value=(b.dataset.useSender.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i)||[])[0]||"";$("noxCommSubject").value=b.dataset.subject;$("noxCommBody").value="";$("noxCommNotice").textContent="A new email draft is being prepared; this is not a reply in the original thread. Add the message and save/send after review.";});
    } catch(e) {$("noxCommResults").textContent=e.message;}
  };
  $("noxCommAudit").onclick = async () => {
    try { const d=await api("/api/connected/audit"); $("noxCommAuditResults").innerHTML=d.events.map(e=>`<div class="taskrow"><strong>${esc(e.action)}</strong> — ${esc(e.status)}<br><span class="tiny">${esc(e.created_at)}</span><div>${esc(e.destination||"")}</div><div>${esc(e.detail||"")}</div></div>`).join("")||"No events yet."; }
    catch(e){$("noxCommAuditResults").textContent=e.message;}
  };
  $("noxCommClearAudit").onclick = async () => {
    if (!window.confirm("Delete this account's communication audit history?")) return;
    try {await api("/api/connected/audit",{method:"DELETE"});$("noxCommAuditResults").textContent="Audit history deleted."; }
    catch(e){$("noxCommAuditResults").textContent=e.message;}
  };
  const mailIntent = /\b(?:send|draft|write|compose|reply|forward|search|find|read|check|open|email|e-mail|gmail|inbox)\b.{0,100}\b(?:email|gmail|inbox|mail|message|recipient|attachment|file|report|to|rahul)\b/i;
  const unsupportedIntent = /\b(?:whatsapp|linkedin|outlook|sms|text message|phone call|call this contact|calendar invite)\b.{0,100}\b(?:send|message|call|invite|schedule|text|contact|reply|open)\b/i;
  window.NOXCommunications = {
    shouldHandle(text) { return mailIntent.test(String(text||"")) || unsupportedIntent.test(String(text||"")); },
    async handleCommand(text) {
      openPanel();
      const value=String(text||"").trim();
      const email=(value.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i)||[])[0];
      if(email) $("noxCommTo").value=email;
      const subject=(value.match(/\bsubject\s*[:=]\s*["']?(.+?)["']?(?:\s+body\s*[:=]|$)/i)||[])[1];
      const body=(value.match(/\b(?:body|message)\s*[:=]\s*["']?([\s\S]+)$/i)||[])[1];
      if(subject) $("noxCommSubject").value=subject.trim();
      if(body) $("noxCommBody").value=body.trim().replace(/["']$/,"");
      $("noxCommNotice").textContent = email && subject && body
        ? "Command details filled in. Review the recipient and content, then choose Save draft or Review & send."
        : "I opened the communication workspace. Please provide the exact recipient, subject, and message. NOX will not send an ambiguous command.";
    },
    open: openPanel,
    refresh
  };
  if (new URLSearchParams(location.search).get("connected")==="gmail") { openPanel(); $("noxCommNotice").textContent="Gmail OAuth returned successfully. Refresh provider status to verify the connection."; }
  if (new URLSearchParams(location.search).has("error")) { openPanel(); $("noxCommNotice").textContent="Connection callback reported an error. Check the setup and try again."; }
})();