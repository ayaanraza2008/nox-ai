import React, { useEffect, useRef } from "react";

/**
 * Canvas-rendered holographic core. micLevelRef and ttsLevelRef contain
 * normalized 0..1 levels. Browser speechSynthesis does not expose its rendered
 * audio stream, so TTS animation is explicitly a playback/boundary fallback.
 */
export default function HolographicCore({ mode, micLevelRef, ttsLevelRef, ttsAudioReactiveRef, motionIntensity = 1, userReducedMotion = false }) {
  const canvasRef = useRef(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const reducedMotion = userReducedMotion || (typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
  const pointerRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return undefined;
    let raf = 0;
    let width = 0;
    let height = 0;
    let dpr = 1;
    let rotation = 0;
    let smoothed = 0;
    let statePulse = 0;
    let time = 0;
    let particles = [];
    let lastFrame = 0;
    let previousMode = "";
    let shockwaves = [];

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 1.6);
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const cores = typeof navigator !== "undefined" ? navigator.hardwareConcurrency || 8 : 8;
      // Adaptive density adds depth without thousands of DOM nodes.
      const count = reducedMotion ? 84 : width < 420 ? (cores <= 4 ? 150 : 210)
        : width < 760 ? (cores <= 4 ? 230 : 320) : (cores <= 4 ? 430 : 760);
      particles = Array.from({ length: count }, (_, i) => {
        const z = Math.random() * 2 - 1;
        const a = Math.random() * Math.PI * 2;
        const radius = Math.sqrt(1 - z * z);
        return {
          x: Math.cos(a) * radius,
          y: z,
          z: Math.sin(a) * radius,
          size: 0.55 + Math.random() * 1.35,
          phase: Math.random() * Math.PI * 2,
          hue: Math.random() < 0.56 ? 188 + Math.random() * 30 : 250 + Math.random() * 42
        };
      });
    };

    const draw = (timestamp = 0) => {
      if (document.hidden) { raf = 0; return; }
      const activeMode = modeRef.current;
      // Cap expensive canvas work on high-refresh displays; animation remains smooth.
      if (timestamp - lastFrame < 1000 / (reducedMotion ? 18 : 60)) {
        raf = window.requestAnimationFrame(draw);
        return;
      }
      const delta = lastFrame ? Math.min(2, (timestamp - lastFrame) / 16.67) : 1;
      lastFrame = timestamp;
      // State changes create a single intentional wave; no random fake event pulses.
      if (activeMode !== previousMode) {
        if (["SUCCESS", "ERROR", "USER_LISTENING", "NOX_SPEAKING", "WORKING"].includes(activeMode)) {
          shockwaves.push({ born: time, strength: activeMode === "SUCCESS" ? 1 : activeMode === "ERROR" ? 0.48 : 0.68, tint: activeMode === "ERROR" ? "255, 105, 125" : "112, 218, 255" });
          if (shockwaves.length > 3) shockwaves.shift();
        }
        previousMode = activeMode;
      }
      // The microphone meter is valid in both listening and detected-user-speech states.
      // If permission/metering is unavailable, its zero value leaves the visual calm.
      const sourceLevel = activeMode === "USER_LISTENING" || activeMode === "USER_SPEAKING"
        ? (micLevelRef.current || 0)
        : activeMode === "NOX_SPEAKING"
          ? (ttsLevelRef.current || 0)
          : 0;
      const listening = activeMode === "USER_LISTENING" || activeMode === "USER_SPEAKING";
      const thinking = activeMode === "PROCESSING" || activeMode === "THINKING";
      const working = activeMode === "WORKING";
      const success = activeMode === "SUCCESS";
      const error = activeMode === "ERROR";
      const paused = activeMode === "PAUSED" || activeMode === "INTERRUPTED";
      const target = Math.max(0, Math.min(1, sourceLevel));
      smoothed += (target - smoothed) * (target > smoothed ? 0.24 : 0.075);
      // Quiet, restrained motion while thinking; a stronger orbit while executing.
      const targetStatePulse = thinking ? (0.12 + 0.08 * (0.5 + 0.5 * Math.sin(time * 2.2)))
        : working ? (0.22 + 0.12 * (0.5 + 0.5 * Math.sin(time * 3.1)))
          : listening ? 0.12 + smoothed * 0.28
            : success ? (0.38 + 0.24 * (0.5 + 0.5 * Math.sin(time * 5.2)))
              : error ? 0.06 : 0;
      // Ease state changes in and out instead of snapping between visual presets.
      statePulse += (targetStatePulse - statePulse) * (targetStatePulse > statePulse ? 0.045 : 0.025);
      const energy = Math.max(smoothed, statePulse);
      const idleMotion = reducedMotion ? 0.12 : Math.max(0.32, motionIntensity);
      // A paused/error core settles down; active work gets a restrained speed lift.
      const speed = (paused ? 0.00008 : 0.0021 + energy * 0.018 + (thinking ? 0.002 : working ? 0.005 : listening ? 0.0008 : 0)) * idleMotion;
      rotation += speed * delta;
      time += (reducedMotion ? 0.004 : 0.011 + energy * 0.03) * delta * (paused ? 0.08 : reducedMotion ? 0.35 : Math.max(0.32, motionIntensity));
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width * 0.36, height * 0.42, 132) * (1 + energy * 0.11);
      const glow = ctx.createRadialGradient(cx, cy, radius * 0.04, cx, cy, radius * 1.32);
      const coreTint = error ? "255, 105, 125" : success ? "202, 244, 255" : paused ? "135, 151, 184" : "72, 194, 255";
      glow.addColorStop(0, `rgba(${coreTint}, ${0.07 + energy * 0.16})`);
      glow.addColorStop(0.55, `rgba(120, 72, 255, ${0.035 + energy * 0.07})`);
      glow.addColorStop(1, "rgba(40, 100, 255, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 1.32, 0, Math.PI * 2);
      ctx.fill();

      // State-triggered expanding wavefronts; they decay quickly and never run on a random timer.
      shockwaves = shockwaves.filter((wave) => time - wave.born < 2.1);
      shockwaves.forEach((wave) => {
        const age = Math.max(0, time - wave.born);
        const progress = age / 2.1;
        const waveRadius = radius * (0.32 + progress * 1.08);
        ctx.beginPath();
        ctx.arc(cx, cy, waveRadius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${wave.tint}, ${(1 - progress) * 0.24 * wave.strength})`;
        ctx.lineWidth = 0.7 + (1 - progress) * 1.6 * wave.strength;
        ctx.stroke();
      });

      // Soft radial energy filaments extend from the core and intensify with audio.
      ctx.save();
      ctx.translate(cx, cy);
      const filamentCount = reducedMotion ? 12 : 24;
      for (let i = 0; i < filamentCount; i += 1) {
        const angle = (i / filamentCount) * Math.PI * 2 + rotation * (i % 2 ? 0.28 : -0.18);
        const inner = radius * (0.72 + 0.025 * Math.sin(time + i));
        const outer = radius * (1.03 + energy * (0.18 + 0.12 * Math.sin(time * 1.4 + i)));
        ctx.beginPath();
        ctx.moveTo(Math.cos(angle) * inner, Math.sin(angle) * inner);
        ctx.lineTo(Math.cos(angle) * outer, Math.sin(angle) * outer);
        ctx.strokeStyle = `rgba(104, 198, 255, ${0.035 + energy * 0.16})`;
        ctx.lineWidth = 0.45 + energy * 0.7;
        ctx.stroke();
      }
      ctx.restore();

      const projected = particles.map((p) => {
        const wobble = Math.sin(time + p.phase) * (0.025 + energy * 0.09);
        // Thinking draws particles inward in a slow spiral; working pushes energy outward.
        const spiralScale = listening
          ? 0.84 + 0.16 * (0.5 + 0.5 * Math.sin(time * 1.25 + p.phase))
          : thinking ? 0.82 + 0.18 * (0.5 + 0.5 * Math.sin(time * 1.65 + p.phase))
            : working ? 0.96 + 0.1 * Math.sin(time * 1.2 + p.phase) : paused ? 0.99 : 1;
        const x = (p.x * Math.cos(rotation) - p.z * Math.sin(rotation)) * spiralScale;
        const z = p.x * Math.sin(rotation) + p.z * Math.cos(rotation);
        const perspective = 1.0 / (1.65 - (z + wobble) * 0.42);
        return {
          x: cx + x * radius * perspective + pointerRef.current.x * (reducedMotion ? 0 : 9 * motionIntensity) * perspective,
          y: cy + (p.y + wobble) * radius * spiralScale * perspective + pointerRef.current.y * (reducedMotion ? 0 : 7 * motionIntensity) * perspective,
          z,
          depth: perspective,
          size: p.size * perspective * (1 + energy * 0.65),
          hue: p.hue,
          phase: p.phase
        };
      }).sort((a, b) => a.z - b.z);

      const linkDistance = width < 420 ? 20 : 24;
      // Spatial buckets avoid comparing every particle with every other particle.
      // This keeps the lattice detailed without making canvas work quadratic.
      const cellSize = linkDistance;
      const buckets = new Map();
      projected.forEach((point, index) => {
        point.index = index;
        if (point.z < -0.2) return;
        const gx = Math.floor(point.x / cellSize);
        const gy = Math.floor(point.y / cellSize);
        const key = `${gx},${gy}`;
        if (!buckets.has(key)) buckets.set(key, []);
        buckets.get(key).push(point);
      });
      for (const a of projected) {
        if (a.z < -0.35) continue;
        const gx = Math.floor(a.x / cellSize);
        const gy = Math.floor(a.y / cellSize);
        const nearby = [];
        for (let ox = -1; ox <= 1; ox += 1) {
          for (let oy = -1; oy <= 1; oy += 1) {
            const cell = buckets.get(`${gx + ox},${gy + oy}`) || [];
            for (const b of cell) {
              if (b.index <= a.index) continue;
              const dist = Math.hypot(a.x - b.x, a.y - b.y);
              if (dist < linkDistance) nearby.push({ b, dist });
            }
          }
        }
        nearby.sort((u, v) => u.dist - v.dist);
        nearby.slice(0, 3).forEach(({ b, dist }) => {
          ctx.strokeStyle = `rgba(91, 174, 255, ${(1 - dist / linkDistance) * (0.08 + energy * 0.22)})`;
          ctx.lineWidth = 0.45 + energy * 0.35;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        });
      }

      projected.forEach((p) => {
        const alpha = Math.max(0.16, Math.min(0.95, 0.28 + (p.z + 1) * 0.27 + energy * 0.28));
        ctx.fillStyle = `hsla(${p.hue}, 100%, ${68 + energy * 18}%, ${alpha})`;
        ctx.shadowBlur = 4 + energy * 11;
        ctx.shadowColor = `hsla(${p.hue}, 100%, 68%, ${0.35 + energy * 0.4})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.shadowBlur = 0;

      // A compact inner pulse makes thinking/execution visible without faking speech.
      const corePulse = 0.72 + energy * 0.18 + (thinking || working ? 0.04 * Math.sin(time * (working ? 3.1 : 2.1)) : 0);
      const coreGlow = ctx.createRadialGradient(cx, cy, radius * 0.025, cx, cy, radius * 0.58);
      coreGlow.addColorStop(0, `rgba(${coreTint}, ${0.16 + energy * 0.12})`);
      coreGlow.addColorStop(0.45, `rgba(105, 115, 255, ${0.08 + energy * 0.08})`);
      coreGlow.addColorStop(1, "rgba(30, 40, 90, 0)");
      ctx.fillStyle = coreGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * corePulse * 0.58, 0, Math.PI * 2);
      ctx.fill();

      // Layered singularity nucleus: cool-white center, violet corona and fine contours.
      const nucleusRadius = radius * (0.105 + energy * 0.025) * corePulse;
      const nucleus = ctx.createRadialGradient(
        cx - nucleusRadius * 0.22, cy - nucleusRadius * 0.28, nucleusRadius * 0.025,
        cx, cy, nucleusRadius * 2.7
      );
      nucleus.addColorStop(0, `rgba(235, 253, 255, ${0.9 + energy * 0.08})`);
      nucleus.addColorStop(0.12, `rgba(124, 228, 255, ${0.82 + energy * 0.12})`);
      nucleus.addColorStop(0.38, `rgba(91, 129, 255, ${0.28 + energy * 0.18})`);
      nucleus.addColorStop(0.72, `rgba(150, 92, 255, ${0.12 + energy * 0.12})`);
      nucleus.addColorStop(1, "rgba(80, 150, 255, 0)");
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = nucleus;
      ctx.beginPath();
      ctx.arc(cx, cy, nucleusRadius * 2.7, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = `rgba(202, 246, 255, ${0.24 + energy * 0.28})`;
      ctx.lineWidth = 0.65;
      ctx.beginPath();
      ctx.ellipse(cx, cy, nucleusRadius * 1.8, nucleusRadius * 0.72, time * 0.18, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.ellipse(cx, cy, nucleusRadius * 1.42, nucleusRadius * 0.9, -time * 0.13, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // A thin event horizon gives the nucleus a defined silhouette and depth.
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      const horizonPulse = 1 + Math.sin(time * 1.4) * 0.025 + energy * 0.04;
      const horizon = ctx.createRadialGradient(cx, cy, radius * 0.18, cx, cy, radius * 0.52 * horizonPulse);
      horizon.addColorStop(0, "rgba(54, 102, 220, 0)");
      horizon.addColorStop(0.66, `rgba(74, 174, 255, ${0.035 + energy * 0.07})`);
      horizon.addColorStop(0.82, `rgba(173, 133, 255, ${0.07 + energy * 0.08})`);
      horizon.addColorStop(1, "rgba(80, 120, 255, 0)");
      ctx.fillStyle = horizon;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 0.52 * horizonPulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // Delicate rotating orbital arcs add depth without replacing the particle field.
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-rotation * 0.55);
      ctx.strokeStyle = `rgba(${coreTint}, ${0.12 + energy * 0.2})`;
      ctx.lineWidth = 0.7;
      ctx.beginPath();
      ctx.ellipse(0, 0, radius * 1.04, radius * 0.29, 0, 0.1, Math.PI * 1.9);
      ctx.stroke();
      ctx.strokeStyle = `rgba(177, 108, 255, ${0.1 + energy * 0.18})`;
      ctx.beginPath();
      ctx.ellipse(0, 0, radius * 0.88, radius * 0.37, 0.95, 0.3, Math.PI * 1.82);
      ctx.stroke();
      ctx.rotate(rotation * 0.82);
      ctx.strokeStyle = `rgba(105, 226, 255, ${0.07 + energy * 0.17})`;
      ctx.beginPath();
      ctx.ellipse(0, 0, radius * 1.12, radius * 0.22, -0.32, 0.25, Math.PI * 1.65);
      ctx.stroke();
      ctx.rotate(-rotation * 0.34);
      ctx.strokeStyle = `rgba(194, 184, 255, ${0.035 + energy * 0.11})`;
      ctx.lineWidth = 0.55;
      ctx.beginPath();
      ctx.ellipse(0, 0, radius * 0.76, radius * 0.48, 0.42, 0.35, Math.PI * 1.75);
      ctx.stroke();
      // Tiny orbiting nodes create depth cues without obscuring the central particle sphere.
      for (let i = 0; i < 4; i += 1) {
        const angle = time * (0.32 + i * 0.055) + i * Math.PI / 2;
        const ox = Math.cos(angle) * radius * (0.9 + i * 0.045);
        const oy = Math.sin(angle * 0.8 + i) * radius * (0.24 + i * 0.035);
        ctx.beginPath();
        ctx.arc(ox, oy, 1.1 + energy * 1.4, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(145, 224, 255, ${0.38 + energy * 0.35})`;
        ctx.fill();
      }
      ctx.restore();

      // Flowing plasma ribbons: curved, broken bands imply a 3D toroidal field.
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      const ribbonCount = reducedMotion ? 2 : 4;
      for (let r = 0; r < ribbonCount; r += 1) {
        const phase = time * (0.22 + r * 0.035) * (paused ? 0.12 : 1) + r * Math.PI / 2;
        const rx = radius * (0.58 + r * 0.105);
        const ry = radius * (0.16 + r * 0.028);
        ctx.beginPath();
        for (let step = 0; step <= 84; step += 1) {
          const t = step / 84 * Math.PI * 2;
          const wobble = Math.sin(t * 3 + phase) * radius * (0.012 + energy * 0.014);
          const x = cx + Math.cos(t + phase * 0.12) * rx;
          const y = cy + Math.sin(t + phase) * ry + wobble;
          if (step === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        const ribbon = ctx.createLinearGradient(cx - rx, cy - ry, cx + rx, cy + ry);
        ribbon.addColorStop(0, "rgba(95, 120, 255, 0.015)");
        ribbon.addColorStop(0.34, `rgba(106, 221, 255, ${0.055 + energy * 0.06})`);
        ribbon.addColorStop(0.62, `rgba(188, 143, 255, ${0.045 + energy * 0.05})`);
        ribbon.addColorStop(1, "rgba(95, 120, 255, 0.015)");
        ctx.strokeStyle = ribbon;
        ctx.lineWidth = 0.55 + energy * 0.55;
        ctx.stroke();
      }
      // Two fine meridian arcs cross the field like a suspended magnetic cage.
      ctx.strokeStyle = `rgba(151, 218, 255, ${0.045 + energy * 0.055})`;
      ctx.lineWidth = 0.55;
      ctx.beginPath();
      ctx.ellipse(cx, cy, radius * 0.43, radius * 0.98, rotation * 0.26, -Math.PI * 0.48, Math.PI * 0.48);
      ctx.stroke();
      ctx.beginPath();
      ctx.ellipse(cx, cy, radius * 0.43, radius * 0.98, -rotation * 0.22, Math.PI * 0.52, Math.PI * 1.48);
      ctx.stroke();
      ctx.restore();

      // Bright couriers travel on elliptical paths with short, fading light trails.
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      for (let i = 0; i < 3; i += 1) {
        const angle = time * (0.58 + i * 0.17) + i * (Math.PI * 2 / 3);
        const orbitX = radius * (0.82 + i * 0.12);
        const orbitY = radius * (0.22 + i * 0.055);
        const px = cx + Math.cos(angle) * orbitX;
        const py = cy + Math.sin(angle * 0.86 + i) * orbitY;
        const tailX = px - Math.cos(angle) * (7 + energy * 9);
        const tailY = py - Math.sin(angle * 0.86 + i) * (3 + energy * 5);
        const trail = ctx.createLinearGradient(tailX, tailY, px, py);
        trail.addColorStop(0, "rgba(104, 196, 255, 0)");
        trail.addColorStop(1, `rgba(204, 247, 255, ${0.42 + energy * 0.35})`);
        ctx.strokeStyle = trail;
        ctx.lineWidth = 0.8 + energy * 0.5;
        ctx.beginPath();
        ctx.moveTo(tailX, tailY);
        ctx.lineTo(px, py);
        ctx.stroke();
        ctx.fillStyle = `rgba(225, 251, 255, ${0.65 + energy * 0.3})`;
        ctx.shadowColor = "rgba(91, 216, 255, 0.8)";
        ctx.shadowBlur = 5 + energy * 7;
        ctx.beginPath();
        ctx.arc(px, py, 1.05 + energy * 0.75, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
      ctx.restore();

      // The equalizer remains nearly still in silence and follows the same energy.
      const bars = 39;
      const gap = 3;
      const barWidth = Math.max(2, Math.min(4, (width * 0.74) / bars - gap));
      const totalWidth = bars * (barWidth + gap) - gap;
      const startX = cx - totalWidth / 2;
      const baseY = height - 9;
      for (let i = 0; i < bars; i += 1) {
        const wave = Math.abs(Math.sin(time * 1.8 + i * 0.47) * Math.cos(time * 0.75 + i * 0.19));
        const heightPx = 1.3 + (energy > 0.025 ? wave * energy * 21 : 0);
        ctx.fillStyle = `rgba(${energy > 0.025 ? "97, 185, 255" : "99, 112, 146"}, ${energy > 0.025 ? 0.3 + energy * 0.55 : 0.17})`;
        ctx.beginPath();
        ctx.roundRect(startX + i * (barWidth + gap), baseY - heightPx, barWidth, heightPx, 2);
        ctx.fill();
      }

      canvas.dataset.mode = activeMode;
      canvas.dataset.audioSource = activeMode === "USER_SPEAKING" ? "microphone-amplitude"
        : activeMode === "NOX_SPEAKING" ? (ttsAudioReactiveRef?.current ? "neural-tts-measured-rms" : "browser-speech-estimated-fallback") : "none";
      canvas.dataset.activity = thinking ? "thinking-animation" : working ? "working-animation"
        : error ? "error-state" : paused ? "paused" : listening ? "listening" : success ? "success" : "idle";
      raf = window.requestAnimationFrame(draw);
    };

    resize();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    observer?.observe(canvas);
    if (!observer) window.addEventListener("resize", resize, { passive: true });
    const onPointerMove = (event) => {
      if (reducedMotion) return;
      pointerRef.current = {
        x: (event.clientX / Math.max(1, window.innerWidth) - 0.5) * 2,
        y: (event.clientY / Math.max(1, window.innerHeight) - 0.5) * 2
      };
    };
    const onVisibilityChange = () => {
      if (document.hidden) {
        if (raf) window.cancelAnimationFrame(raf);
        raf = 0;
      } else if (!raf) {
        raf = window.requestAnimationFrame(draw);
      }
    };
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("visibilitychange", onVisibilityChange);
    raf = window.requestAnimationFrame(draw);
    return () => {
      if (raf) window.cancelAnimationFrame(raf);
      observer?.disconnect();
      if (!observer) window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [micLevelRef, ttsLevelRef, reducedMotion, motionIntensity]);

  const label = mode === "USER_SPEAKING" ? "MIC AUDIO REACTIVE"
    : mode === "NOX_SPEAKING" ? (ttsAudioReactiveRef?.current ? "LIVE AUDIO REACTIVE" : "VOICE · FALLBACK MODE")
      : mode === "USER_LISTENING" ? "LISTENING"
        : mode === "PROCESSING" || mode === "THINKING" ? "THINKING"
          : mode === "WORKING" ? "EXECUTING TASK"
            : mode === "SUCCESS" ? "TASK COMPLETE"
              : mode === "ERROR" ? "VOICE ISSUE"
        : mode === "PAUSED" || mode === "INTERRUPTED" ? "PAUSED"
          : "CORE IDLE";

  return <div className={`holo-stage holo-${mode.toLowerCase().replaceAll("_", "-")}`} aria-label={`NOX holographic core: ${label}`}>
    <canvas className="holo-canvas" ref={canvasRef} aria-hidden="true" />
    <div className="holo-energy-shells" aria-hidden="true"><span /><span /><span /><i /><i /></div>
    <div className="holo-scan-plane" aria-hidden="true" />
    <div className="holo-center-mark"><span /><i /></div>
    <div className="holo-caption"><i /> NOX CORE <small>{label}</small></div>
  </div>;
}
