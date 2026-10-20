(() => {
  "use strict";
  const start = () => {
    const panel = document.getElementById("corePanel");
    const canvas = document.getElementById("coreCanvas");
    if (!panel || !canvas || panel.querySelector(".nox-living-hud")) return;

    const style = document.createElement("style");
    style.id = "nox-living-core-style";
    style.textContent = `
      #corePanel{position:relative;isolation:isolate;overflow:hidden}
      #corePanel .corecanvas{position:relative;z-index:1;filter:brightness(calc(1 + var(--nox-energy,0)*.16));transition:filter .25s ease}
      .nox-living-hud{position:absolute;z-index:2;left:0;right:0;top:42px;bottom:66px;pointer-events:none;overflow:hidden;--nox-intensity:.72}
      .nox-living-hud:before{content:"";position:absolute;inset:8% 8%;border-radius:50%;background:radial-gradient(ellipse at center,transparent 35%,rgba(78,218,255,.035) 51%,transparent 70%);opacity:calc(.35 + var(--nox-energy,0)*.4)}
      .nox-hud-ring{position:absolute;left:50%;top:50%;width:min(65%,330px);aspect-ratio:1;border:1px solid rgba(106,224,255,.20);border-radius:50%;transform:translate(-50%,-50%) rotateX(68deg) rotateZ(-20deg);box-shadow:0 0 22px rgba(83,218,255,.06),inset 0 0 20px rgba(83,218,255,.035);animation:noxOrbitA 24s linear infinite}
      .nox-hud-ring:before,.nox-hud-ring:after{content:"";position:absolute;border-radius:50%;inset:9%;border:1px dashed rgba(156,133,255,.22)}
      .nox-hud-ring:after{inset:25%;border-style:solid;border-color:rgba(114,235,255,.15)}
      .nox-hud-ring.r2{width:min(74%,380px);border-color:rgba(163,139,255,.18);transform:translate(-50%,-50%) rotateX(70deg) rotateZ(58deg);animation:noxOrbitB 32s linear infinite}
      .nox-hud-ring.r2:before{inset:15%;border-style:solid;border-color:rgba(112,221,255,.15)}
      .nox-hud-ring.r3{width:min(53%,270px);border-color:rgba(130,238,255,.15);transform:translate(-50%,-50%) rotateX(74deg) rotateZ(112deg);animation:noxOrbitA 18s linear infinite reverse}
      .nox-hud-tick{position:absolute;left:50%;top:50%;width:6px;height:6px;border:1px solid rgba(132,235,255,.8);border-radius:50%;box-shadow:0 0 10px rgba(92,223,255,.5);transform:translate(-50%,-50%);opacity:calc(.45 + var(--nox-energy,0)*.5)}
      .nox-hud-tick.t1{margin:-142px 0 0 0}.nox-hud-tick.t2{margin:0 0 0 152px}.nox-hud-tick.t3{margin:139px 0 0 0}.nox-hud-tick.t4{margin:0 0 0 -152px}
      .nox-hud-readout{position:absolute;left:13px;top:10px;font:8px var(--mono,monospace);letter-spacing:.16em;color:rgba(142,225,255,.7);text-shadow:0 0 12px rgba(85,220,255,.2)}
      .nox-hud-readout span{display:block;margin-top:5px;color:rgba(163,143,255,.7)}
      .nox-hud-scan{position:absolute;left:7%;right:7%;top:50%;height:1px;background:linear-gradient(90deg,transparent,rgba(110,226,255,.24),transparent);transform:translateY(-50%);opacity:calc(.25 + var(--nox-energy,0)*.55);box-shadow:0 0 12px rgba(102,224,255,.25)}
      #corePanel[data-nox-state="listening"] .nox-hud-ring{border-color:rgba(105,239,255,.4);box-shadow:0 0 26px rgba(83,218,255,.12)}
      #corePanel[data-nox-state="thinking"] .nox-hud-ring{animation-duration:10s}
      #corePanel[data-nox-state="speaking"] .nox-hud-ring{border-color:rgba(173,145,255,.4)}
      #corePanel[data-nox-state="error"] .nox-hud-ring{border-color:rgba(255,127,155,.35)}
      .nox-core-control{display:flex;align-items:center;gap:7px;margin-left:auto;color:var(--muted);font:8px var(--mono,monospace);letter-spacing:.1em;white-space:nowrap}
      .nox-core-control input{width:76px;accent-color:var(--cyan);cursor:pointer}
      @keyframes noxOrbitA{from{rotate:0deg}to{rotate:360deg}}
      @keyframes noxOrbitB{from{rotate:360deg}to{rotate:0deg}}
      @media(max-width:720px){.nox-living-hud{top:38px;bottom:62px}.nox-hud-ring{width:76%}.nox-hud-ring.r2{width:88%}.nox-hud-ring.r3{width:62%}.nox-hud-tick.t1{margin-top:-92px}.nox-hud-tick.t2{margin-left:100px}.nox-hud-tick.t3{margin-top:92px}.nox-hud-tick.t4{margin-left:-100px}.nox-hud-readout{font-size:7px}.nox-core-control input{width:52px}}
      @media(prefers-reduced-motion:reduce){.nox-hud-ring{animation:none!important}#corePanel .corecanvas{transition:none}}
      body.reduced .nox-hud-ring{animation:none!important}
    `;
    document.head.appendChild(style);

    const hud = document.createElement("div");
    hud.className = "nox-living-hud";
    hud.setAttribute("aria-hidden", "true");
    hud.innerHTML = '<div class="nox-hud-readout">NOX / FIELD DYNAMICS<span id="noxHudMode">AMBIENT RESONANCE</span></div><div class="nox-hud-ring"></div><div class="nox-hud-ring r2"></div><div class="nox-hud-ring r3"></div><i class="nox-hud-tick t1"></i><i class="nox-hud-tick t2"></i><i class="nox-hud-tick t3"></i><i class="nox-hud-tick t4"></i><div class="nox-hud-scan"></div>';
    panel.insertBefore(hud, canvas);

    const top = panel.querySelector(".coretop");
    const control = document.createElement("label");
    control.className = "nox-core-control";
    control.title = "Adjust holographic overlay intensity";
    control.innerHTML = 'FIELD <input id="noxCoreIntensity" type="range" min="20" max="100" step="5" value="72" aria-label="Holographic field intensity">';
    top?.appendChild(control);
    const slider = control.querySelector("input");
    try { slider.value = localStorage.getItem("nox-core-intensity") || "72"; } catch (_) {}
    const applyIntensity = () => {
      const v = Math.max(20, Math.min(100, Number(slider.value) || 72));
      panel.style.setProperty("--nox-field-opacity", String(v / 100));
      hud.style.opacity = String(.45 + v / 180);
      try { localStorage.setItem("nox-core-intensity", String(v)); } catch (_) {}
    };
    slider.addEventListener("input", applyIntensity);
    applyIntensity();

    const caption = document.getElementById("coreCaption");
    const fps = document.getElementById("fpsLabel");
    const voiceStatus = document.getElementById("voiceStatus");
    const wave = document.getElementById("wave");
    const modeLabel = document.getElementById("noxHudMode");
    const syncState = () => {
      const text = ((caption?.textContent || "") + " " + (voiceStatus?.textContent || "") + " " + (fps?.textContent || "")).toLowerCase();
      let mode = "idle", label = "AMBIENT RESONANCE";
      if (/error|failed|unavailable/.test(text)) { mode = "error"; label = "SIGNAL DEGRADED"; }
      else if (/speaking|tts audio/.test(text)) { mode = "speaking"; label = "OUTPUT RESONANCE"; }
      else if (/listening|mic vad|user voice/.test(text)) { mode = "listening"; label = "INPUT RESONANCE"; }
      else if (/thinking|processing|executing/.test(text)) { mode = "thinking"; label = "NEURAL PROCESSING"; }
      else if (/success|complete|ready/.test(text)) { mode = "success"; label = "SYSTEM SYNCHRONIZED"; }
      panel.dataset.noxState = mode;
      if (modeLabel) modeLabel.textContent = label;
      panel.querySelectorAll(".statechip").forEach(chip => chip.classList.toggle("active", chip.dataset.state === mode || (mode === "idle" && chip.dataset.state === "idle")));
    };
    const observer = new MutationObserver(syncState);
    [caption, fps, voiceStatus].filter(Boolean).forEach(el => observer.observe(el, { childList: true, characterData: true, subtree: true, attributes: true }));
    syncState();

    let raf = 0, disposed = false;
    const animate = () => {
      if (disposed) return;
      if (!document.hidden) {
        let energy = 0;
        if (wave) {
          const bars = [...wave.children];
          for (const bar of bars) {
            const h = parseFloat(bar.style.height) || 0;
            energy = Math.max(energy, Math.max(0, Math.min(1, (h - 3) / 28)));
          }
        }
        panel.style.setProperty("--nox-energy", String(energy));
        hud.style.setProperty("--nox-energy", String(energy));
      }
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && raf) { cancelAnimationFrame(raf); raf = 0; }
      else if (!document.hidden && !disposed && !raf) raf = requestAnimationFrame(animate);
    });
    window.addEventListener("pagehide", () => { disposed = true; if (raf) cancelAnimationFrame(raf); observer.disconnect(); }, { once: true });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();