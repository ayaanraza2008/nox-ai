(() => {
  "use strict";
  if (window.__NOXGitHubCIDashboardLoaded) return;
  window.__NOXGitHubCIDashboardLoaded = true;
  const style = document.createElement("style");
  style.textContent = `
    #noxCiOpen{position:fixed;right:18px;bottom:66px;z-index:99978;border:1px solid #8e85ff66;background:linear-gradient(135deg,#17152ff5,#0b2637f5);color:#e8e5ff;border-radius:10px;padding:10px 13px;font:10px ui-monospace,monospace;letter-spacing:.07em;box-shadow:0 0 22px #8e85ff12}
    #noxCiLayer{display:none;position:fixed;inset:0;z-index:99989;background:#02060be8;backdrop-filter:blur(12px);padding:2vh 2vw;color:#e6f5ff}
    #noxCiLayer.open{display:grid;place-items:center}
    .nc-shell{width:min(1080px,100%);height:min(92vh,850px);display:flex;flex-direction:column;border:1px solid #9b91ff44;border-radius:14px;overflow:hidden;background:#08111df7;box-shadow:0 20px 90px #000a;font:12px/1.5 system-ui,sans-serif}
    .nc-head,.nc-toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:11px 14px;border-bottom:1px solid #8f8cff20}
    .nc-head b{letter-spacing:.14em}.nc-head small,.nc-help{color:#91a8c2;font-size:10px}.nc-spacer{flex:1}
    .nc-btn{border:1px solid #938bff3d;background:#111c30;color:#e5e9ff;border-radius:7px;padding:8px 10px;font:10px ui-monospace,monospace;cursor:pointer}
    .nc-btn:hover{border-color:#a7a0ff99}.nc-btn:disabled{opacity:.45;cursor:wait}
    .nc-status{font:10px ui-monospace,monospace;color:#a4c5dd;overflow-wrap:anywhere}
    .nc-main{display:grid;grid-template-columns:minmax(230px,34%) minmax(0,1fr);min-height:0;flex:1}
    .nc-runs{overflow:auto;padding:10px;border-right:1px solid #8f8cff20}.nc-detail{padding:14px;overflow:auto;min-width:0}
    .nc-label{display:block;font:9px ui-monospace,monospace;letter-spacing:.13em;color:#aaa4ff;text-transform:uppercase;margin:4px 0 9px}
    .nc-run{display:block;width:100%;text-align:left;margin:6px 0;padding:10px;border:1px solid #8f8cff24;background:#0b1726;color:#d7e7f6;border-radius:8px;cursor:pointer}
    .nc-run:hover,.nc-run.active{border-color:#9c93ff99;background:#121d34}.nc-run b{display:block;font-size:11px;overflow-wrap:anywhere}.nc-run small{display:block;color:#91a8c2;font:9px ui-monospace,monospace;margin-top:4px}
    .nc-pill{display:inline-block;border-radius:99px;padding:2px 7px;font:9px ui-monospace,monospace;background:#17283b;color:#bdd9f1;margin:3px 4px 3px 0}
    .nc-pill.ok{background:#10372f;color:#83f4c4}.nc-pill.bad{background:#411c2a;color:#ff9fb1}.nc-pill.wait{background:#42371a;color:#ffe2a0}
    .nc-job{border:1px solid #8f8cff22;border-radius:8px;margin:9px 0;overflow:hidden}.nc-job summary{padding:10px;cursor:pointer;background:#0c1928;overflow-wrap:anywhere}.nc-job-body{padding:8px 12px}.nc-step{display:flex;gap:9px;padding:6px 0;border-bottom:1px solid #ffffff0a;font-size:10px}.nc-step:last-child{border-bottom:0}.nc-step span:last-child{margin-left:auto;white-space:nowrap;color:#a3bfd4;font-family:ui-monospace,monospace}
    .nc-meta{color:#9cb7cc;font:10px ui-monospace,monospace;overflow-wrap:anywhere}.nc-link{color:#a8a0ff;text-decoration:none}.nc-link:hover{text-decoration:underline}
    @media(max-width:650px){#noxCiOpen{right:10px;bottom:62px}.nc-main{grid-template-columns:1fr;grid-template-rows:minmax(145px,30%) 1fr}.nc-runs{border-right:0;border-bottom:1px solid #8f8cff20}.nc-shell{height:96vh}.nc-head small{display:none}}
  `;
  document.head.append(style);
  const open=document.createElement("button");open.id="noxCiOpen";open.type="button";open.textContent="◈ CI / TEST STATUS";document.body.append(open);
  const layer=document.createElement("div");layer.id="noxCiLayer";
  layer.innerHTML=`
    <section class="nc-shell" role="dialog" aria-modal="true" aria-label="NOX GitHub CI dashboard">
      <header class="nc-head"><span>◈</span><div><b>CI / TEST DASHBOARD</b><br><small>REAL GITHUB ACTIONS STATUS · NO DEPLOY CLAIMS</small></div><span class="nc-spacer"></span><button class="nc-btn" id="ncClose">CLOSE ✕</button></header>
      <div class="nc-toolbar"><button class="nc-btn" id="ncRefresh">↻ REFRESH</button><span class="nc-status" id="ncRepo">Loading repository status…</span><span class="nc-spacer"></span><span class="nc-status" id="ncStatus" role="status">Loading latest runs…</span></div>
      <div class="nc-main"><aside class="nc-runs"><label class="nc-label">Recent workflow runs</label><div id="ncRuns"></div><p class="nc-help">Select a run to inspect job and step states.</p></aside><main class="nc-detail" id="ncDetail"><p class="nc-help">Choose a workflow run from the list.</p></main></div>
    </section>`;
  document.body.append(layer);
  const $=id=>document.getElementById(id);
  let busy=false, selected=null;
  const status=t=>{$("ncStatus").textContent=t;};
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  function pill(value){
    const v=String(value||"unknown").toLowerCase();
    const cls=v==="success"||v==="completed"&&value==="success"?"ok":v==="failure"||v==="cancelled"||v==="timed_out"?"bad":v==="in_progress"||v==="queued"||v==="waiting"?"wait":"";
    return '<span class="nc-pill '+cls+'">'+esc(value||"unknown")+'</span>';
  }
  async function api(url){
    const r=await fetch(url,{credentials:"same-origin",cache:"no-store"});
    const d=await r.json().catch(()=>({}));
    if(!r.ok)throw Error(d.detail||"Request failed (HTTP "+r.status+")");
    return d;
  }
  async function run(fn){
    if(busy)return;busy=true;$("ncRefresh").disabled=true;
    try{await fn();}catch(e){status(e.message||"Request failed.");}
    finally{busy=false;$("ncRefresh").disabled=false;}
  }
  function fmt(s){if(!s)return "time unavailable";try{return new Date(s).toLocaleString();}catch{return s;}}
  function renderRuns(data){
    const root=$("ncRuns");root.replaceChildren();
    $("ncRepo").textContent=data.repository+" · base "+data.base_branch;
    if(!data.runs.length){const p=document.createElement("p");p.className="nc-help";p.textContent="No recent workflow runs found for this base branch.";root.append(p);return;}
    data.runs.forEach(item=>{
      const b=document.createElement("button");b.type="button";b.className="nc-run"+(selected===item.id?" active":"");
      b.innerHTML='<b>'+esc(item.name)+' #'+esc(item.run_number)+'</b>'+pill(item.status)+(item.conclusion?pill(item.conclusion):"")+'<small>'+esc(item.branch)+' · '+esc((item.sha||"").slice(0,8))+'</small><small>'+esc(fmt(item.created_at))+'</small>';
      b.addEventListener("click",()=>run(()=>loadDetail(item.id)));
      root.append(b);
    });
    status(data.runs.length+" workflow run(s) loaded");
  }
  async function loadRuns(){
    const data=await api("/api/github/ci/runs?limit=15");renderRuns(data);
    if(selected && data.runs.some(x=>x.id===selected)) await loadDetail(selected);
    else if(data.runs.length) await loadDetail(data.runs[0].id);
  }
  async function loadDetail(id){
    selected=id;
    const d=await api("/api/github/ci/runs/"+encodeURIComponent(id));
    const root=$("ncDetail");root.replaceChildren();
    const h=document.createElement("div");
    h.innerHTML='<label class="nc-label">Selected workflow</label><h3 style="margin:0 0 8px;font-size:15px">'+esc(d.name)+'</h3>'+pill(d.status)+(d.conclusion?pill(d.conclusion):"")+'<p class="nc-meta">Branch: '+esc(d.branch)+'<br>Commit: '+esc(d.sha)+'<br>Run ID: '+esc(d.id)+'</p><p><a class="nc-link" href="'+esc(d.html_url)+'" target="_blank" rel="noopener noreferrer">Open full run on GitHub ↗</a></p>';
    root.append(h);
    const label=document.createElement("label");label.className="nc-label";label.textContent="Jobs and steps";root.append(label);
    if(!d.jobs.length){const p=document.createElement("p");p.className="nc-help";p.textContent="GitHub has not reported jobs for this run yet.";root.append(p);}
    d.jobs.forEach(job=>{
      const details=document.createElement("details");details.className="nc-job";details.open=job.conclusion==="failure"||job.status==="in_progress";
      const summary=document.createElement("summary");summary.innerHTML='<b>'+esc(job.name)+'</b> '+pill(job.status)+(job.conclusion?pill(job.conclusion):"");
      details.append(summary);
      const body=document.createElement("div");body.className="nc-job-body";
      job.steps.forEach(step=>{
        const line=document.createElement("div");line.className="nc-step";
        line.innerHTML='<span>'+esc(step.number)+'. '+esc(step.name)+'</span><span>'+esc(step.conclusion||step.status||"pending")+'</span>';
        body.append(line);
      });
      details.append(body);root.append(details);
    });
    const note=document.createElement("p");note.className="nc-help";note.textContent=d.note||"GitHub Actions state only; not proof that Render is healthy.";root.append(note);
    document.querySelectorAll(".nc-run").forEach(b=>b.classList.toggle("active",b.textContent.includes("#"+d.id)));
    status("Run #"+d.id+" · "+(d.conclusion||d.status));
  }
  open.addEventListener("click",()=>{layer.classList.add("open");run(loadRuns);});
  $("ncClose").addEventListener("click",()=>layer.classList.remove("open"));
  layer.addEventListener("click",e=>{if(e.target===layer)layer.classList.remove("open");});
  document.addEventListener("keydown",e=>{if(e.key==="Escape")layer.classList.remove("open");});
  $("ncRefresh").addEventListener("click",()=>run(loadRuns));
  window.NOXGitHubCIDashboard={open:()=>open.click(),refresh:()=>run(loadRuns)};
})();