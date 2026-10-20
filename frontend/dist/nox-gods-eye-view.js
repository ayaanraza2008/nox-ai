(function(){
"use strict";
const $=id=>document.getElementById(id);
let config=null,busy=false;
function status(message,error=false){const el=$("godsEyeStatus");if(el){el.textContent=message;el.dataset.state=error?"error":"normal"}}
function reveal(){const panel=$("godsEyeViewPanel");if(panel){panel.scrollIntoView({behavior:"smooth",block:"start"});panel.classList.remove("off")}}
async function refresh(){
 if(busy)return;busy=true;status("CHECKING NOX CONFIGURATION…");
 try{
  const response=await fetch("/api/integrations/gods-eye-view",{credentials:"same-origin",headers:{Accept:"application/json"}});
  if(!response.ok)throw new Error("HTTP "+response.status);
  config=await response.json();
  const launch=$("godsEyeLaunch"),copy=$("godsEyeCopyUrl");
  if(config.configured&&config.url){
   launch.href=config.url;launch.classList.remove("hidden");launch.setAttribute("aria-disabled","false");
   copy.disabled=false;copy.dataset.url=config.url;
   status("URL CONFIGURED · SERVICE HEALTH NOT VERIFIED");
   $("godsEyeConnectionDetail").textContent="The launch URL is configured. Open the workspace to verify that the globe and its data providers actually load.";
  }else{
   launch.classList.add("hidden");copy.disabled=true;status("SETUP REQUIRED",true);
   $("godsEyeConnectionDetail").textContent=config.reason||"Deploy the separate upstream service and configure GODS_EYE_VIEW_URL on NOX.";
  }
  $("godsEyeCommit").textContent=(config.upstream_commit||"Unknown").slice(0,12);
 }catch(error){
  status("CONFIGURATION CHECK FAILED",true);
  $("godsEyeConnectionDetail").textContent="NOX could not read integration configuration: "+error.message;
  $("godsEyeLaunch").classList.add("hidden");
 }finally{busy=false}
}
function handleCommand(message){
 const s=String(message||"");
 if(!/\b(god'?s eye view|gods eye view|godseyeview|globe workspace)\b/i.test(s))return false;
 reveal();
 if(/\b(open|launch|start)\b/i.test(s)&&config&&config.configured&&config.url){
  window.open(config.url,"_blank","noopener,noreferrer");
  status("LAUNCH REQUESTED · CHECK THE NEW TAB");
 }else{
  status(config&&config.configured?"READY TO LAUNCH":"SETUP REQUIRED");
  $("godsEyeConnectionDetail").textContent=config&&config.configured
   ?"Use Launch full workspace to open the actual upstream application. NOX chat cannot yet toggle native layers remotely."
   :"The dedicated service must be deployed and GODS_EYE_VIEW_URL configured before the globe can launch.";
 }
 return true;
}
$("godsEyeRefresh").addEventListener("click",refresh);
$("godsEyeCopyUrl").addEventListener("click",async()=>{
 if(!config||!config.url)return;
 try{await navigator.clipboard.writeText(config.url);status("WORKSPACE URL COPIED")}
 catch{status("CLIPBOARD UNAVAILABLE · OPEN THE LINK MANUALLY",true)}
});
document.querySelectorAll('[data-scroll="godsEyeViewPanel"]').forEach(el=>el.addEventListener("click",reveal));
window.NOXGodsEyeView={handleCommand,refresh,open:reveal};
refresh();
})();