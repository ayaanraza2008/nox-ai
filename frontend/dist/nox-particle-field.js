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
    const draw = (now) => {
      if (disposed) return;
      raf = 0;
      if (document.hidden || reduce?.matches || document.body.classList.contains("reduced")) {
        ctx.clearRect(0,0,w,h);
        if (!document.hidden && !disposed) raf = requestAnimationFrame(draw);
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

      for(const p of particles){
        p.px=p.x;p.py=p.y;
        p.angle += p.speed*dt*(1+energy*2.8);
        const wobble=Math.sin(now*.00045*p.drift+p.seed)*min*.012;
        const radius=min*p.orbit*(1+energy*.19)+wobble;
        const perspective=.62+p.depth*.52;
        p.x=cx+Math.cos(p.angle+phase*.018)*radius*perspective;
        p.y=cy+Math.sin(p.angle+phase*.018)*radius*.73*perspective + Math.sin(now*.00055+p.seed)*min*.014;
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
      if(energy>.34){
        const radius=min*(.18+((now*.00028)%1)*.3);
        ctx.beginPath();ctx.ellipse(cx,cy,radius,radius*.72,phase*.08,0,Math.PI*2);
        ctx.strokeStyle="rgba(117,230,255,"+(.19*energy)+")";ctx.lineWidth=1;ctx.stroke();
      }
      if(!document.hidden && !disposed) raf=requestAnimationFrame(draw);
    };
    const visibility = () => {
      if(document.hidden){if(raf)cancelAnimationFrame(raf);raf=0;last=0;}
      else if(!raf && !disposed) raf=requestAnimationFrame(draw);
    };
    document.addEventListener("visibilitychange",visibility);
    window.addEventListener("resize",resize,{passive:true});
    window.addEventListener("pagehide",()=>{disposed=true;if(raf)cancelAnimationFrame(raf);window.removeEventListener("nox:core-frame",frameState);document.removeEventListener("visibilitychange",visibility);},{once:true});
    resize();
    if(!reduce?.matches) raf=requestAnimationFrame(draw);
  };
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();
})();