import React, { useEffect, useRef, useState } from "react";
import {
  Activity, AudioLines, Bot, ChevronRight, Clock3, Command, Grip, Send,
  Maximize2, Minimize2, Mic, Pin, PinOff, RotateCcw, ShieldCheck, Sparkles,
  X, Zap
} from "lucide-react";
import HolographicCore from "./HolographicCore.jsx";

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function readStored(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    return value ?? fallback;
  } catch {
    return fallback;
  }
}

function FloatingPanel({
  id, title, eyebrow, subtitle, children, className = "", position = { x: 0, y: 0 },
  pinned, minimized, maximized, onDragStart, onDragMove, onDragEnd, onPin, onMinimize,
  onMaximize, onClose
}) {
  return <article
    className={"spatial-panel spatial-panel-" + id + " " + className + (minimized ? " is-minimized" : "") + (maximized ? " is-maximized" : "")}
    style={{ "--panel-x": position.x + "px", "--panel-y": position.y + "px" }}
    aria-label={title}
  >
    <header className="spatial-panel-header"
      onPointerDown={(event) => onDragStart(event, id, position, pinned)}
      onPointerMove={onDragMove}
      onPointerUp={onDragEnd}
      onPointerCancel={onDragEnd}
      title={pinned ? "Unpin this panel to move it" : "Drag to reposition"}
    >
      <span className="spatial-drag-grip" aria-hidden="true"><Grip size={13} /></span>
      <div className="spatial-panel-heading">
        {eyebrow && <small>{eyebrow}</small>}
        <b>{title}</b>
        {subtitle && <span>{subtitle}</span>}
      </div>
      <div className="spatial-panel-actions">
        <button type="button" aria-label={pinned ? "Unpin panel" : "Pin panel"} title={pinned ? "Unpin panel" : "Pin panel"} onClick={() => onPin(id)}>{pinned ? <Pin size={13} /> : <PinOff size={13} />}</button>
        <button type="button" aria-label={minimized ? "Restore panel" : "Minimize panel"} title={minimized ? "Restore panel" : "Minimize panel"} onClick={() => onMinimize(id)}>{minimized ? <Maximize2 size={13} /> : <Minimize2 size={13} />}</button>
        <button type="button" aria-label={maximized ? "Return panel to layout" : "Expand panel"} title={maximized ? "Return to layout" : "Expand panel"} onClick={() => onMaximize(id)}>{maximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />}</button>
        <button type="button" aria-label={"Hide " + title + " panel"} title="Hide panel (restore below)" onClick={() => onClose(id)}><X size={13} /></button>
      </div>
    </header>
    {!minimized && <div className="spatial-panel-body">{children}</div>}
  </article>;
}

