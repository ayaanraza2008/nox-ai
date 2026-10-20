(() => {
  "use strict";
  if (window.__NOXGitHubBridgeLoaded) return;
  window.__NOXGitHubBridgeLoaded = true;
  const style = document.createElement("style");
  style.textContent = `
    #noxGithubOpen{position:fixed;right:18px;bottom:18px;z-index:99980;border:1px solid #70dfea66;background:linear-gradient(135deg,#102536f2,#211b40f2);color:#dffaff;border-radius:10px;padding:11px 13px;font:10px ui-monospace,monospace;letter-spacing:.08em;box-shadow:0 0 24px #42d9ff15}
    #noxGithubLayer{display:none;position:fixed;inset:0;z-index:99990;background:#02060be8;backdrop-filter:blur(12px);padding:2vh 2vw;color:#e6f5ff}
    #noxGithubLayer.open{display:grid;place-items:center}
    .ng-shell{width:min(1280px,100%);height:min(94vh,900px);display:flex;flex-direction:column;border:1px solid #67dfea40;border-radius:14px;overflow:hidden;background:#08111df7;box-shadow:0 20px 90px #000a;font:12px/1.5 system-ui,sans-serif}
    .ng-head,.ng-toolbar,.ng-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 13px;border-bottom:1px solid #74d8e31e}
    .ng-head b{letter-spacing:.15em;font-size:12px}.ng-head small,.ng-help{color:#86a2b7;font-size:10px}.ng-spacer{flex:1}
    .ng-btn,.ng-input,.ng-area{border:1px solid #74d8e32d;background:#0a1926;color:#dff7ff;border-radius:7px;padding:8px 10px;font:11px ui-monospace,monospace}
    .ng-btn{cursor:pointer}.ng-btn:hover{border-color:#71eaff99}.ng-btn.primary{background:#153747;border-color:#65dce777}.ng-btn:disabled{opacity:.4;cursor:not-allowed}
    .ng-input{min-width:0}.ng-main{display:grid;grid-template-columns:250px minmax(0,1fr);min-height:0;flex:1}
    .ng-files{overflow:auto;padding:10px;border-right:1px solid #74d8e31e}.ng-editor{display:flex;flex-direction:column;gap:8px;padding:12px;min-width:0;min-height:0;overflow:auto}
    .ng-label{font:9px ui-monospace,monospace;letter-spacing:.12em;color:#76e8f7;text-transform:uppercase;display:block;margin-bottom:5px}
    .ng-entry{display:block;width:100%;text-align:left;margin:4px 0;padding:8px;border:1px solid #74d8e31b;background:#0a1723;color:#b9d8e8;border-radius:6px;overflow-wrap:anywhere;cursor:pointer;font:10px ui-monospace,monospace}
    .ng-entry:hover{border-color:#71eaff88}.ng-area{width:100%;resize:vertical;min-height:160px;white-space:pre;tab-size:2}.ng-area.source{height:30vh}.ng-area.diff{height:22vh;color:#b6f3e5;background:#030a12}
    .ng-field{min-width:0}.ng-check{display:flex;align-items:center;gap:7px;font-size:11px;color:#ffd68a}.ng-status{font:10px ui-monospace,monospace;color:#9ec3d7;overflow-wrap:anywhere}
    @media(max-width:650px){#noxGithubOpen{right:10px;bottom:10px}.ng-main{grid-template-columns:1fr;grid-template-rows:minmax(110px,25%) 1fr}.ng-files{border-right:0;border-bottom:1px solid #74d8e31e}.ng-area.source{height:180px}.ng-shell{height:96vh}.ng-head small{display:none}}
  `;
  document.head.append(style);
  const open = document.createElement("button");
  open.id = "noxGithubOpen"; open.type = "button"; open.textContent = "⌘ GITHUB BRIDGE";
  document.body.append(open);
  const layer = document.createElement("div"); layer.id = "noxGithubLayer";
  layer.innerHTML = `
    <section class="ng-shell" role="dialog" aria-modal="true" aria-label="NOX GitHub Bridge">
      <header class="ng-head"><span>⌘</span><div><b>GITHUB BRIDGE</b><br><small>READ · REVIEW DIFF · APPROVE · DRAFT PR</small></div><span class="ng-spacer"></span><button class="ng-btn" id="ngClose">CLOSE ✕</button></header>
      <div class="ng-toolbar"><button class="ng-btn" id="ngUp">↑ UP</button><button class="ng-btn" id="ngRefresh">REFRESH TREE</button><span class="ng-status" id="ngRepo">Checking server configuration…</span><span class="ng-spacer"></span><span class="ng-status" id="ngStatus" role="status">Loading repository…</span></div>
      <div class="ng-main"><aside class="ng-files"><label class="ng-label">Repository files</label><div id="ngTree"></div><p class="ng-help">Hidden files are omitted. Click a file to load its UTF-8 text.</p></aside>
      <main class="ng-editor">
        <div class="ng-field"><label class="ng-label" for="ngPath">Selected file path</label><input class="ng-input" id="ngPath" style="width:100%" readonly placeholder="Choose a file from the repository"></div>
        <div class="ng-field"><label class="ng-label" for="ngSource">Current GitHub version (read-only)</label><textarea class="ng-area source" id="ngSource" readonly spellcheck="false" placeholder="Select a file from the tree."></textarea></div>
        <div class="ng-field"><label class="ng-label" for="ngProposed">Proposed replacement</label><textarea class="ng-area source" id="ngProposed" spellcheck="false" placeholder="Edit the selected file here. Max 50,000 characters."></textarea></div>
        <div class="ng-field"><label class="ng-label" for="ngTitle">Pull request title</label><input class="ng-input" id="ngTitle" maxlength="120" style="width:100%" value="NOX proposed code improvement"></div>
        <div class="ng-actions"><button class="ng-btn primary" id="ngPreview">1 · PREVIEW DIFF</button><button class="ng-btn primary" id="ngPublish" disabled>2 · CREATE DRAFT PR</button><label class="ng-check"><input type="checkbox" id="ngConfirm"> I reviewed this diff and approve creating a draft PR</label></div>
        <div class="ng-field"><label class="ng-label">Diff preview</label><textarea class="ng-area diff" id="ngDiff" readonly placeholder="Preview the change before approval."></textarea></div>
        <p class="ng-help">Safety: preview is read-only. Publishing rechecks the original file SHA, writes only to a new NOX proposal branch, and opens a draft PR. It never writes to the base branch, merges, or deploys. Only edit files you are authorized to change.</p>
      </main></div>
    </section>`;
  document.body.append(layer);
  const $ = id => document.getElementById(id);
  let folder = "", selected = null, previewed = false, busy = false;
  const status = value => { $("ngStatus").textContent = value; };
  async function api(url, options = {}) {
    const response = await fetch(url, {credentials:"same-origin", cache:"no-store", ...options,
      headers: options.body ? {"Content-Type":"application/json", ...(options.headers||{})} : (options.headers||{})});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(data.detail || "GitHub request failed (HTTP " + response.status + ")");
    return data;
  }
  function setBusy(value) {
    busy = value;
    ["ngUp","ngRefresh","ngPreview","ngPublish"].forEach(id => $(id).disabled = value || (id==="ngPublish" && !previewed));
  }
  async function run(action) {
    if (busy) return;
    setBusy(true);
    try { await action(); }
    catch (e) { status(e.message || "Request failed."); }
    finally { setBusy(false); }
  }
  function invalidatePreview() {
    previewed = false; $("ngPublish").disabled = true; $("ngConfirm").checked = false;
    $("ngDiff").value = ""; 
  }
  async function loadStatus() {
    const data = await api("/api/github/status");
    $("ngRepo").textContent = data.configured ? data.repository + " · base: " + data.base_branch : "Setup required: server GitHub secrets";
    if (!data.configured) status("Set GITHUB_TOKEN and NOX_GITHUB_REPOSITORY in Render.");
  }
  async function loadTree(path = folder) {
    folder = path;
    const data = await api("/api/github/tree" + (path ? "?path=" + encodeURIComponent(path) : ""));
    const root = $("ngTree"); root.replaceChildren();
    if (!data.entries.length) { const note=document.createElement("p"); note.className="ng-help"; note.textContent="No visible files in this folder."; root.append(note); return; }
    data.entries.forEach(entry => {
      const button=document.createElement("button"); button.type="button"; button.className="ng-entry";
      button.textContent=(entry.type==="dir"?"▸ ":"▤ ")+entry.name;
      button.addEventListener("click",()=>run(async()=>{ if(entry.type==="dir") await loadTree(entry.path); else await loadFile(entry.path); }));
      root.append(button);
    });
    status("Showing " + (path || "/") + " · " + data.entries.length + " entries");
  }
  async function loadFile(path) {
    const data=await api("/api/github/file?path="+encodeURIComponent(path));
    selected={path:data.path,sha:data.sha};
    $("ngPath").value=data.path; $("ngSource").value=data.content; $("ngProposed").value=data.content;
    invalidatePreview(); status("Loaded " + data.path + " · SHA checked on preview/publish");
  }
  async function preview() {
    if(!selected) throw Error("Select a file first.");
    const content=$("ngProposed").value;
    if(content.length>50000) throw Error("File exceeds 50,000 characters.");
    const data=await api("/api/github/preview",{method:"POST",body:JSON.stringify({changes:[{path:selected.path,content,expected_sha:selected.sha}]})});
    $("ngDiff").value=data.changes[0].diff || "(No visible diff)";
    previewed=true; $("ngPublish").disabled=false; $("ngConfirm").checked=false;
    status("Diff ready · " + data.changes[0].added + " additions / " + data.changes[0].removed + " removals");
  }
  async function publish() {
    if(!previewed) throw Error("Preview the diff first.");
    if(!$("ngConfirm").checked) throw Error("Tick the approval checkbox after reviewing the diff.");
    if(!$("ngTitle").value.trim() || $("ngTitle").value.trim().length<5) throw Error("Enter a descriptive PR title.");
    if(!window.confirm("Create a DRAFT pull request on a new branch? Nothing will be merged or deployed.")) return;
    const data=await api("/api/github/publish",{method:"POST",body:JSON.stringify({
      title:$("ngTitle").value.trim(), body:"Proposed and reviewed in NOX GitHub Bridge.",
      confirmed:true, changes:[{path:selected.path,content:$("ngProposed").value,expected_sha:selected.sha}]
    })});
    status("Draft PR #" + data.number + " created · " + data.branch);
    $("ngDiff").value += "\n\n" + data.note + "\n" + data.pull_request;
    previewed=false; $("ngPublish").disabled=true;
    if(data.pull_request) { const link=document.createElement("a");link.href=data.pull_request;link.target="_blank";link.rel="noopener noreferrer";link.textContent="Open draft PR #" + data.number;link.style.cssText="color:#71eaff;margin:4px 0;display:block";$("ngDiff").after(link); }
  }
  open.addEventListener("click",()=>{layer.classList.add("open");run(async()=>{await loadStatus();await loadTree("");});});
  $("ngClose").addEventListener("click",()=>layer.classList.remove("open"));
  layer.addEventListener("click",e=>{if(e.target===layer)layer.classList.remove("open");});
  document.addEventListener("keydown",e=>{if(e.key==="Escape")layer.classList.remove("open");});
  $("ngUp").addEventListener("click",()=>run(async()=>{folder=folder.split("/").slice(0,-1).join("/");await loadTree(folder);}));
  $("ngRefresh").addEventListener("click",()=>run(async()=>{await loadStatus();await loadTree(folder);}));
  $("ngPreview").addEventListener("click",()=>run(preview));
  $("ngPublish").addEventListener("click",()=>run(publish));
  $("ngProposed").addEventListener("input",invalidatePreview);
  $("ngConfirm").addEventListener("change",()=>{if(previewed)$("ngPublish").disabled=busy||!$("ngConfirm").checked;});
  window.NOXGitHubBridge={open:()=>open.click()};
})();