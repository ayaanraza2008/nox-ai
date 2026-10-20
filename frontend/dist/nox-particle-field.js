(() => {
  "use strict";
  const boot = () => {
    const panel = document.getElementById("corePanel");
    const source = document.getElementById("coreCanvas");
    if (!panel || !source || panel.querySelector(".nox-particle-canvas")) return;

    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const style = document.createElement("style");
    style.textContent = `
      #corePanel{isolation:isolate}
      #corePanel .nox-particle-canvas{position:absolute;z-index:1;pointer-events:none;display:block;mix-blend-mode:screen;opacity:.94}
      #corePanel .corecanvas{position:relative;z-index:0}
      #corePanel .nox-particle-canvas{z-index:1}
      #corePanel .nox-living-hud{z-index:2}
      @media(prefers-reduced-motion:reduce){#corePanel .nox-particle-canvas{display:none}}
      body.reduced #corePanel .nox-particle-canvas{display:none}
    `;
    document.head.appendChild(style);

    const canvas = document.createElement("canvas");
    canvas.className = "nox-particle-canvas";
    canvas.setAttribute("aria-hidden", "true");
    panel.insertBefore(canvas, source.nextSibling);
    const ctx = canvas.getContext("2d", { alpha: true, desynchronized: true });
    if (!ctx) { canvas.remove(); return; }

    const mobile = () => window.innerWidth < 600;
    let w = 1, h = 1, dpr = 1, raf = 0, disposed = false;
    let energy = 0, targetEnergy = 0, mode = "ambient", phase = 0, last = 0;
    let particles = [];
    let pointer = { x: 0, y: 0, active: false };
    let ripple = { x: 0, y: 0, start: -1 };
    const rand = (a,b) => a + Math.random() * (b-a);
    const makeParticle = (initial = false) => ({
      angle: rand(0, Math.PI*2),
      orbit: rand(.18,.52),
      depth: rand(.25,1),
      speed: rand(-.18,.18),
      size: rand(.45,1.65),
      seed: rand(0, Math.PI*2),
      alpha: rand(.15,.65),
      twinkle: rand(.5,2.1),
      drift: rand(.5,1.7),
      x: initial ? rand(0,w) : w/2,
      y: initial ? rand(0,h) : h/2,
      px: 0, py: 0
    });
    const resize = () => {
      const p = panel.getBoundingClientRect();
      const c = source.getBoundingClientRect();
      w = Math.max(1,c.width); h = Math.max(1,c.height);
      dpr = Math.min(window.devicePixelRatio || 1, mobile() ? 1 : 1.35);
      canvas.width = Math.round(w*dpr); canvas.height = Math.round(h*dpr);
      canvas.style.left = (c.left-p.left+panel.scrollLeft) + "px";
      canvas.style.top = (c.top-p.top+panel.scrollTop) + "px";
      canvas.style.width = w + "px"; canvas.style.height = h + "px";
      ctx.setTransform(dpr,0,0,dpr,0,0);
      const count = reduce?.matches || document.body.classList.contains("reduced") ? 0 : mobile() ? 54 : 108;
      particles = Array.from({length:count}, () => makeParticle(true));
    };
    const frameState = (e) => {
      const v = e?.detail || {};
      targetEnergy = Math.max(0,Math.min(1,Number(v.energy)||0));
      mode = String(v.kind && v.kind !== "ambient" ? v.kind : (v.mode || v.kind || "ambient"));
      phase = Number(v.phase) || phase;
    };
    window.addEventListener("nox:core-frame", frameState);
    const pointerMove = (e) => {
      const r = canvas.getBoundingClientRect();
      pointer.x = e.clientX - r.left; pointer.y = e.clientY - r.top; pointer.active = true;
    };
    const pointerLeave = () => { pointer.active = false; };
    const pointerDown = (e) => {
      const r = canvas.getBoundingClientRect();
      ripple = { x: e.clientX - r.left, y: e.clientY - r.top, start: performance.now() };
      targetEnergy = Math.min(1, Math.max(targetEnergy, 0.42));
    };
    canvas.addEventListener("pointermove", pointerMove, { passive: true });
    canvas.addEventListener("pointerleave", pointerLeave, { passive: true });
    canvas.addEventListener("pointerdown", pointerDown, { passive: true });
    const draw = (now) => {
      if (disposed) return;
      raf = 0;
      if (document.hidden || reduce?.matches || document.body.classList.contains("reduced")) {
        ctx.clearRect(0,0,w,h);
        return;
      }
      const dt = Math.min(.04, Math.max(0,(now-(last||now))/1000)); last = now;
      energy += (targetEnergy-energy) * (targetEnergy > energy ? .24 : .08);
      ctx.clearRect(0,0,w,h);
      const cx=w*.5, cy=h*.49, min=Math.min(w,h);
      const listening = mode === "user" || mode === "listening";
      const speaking = mode === "nox" || mode === "speaking";
      const pulse = 1 + Math.sin(now*.00125)*.025 + energy*.15;
      const halo = ctx.createRadialGradient(cx,cy, min*.045,cx,cy,min*(.45+energy*.15));
      halo.addColorStop(0, listening ? "rgba(205,250,255,"+(.045+energy*.12)+")" : "rgba(98,205,255,"+(.035+energy*.11)+")");
      halo.addColorStop(.45, "rgba(123,106,255,"+(.018+energy*.045)+")");
      halo.addColorStop(1,"rgba(0,0,0,0)");
      ctx.fillStyle=halo;ctx.fillRect(0,0,w,h);

      const orbitX=min*.34*pulse, orbitY=min*.22*pulse;
      ctx.save();ctx.translate(cx,cy);
      for(let ring=0;ring<3;ring++){
        ctx.beginPath();
        ctx.ellipse(0,0,orbitX*(.72+ring*.18),orbitY*(.72+ring*.2),phase*.025+ring*1.04,0,Math.PI*2);
        ctx.strokeStyle=ring%2 ? "rgba(157,130,255,"+(.08+energy*.12)+")" : "rgba(91,225,255,"+(.08+energy*.15)+")";
        ctx.lineWidth=ring===1?1:.65;ctx.stroke();
      }
      ctx.restore();

      // Soft volumetric plasma filaments: layered curves respond to the live core energy.
      ctx.save();
      ctx.globalCompositeOperation = "screen";
      const filamentCount = mobile() ? 4 : 7;
      for (let k = 0; k < filamentCount; k++) {
        const a0 = now * (0.00016 + k * 0.000012) * (k % 2 ? -1 : 1) + phase * 0.012 + k * Math.PI * 2 / filamentCount;
        const spread = min * (0.12 + (k % 3) * 0.045 + energy * 0.055);
        const bend = min * (0.055 + energy * 0.07);
        const x1 = cx + Math.cos(a0) * spread;
        const y1 = cy + Math.sin(a0 * 1.18) * spread * 0.72;
        const x2 = cx + Math.cos(a0 + 1.7) * (spread + bend);
        const y2 = cy + Math.sin(a0 + 1.7) * (spread + bend) * 0.72;
        const x3 = cx + Math.cos(a0 + 3.1) * (spread * 0.7);
        const y3 = cy + Math.sin(a0 + 3.1) * spread * 0.52;
        const x4 = cx + Math.cos(a0 + 4.4) * (spread + bend * 0.45);
        const y4 = cy + Math.sin(a0 + 4.4) * (spread + bend * 0.45) * 0.7;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.bezierCurveTo(x2, y2, x3, y3, x4, y4);
        const alpha = 0.055 + energy * 0.18;
        const grad = ctx.createLinearGradient(x1, y1, x4, y4);
        grad.addColorStop(0, "rgba(91,229,255,0)");
        grad.addColorStop(0.35, "rgba(100,220,255," + alpha + ")");
        grad.addColorStop(0.7, "rgba(167,139,255," + (alpha * 0.9) + ")");
        grad.addColorStop(1, "rgba(105,230,255,0)");
        ctx.strokeStyle = grad;
        ctx.lineWidth = 0.7 + energy * 1.3;
        ctx.shadowBlur = 5 + energy * 14;
        ctx.shadowColor = k % 2 ? "#8c82ff" : "#62e8ff";
        ctx.stroke();
      }
      ctx.shadowBlur = 0;
      // Central bloom stays subtle while idle and expands during speech/listening.
      const bloomRadius = min * (0.11 + energy * 0.12);
      const bloom = ctx.createRadialGradient(cx, cy, min * 0.012, cx, cy, bloomRadius);
      bloom.addColorStop(0, "rgba(111,222,255," + (0.045 + energy * 0.16) + ")");
      bloom.addColorStop(0.48, "rgba(133,112,255," + (0.025 + energy * 0.07) + ")");
      bloom.addColorStop(1, "rgba(55,140,255,0)");
      ctx.fillStyle = bloom;
      ctx.fillRect(cx - bloomRadius, cy - bloomRadius, bloomRadius * 2, bloomRadius * 2);
      ctx.restore();

      for(const p of particles){
        p.px=p.x;p.py=p.y;
        p.angle += p.speed*dt*(1+energy*2.8);
        const wobble=Math.sin(now*.00045*p.drift+p.seed)*min*.012;
        const radius=min*p.orbit*(1+energy*.19)+wobble;
        const perspective=.62+p.depth*.52;
        p.x=cx+Math.cos(p.angle+phase*.018)*radius*perspective;
        p.y=cy+Math.sin(p.angle+phase*.018)*radius*.73*perspective + Math.sin(now*.00055+p.seed)*min*.014;
        if (pointer.active) {
          const dx = p.x - pointer.x, dy = p.y - pointer.y, d = Math.hypot(dx,dy) || 1;
          const reach = min * 0.19;
          if (d < reach) { const push = (1 - d / reach) * min * 0.035; p.x += dx / d * push; p.y += dy / d * push; }
        }
      }
      ctx.lineCap="round";
      const maxDist=min*(mobile() ? 0.12 : 0.105);
      for(let i=0;i<particles.length;i++){
        const a=particles[i];
        for(let j=i+1;j<particles.length;j++){
          const b=particles[j],dx=a.x-b.x,dy=a.y-b.y,dist=Math.hypot(dx,dy);
          if(dist<maxDist && ((i+j)%3===0)){
            ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);
            ctx.strokeStyle="rgba(100,210,255,"+((1-dist/maxDist)*(.07+energy*.16))+")";
            ctx.lineWidth=.45;ctx.stroke();
          }
        }
        const flicker=.55+.45*Math.sin(now*.001*p.twinkle+p.seed);
        const radius=p.size*(.8+energy*1.8)*(.75+p.depth*.4);
        ctx.beginPath();ctx.arc(a.x,a.y,radius,0,Math.PI*2);
        ctx.fillStyle= listening ? "rgba(220,252,255,"+(p.alpha*flicker)+")" : speaking ? "rgba(176,157,255,"+(p.alpha*flicker)+")" : (i%4===0 ? "rgba(174,151,255,"+(p.alpha*flicker)+")" : "rgba(103,226,255,"+(p.alpha*flicker)+")");
        ctx.shadowBlur=radius>1.5?7:3;ctx.shadowColor=listening?"#bdfaff":"#6fe8ff";ctx.fill();ctx.shadowBlur=0;
        if(energy>.16 && i%7===0){
          ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(a.x+(a.x-cx)*(.045+energy*.12),a.y+(a.y-cy)*(.045+energy*.12));
          ctx.strokeStyle="rgba(135,231,255,"+(energy*.22)+")";ctx.lineWidth=.7;ctx.stroke();
        }
      }
      if (ripple.start >= 0) {
        const age = (now - ripple.start) / 760;
        if (age < 1) {
          const rr = min * (0.025 + age * 0.22);
          ctx.save(); ctx.globalCompositeOperation = "screen";
          ctx.beginPath(); ctx.arc(ripple.x, ripple.y, rr, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(105,225,255," + ((1-age)*0.48) + ")";
          ctx.lineWidth = 1.2 + (1-age)*1.5; ctx.shadowBlur = 12; ctx.shadowColor = "#6de7ff"; ctx.stroke();
          ctx.beginPath(); ctx.arc(ripple.x, ripple.y, rr*0.72, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(164,135,255," + ((1-age)*0.32) + ")"; ctx.lineWidth = 0.8; ctx.stroke();
          ctx.restore();
        } else ripple.start = -1;
      }
      if(energy>.34){
        const radius=min*(.18+((now*.00028)%1)*.3);
        ctx.beginPath();ctx.ellipse(cx,cy,radius,radius*.72,phase*.08,0,Math.PI*2);
        ctx.strokeStyle="rgba(117,230,255,"+(.19*energy)+")";ctx.lineWidth=1;ctx.stroke();
      }
      if(!document.hidden && !disposed) raf=requestAnimationFrame(draw);
    };
    const visibility = () => {
      if(document.hidden || reduce?.matches || document.body.classList.contains("reduced")){if(raf)cancelAnimationFrame(raf);raf=0;last=0;}
      else if(!raf && !disposed) raf=requestAnimationFrame(draw);
    };
    const motionObserver = new MutationObserver(visibility);
    motionObserver.observe(document.body,{attributes:true,attributeFilter:["class"]});
    reduce?.addEventListener?.("change",visibility);
    document.addEventListener("visibilitychange",visibility);
    window.addEventListener("resize",resize,{passive:true});
    window.addEventListener("pagehide",()=>{disposed=true;if(raf)cancelAnimationFrame(raf);window.removeEventListener("nox:core-frame",frameState);canvas.removeEventListener("pointermove",pointerMove);canvas.removeEventListener("pointerleave",pointerLeave);canvas.removeEventListener("pointerdown",pointerDown);document.removeEventListener("visibilitychange",visibility);reduce?.removeEventListener?.("change",visibility);motionObserver.disconnect();},{once:true});
    resize();
    if(!reduce?.matches && !document.body.classList.contains("reduced")) raf=requestAnimationFrame(draw);
  };
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();
})();