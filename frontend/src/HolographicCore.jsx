import React, { useEffect, useRef } from "react";

/**
 * Canvas-rendered holographic core. micLevelRef and ttsLevelRef contain
 * normalized 0..1 levels. Browser speechSynthesis does not expose its rendered
 * audio stream, so TTS animation is explicitly a playback/boundary fallback.
 */
export default function HolographicCore({ mode, micLevelRef, ttsLevelRef }) {
  const canvasRef = useRef(null);
  const reducedMotion = typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;

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
    let time = 0;
    let particles = [];

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 1.6);
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = reducedMotion ? 220 : (width < 420 ? 340 : 650);
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

    const draw = () => {
      const sourceLevel = mode === "USER_SPEAKING"
        ? (micLevelRef.current || 0)
        : mode === "VAULTAR_SPEAKING"
          ? (ttsLevelRef.current || 0)
          : 0;
      const listening = mode === "USER_LISTENING";
      const target = Math.max(0, Math.min(1, sourceLevel));
      smoothed += (target - smoothed) * (target > smoothed ? 0.24 : 0.075);
      const energy = smoothed;
      const idleMotion = reducedMotion ? 0.15 : 1;
      const speed = (0.0025 + energy * 0.024) * idleMotion;
      rotation += speed;
      time += reducedMotion ? 0.004 : 0.012 + energy * 0.035;
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width * 0.36, height * 0.42, 132) * (1 + energy * 0.11);
      const glow = ctx.createRadialGradient(cx, cy, radius * 0.04, cx, cy, radius * 1.32);
      glow.addColorStop(0, `rgba(72, 194, 255, ${0.07 + energy * 0.13})`);
      glow.addColorStop(0.55, `rgba(120, 72, 255, ${0.035 + energy * 0.07})`);
      glow.addColorStop(1, "rgba(40, 100, 255, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 1.32, 0, Math.PI * 2);
      ctx.fill();

      const projected = particles.map((p) => {
        const wobble = Math.sin(time + p.phase) * (0.025 + energy * 0.09);
        const x = p.x * Math.cos(rotation) - p.z * Math.sin(rotation);
        const z = p.x * Math.sin(rotation) + p.z * Math.cos(rotation);
        const perspective = 1.0 / (1.65 - (z + wobble) * 0.42);
        return {
          x: cx + x * radius * perspective,
          y: cy + (p.y + wobble) * radius * perspective,
          z,
          depth: perspective,
          size: p.size * perspective * (1 + energy * 0.65),
          hue: p.hue,
          phase: p.phase
        };
      }).sort((a, b) => a.z - b.z);

      const linkDistance = width < 420 ? 20 : 24;
      for (let i = 0; i < projected.length; i += 1) {
        const a = projected[i];
        if (a.z < -0.35) continue;
        for (let j = i + 1; j < Math.min(i + 7, projected.length); j += 1) {
          const b = projected[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          if (dist < linkDistance && b.z > -0.2) {
            ctx.strokeStyle = `rgba(91, 174, 255, ${(1 - dist / linkDistance) * (0.08 + energy * 0.22)})`;
            ctx.lineWidth = 0.45 + energy * 0.35;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
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

      // Delicate rotating orbital arcs add depth without replacing the particle field.
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-rotation * 0.55);
      ctx.strokeStyle = `rgba(92, 181, 255, ${0.12 + energy * 0.2})`;
      ctx.lineWidth = 0.7;
      ctx.beginPath();
      ctx.ellipse(0, 0, radius * 1.04, radius * 0.29, 0, 0.1, Math.PI * 1.9);
      ctx.stroke();
      ctx.strokeStyle = `rgba(177, 108, 255, ${0.1 + energy * 0.18})`;
      ctx.beginPath();
      ctx.ellipse(0, 0, radius * 0.88, radius * 0.37, 0.95, 0.3, Math.PI * 1.82);
      ctx.stroke();
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

      canvas.dataset.mode = mode;
      canvas.dataset.audioSource = mode === "USER_SPEAKING" ? "microphone-amplitude"
        : mode === "VAULTAR_SPEAKING" ? "tts-playback-fallback" : "none";
      raf = window.requestAnimationFrame(draw);
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    raf = window.requestAnimationFrame(draw);
    return () => {
      window.cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [mode, micLevelRef, ttsLevelRef, reducedMotion]);

  const label = mode === "USER_SPEAKING" ? "MIC AUDIO REACTIVE"
    : mode === "VAULTAR_SPEAKING" ? "VOICE PLAYBACK · ESTIMATED"
      : mode === "USER_LISTENING" ? "LISTENING"
        : mode === "PROCESSING" ? "PROCESSING"
          : mode === "ERROR" ? "VOICE ISSUE" : "CORE IDLE";

  return <div className={`holo-stage holo-${mode.toLowerCase()}`} aria-label={`NOX holographic core: ${label}`}>
    <canvas className="holo-canvas" ref={canvasRef} aria-hidden="true" />
    <div className="holo-center-mark"><span /></div>
    <div className="holo-caption"><i /> NOX CORE <small>{label}</small></div>
  </div>;
}
