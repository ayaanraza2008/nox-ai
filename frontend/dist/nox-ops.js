(function(){
"use strict";
const $=id=>document.getElementById(id);
const labels={ready:"READY",configured:"CONFIGURED",limited:"LIMITED",setup_required:"SETUP REQUIRED",degraded:"DEGRADED",failed:"FAILED",unknown:"UNKNOWN"};
let busy=false;
function addCheck(host,item){
 const row=document.createElement("div");row.className="ops-check";
 const main=document.createElement("div");main.className="ops-check-main";
 const title=document.createElement("strong");title.textContent=String(item.label||item.id||"Check");
 const detail=document.createElement("small");detail.textContent=String(item.detail||"No detail provided.");
 main.append(title,detail);
 const tag=document.createElement("span");tag.className="ops-tag";tag.dataset.state=String(item.status||"unknown");tag.textContent=labels[item.status]||String(item.status||"UNKNOWN").replaceAll("_"," ").toUpperCase();
 row.append(main,tag);host.append(row);
}
async function refresh(){
 if(busy)return;busy=true;
 const button=$("opsRefresh");if(button){button.disabled=true;button.textContent="Checking…"}
 const overall=$("opsOverall"),host=$("opsChecks");
 if(overall){overall.textContent="RUNNING SESSION-SCOPED CHECKS…";overall.dataset.state="checking"}
 if(host)host.replaceChildren();
 try{
  const response=await fetch("/api/ops/overview",{credentials:"same-origin",headers:{Accept:"application/json"},cache:"no-store"});
  if(!response.ok)throw new Error("HTTP "+response.status);
  const data=await response.json();
  if(overall){
   overall.dataset.state=data.overall_status||"unknown";
   overall.textContent=(data.overall_status==="operational"?"CORE SYSTEM OPERATIONAL":"ATTENTION REQUIRED")+" · "+new Date(data.generated_at||Date.now()).toLocaleTimeString();
  }
  (Array.isArray(data.checks)?data.checks:[]).forEach(item=>addCheck(host,item));
  const tasks=data.tasks||{};
  if($("opsActiveTasks"))$("opsActiveTasks").textContent=String(tasks.active??"—");
  if($("opsTaskDetail"))$("opsTaskDetail").textContent=String(tasks.queued??0)+" queued · "+String(tasks.running??0)+" running · "+String(tasks.paused??0)+" paused";
  const caps=data.capabilities||{};
  if($("opsCapabilities"))$("opsCapabilities").textContent=String(caps.ready??0)+" / "+String(caps.total??0);
  if($("opsCapabilityDetail"))$("opsCapabilityDetail").textContent=String(caps.limited??0)+" limited · "+String(caps.setup_required??0)+" need setup";
  if($("opsPrivacy"))$("opsPrivacy").textContent=String(data.privacy||"External provider availability is not tested by this check.");
 }catch(error){
  if(overall){overall.dataset.state="failed";overall.textContent="DIAGNOSTICS UNAVAILABLE · "+error.message}
  if(host){const row=document.createElement("div");row.className="ops-check";row.textContent="Could not retrieve operational overview. Check NOX API health and try again.";host.append(row)}
 }finally{
  busy=false;if(button){button.disabled=false;button.textContent="Run deep check"}
 }
}
const button=$("opsRefresh");if(button)button.addEventListener("click",refresh);
refresh();
window.NOXOpsDiagnostics={refresh};
})();