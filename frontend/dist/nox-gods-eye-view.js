(function(){
"use strict";
const $=id=>document.getElementById(id);
const state={config:null,loading:false};
function setStatus(message,error=false){const el=$("godsEyeStatus");if(!el)return;el.textContent=message;el.dataset.state=error?"error":"normal"}
function reveal(){const panel=$("godsEyeViewPanel");if(panel){panel.scrollIntoView({behavior:"smooth",block:"start"});panel.classList.remove("off")} }
async function loadConfig(){
 if(state.loading)return;
 state.loading=true;
 setStatus("CHECKING NOX CONFIGURATION…");
 try{
  const response=await fetch("/api/integrations/gods-eye-view",{credentials:"same-origin",headers:{Accept:"application/json"}});
  if(!response.ok)throw new Error("NOX API returned HTTP "+response.status);
  const data=await response.json();state.config=data;
  const launch=$("godsEyeLaunch"),copy=$("godsEyeCopyUrl");
  if(data.configured&&data.url){
   launch.href=data.url;launch.classList.remove("hidden");launch.setAttribute("aria-disabled","false");
   copy.disabled=false;copy.dataset.url=data.url;
   setStatus("URL CONFIGURED · SERVICE HEALTH NOT YET VERIFIED");
   $("godsEyeConnectionDetail").textContent="The launch URL is configured. NOX does not invent a live/online status; open the workspace to verify its actual provider and globe state.";
  }else{
   launch.classList.add("hidden");copy.disabled=true;
   setStatus("SETUP REQUIRED",true);
   $("godsEyeConnectionDetail").textContent=data.reason||"Set GODS_EYE_VIEW_URL on the NOX hosting service after the separate God's Eye View service has been created.";
  }
  $("godsEyeCommit").textContent=(data.upstream_commit||"Not pinned").slice(0,12);
 }catch(error){
  setStatus("NOX INTEGRATION STATUS UNAVAILABLE",true);
  $("godsEyeConnectionDetail").textContent="Could not read the integration configuration: "+error.message;
  $("godsEyeLaunch").classList.add("hidden");
 }finally{state.loading=false}
}
function intent(text){return /\b(god'?s eye view|gods eye view|godseyeview|god's eye|globe workspace)\b/i.test(text)||/\b(show|enable|open|reset|explain)\b.*\b(aircraft|flights|earthquakes|satellites|satellite layer|globe view|map layer)\b/i.test(text)}
function handleCommand(text){
 if(!intent(text))return false;
 reveal();
 if(/\b(open|launch|start)\b/i.test(text)&&state.config&&state.config.configured&&state.config.url){
  window.open(state.config.url,"_blank","noopener,noreferrer");
  setStatus("LAUNCH REQUESTED · VERIFY THE NEW TAB");
  $("godsEyeConnectionDetail").textContent="Opened the separate upstream workspace in a new tab. If the browser blocked it, use the Launch workspace link below.";
 }else if(/\b(aircraft|flights|earthquakes|satellites|satellite layer|map layer|globe view|reset)\b/i.test(text)){
  setStatus("NATIVE WORKSPACE ACTION REQUIRED");
  $("godsEyeConnectionDetail").textContent="NOX has opened this workspace panel, but cross-app layer commands are not connected yet. Launch God's Eye View and use its native layer/search/camera controls; NOX will not claim a layer changed without confirmation.";
 }else{
  setStatus(state.config&&state.config.configured?"READY TO LAUNCH":"SETUP REQUIRED");
  $("godsEyeConnectionDetail").textContent="Use Launch workspace to open the real upstream application. The globe and provider APIs run in a separate service to avoid colliding with NOX's existing API routes.";
 }
 return true;
}
$("godsEyeRefresh").addEventListener("click",loadConfig);
$("godsEyeCopyUrl").addEventListener("click",async()=>{
 const url=state.config&&state.config.url;if(!url)return;
 try{await navigator.clipboard.writeText(url);setStatus("WORKSPACE URL COPIED")}
 catch{setStatus("CLIPBOARD UNAVAILABLE · COPY THE LINK MANUALLY",true)}
});
document.querySelectorAll('[data-scroll="godsEyeViewPanel"]').forEach(button=>button.addEventListener("click",reveal));
window.NOXGodsEyeView={handleCommand,refresh:loadConfig,open:reveal};
loadConfig();
})();