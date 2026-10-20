(() => {
  "use strict";
  if (window.__NOXVisionResearchLoaded) return;
  window.__NOXVisionResearchLoaded = true;
  const $ = id => document.getElementById(id);
  const visionStatus = (id, text) => { const n=$(id); if(n) n.textContent=text; };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const video=$("cameraPreview"), image=$("imagePreview"), stage=$("visionStage"), overlay=$("visionOverlay");
  if (!video || !image || !stage || !overlay) return;
  const ctx=overlay.getContext("2d");
  let stream=null, detector=null, modelPromise=null, cameraFacing="environment", detectOn=false, paused=false, raf=0, lastRun=0, imageUrl=null, lastItems=[], nextTrack=1, controller=null, ocrWorker=null, ocrPromise=null, researchFileUrl=null, researchFile=null;
  const MIN_SCORE=0.45;
  function status(msg){visionStatus("visionMessage",msg);}
  function fitCanvas(source){
    const rect=stage.getBoundingClientRect();
    const w=source?.videoWidth || source?.naturalWidth || rect.width || 640;
    const h=source?.videoHeight || source?.naturalHeight || rect.height || 360;
    stage.style.aspectRatio=w+" / "+h;
    overlay.width=Math.max(1,Math.round(w)); overlay.height=Math.max(1,Math.round(h));
    overlay.style.width="100%"; overlay.style.height="100%";
    return {w:overlay.width,h:overlay.height};
  }
  function clearBoxes(){ctx.clearRect(0,0,overlay.width,overlay.height);lastItems=[];visionStatus("visionDetections","No detections yet.");}
  function iou(a,b){
    const x1=Math.max(a[0],b[0]),y1=Math.max(a[1],b[1]),x2=Math.min(a[0]+a[2],b[0]+b[2]),y2=Math.min(a[1]+a[3],b[1]+b[3]);
    const inter=Math.max(0,x2-x1)*Math.max(0,y2-y1),union=a[2]*a[3]+b[2]*b[3]-inter;
    return union>0?inter/union:0;
  }
  function assignTracks(predictions){
    const used=new Set();
    return predictions.map(p=>{
      let best=-1,bestScore=0.15;
      lastItems.forEach((old,i)=>{if(used.has(i)||old.class!==p.class)return;const score=iou(old.bbox,p.bbox);if(score>bestScore){best=i;bestScore=score;}});
      let id;
      if(best>=0){used.add(best);id=lastItems[best].trackId;}else id=nextTrack++;
      return {...p,trackId:id};
    });
  }
  function draw(predictions,source){
    const {w,h}=fitCanvas(source);
    ctx.clearRect(0,0,w,h);
    const shown=predictions.filter(p=>p.score>=MIN_SCORE);
    const tracked=assignTracks(shown);
    tracked.forEach(p=>{
      const [x,y,bw,bh]=p.bbox, color="#6df7e8", label=p.class+" "+Math.round(p.score*100)+"% · #"+p.trackId;
      ctx.lineWidth=Math.max(2,w/450);ctx.strokeStyle=color;ctx.shadowColor=color;ctx.shadowBlur=8;ctx.strokeRect(x,y,bw,bh);ctx.shadowBlur=0;
      ctx.font="bold "+Math.max(12,w/70)+"px system-ui";
      const tw=ctx.measureText(label).width, th=Math.max(20,w/45);
      const ly=Math.max(0,y-th);
      ctx.fillStyle="#06131be8";ctx.fillRect(x,ly,Math.min(w-x,tw+12),th);
      ctx.fillStyle=color;ctx.fillText(label,x+6,ly+th*.72);
    });
    lastItems=tracked;
    const counts={};tracked.forEach(p=>counts[p.class]=(counts[p.class]||0)+1);
    const summary=Object.entries(counts).map(([k,v])=>v+" "+k+(v===1?"":"s")).join(" · ");
    visionStatus("visionDetections",tracked.length?summary+" · IDs are short-term visual tracking, not identities.":"No supported objects detected in this frame.");
    visionStatus("visionFrameState",tracked.length+" OBJECT(S)");
  }
  function activeSource(){return !image.classList.contains("hidden")&&image.complete&&image.naturalWidth?image:video;}
  async function loadDetector(){
    if(detector)return detector;
    if(modelPromise)return modelPromise;
    modelPromise=(async()=>{
      visionStatus("visionModelState","LOADING MODEL…");
      const loadScript=(src,ready)=>new Promise((resolve,reject)=>{
        if(ready()){resolve();return;}
        let script=document.querySelector('script[data-nox-model="'+src+'"]');
        if(!script){script=document.createElement("script");script.src=src;script.async=true;script.dataset.noxModel=src;document.head.append(script);}
        script.addEventListener("load",()=>ready()?resolve():reject(Error("Model library did not initialize.")),{once:true});
        script.addEventListener("error",()=>reject(Error("Could not load open-source detector from CDN.")),{once:true});
      });
      await loadScript("https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.22.0/dist/tf.min.js",()=>!!window.tf);
      await loadScript("https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3/dist/coco-ssd.min.js",()=>!!window.cocoSsd);
      detector=await window.cocoSsd.load({base:"lite_mobilenet_v2"});
      visionStatus("visionModelState","COCO-SSD · LOCAL");
      return detector;
    })().catch(e=>{modelPromise=null;visionStatus("visionModelState","UNAVAILABLE");throw e;});
    return modelPromise;
  }
  async function detectOnce(source){
    if(!source||(!source.videoWidth&&!source.naturalWidth))return;
    const model=await loadDetector();
    const predictions=await model.detect(source,20,MIN_SCORE);
    draw(predictions,source);
  }
  async function loop(){
    if(!detectOn||paused||document.hidden){raf=0;if(detectOn&&!paused&&!document.hidden)raf=requestAnimationFrame(loop);return;}
    const now=performance.now();
    if(now-lastRun<350){raf=requestAnimationFrame(loop);return;}
    lastRun=now;
    try{await detectOnce(video);}catch(e){detectOn=false;visionStatus("visionFrameState","STOPPED");status("Detection stopped: "+(e.message||"model error"));$("visionPause").disabled=true;return;}
    if(detectOn&&!paused&&!document.hidden)raf=requestAnimationFrame(loop);else raf=0;
  }
  function stopTracks(){
    detectOn=false;paused=false;if(raf)cancelAnimationFrame(raf);raf=0;
    if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}
    video.pause();video.srcObject=null;video.classList.add("hidden");
    $("cameraStart").disabled=false;$("cameraStop").disabled=true;$("visionPause").disabled=true;$("visionSwitch").disabled=true;if($("visionCapture"))$("visionCapture").disabled=true;
    visionStatus("cameraStatus","CAMERA OFF");visionStatus("visionFrameState","IDLE");clearBoxes();
  }
  async function startCamera(){
    if(!navigator.mediaDevices?.getUserMedia){status("Camera needs HTTPS or localhost and a browser with camera support.");return;}
    stopTracks();image.classList.add("hidden");image.removeAttribute("src");
    try{
      stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:cameraFacing},width:{ideal:960},height:{ideal:540}}});
      video.srcObject=stream;video.classList.remove("hidden");await video.play();
      $("cameraStart").disabled=true;$("cameraStop").disabled=false;$("visionPause").disabled=false;$("visionSwitch").disabled=false;if($("visionCapture"))$("visionCapture").disabled=false;
      visionStatus("cameraStatus","● CAMERA ACTIVE");status("Camera active with your permission. Loading local object detector…");
      await loadDetector();detectOn=true;paused=false;lastRun=0;raf=requestAnimationFrame(loop);
    }catch(e){stopTracks();status("Camera/detector unavailable: "+(e.message||"permission denied")+". You can still upload an image.");}
  }
  $("cameraStart").onclick=()=>startCamera();
  const captureButton=$("visionCapture");
  if(captureButton)captureButton.onclick=()=>{
    if(!stream||!video.videoWidth||!video.videoHeight){status("Enable the camera before capturing a frame.");return;}
    const canvas=document.createElement("canvas");canvas.width=video.videoWidth;canvas.height=video.videoHeight;
    canvas.getContext("2d",{alpha:false}).drawImage(video,0,0,canvas.width,canvas.height);
    canvas.toBlob(blob=>{
      if(!blob){status("Could not capture this frame.");return;}
      const file=new File([blob],"nox-camera-frame.jpg",{type:"image/jpeg",lastModified:Date.now()});
      try{const transfer=new DataTransfer();transfer.items.add(file);$("imageUpload").files=transfer.files;stopTracks();$("imageUpload").dispatchEvent(new Event("change",{bubbles:true}));status("Frame captured. Camera is now off. Send your chat message to share this frame with the configured vision model.");}
      catch(e){status("Frame captured, but this browser could not attach it to chat: "+(e.message||"unsupported file input"));}
    },"image/jpeg",0.88);
  };
  $("cameraStop").onclick=()=>{stopTracks();status("Camera and detection stopped; camera tracks released.");};
  $("visionPause").onclick=()=>{
    if(!stream)return;
    paused=!paused;$("visionPause").textContent=paused?"Resume detection":"Pause detection";
    visionStatus("visionFrameState",paused?"PAUSED":"RUNNING");
    if(!paused){lastRun=0;raf=requestAnimationFrame(loop);}else{if(raf)cancelAnimationFrame(raf);raf=0;}
  };
  $("visionSwitch").onclick=async()=>{
    if(!stream)return;
    cameraFacing=cameraFacing==="environment"?"user":"environment";
    await startCamera();
  };
  $("imageUpload").addEventListener("change",async()=>{
    if(!image.src||image.classList.contains("hidden"))return;
    if(stream)stopTracks();
    image.onload=async()=>{
      try{await loadDetector();await detectOnce(image);status("Still image detected locally in this browser. No image was uploaded for object detection.");}
      catch(e){status("Still-image detection unavailable: "+(e.message||"model error"));}
    };
    if(image.complete&&image.naturalWidth)image.onload();
  });
  $("clearMedia").addEventListener("click",()=>{stopTracks();clearBoxes();image.classList.add("hidden");if(image.src.startsWith("blob:"))URL.revokeObjectURL(image.src);image.removeAttribute("src");});
  document.addEventListener("visibilitychange",()=>{if(document.hidden&&raf){cancelAnimationFrame(raf);raf=0;}else if(detectOn&&!paused&&!raf)raf=requestAnimationFrame(loop);});
  window.addEventListener("beforeunload",()=>{stopTracks();if(image.src.startsWith("blob:"))URL.revokeObjectURL(image.src);if(researchFileUrl)URL.revokeObjectURL(researchFileUrl);if(ocrWorker)ocrWorker.terminate().catch(()=>{});});

  // Public-information research panel: the image stays local; only OCR text is submitted.
  function researchStatus(s){visionStatus("researchStatus",s);}
  function researchHtmlResult(data){
    const root=$("researchResults");
    const section=(label,items)=>items?.length?'<div class="footnote" style="margin:8px 0"><b>'+esc(label)+'</b><ul>'+items.map(x=>'<li>'+esc(x)+'</li>').join("")+'</ul></div>':"";
    let html='<div class="statusline"><span>Input type</span><span class="statusvalue">'+esc(data.kind)+'</span></div><div class="footnote">Examined: '+esc(data.input_examined)+'<br>Checked: '+esc(data.checked_at||"")+'</div>';
    if(data.normalized_number)html+='<div class="statusline"><span>Normalized number</span><span class="statusvalue">'+esc(data.normalized_number)+'</span></div>';
    if(data.country||data.number_type)html+='<div class="statusline"><span>Number metadata</span><span class="statusvalue">'+esc(data.country||"unknown")+' · '+esc(data.number_type||"unknown")+'</span></div>';
    if(data.domain_metadata)html+='<div class="footnote">Domain '+esc(data.domain_metadata.domain)+' · MX records: '+esc((data.domain_metadata.mx_records||[]).join(", ")||"none returned")+' · A records: '+esc((data.domain_metadata.a_records||[]).join(", ")||"none returned")+'</div>';
    html+=section("Confirmed facts",data.confirmed_facts)+section("Possible matches (not identity proof)",data.possible_matches)+section("Warnings",data.warnings)+section("Limitations",data.limits);
    if(data.sources?.length){html+='<label class="nc-label">Public source results</label>'+data.sources.map(s=>'<div class="nc-run"><b>'+esc(s.title)+'</b><small>'+esc(s.snippet)+'</small><p><a class="nc-link" href="'+esc(s.url)+'" target="_blank" rel="noopener noreferrer">Open source ↗</a></p></div>').join("");}
    else html+='<p class="footnote">No public search result was returned. This does not prove that no public information exists.</p>';
    html+='<p class="footnote">'+esc(data.disclosure||"Public-source search results can be incomplete.")+'</p>';
    root.innerHTML=html;
    const links=$("researchImageLinks");
    links.replaceChildren();
    if(data.kind==="image"){
      const note=document.createElement("p");note.className="footnote";note.textContent="Optional visual search: these links open official search pages. You must choose and upload the image yourself; NOX does not send it automatically.";
      const a=document.createElement("a");a.className="nc-link";a.href="https://lens.google.com/";a.target="_blank";a.rel="noopener noreferrer";a.textContent="Google Lens ↗";
      const b=document.createElement("a");b.className="nc-link";b.href="https://www.bing.com/visualsearch";b.target="_blank";b.rel="noopener noreferrer";b.textContent="Bing Visual Search ↗";b.style.marginLeft="12px";
      links.append(note,a,b);
    }
  }
  async function getOcrWorker(){
    if(ocrWorker)return ocrWorker;if(ocrPromise)return ocrPromise;
    ocrPromise=(async()=>{
      const load=(src,ready)=>new Promise((resolve,reject)=>{
        if(ready()){resolve();return;}let s=document.querySelector('script[data-nox-ocr="'+src+'"]');
        if(!s){s=document.createElement("script");s.src=src;s.async=true;s.dataset.noxOcr=src;document.head.append(s);}
        s.addEventListener("load",()=>ready()?resolve():reject(Error("OCR library failed to initialize.")),{once:true});
        s.addEventListener("error",()=>reject(Error("Could not load local OCR library.")),{once:true});
      });
      await load("https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js",()=>!!window.Tesseract);
      ocrWorker=await window.Tesseract.createWorker("eng");
      return ocrWorker;
    })().catch(e=>{ocrPromise=null;throw e;});
    return ocrPromise;
  }
  $("researchImagePick").onclick=()=>$("researchImageFile").click();
  $("researchImageFile").addEventListener("change",()=>{
    researchFile=$("researchImageFile").files?.[0]||null;
    if(researchFileUrl)URL.revokeObjectURL(researchFileUrl);
    researchFileUrl=researchFile?URL.createObjectURL(researchFile):null;
    if(researchFile){$("researchKind").value="image";researchStatus("Image selected. OCR will run locally only after you press Research.");}
  });
  $("researchKind").addEventListener("change",()=>{if($("researchKind").value!=="image")researchFile=null;});
  $("researchClear").onclick=()=>{
    if(controller)controller.abort();controller=null;
    if(researchFileUrl)URL.revokeObjectURL(researchFileUrl);researchFileUrl=null;researchFile=null;
    $("researchImageFile").value="";$("researchValue").value="";$("researchResults").replaceChildren();$("researchImageLinks").replaceChildren();
    researchStatus("Input and displayed results cleared from this page. Already viewed public source pages are outside NOX's control.");
  };
  $("researchStop").onclick=()=>{if(controller)controller.abort();controller=null;$("researchStop").disabled=true;researchStatus("Research stopped by user.");};
  $("researchRun").onclick=async()=>{
    if(controller)controller.abort();controller=new AbortController();const own=controller;
    $("researchRun").disabled=true;$("researchStop").disabled=false;$("researchResults").replaceChildren();researchStatus("Preparing input…");
    try{
      const kind=$("researchKind").value;let value=$("researchValue").value.trim();
      if(kind==="image"&&researchFile){
        if(!/^image\/(png|jpeg|webp)$/.test(researchFile.type)||researchFile.size>8*1024*1024)throw Error("Choose a PNG, JPEG, or WebP image under 8 MB.");
        researchStatus("Loading OCR engine; image remains in this browser…");
        const worker=await getOcrWorker();if(own.signal.aborted)return;
        const {data}=await worker.recognize(researchFileUrl);value=(data.text||"").trim();
        if(!value)value=$("researchValue").value.trim();
        else if(!$("researchValue").value.trim())$("researchValue").value=value;
        if(!value)throw Error("No useful visible text was recognized. Add a visible sign, logo, product, or landmark description.");
      }
      if(!value)throw Error("Enter one starting point first.");
      if(value.length>1500)throw Error("Input is too long.");
      researchStatus("Searching permitted public sources…");
      const response=await fetch("/api/research/public",{method:"POST",credentials:"same-origin",cache:"no-store",signal:own.signal,headers:{"Content-Type":"application/json"},body:JSON.stringify({kind,value})});
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw Error(data.detail||"Public research request failed (HTTP "+response.status+").");
      if(own.signal.aborted)return;
      researchHtmlResult(data);researchStatus("Research finished. Review source links and distinguish facts from possible matches.");
    }catch(e){if(e.name==="AbortError")return;researchStatus(e.message||"Research failed.");}
    finally{if(controller===own)controller=null;$("researchRun").disabled=false;$("researchStop").disabled=true;}
  };
})();