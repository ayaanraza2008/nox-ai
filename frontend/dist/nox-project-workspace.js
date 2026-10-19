(() => {
  "use strict";
  const style = document.createElement("style");
  style.textContent = `
  #noxProjectOpen{position:fixed;right:22px;bottom:82px;z-index:1190;border:1px solid #78e4d477;border-radius:12px;padding:11px 14px;background:linear-gradient(135deg,#123b42,#1b2446);color:#d8fff6;font:700 10px system-ui,sans-serif;letter-spacing:.12em;box-shadow:0 8px 30px #0008;cursor:pointer}
  #noxProjectLayer{position:fixed;inset:0;z-index:1300;display:none;place-items:center;padding:12px;background:#020611e8;backdrop-filter:blur(18px);color:#e8f6ff;font:13px system-ui,sans-serif}
  #noxProjectLayer.open{display:grid}.np-shell{width:min(1180px,100%);height:min(94vh,900px);display:flex;flex-direction:column;overflow:hidden;border:1px solid #73e5d53b;border-radius:18px;background:radial-gradient(ellipse at 40% 0%,#172e42,#070d18 65%);box-shadow:0 20px 90px #000a}
  .np-head{display:flex;align-items:center;gap:10px;padding:13px 16px;border-bottom:1px solid #80e9df22;background:#07131eea}.np-head b{letter-spacing:.14em}.np-head small{color:#8daabd;font:9px monospace}.np-spacer{flex:1}.np-btn{border:1px solid #80d9db38;background:#0c1c29;color:#e2f9fa;border-radius:8px;padding:9px 11px;font-size:10px;cursor:pointer}.np-btn.primary{background:linear-gradient(135deg,#176b72,#464185);border-color:#7ee9dc75}.np-btn.approve{border-color:#66d5a577;color:#a9ffd7}.np-btn.reject{border-color:#f68a9b77;color:#ffc1ca}.np-btn:disabled{opacity:.4;cursor:not-allowed}
  .np-toolbar{display:flex;gap:8px;align-items:center;padding:10px 14px;border-bottom:1px solid #8fd6e315;flex-wrap:wrap}.np-input,.np-select,.np-area{box-sizing:border-box;width:100%;min-width:0;background:#050e18;color:#e8f6ff;border:1px solid #80d9db30;border-radius:8px;padding:10px;outline:none;font:12px ui-monospace,monospace}.np-input:focus,.np-select:focus,.np-area:focus{border-color:#69e5d4}.np-project-name{max-width:260px}.np-work{min-height:0;flex:1;display:grid;grid-template-columns:210px minmax(0,1fr) 270px}.np-files,.np-editor,.np-review{min-width:0;min-height:0;padding:13px;overflow:auto}.np-files{border-right:1px solid #80d9db1d;background:#06111b88}.np-review{border-left:1px solid #80d9db1d;background:#06111b88}.np-label{display:block;margin:0 0 6px;color:#85a7bb;font:9px monospace;letter-spacing:.12em;text-transform:uppercase}.np-field{margin-bottom:12px}.np-area{resize:vertical;line-height:1.5;min-height:180px}.np-area.source{height:clamp(200px,36vh,380px)}.np-area.proposed{height:170px}.np-file-list{display:flex;flex-direction:column;gap:5px;margin-top:10px}.np-file{width:100%;text-align:left;overflow-wrap:anywhere;border:1px solid transparent;border-radius:7px;background:#0a1925;color:#a9c4d4;padding:8px;font:10px ui-monospace,monospace;cursor:pointer}.np-file.active{border-color:#65dcd47a;background:#123139;color:#e0fffa}.np-help{font-size:10px;line-height:1.5;color:#7896aa}.np-status{font-size:10px;line-height:1.5;color:#a8c6d6;overflow-wrap:anywhere}.np-output{white-space:pre-wrap;overflow-wrap:anywhere;max-height:240px;overflow:auto;background:#030912;border:1px solid #7cc9e21d;border-radius:8px;padding:10px;color:#a8dfe5;font:10px/1.5 ui-monospace,monospace;min-height:44px}.np-actions{display:flex;gap:6px;flex-wrap:wrap}.np-review-item{width:100%;text-align:left;display:block;margin:6px 0;padding:8px;border:1px solid #6ddbd52b;border-radius:8px;background:#091722;color:#b7d6e1;cursor:pointer;font-size:10px;overflow-wrap:anywhere}.np-review-item.active{border-color:#83d7ce;background:#112d34}.np-review-item small{display:block;margin-top:4px;color:#7e9bac;font:9px monospace}.np-pill{display:inline-block;border:1px solid #72d8cc44;border-radius:99px;padding:4px 7px;color:#91e9d9;font:9px monospace}
  @media(max-width:900px){.np-work{grid-template-columns:150px minmax(0,1fr)}.np-review{grid-column:1/-1;border-left:0;border-top:1px solid #80d9db1d;max-height:260px}.np-area.source{height:230px}}
  @media(max-width:560px){#noxProjectOpen{right:12px;bottom:76px;padding:9px}.np-shell{height:96vh}.np-toolbar{align-items:stretch}.np-project-name{max-width:none}.np-work{grid-template-columns:1fr;overflow:auto}.np-files{border-right:0;border-bottom:1px solid #80d9db1d;max-height:145px}.np-editor,.np-review{overflow:visible}.np-review{max-height:none}.np-area.source{height:200px}.np-head small{display:none}}
  @media(prefers-reduced-motion:reduce){#noxProjectLayer{backdrop-filter:none}}
  `;
  document.head.append(style);
  const open = document.createElement("button");
  open.id = "noxProjectOpen";
  open.type = "button";
  open.textContent = "▦ PROJECT WORKSPACE";
  document.body.append(open);
  const layer = document.createElement("div");
  layer.id = "noxProjectLayer";
  layer.innerHTML = `
    <section class="np-shell" role="dialog" aria-modal="true" aria-label="NOX Project Workspace">
      <header class="np-head"><span class="np-pill">NOX / LAB 02</span><div><b>PROJECT WORKSPACE</b><br><small>REVIEW · DIFF · APPROVE · VALIDATE</small></div><span class="np-spacer"></span><button class="np-btn" id="npClose">CLOSE ✕</button></header>
      <div class="np-toolbar"><select id="npProject" class="np-select" style="max-width:260px"><option value="">No project loaded</option></select><input id="npProjectName" class="np-input np-project-name" maxlength="80" placeholder="New project name"><button class="np-btn primary" id="npCreate">+ CREATE PROJECT</button><span class="np-spacer"></span><span class="np-status" id="npStatus" role="status">Create a project or load an existing one.</span></div>
      <div class="np-work">
        <aside class="np-files"><label class="np-label" for="npPath">Workspace file path</label><input id="npPath" class="np-input" maxlength="240" placeholder="src/main.py"><p class="np-help">Relative paths only. Files you paste here are saved to NOX's workspace snapshot, not your computer or GitHub.</p><div class="np-actions"><button class="np-btn" id="npNewFile">NEW FILE</button><button class="np-btn" id="npRefresh">REFRESH</button></div><label class="np-label" style="margin-top:18px">Saved files</label><div id="npFiles" class="np-file-list"></div></aside>
        <main class="np-editor">
          <div class="np-field"><label class="np-label" for="npSource">Current workspace snapshot</label><textarea id="npSource" class="np-area source" maxlength="50000" spellcheck="false" placeholder="Paste the file's current contents here, then save it to the workspace."></textarea><div class="np-actions" style="margin-top:7px"><button class="np-btn primary" id="npSave">SAVE SNAPSHOT</button><button class="np-btn" id="npValidate">VALIDATE FILE</button></div></div>
          <div class="np-field"><label class="np-label" for="npSummary">Patch summary</label><input id="npSummary" class="np-input" maxlength="240" placeholder="Describe the intended change"></div>
          <div class="np-field"><label class="np-label" for="npProposed">Proposed replacement content</label><textarea id="npProposed" class="np-area proposed" maxlength="50000" spellcheck="false" placeholder="Paste or edit the proposed full file contents here."></textarea><div class="np-actions" style="margin-top:7px"><button class="np-btn primary" id="npPropose">GENERATE DIFF / STAGE PATCH</button></div></div>
          <div class="np-field"><label class="np-label">Validation result</label><pre id="npValidation" class="np-output">Python and JSON files can be syntax-checked without execution. Other file types are stored as text only.</pre></div>
        </main>
        <aside class="np-review"><label class="np-label">Patch queue</label><div id="npPatches" class="np-file-list"></div><label class="np-label" style="margin-top:14px">Selected diff</label><pre id="npDiff" class="np-output">Select a patch to inspect its diff.</pre><div class="np-actions" style="margin-top:8px"><button class="np-btn approve" id="npApprove">APPROVE + APPLY TO SNAPSHOT</button><button class="np-btn reject" id="npReject">REJECT</button></div><p class="np-help">Approval updates only the saved workspace copy. It never edits local disk, GitHub, or a deployed app. Re-review any changed file before approving a patch.</p></aside>
      </div>
    </section>`;
  document.body.append(layer);
  const $ = id => document.getElementById(id);
  let projectId = "", selectedPath = "", selectedPatch = "", busy = false;
  const status = message => { $("npStatus").textContent = message; };
  async function api(url, options = {}) {
    const response = await fetch(url, {credentials:"same-origin", cache:"no-store", ...options,
      headers: options.body ? {"Content-Type":"application/json", ...(options.headers||{})} : (options.headers||{})});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(data.detail || "Request failed (HTTP " + response.status + ")");
    return data;
  }
  async function ensureSession() {
    const response = await fetch("/api/session", {credentials:"same-origin",cache:"no-store"});
    if (!response.ok) throw Error("Browser session could not be initialized.");
  }
  function setBusy(value) {
    busy = value;
    ["npCreate","npNewFile","npRefresh","npSave","npValidate","npPropose","npApprove","npReject"].forEach(id => $(id).disabled = value);
  }
  async function run(action, successMessage) {
    if (busy) return;
    setBusy(true);
    try { await action(); if (successMessage) status(successMessage); }
    catch (error) { status(error.message || "Workspace request failed."); }
    finally { setBusy(false); }
  }
  function renderFiles(files) {
    const root = $("npFiles"); root.replaceChildren();
    if (!files.length) { const note = document.createElement("p"); note.className="np-help"; note.textContent="No saved files yet."; root.append(note); return; }
    files.forEach(file => {
      const button = document.createElement("button"); button.type="button"; button.className="np-file"+(file.path===selectedPath?" active":"");
      button.textContent=file.path; button.title=file.characters+" characters · v"+file.version;
      button.addEventListener("click", () => run(async()=>loadFile(file.path), "Loaded "+file.path));
      root.append(button);
    });
  }
  function renderPatches(patches) {
    const root=$("npPatches"); root.replaceChildren();
    if (!patches.length) { const note=document.createElement("p"); note.className="np-help"; note.textContent="No patch proposals yet."; root.append(note); $("npDiff").textContent="Select a patch to inspect its diff."; return; }
    patches.forEach(patch=>{
      const button=document.createElement("button"); button.type="button"; button.className="np-review-item"+(patch.id===selectedPatch?" active":"");
      button.textContent=patch.summary;
      const small=document.createElement("small"); small.textContent=patch.path+" · "+patch.status.toUpperCase(); button.append(small);
      button.addEventListener("click",()=>{selectedPatch=patch.id;$("npDiff").textContent=patch.diff;renderPatches(patches);});
      root.append(button);
    });
    const chosen=patches.find(p=>p.id===selectedPatch);
    if(chosen) $("npDiff").textContent=chosen.diff;
    else {selectedPatch=patches[0].id;$("npDiff").textContent=patches[0].diff;renderPatches(patches);}
    const active=patches.find(p=>p.id===selectedPatch);
    $("npApprove").disabled=busy||!active||active.status!=="pending";
    $("npReject").disabled=busy||!active||active.status!=="pending";
  }
  async function loadProjects(preferred) {
    await ensureSession();
    const data=await api("/api/workspace/projects");
    const select=$("npProject");select.replaceChildren();
    if(!data.projects.length){const opt=document.createElement("option");opt.value="";opt.textContent="No projects yet";select.append(opt);projectId="";renderFiles([]);renderPatches([]);return;}
    data.projects.forEach(project=>{const opt=document.createElement("option");opt.value=project.id;opt.textContent=project.name+" · "+project.file_count+" files";select.append(opt);});
    projectId=data.projects.some(p=>p.id===(preferred||projectId))?(preferred||projectId):data.projects[0].id;
    select.value=projectId;await loadProjectData();
  }
  async function loadProjectData() {
    if(!projectId){renderFiles([]);renderPatches([]);return;}
    const [files,patches]=await Promise.all([
      api("/api/workspace/projects/"+encodeURIComponent(projectId)+"/files"),
      api("/api/workspace/projects/"+encodeURIComponent(projectId)+"/patches")
    ]);
    if(!files.files.some(f=>f.path===selectedPath))selectedPath=files.files[0]?.path||"";
    renderFiles(files.files);renderPatches(patches.patches);
    if(selectedPath) await loadFile(selectedPath);
    else {$("npPath").value="";$("npSource").value="";$("npProposed").value="";$("npValidation").textContent="Save a source file before creating a patch.";}
  }
  async function loadFile(path) {
    if(!projectId||!path)return;
    const data=await api("/api/workspace/projects/"+encodeURIComponent(projectId)+"/files/"+path.split("/").map(encodeURIComponent).join("/"));
    selectedPath=data.file.path;$("npPath").value=data.file.path;$("npSource").value=data.file.content;$("npProposed").value=data.file.content;
    await loadProjectDataNoFile();
  }
  async function loadProjectDataNoFile() {
    const [files,patches]=await Promise.all([
      api("/api/workspace/projects/"+encodeURIComponent(projectId)+"/files"),
      api("/api/workspace/projects/"+encodeURIComponent(projectId)+"/patches")
    ]);
    renderFiles(files.files);renderPatches(patches.patches);
  }
  async function createProject() {
    const name=$("npProjectName").value.trim();if(!name)throw Error("Enter a project name first.");
    const data=await api("/api/workspace/projects",{method:"POST",body:JSON.stringify({name})});
    $("npProjectName").value="";projectId=data.project.id;selectedPath="";selectedPatch="";await loadProjects(projectId);
  }
  async function saveFile() {
    if(!projectId)throw Error("Create or select a project first.");
    const path=$("npPath").value.trim();if(!path)throw Error("Enter a relative file path.");
    const data=await api("/api/workspace/projects/"+encodeURIComponent(projectId)+"/files",{method:"PUT",body:JSON.stringify({path,content:$("npSource").value})});
    selectedPath=data.file.path;$("npPath").value=selectedPath;$("npProposed").value=$("npSource").value;
    await loadProjectDataNoFile();
  }
  async function proposePatch() {
    if(!projectId)throw Error("Create or select a project first.");
    const path=$("npPath").value.trim(),summary=$("npSummary").value.trim();
    if(!path||!summary)throw Error("Enter the saved file path and a short patch summary.");
    const data=await api("/api/workspace/projects/"+encodeURIComponent(projectId)+"/patches",{method:"POST",body:JSON.stringify({path,summary,proposed_content:$("npProposed").value})});
    selectedPatch=data.patch.id;$("npDiff").textContent=data.patch.diff;await loadProjectDataNoFile();
  }
  async function reviewPatch(decision) {
    if(!selectedPatch)throw Error("Select a patch proposal first.");
    if(decision==="approved"&&!window.confirm("Approve this patch and replace the saved workspace snapshot? This will not edit your computer or GitHub."))return;
    const data=await api("/api/workspace/patches/"+encodeURIComponent(selectedPatch)+"/review",{method:"POST",body:JSON.stringify({decision})});
    status("Patch "+data.patch.status+". Only the workspace snapshot can change.");
    await loadProjectData();
  }
  async function validateFile() {
    if(!projectId)throw Error("Create or select a project first.");
    const path=$("npPath").value.trim();if(!path)throw Error("Enter a saved file path.");
    const data=await api("/api/workspace/projects/"+encodeURIComponent(projectId)+"/validate",{method:"POST",body:JSON.stringify({path})});
    $("npValidation").textContent=JSON.stringify(data.validation,null,2);
    status(data.validation.valid===true?"Validation passed (no code executed).":data.validation.valid===false?"Validation found an issue.":"No validator available for this file type.");
  }
  open.addEventListener("click",()=>{layer.classList.add("open");run(()=>loadProjects(),"Project workspace ready.");});
  $("npClose").addEventListener("click",()=>layer.classList.remove("open"));
  layer.addEventListener("click",e=>{if(e.target===layer)layer.classList.remove("open");});
  document.addEventListener("keydown",e=>{if(e.key==="Escape")layer.classList.remove("open");});
  $("npCreate").addEventListener("click",()=>run(createProject));
  $("npProject").addEventListener("change",()=>run(async()=>{projectId=$("npProject").value;selectedPath="";selectedPatch="";await loadProjectData();},"Project loaded."));
  $("npNewFile").addEventListener("click",()=>{selectedPath="";$("npPath").value="";$("npSource").value="";$("npProposed").value="";$("npSource").focus();status("Enter a path and content, then save the snapshot.");});
  $("npRefresh").addEventListener("click",()=>run(loadProjectData,"Workspace refreshed."));
  $("npSave").addEventListener("click",()=>run(saveFile,"Snapshot saved."));
  $("npPropose").addEventListener("click",()=>run(proposePatch,"Patch staged for review; the current file is unchanged."));
  $("npValidate").addEventListener("click",()=>run(validateFile));
  $("npApprove").addEventListener("click",()=>run(()=>reviewPatch("approved")));
  $("npReject").addEventListener("click",()=>run(()=>reviewPatch("rejected")));
  window.NOXProjectWorkspace={open:()=>open.click(),refresh:()=>run(loadProjectData)};
})();