export default function SpatialDashboard({
  status, coreMode, busy, micLevelRef, ttsLevelRef, voiceMode, voiceMuted, voiceState,
  voiceTranscript, chatHistory, currentChatId, onNewChat, onOpenChat, onJump,
  capabilities, capabilityError, tasks, taskNotice, pairing, input, onInputChange, onSendMessage,
  onStartVoiceMode, onStopVoiceMode, onToggleVoiceMute, onInterruptVoice, onControlTask, onStopGeneration, canStopGeneration
}) {
  const [clock, setClock] = useState(() => new Date());
  const [positions, setPositions] = useState(() => readStored("nox-spatial-panel-positions", {}));
  const [pinned, setPinned] = useState(() => readStored("nox-spatial-panel-pinned", []));
  const [minimized, setMinimized] = useState(() => readStored("nox-spatial-panel-minimized", []));
  const [hidden, setHidden] = useState(() => readStored("nox-spatial-panel-hidden", []));
  const [maximized, setMaximized] = useState("");
  const [motionIntensity, setMotionIntensity] = useState(() => {
    try { return Number(localStorage.getItem("nox-motion-intensity") || "0.8"); } catch { return 0.8; }
  });
  const [reducedMotion, setReducedMotion] = useState(() => {
    try { return localStorage.getItem("nox-reduced-motion") === "true"; } catch { return false; }
  });
  const dragRef = useRef(null);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => { try { localStorage.setItem("nox-spatial-panel-positions", JSON.stringify(positions)); } catch {} }, [positions]);
  useEffect(() => { try { localStorage.setItem("nox-spatial-panel-pinned", JSON.stringify(pinned)); } catch {} }, [pinned]);
  useEffect(() => { try { localStorage.setItem("nox-spatial-panel-minimized", JSON.stringify(minimized)); } catch {} }, [minimized]);
  useEffect(() => { try { localStorage.setItem("nox-spatial-panel-hidden", JSON.stringify(hidden)); } catch {} }, [hidden]);
  useEffect(() => {
    try { localStorage.setItem("nox-motion-preset", motionPreset); } catch {}
    document.documentElement.dataset.noxMotion = motionPreset;
    document.documentElement.style.setProperty("--nox-motion-scale", motionPreset === "off" ? "0" : motionPreset === "enhanced" ? "1.25" : "0.7");
  }, [motionPreset]);
  useEffect(() => { try { localStorage.setItem("nox-reduced-motion", String(reducedMotion)); } catch {} }, [reducedMotion]);

  const dragStart = (event, id, position, isPinned) => {
    if (isPinned || event.target.closest("button") || event.button !== 0) return;
    dragRef.current = { id, x: event.clientX, y: event.clientY, originX: position.x || 0, originY: position.y || 0 };
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch {}
  };
  const dragMove = (event) => {
    const drag = dragRef.current;
    if (!drag) return;
    setPositions((old) => ({
      ...old,
      [drag.id]: {
        x: clamp(drag.originX + event.clientX - drag.x, -150, 150),
        y: clamp(drag.originY + event.clientY - drag.y, -90, 90)
      }
    }));
  };
  const dragEnd = () => { dragRef.current = null; };
  const toggleArrayValue = (setter, id) => setter((old) => old.includes(id) ? old.filter((item) => item !== id) : [...old, id]);
  const panelProps = (id) => ({
    position: positions[id] || { x: 0, y: 0 },
    pinned: pinned.includes(id),
    minimized: minimized.includes(id),
    maximized: maximized === id,
    onDragStart: dragStart,
    onDragMove: dragMove,
    onDragEnd: dragEnd,
    onPin: (key) => toggleArrayValue(setPinned, key),
    onMinimize: (key) => toggleArrayValue(setMinimized, key),
    onMaximize: (key) => setMaximized((old) => old === key ? "" : key),
    onClose: (key) => { setHidden((old) => old.includes(key) ? old : [...old, key]); setMaximized((old) => old === key ? "" : old); }
  });
  const liveTasks = tasks.filter((task) => ["queued", "running", "paused"].includes(task.status));
  const readyCount = capabilities?.modules?.filter((module) => module.status === "ready").length;
  const linkedDeviceOnline = pairing?.devices?.some((device) => { const seen = Date.parse(device.last_seen || ""); return Number.isFinite(seen) && Date.now() - seen >= 0 && Date.now() - seen < 30000 && !device.disconnected; });
  const dashboardTasks = [...liveTasks, ...tasks.filter((task) => !liveTasks.some((active) => active.id === task.id))].slice(0, 3);
  const modeLabel = voiceMode
    ? (voiceMuted ? "MICROPHONE MUTED" : ({ connecting: "CONNECTING", listening: "LISTENING", thinking: "THINKING", speaking: "SPEAKING", interrupted: "INTERRUPTED", error: "VOICE ERROR" }[voiceState] || "VOICE ACTIVE"))
    : busy ? "THINKING"
      : liveTasks.some((task) => task.status === "running") ? "WORKING"
        : status.includes("FAILED") || status.includes("UNAVAILABLE") ? "ATTENTION NEEDED" : "IDLE";
  const recentlyCompleted = tasks.some((task) => task.status === "completed" && Number.isFinite(Date.parse(task.updated_at || "")) && Date.now() - Date.parse(task.updated_at) < 2600);
  const audioOrErrorMode = ["NOX_SPEAKING", "USER_SPEAKING", "USER_LISTENING", "ERROR"].includes(coreMode);
  const coreVisualMode = audioOrErrorMode ? coreMode : busy ? "PROCESSING" : liveTasks.some((task) => task.status === "running") ? "WORKING" : recentlyCompleted ? "SUCCESS" : coreMode;
  const hiddenCount = hidden.length;

  return <section className={"spatial-dashboard" + (reducedMotion ? " motion-reduced" : "")} aria-label="NOX spatial command center">
    <div className="spatial-ambient" aria-hidden="true"><span /><span /><span /></div>
    <div className="spatial-deck-heading">
      <div><span className="spatial-kicker"><i /> HOLOGRAPHIC COMMAND DECK</span><h2>Systems <em>in motion.</em></h2><p>One intelligence. Every active workspace.</p></div>
      <div className="spatial-deck-tools">
        <div className="spatial-clock"><Clock3 size={14} /><span>{clock.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span><small>{clock.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</small></div>
        <div className="spatial-motion-control"><span>MOTION</span><div className="motion-preset-group" role="group" aria-label="Motion intensity">{[{ id: "off", label: "Off" }, { id: "subtle", label: "Subtle" }, { id: "enhanced", label: "Enhanced" }].map((preset) => <button key={preset.id} type="button" className={motionPreset === preset.id ? "active" : ""} aria-pressed={motionPreset === preset.id} onClick={() => setMotionPreset(preset.id)}>{preset.label}</button>)}</div></div>
        <button type="button" className={"spatial-motion-toggle" + (reducedMotion ? " active" : "")} onClick={() => setReducedMotion((old) => !old)} aria-pressed={reducedMotion} title="Toggle reduced motion"><Activity size={14} /> {reducedMotion ? "REDUCED" : "MOTION ON"}</button>
      </div>
    </div>

    <div className="spatial-grid">
      {!hidden.includes("system") && <FloatingPanel id="system" title="System telemetry" eyebrow="LIVE STATUS" subtitle="Signals from NOX services" className="spatial-grid-system" {...panelProps("system")}>
        <div className="spatial-status-row"><span className={"spatial-status-led " + (modeLabel.includes("ATTENTION") || voiceState === "error" ? "is-warning" : "is-live")} /><div><b>{modeLabel}</b><small>{status}</small></div><span className="spatial-live-pill">{voiceMode ? "VOICE" : "CORE"}</span></div>
        <div className="spatial-metric-grid">
          <div><small>AI MODULES READY</small><b>{capabilityError ? "—" : readyCount ?? "…"}</b></div>
          <div><small>ACTIVE TASKS</small><b>{liveTasks.length}</b></div>
          <div><small>DEVICE LINK</small><b>{linkedDeviceOnline ? "ONLINE" : pairing ? "PAIRED" : "LOCAL"}</b></div>
        </div>
        <div className="spatial-system-foot"><span><span className="spatial-status-led is-live" /> Browser session</span><span>{capabilityError ? "CAPABILITIES OFFLINE" : capabilities ? "CAPABILITIES SYNCED" : "SYNCING…"}</span></div>
      </FloatingPanel>}

      {!hidden.includes("workspace") && <FloatingPanel id="workspace" title="Workspace" eyebrow="QUICK ACCESS" subtitle="Navigate active NOX tools" className="spatial-grid-workspace" {...panelProps("workspace")}>
        <button type="button" className="spatial-nav-action" onClick={onNewChat}><span><Sparkles size={15} /></span><div><b>New conversation</b><small>Start a clean context</small></div><ChevronRight size={14} /></button>
        <button type="button" className="spatial-nav-action" onClick={() => onJump("chat-panel")}><span><AudioLines size={15} /></span><div><b>Conversation</b><small>Text and voice interface</small></div><ChevronRight size={14} /></button>
        <button type="button" className="spatial-nav-action" onClick={() => onJump("task-panel")}><span><Command size={15} /></span><div><b>Task orchestrator</b><small>Real queue and execution logs</small></div><ChevronRight size={14} /></button>
        <button type="button" className="spatial-nav-action" onClick={() => onJump("capability-panel")}><span><Zap size={15} /></span><div><b>Capabilities</b><small>Provider and tool availability</small></div><ChevronRight size={14} /></button>
        <div className="spatial-history-heading"><span>RECENT CONVERSATIONS</span><button type="button" onClick={() => onJump("chat-panel")}>OPEN ALL</button></div>
        <div className="spatial-history-list">{chatHistory.slice(0, 4).map((chat) => <button type="button" key={chat.id} className={"spatial-history-item" + (chat.id === currentChatId ? " current" : "")} onClick={() => onOpenChat(chat)} title={chat.title}><span /><b>{chat.title || "New conversation"}</b></button>)}{chatHistory.length === 0 && <p>No saved conversations yet.</p>}</div>
      </FloatingPanel>}

      <div className="spatial-core-zone" aria-label="Central living holographic core">
        <div className="spatial-core-halo" aria-hidden="true" />
        <div className="spatial-core-topline"><span><i /> LIVE CORE</span><span>{modeLabel}</span></div>
        <HolographicCore mode={coreVisualMode} micLevelRef={micLevelRef} ttsLevelRef={ttsLevelRef} motionIntensity={reducedMotion || motionPreset === "off" ? 0.12 : motionIntensity} userReducedMotion={reducedMotion || motionPreset === "off"} />
        <div className="spatial-core-footer"><span><Bot size={13} /> NOX NEURAL INTERFACE</span><span>{voiceMode ? "AUDIO LINK ACTIVE" : "STANDING BY"}</span></div>
      </div>

      {!hidden.includes("activity") && <FloatingPanel id="activity" title="Active operations" eyebrow="TASK TELEMETRY" subtitle="Actual task queue · refreshes from backend" className="spatial-grid-activity" {...panelProps("activity")}>
        <div className="spatial-activity-summary"><div><small>IN QUEUE</small><b>{liveTasks.length}</b></div><div><small>COMPLETED</small><b>{tasks.filter((task) => task.status === "completed").length}</b></div><div><small>FAILED</small><b>{tasks.filter((task) => task.status === "failed").length}</b></div><button type="button" onClick={() => onJump("task-panel")}>OPEN QUEUE <ChevronRight size={12} /></button></div>
        {taskNotice && <p className="spatial-notice">{taskNotice}</p>}
        <div className="spatial-task-list">{dashboardTasks.map((task) => <div className="spatial-task-row" key={task.id}><button type="button" className="spatial-task-item" onClick={() => onJump("task-panel")}><span className={"spatial-task-dot task-" + task.status} /><span className="spatial-task-copy"><b>{task.goal}</b><small>{task.status.replaceAll("_", " ").toUpperCase()} · {task.progress || 0}%</small><span className="spatial-task-progress"><i style={{ width: clamp(Number(task.progress) || 0, 0, 100) + "%" }} /></span></span></button>{["queued", "running", "paused"].includes(task.status) && <button type="button" className="spatial-task-cancel" onClick={() => onControlTask(task.id, "cancel")} aria-label={"Cancel task " + task.goal} title="Cancel task"><X size={12} /></button>}</div>)}{tasks.length === 0 && <p className="spatial-empty">No task activity yet. Task state will appear here when work starts.</p>}</div>
      </FloatingPanel>}

      {!hidden.includes("voice") && <FloatingPanel id="voice" title="Voice link" eyebrow="CONVERSATION CONTROL" subtitle="Real browser voice session state" className="spatial-grid-voice" {...panelProps("voice")}>
        <div className="spatial-voice-state"><div className={"spatial-voice-orb " + (voiceMode ? "active " + voiceState : "")}><AudioLines size={18} /></div><div><b>{modeLabel}</b><small>{voiceMode ? voiceTranscript || "Microphone session active." : "Voice mode is stopped; microphone is not requested."}</small></div></div>
        <div className="spatial-voice-controls">{canStopGeneration && <button type="button" className="spatial-stop-generation" onClick={onStopGeneration}><X size={14} /> STOP REPLY</button>}{voiceMode ? <><button type="button" onClick={onToggleVoiceMute} className={voiceMuted ? "active" : ""}><Mic size={14} /> {voiceMuted ? "UNMUTE" : "MUTE"}</button><button type="button" onClick={onInterruptVoice}><Activity size={14} /> INTERRUPT</button><button type="button" onClick={onStopVoiceMode}><X size={14} /> END SESSION</button></> : <button type="button" className="spatial-voice-start" onClick={onStartVoiceMode}><Mic size={15} /> START VOICE MODE</button>}</div>
        <form className="spatial-quick-composer" onSubmit={(event) => { event.preventDefault(); onSendMessage(); }}><input aria-label="Quick message to NOX" value={input} onChange={(event) => onInputChange(event.target.value)} placeholder="Message NOX…" /><button type="submit" disabled={busy || !input.trim()} aria-label="Send message to NOX" title="Send message"><Send size={14} /></button></form>
        <p className="spatial-privacy-note"><ShieldCheck size={12} /> Microphone permission is requested only when Voice Mode starts. Browser speech services may process audio remotely.</p>
      </FloatingPanel>}
    </div>

    {hiddenCount > 0 && <div className="spatial-restore-tray"><span>HIDDEN PANELS</span>{hidden.map((id) => <button type="button" key={id} onClick={() => setHidden((old) => old.filter((item) => item !== id))}><RotateCcw size={12} /> RESTORE {id.toUpperCase()}</button>)}</div>}
    <div className="spatial-deck-foot"><span><span className="spatial-foot-led" /> LIVE DATA · NOT A SIMULATION</span><span>DRAG PANEL HEADERS TO REPOSITION · PIN TO LOCK</span></div>
  </section>;
}
