import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, AudioLines, Bot, ChevronDown, Command, Mic, Pause, Play, Send, ShieldCheck, Sparkles, Volume2, VolumeX, XCircle, Zap } from "lucide-react";
import "./style.css";
import HolographicCore from "./HolographicCore.jsx";

function App() {
  const [messages, setMessages] = useState([{ role: "assistant", content: "Systems initialized. I'm NOX. What are we working on today?" }]);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [speakReplies, setSpeakReplies] = useState(true);
  const [status, setStatus] = useState("ALL SYSTEMS READY");
  const [accentColor, setAccentColor] = useState(() => {
    try { return localStorage.getItem("nox-accent-color") || "#ff3e4d"; }
    catch { return "#ff3e4d"; }
  });

  useEffect(() => {
    document.documentElement.style.setProperty("--red", accentColor);
    try { localStorage.setItem("nox-accent-color", accentColor); } catch {}
  }, [accentColor]);
  const [capabilities, setCapabilities] = useState(null);
  const [capabilityError, setCapabilityError] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [taskGoal, setTaskGoal] = useState("");
  const [taskBusy, setTaskBusy] = useState(false);
  const [taskNotice, setTaskNotice] = useState("");
  const endRef = useRef(null);
  const recognitionRef = useRef(null);
  const [coreMode, setCoreMode] = useState("IDLE");
  const micLevelRef = useRef(0);
  const ttsLevelRef = useRef(0);
  const audioContextRef = useRef(null);
  const micStreamRef = useRef(null);
  const meterFrameRef = useRef(0);
  const listeningRef = useRef(false);
  const ttsDecayRef = useRef(0);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  useEffect(() => {
    let active = true;
    fetch("/api/capabilities")
      .then((response) => { if (!response.ok) throw new Error("Capability status unavailable"); return response.json(); })
      .then((data) => { if (active) { setCapabilities(data); setCapabilityError(false); } })
      .catch(() => { if (active) setCapabilityError(true); });
    return () => { active = false; };
  }, []);

  const statusLabel = (value) => ({ ready: "READY", running: "RUNNING", setup_required: "SETUP REQUIRED", limited: "LIMITED", unavailable: "UNAVAILABLE", error: "ERROR" }[value] || "UNKNOWN");
  async function refreshTasks() {
    try {
      const response = await fetch("/api/tasks?limit=20");
      if (!response.ok) throw new Error("Task list unavailable");
      const data = await response.json();
      setTasks(data.tasks || []);
    } catch {
      setTaskNotice("Task API unavailable. Make sure the latest Render deployment is active.");
    }
  }

  useEffect(() => {
    refreshTasks();
    const timer = window.setInterval(refreshTasks, 3000);
    return () => window.clearInterval(timer);
  }, []);

  function resolveWebsiteCommand(rawGoal) {
    const match = rawGoal.trim().match(/^(?:please\s+)?(?:open|launch|visit|go to|browse to|khol|kholo|khul)\s+(.+?)\s*[.!?]*$/i);
    if (!match) return null;
    const target = match[1].trim().replace(/[.!?]+$/, "");
    const knownSites = {
      youtube: "https://www.youtube.com/",
      google: "https://www.google.com/",
      gmail: "https://mail.google.com/",
      github: "https://github.com/",
      instagram: "https://www.instagram.com/",
      facebook: "https://www.facebook.com/",
      whatsapp: "https://web.whatsapp.com/",
      wikipedia: "https://www.wikipedia.org/",
      reddit: "https://www.reddit.com/",
      linkedin: "https://www.linkedin.com/",
      chatgpt: "https://chatgpt.com/",
      render: "https://dashboard.render.com/",
      "google drive": "https://drive.google.com/"
    };
    const key = target.toLowerCase();
    if (knownSites[key]) return { url: knownSites[key], label: target };
    if (/^https?:\/\//i.test(target)) {
      try {
        const url = new URL(target);
        if (url.protocol !== "https:" && url.protocol !== "http:") return null;
        return { url: url.href, label: url.hostname };
      } catch { return null; }
    }
    // Accept an explicit domain only; do not guess URLs for arbitrary app names.
    if (/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}(?::\d{1,5})?(?:[/?#][^\s]*)?$/i.test(target)) {
      try {
        const url = new URL("https://" + target);
        return { url: url.href, label: url.hostname };
      } catch { return null; }
    }
    return null;
  }

  async function submitTask(event) {
    event.preventDefault();
    const goal = taskGoal.trim();
    if (!goal || taskBusy) return;

    // Website navigation runs in the user's own browser after explicit confirmation.
    // A hosted Render worker cannot directly control the user's other apps or desktop.
    const website = resolveWebsiteCommand(goal);
    if (website) {
      const confirmed = window.confirm(`NOX wants to open ${website.label} in a new tab. Continue?`);
      if (!confirmed) {
        setTaskNotice("Website navigation cancelled.");
        return;
      }
      const opened = window.open(website.url, "_blank");
      if (opened) opened.opener = null;
      if (opened) {
        setTaskGoal("");
        setTaskNotice(`Opened ${website.label} in a new browser tab.`);
      } else {
        setTaskNotice("The browser blocked the new tab. Allow pop-ups for this site and try again.");
      }
      return;
    }

    // Android browser companion v2: allowlist Instagram only. Prefer the
    // official Android package intent, with the official HTTPS site as fallback.
    // This requests app launch; Android/browser policy still decides the outcome.
    const openInstagramRequest = /\b(open|launch|start|khol|kholo|khul|chalao)\b|खोल|चला/i.test(goal)
      && /\binstagram\b/i.test(goal);
    if (/Android/i.test(navigator.userAgent) && openInstagramRequest) {
      const confirmed = window.confirm("NOX wants to open the Instagram app or its official website. Continue?");
      if (!confirmed) {
        setTaskNotice("Instagram launch cancelled.");
        return;
      }
      setTaskGoal("");
      setTaskNotice("Requesting Instagram. If the app is installed, Android may open it; otherwise the official website will open.");
      const fallback = encodeURIComponent("https://www.instagram.com/");
      const intentUrl = `intent://instagram.com/#Intent;scheme=https;package=com.instagram.android;S.browser_fallback_url=${fallback};end`;
      // Navigation is initiated directly from the user's confirmed submit action.
      window.location.href = intentUrl;
      return;
    }

    setTaskBusy(true);
    setTaskNotice("");
    try {
      const response = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, language })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create task");
      setTaskGoal("");
      setTaskNotice("Task added to the queue.");
      await refreshTasks();
    } catch (error) {
      setTaskNotice(error.message);
    } finally {
      setTaskBusy(false);
    }
  }

  async function controlTask(taskId, action) {
    try {
      const response = await fetch(`/api/tasks/${taskId}/${action}`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Task action failed");
      setTaskNotice(action === "cancel" ? "Cancellation requested." : action === "pause" ? "Pause requested." : "Task resumed.");
      await refreshTasks();
    } catch (error) {
      setTaskNotice(error.message);
    }
  }


  function getSpeechLanguage(text) {
    if (language === "ur") return "ur-PK";
    if (language === "hi") return "hi-IN";
    if (language === "en") return "en-US";
    // Urdu written in Arabic-derived script
    if (/[\u0600-\u06FF]/.test(text)) return "ur-PK";
    // Hindi written in Devanagari
    if (/[\u0900-\u097F]/.test(text)) return "hi-IN";
    // Hinglish is usually Latin-script Hindi; prefer Hindi voice when available.
    if (language === "hinglish" || /\b(kaise|kya|hai|ho|bhai|mera|tum|nahi|haan|acha|achha|kyun|karna|batao)\b/i.test(text)) return "hi-IN";
    return "en-US";
  }

  function stopMicMeter() {
    if (meterFrameRef.current) cancelAnimationFrame(meterFrameRef.current);
    meterFrameRef.current = 0;
    micLevelRef.current = 0;
    if (micStreamRef.current) micStreamRef.current.getTracks().forEach((track) => track.stop());
    micStreamRef.current = null;
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
  }

  function startMicMeter(stream) {
    stopMicMeter();
    micStreamRef.current = stream;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    const audioContext = new AudioContextClass();
    audioContextRef.current = audioContext;
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.72;
    audioContext.createMediaStreamSource(stream).connect(analyser);
    const samples = new Uint8Array(analyser.fftSize);
    const measure = () => {
      if (audioContextRef.current !== audioContext) return;
      analyser.getByteTimeDomainData(samples);
      let sum = 0;
      for (let i = 0; i < samples.length; i += 1) {
        const sample = (samples[i] - 128) / 128;
        sum += sample * sample;
      }
      const rms = Math.sqrt(sum / samples.length);
      micLevelRef.current = Math.max(0, Math.min(1, (rms - 0.012) * 8));
      if (listeningRef.current) {
        setCoreMode(micLevelRef.current > 0.075 ? "USER_SPEAKING" : "USER_LISTENING");
      }
      meterFrameRef.current = requestAnimationFrame(measure);
    };
    measure();
  }

  useEffect(() => () => {
    listeningRef.current = false;
    recognitionRef.current?.stop();
    stopMicMeter();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    window.clearTimeout(ttsDecayRef.current);
  }, []);

  function speakText(text) {
    if (!("speechSynthesis" in window) || !text?.trim()) {
      setStatus("VOICE NOT SUPPORTED");
      return;
    }
    const synth = window.speechSynthesis;
    synth.cancel();
    window.clearTimeout(ttsDecayRef.current);
    ttsLevelRef.current = 0;
    const utterance = new SpeechSynthesisUtterance(text);
    const lang = getSpeechLanguage(text);
    utterance.lang = lang;
    const chooseVoice = () => {
      const voices = synth.getVoices();
      const prefix = lang.toLowerCase().split("-")[0];
      const matchingVoice = voices.find((voice) => voice.lang?.toLowerCase() === lang.toLowerCase())
        || voices.find((voice) => voice.lang?.toLowerCase().startsWith(prefix));
      if (matchingVoice) utterance.voice = matchingVoice;
      synth.speak(utterance);
    };
    let speechPulseTimer = 0;
    let speechPulsePhase = 0;
    utterance.onstart = () => {
      setCoreMode("NOX_SPEAKING");
      setStatus("AI VOICE ACTIVE");
      // Keep the hologram visibly reactive even on browsers that omit onboundary.
      ttsLevelRef.current = 0.48;
      speechPulseTimer = window.setInterval(() => {
        speechPulsePhase += 0.72;
        ttsLevelRef.current = 0.32 + (0.5 + 0.5 * Math.sin(speechPulsePhase)) * 0.48;
      }, 90);
    };
    utterance.onboundary = () => {
      // speechSynthesis exposes events, not its rendered audio stream; this is a
      // clearly-labelled playback pulse fallback, not true output-amplitude analysis.
      ttsLevelRef.current = 0.42 + Math.random() * 0.28;
      window.clearTimeout(ttsDecayRef.current);
      ttsDecayRef.current = window.setTimeout(() => { ttsLevelRef.current = 0; }, 220);
    };
    utterance.onerror = () => {
      window.clearInterval(speechPulseTimer);
      ttsLevelRef.current = 0;
      setCoreMode("ERROR");
      setStatus("VOICE PLAYBACK ISSUE");
      window.setTimeout(() => setCoreMode("IDLE"), 900);
    };
    utterance.onend = () => {
      window.clearInterval(speechPulseTimer);
      ttsLevelRef.current = 0;
      setCoreMode("IDLE");
      setStatus("AI LINK ACTIVE");
    };
    const voices = synth.getVoices();
    if (voices.length) {
      const prefix = lang.toLowerCase().split("-")[0];
      utterance.voice = voices.find((voice) => voice.lang?.toLowerCase() === lang.toLowerCase())
        || voices.find((voice) => voice.lang?.toLowerCase().startsWith(prefix))
        || null;
      synth.speak(utterance);
    } else {
      // Some mobile browsers load voices asynchronously. Speak only once when
      // the list arrives, with a guarded fallback for browsers that omit the event.
      let spoken = false;
      const speakWhenReady = () => {
        if (spoken) return;
        spoken = true;
        synth.removeEventListener("voiceschanged", speakWhenReady);
        chooseVoice();
      };
      synth.addEventListener("voiceschanged", speakWhenReady, { once: true });
      window.setTimeout(() => {
        if (!synth.getVoices().length) speakWhenReady();
      }, 900);
    }
  }

  async function sendMessage(text = input) {
    const value = text.trim();
    if (!value || busy) return;
    const history = messages.slice(-12).map(({ role, content }) => ({ role, content }));
    setMessages((old) => [...old, { role: "user", content: value }]);
    setInput("");
    setBusy(true);
    setStatus("PROCESSING REQUEST");
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: value, language, history })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Request failed");
      setMessages((old) => [...old, { role: "assistant", content: data.reply, mode: data.mode }]);
      setStatus(data.mode === "ai" ? "AI LINK ACTIVE" : "DEMO MODE");
      if (speakReplies) speakText(data.reply);
    } catch (error) {
      setMessages((old) => [...old, { role: "assistant", content: "Connection error: " + error.message }]);
      setStatus("CONNECTION ISSUE");
    } finally {
      setBusy(false);
    }
  }

  async function toggleMic() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMessages((old) => [...old, { role: "assistant", content: "Speech recognition is not supported by this browser. Try a supported browser or type your message." }]);
      return;
    }
    if (listening) {
      listeningRef.current = false;
      recognitionRef.current?.stop();
      setListening(false);
      stopMicMeter();
      setCoreMode("IDLE");
      return;
    }
    let stream;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone metering is not supported in this browser.");
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      startMicMeter(stream);
    } catch (error) {
      setCoreMode("ERROR");
      setStatus("MICROPHONE UNAVAILABLE");
      setMessages((old) => [...old, { role: "assistant", content: "Microphone access is needed for voice input and live audio-reactive visuals. Check browser microphone permission, then try again." }]);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = language === "hi" ? "hi-IN" : language === "ur" ? "ur-PK" : language === "hinglish" ? "hi-IN" : "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setInput(transcript);
      listeningRef.current = false;
      setListening(false);
      setCoreMode("PROCESSING");
      window.setTimeout(() => setCoreMode("IDLE"), 500);
    };
    recognition.onerror = () => {
      listeningRef.current = false;
      setListening(false);
      stopMicMeter();
      setCoreMode("ERROR");
      window.setTimeout(() => setCoreMode("IDLE"), 900);
    };
    recognition.onend = () => {
      listeningRef.current = false;
      setListening(false);
      stopMicMeter();
      setCoreMode((current) => current === "USER_SPEAKING" || current === "USER_LISTENING" ? "IDLE" : current);
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
      listeningRef.current = true;
      setListening(true);
      setCoreMode("USER_LISTENING");
    } catch (error) {
      stopMicMeter();
      setCoreMode("ERROR");
      setStatus("MICROPHONE START FAILED");
    }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Zap size={20} fill="currentColor" /></div><div><b>NOX<span>AI</span></b><small>PERSONAL INTELLIGENCE</small></div></div>
      <div className="side-label">WORKSPACE</div>
      <button className="nav-item active"><Command size={17} /> Command Center <span className="nav-dot" /></button>
      <button className="nav-item" onClick={() => setMessages([{ role: "assistant", content: "New session started. How can I help?" }])}><Sparkles size={17} /> New session</button>
      <div className="side-bottom"><div className="secure"><ShieldCheck size={17} /><div><b>Private by design</b><small>Keys stay on the server</small></div></div><div className="version">NOX CORE <span>v0.1.0</span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumb">NOX / <span>COMMAND CENTER</span></div><div className="topbar-tools"><label className="accent-picker">ACCENT <select aria-label="Interface accent color" value={accentColor} onChange={(event) => setAccentColor(event.target.value)}><option value="#ff3e4d">Crimson</option><option value="#a78bfa">Violet</option><option value="#38bdf8">Ice blue</option><option value="#34d399">Emerald</option><option value="#fbbf24">Amber</option></select></label><div className="top-status"><i /> {status}</div></div></header>
      <section className="hero"><div className="eyebrow"><span /> PERSONAL AI INTERFACE</div><h1>Think beyond.<br /><em>Move with intent.</em></h1><p>Your space to reason, create, and get things done.</p>
        <div className="core-wrap"><HolographicCore mode={coreMode === "NOX_SPEAKING" ? coreMode : busy ? "PROCESSING" : coreMode} micLevelRef={micLevelRef} ttsLevelRef={ttsLevelRef} /></div>
      </section>
      <section className="capability-panel"><div className="capability-heading"><div><span className="tiny-icon"><ShieldCheck size={16} /></span><b>System Capabilities</b><small>Live backend-reported status · no simulated completion</small></div><button type="button" className="refresh-status" onClick={() => { setCapabilities(null); setCapabilityError(false); fetch("/api/capabilities").then((response) => { if (!response.ok) throw new Error("Status unavailable"); return response.json(); }).then(setCapabilities).catch(() => setCapabilityError(true)); }}>Refresh</button></div>{capabilityError ? <p className="capability-message">Capability status is unavailable. Check that the latest backend deployment has finished.</p> : !capabilities ? <p className="capability-message">Loading verified module status…</p> : <><div className="capability-summary"><span>{capabilities.modules.filter((module) => module.status === "ready").length} READY</span><span>{capabilities.modules.filter((module) => module.status === "limited").length} LIMITED</span><span>{capabilities.modules.filter((module) => module.status === "setup_required").length} SETUP REQUIRED</span></div><div className="capability-grid">{capabilities.modules.map((module) => <article className={"capability-card status-" + module.status} key={module.id}><div className="capability-card-top"><b>{module.name}</b><span>{statusLabel(module.status)}</span></div><p>{module.detail}</p></article>)}</div></>}</section>

      <section className="task-panel"><div className="task-panel-heading"><div><span className="tiny-icon"><Activity size={16} /></span><b>Task Orchestrator</b><small>Queued AI tasks · progress, events and controls</small></div><button type="button" className="refresh-status" onClick={refreshTasks}>Refresh</button></div>
        <form className="task-create" onSubmit={submitTask}><textarea value={taskGoal} onChange={(e) => setTaskGoal(e.target.value)} maxLength={6000} placeholder="Describe a task for NOX… e.g. create a step-by-step plan for my project" aria-label="Task goal" /><button type="submit" disabled={taskBusy || taskGoal.trim().length < 3}><Play size={15} /> {taskBusy ? "Adding…" : "Run task"}</button></form>
        <p className="task-safety-note">Website commands can open supported sites in a new tab after confirmation. Other queued tasks currently generate AI results only; desktop control and multi-step website interaction require additional connected tools and a local companion.</p>
        {taskNotice && <p className="task-notice" role="status">{taskNotice}</p>}
        <div className="task-list">{tasks.length === 0 ? <p className="capability-message">No tasks yet. Create one above to test the queue.</p> : tasks.slice(0,8).map((task) => <article className="task-row" key={task.id}><div className="task-row-main"><div className="task-row-title"><b>{task.goal}</b><span className={"task-status task-" + task.status}>{task.status.replace("_"," ").toUpperCase()}</span></div><div className="task-progress"><span style={{width: task.progress + "%"}} /></div><div className="task-meta"><span>{task.progress}% · {task.attempts} attempt(s)</span><span>{new Date(task.updated_at).toLocaleTimeString()}</span></div>{task.error && <p className="task-error">{task.error}</p>}{task.result && <details className="task-result"><summary>View result</summary><p>{task.result}</p></details>}{task.events?.length > 0 && <details className="task-events"><summary>Execution log ({task.events.length})</summary>{task.events.slice(-5).map((entry,index)=><p key={index}><time>{new Date(entry.at).toLocaleTimeString()}</time> {entry.message}</p>)}</details>}</div><div className="task-actions">{task.status === "paused" ? <button title="Resume task" aria-label="Resume task" onClick={() => controlTask(task.id,"resume")}><Play size={14}/></button> : ["queued","running"].includes(task.status) ? <button title="Pause task" aria-label="Pause task" onClick={() => controlTask(task.id,"pause")}><Pause size={14}/></button> : null}{["queued","running","paused"].includes(task.status) && <button title="Cancel task" aria-label="Cancel task" onClick={() => controlTask(task.id,"cancel")}><XCircle size={14}/></button>}</div></article>)}</div>
      </section>
      <section className="chat-panel"><div className="panel-heading"><div><span className="tiny-icon"><AudioLines size={16} /></span><b>Conversation</b><small>Encrypted transport · API keys remain server-side</small></div><label className="language">LANGUAGE <select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="auto">Auto detect</option><option value="en">English</option><option value="hi">Hindi</option><option value="ur">Urdu</option><option value="hinglish">Hinglish</option></select></label></div>
        <div className="messages">{messages.map((m, i) => <div className={"message " + m.role} key={i}><div className="avatar">{m.role === "assistant" ? <Bot size={17} /> : "YOU"}</div><div className="bubble"><div className="message-label">{m.role === "assistant" ? "NOX" : "YOU"}{m.mode === "demo" && <span className="demo-tag">DEMO</span>}</div><p>{m.content}</p>{m.role === "assistant" && <button type="button" className="message-speak" title="Play this reply aloud" aria-label="Play this reply aloud" onClick={() => speakText(m.content)}><Volume2 size={15} /> Listen</button>}</div></div>)}{busy && <div className="message assistant"><div className="avatar"><Bot size={17} /></div><div className="bubble"><div className="message-label">NOX</div><p className="typing">Processing<span>.</span><span>.</span><span>.</span></p></div></div>}<div ref={endRef} /></div>
        <form className="composer" onSubmit={(e) => { e.preventDefault(); sendMessage(); }}><button type="button" className={"icon-button mic " + (listening ? "recording" : "")} title="Voice input" onClick={toggleMic}><Mic size={18} /></button><input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Message NOX... / NOX से कुछ पूछें" /><button type="button" className={"icon-button voice " + (speakReplies ? "enabled" : "")} title="Toggle voice replies" onClick={() => setSpeakReplies(!speakReplies)}>{speakReplies ? <Volume2 size={18} /> : <VolumeX size={18} />}</button><button className="send-button" type="submit" disabled={busy || !input.trim()}><Send size={17} /><span>Send</span></button></form>
        <div className="composer-foot"><span><Activity size={13} /> {listening ? "LISTENING…" : "READY FOR INPUT"}</span><span>{speakReplies ? "VOICE REPLIES ON" : "VOICE REPLIES OFF"} · AI quality depends on configured provider</span></div>
      </section>
      <footer><span>© 2026 NOX AI</span><span>BUILT FOR FOCUS <ChevronDown size={12} /></span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById("root")).render(<App />);
