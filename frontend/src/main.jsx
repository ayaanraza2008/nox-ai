import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, AudioLines, Bot, ChevronDown, Command, Mic, Pause, Play, Send, ShieldCheck, Sparkles, Volume2, VolumeX, XCircle, Zap } from "lucide-react";
import "./style.css";
import SpatialDashboard from "./SpatialDashboard.jsx";

function MotionEnhancements() {
  useEffect(() => {
    const root = document.documentElement;
    const cursor = document.querySelector(".nox-cursor");
    const finePointer = window.matchMedia("(pointer: fine)").matches;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let pointerFrame = 0;
    let pointerX = 0;
    let pointerY = 0;
    const onPointerMove = (event) => {
      if (!finePointer || reduced || root.dataset.noxMotion === "off" || event.pointerType === "touch") return;
      document.body.classList.add("nox-fine-pointer");
      pointerX = event.clientX;
      pointerY = event.clientY;
      if (pointerFrame) return;
      pointerFrame = window.requestAnimationFrame(() => {
        if (cursor) cursor.style.transform = `translate3d(${pointerX}px, ${pointerY}px, 0)`;
        pointerFrame = 0;
      });
    };
    const onPointerDown = (event) => {
      if (reduced || root.dataset.noxMotion === "off") return;
      const target = event.target.closest("button, .nav-item, .spatial-nav-action, .spatial-task-item, .chat-history-item, summary");
      if (!target || target.disabled || target.getAttribute("aria-disabled") === "true") return;
      const rect = target.getBoundingClientRect();
      const ripple = document.createElement("span");
      ripple.className = "nox-interaction-ripple";
      ripple.style.left = `${event.clientX - rect.left}px`;
      ripple.style.top = `${event.clientY - rect.top}px`;
      target.classList.add("nox-ripple-host");
      target.appendChild(ripple);
      ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
    };
    const revealTargets = ".spatial-panel, .capability-card, .task-row, .pairing-panel, .chat-panel, .task-panel";
    let observer;
    if ("IntersectionObserver" in window && !reduced && root.dataset.noxMotion !== "off") {
      observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("nox-revealed");
          observer.unobserve(entry.target);
        });
      }, { threshold: 0.08, rootMargin: "0px 0px -24px 0px" });
      document.querySelectorAll(revealTargets).forEach((element) => {
        element.classList.add("nox-reveal-ready");
        observer.observe(element);
      });
    }
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("pointerdown", onPointerDown, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerdown", onPointerDown);
      if (pointerFrame) window.cancelAnimationFrame(pointerFrame);
      observer?.disconnect();
    };
  }, []);
  return <div className="nox-cursor" aria-hidden="true" />;
}

function App() {
  const initialGreeting = { role: "assistant", content: "Systems initialized. I'm NOX. What are we working on today?" };
  const [messages, setMessages] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("nox-current-chat") || "null");
      return Array.isArray(saved) && saved.length ? saved : [initialGreeting];
    } catch { return [initialGreeting]; }
  });
  const [chatHistory, setChatHistory] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("nox-chat-history") || "[]");
      return Array.isArray(saved) ? saved : [];
    } catch { return []; }
  });
  const [currentChatId, setCurrentChatId] = useState(() => {
    try { return localStorage.getItem("nox-current-chat-id") || crypto.randomUUID(); }
    catch { return String(Date.now()); }
  });
  const [chatProfileId] = useState(() => {
    try {
      let id = localStorage.getItem("nox-chat-profile-id");
      if (!id) { id = (typeof crypto !== "undefined" && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(36).slice(2); localStorage.setItem("nox-chat-profile-id", id); }
      return id;
    } catch { return String(Date.now()); }
  });
  const [persistentHistoryReady, setPersistentHistoryReady] = useState(false);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [voiceState, setVoiceState] = useState("idle");
  const [voiceMuted, setVoiceMuted] = useState(false);
  const [voiceSpeed, setVoiceSpeed] = useState(1);
  const [voiceVolume, setVoiceVolume] = useState(1);
  const [availableVoices, setAvailableVoices] = useState([]);
  const [selectedVoiceName, setSelectedVoiceName] = useState("");
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const [speakReplies, setSpeakReplies] = useState(true);
  const [status, setStatus] = useState("ALL SYSTEMS READY");
  const [accentColor, setAccentColor] = useState(() => {
    try {
      const saved = localStorage.getItem("nox-accent-color");
      return !saved || saved.toLowerCase() === "#ff3e4d" ? "#9b8cff" : saved;
    } catch { return "#9b8cff"; }
  });

  useEffect(() => {
    try {
      localStorage.setItem("nox-current-chat", JSON.stringify(messages.slice(-300)));
      localStorage.setItem("nox-current-chat-id", currentChatId);
      const titleMessage = messages.find((item) => item.role === "user")?.content || "New conversation";
      const entry = { id: currentChatId, title: titleMessage.slice(0, 64), updatedAt: new Date().toISOString(), messages: messages.slice(-300) };
      setChatHistory((old) => {
        const next = [entry, ...old.filter((item) => item.id !== currentChatId)];
        try { localStorage.setItem("nox-chat-history", JSON.stringify(next)); } catch {}
        return next;
      });
    } catch {}
  }, [messages, currentChatId]);

  useEffect(() => {
    let active = true;
    fetch("/api/chats?user_id=" + encodeURIComponent(chatProfileId))
      .then((response) => { if (!response.ok) throw new Error("Persistent history unavailable"); return response.json(); })
      .then((data) => {
        if (!active) return;
        const remote = Array.isArray(data.chats) ? data.chats : [];
        setChatHistory((local) => {
          const merged = new Map();
          [...remote, ...local].forEach((chat) => {
            const previous = merged.get(chat.id);
            if (!previous || String(chat.updatedAt || "") > String(previous.updatedAt || "")) merged.set(chat.id, chat);
          });
          const next = [...merged.values()].sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")));
          try { localStorage.setItem("nox-chat-history", JSON.stringify(next)); } catch {}
          return next;
        });
        const current = remote.find((chat) => chat.id === localStorage.getItem("nox-current-chat-id"));
        if (current && Array.isArray(current.messages) && current.messages.length) setMessages(current.messages);
        setPersistentHistoryReady(true);
      })
      .catch(() => { if (active) setPersistentHistoryReady(true); });
    return () => { active = false; };
  }, [chatProfileId]);

  useEffect(() => {
    if (!persistentHistoryReady || !messages.length) return;
    const title = messages.find((item) => item.role === "user")?.content || "New conversation";
    const payload = { chat_id: currentChatId, title: title.slice(0, 120), updated_at: new Date().toISOString(), messages: messages.slice(-300) };
    fetch("/api/chats?user_id=" + encodeURIComponent(chatProfileId), {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    }).catch(() => setStatus("CHAT SAVE DELAYED · CHECK CONNECTION"));
  }, [messages, currentChatId, chatProfileId, persistentHistoryReady]);

  function startNewChat() {
    const id = (typeof crypto !== "undefined" && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());
    setCurrentChatId(id);
    setMessages([{ role: "assistant", content: "New session started. How can I help?" }]);
    setInput("");
  }

  function openSavedChat(chat) {
    setCurrentChatId(chat.id);
    setMessages(Array.isArray(chat.messages) ? chat.messages : [initialGreeting]);
  }

  async function deleteSavedChat(id) {
    try {
      const response = await fetch("/api/chats/" + encodeURIComponent(id) + "?user_id=" + encodeURIComponent(chatProfileId), { method: "DELETE" });
      if (!response.ok) throw new Error("Could not delete chat from database");
    } catch {
      setStatus("CHAT DELETE FAILED · RETRY");
      return;
    }
    if (pairing?.session_id && pairing?.device_token) {
      try {
        await fetch("/api/pairing/history/" + encodeURIComponent(id) + "?session_id=" + encodeURIComponent(pairing.session_id), {
          method: "DELETE", headers: { "X-NOX-Device-Token": pairing.device_token }
        });
      } catch {}
    }
    setChatHistory((old) => {
      const next = old.filter((chat) => chat.id !== id);
      try { localStorage.setItem("nox-chat-history", JSON.stringify(next)); } catch {}
      return next;
    });
    if (id === currentChatId) startNewChat();
  }

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
  const [pairing, setPairing] = useState(() => {
    try { return JSON.parse(localStorage.getItem("nox-pairing") || "null"); } catch { return null; }
  });
  const [pairCode, setPairCode] = useState("");
  const [pairTargetDevice, setPairTargetDevice] = useState("");
  const [pairDeviceName, setPairDeviceName] = useState(() => /Android|iPhone|iPad/i.test(navigator.userAgent) ? "NOX Mobile" : "NOX PC");
  const [pairNotice, setPairNotice] = useState("");
  const [pairBusy, setPairBusy] = useState(false);
  const endRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const shouldFollowChatRef = useRef(true);
  const chatAbortRef = useRef(null);
  const chatAbortReasonRef = useRef("");
  const recognitionRef = useRef(null);
  const sendMessageRef = useRef(null);
  const voiceRecognitionRef = useRef(null);
  const voiceModeRef = useRef(false);
  const voiceMutedRef = useRef(false);
  const voiceRequestPendingRef = useRef(false);
  const voiceSpeakingRef = useRef(false);
  const voiceTranscriptRef = useRef("");
  const voiceDebounceRef = useRef(0);
  const voiceRestartRef = useRef(0);
  const [coreMode, setCoreMode] = useState("IDLE");
  const micLevelRef = useRef(0);
  const ttsLevelRef = useRef(0);
  const audioContextRef = useRef(null);
  const micStreamRef = useRef(null);
  const meterFrameRef = useRef(0);
  const listeningRef = useRef(false);
  const ttsDecayRef = useRef(0);
  const ttsAudioRef = useRef(null);
  const ttsAudioContextRef = useRef(null);
  const ttsAnalyserRef = useRef(null);
  const ttsMeterFrameRef = useRef(0);
  const ttsObjectUrlRef = useRef("");
  const ttsAudioReactiveRef = useRef(false);
  const sharedHistoryReadyRef = useRef(false);

  useEffect(() => {
    if (!shouldFollowChatRef.current) return;
    endRef.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "end" });
  }, [messages, busy]);

  function jumpToSection(id) {
    const target = document.getElementById(id);
    if (!target) return;
    target.classList.remove("nox-arrival");
    target.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
    window.requestAnimationFrame(() => target.classList.add("nox-arrival"));
  }

  useEffect(() => {
    let active = true;
    fetch("/api/capabilities")
      .then((response) => { if (!response.ok) throw new Error("Capability status unavailable"); return response.json(); })
      .then((data) => { if (active) { setCapabilities(data); setCapabilityError(false); } })
      .catch(() => { if (active) setCapabilityError(true); });
    return () => { active = false; };
  }, []);

  const statusLabel = (value) => ({ ready: "READY", running: "RUNNING", setup_required: "SETUP REQUIRED", limited: "LIMITED", unavailable: "UNAVAILABLE", error: "ERROR" }[value] || "UNKNOWN");
  // A paired record is not proof that a companion is currently reachable.
  const isDeviceOnline = (device) => {
    const seen = Date.parse(device?.last_seen || "");
    return Number.isFinite(seen) && Date.now() - seen >= 0 && Date.now() - seen < 30000 && !device?.disconnected;
  };
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

  useEffect(() => {
    if (!pairing?.session_id || !pairing?.device_token) return;
    let active = true;
    const checkPairing = async () => {
      try {
        const response = await fetch("/api/pairing/status?session_id=" + encodeURIComponent(pairing.session_id), {
          headers: { "X-NOX-Device-Token": pairing.device_token }
        });
        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            localStorage.removeItem("nox-pairing");
            if (active) { setPairing(null); setPairNotice("Pairing session is no longer valid. Pair again."); }
          }
          return;
        }
        const data = await response.json();
        if (active) {
          const companionDevices = (data.devices || []).filter((device) => /companion/i.test(device.name) && isDeviceOnline(device));
          setPairing((current) => current ? { ...current, devices: data.devices || [], current_device_id: data.current_device_id } : current);
          setPairTargetDevice((current) => current && companionDevices.some((device) => device.device_id === current) ? current : (companionDevices[0]?.device_id || ""));
        }
      } catch { if (active) setPairNotice("Pairing server temporarily unreachable. NOX will retry automatically."); }
    };
    checkPairing();
    const timer = window.setInterval(checkPairing, 10000);
    return () => { active = false; window.clearInterval(timer); };
  }, [pairing?.session_id, pairing?.device_token]);

  // Load shared conversations only after the paired session is authenticated.
  useEffect(() => {
    let active = true;
    sharedHistoryReadyRef.current = false;
    if (!pairing?.session_id || !pairing?.device_token) return () => { sharedHistoryReadyRef.current = false; };
    const loadSharedHistory = async () => {
      try {
        const response = await fetch("/api/pairing/history?session_id=" + encodeURIComponent(pairing.session_id), {
          headers: { "X-NOX-Device-Token": pairing.device_token }
        });
        if (!response.ok) throw new Error("Shared history unavailable");
        const data = await response.json();
        if (!active) return;
        const remote = Array.isArray(data.chats) ? data.chats : [];
        setChatHistory((local) => {
          const merged = new Map();
          [...local, ...remote].forEach((chat) => {
            const previous = merged.get(chat.id);
            if (!previous || String(chat.updatedAt || "") > String(previous.updatedAt || "")) merged.set(chat.id, chat);
          });
          const next = [...merged.values()].sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || ""))).slice(0, 30);
          try { localStorage.setItem("nox-chat-history", JSON.stringify(next)); } catch {}
          return next;
        });
        const currentRemote = remote.find((chat) => chat.id === currentChatId);
        if (currentRemote && Array.isArray(currentRemote.messages) && currentRemote.messages.length) setMessages(currentRemote.messages);
        sharedHistoryReadyRef.current = true;
      } catch {
        if (active) setPairNotice("Cross-device chat sync is temporarily unavailable; this device will keep its local history.");
      }
    };
    loadSharedHistory();
    return () => { active = false; sharedHistoryReadyRef.current = false; };
  }, [pairing?.session_id, pairing?.device_token]);

  // Sync the active conversation to the authenticated pairing session.
  useEffect(() => {
    if (!sharedHistoryReadyRef.current || !pairing?.session_id || !pairing?.device_token || !messages.length) return;
    const title = messages.find((item) => item.role === "user")?.content || "New conversation";
    fetch("/api/pairing/history?session_id=" + encodeURIComponent(pairing.session_id), {
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-NOX-Device-Token": pairing.device_token },
      body: JSON.stringify({ chat_id: currentChatId, title: title.slice(0, 120), updated_at: new Date().toISOString(), messages: messages.slice(-300) })
    }).catch(() => {});
  }, [messages, currentChatId, pairing?.session_id, pairing?.device_token]);

  async function createPairing() {
    setPairBusy(true); setPairNotice("");
    try {
      const response = await fetch("/api/pairing/create", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_name: pairDeviceName })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create pairing");
      const saved = { ...data, devices: [{ device_id: data.device_id, name: pairDeviceName, disconnected: 0 }] };
      localStorage.setItem("nox-pairing", JSON.stringify(saved));
      setPairing(saved);
      setPairNotice("Pair code created. Enter it on the other device within five minutes.");
    } catch (error) { setPairNotice("Pairing failed: " + error.message); }
    finally { setPairBusy(false); }
  }

  async function joinPairing() {
    if (pairCode.trim().length !== 6 || [...pairCode.trim()].some((char) => char < "0" || char > "9")) { setPairNotice("Enter the six-digit code shown on the other device."); return; }
    setPairBusy(true); setPairNotice("");
    try {
      const response = await fetch("/api/pairing/join", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: pairCode.trim(), device_name: pairDeviceName })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not join pairing");
      const saved = { ...data, devices: [] };
      localStorage.setItem("nox-pairing", JSON.stringify(saved));
      setPairing(saved); setPairCode("");
      setPairNotice("This browser joined the session. Install and connect the native companion for device-level actions.");
    } catch (error) { setPairNotice("Could not pair: " + error.message); }
    finally { setPairBusy(false); }
  }

  async function disconnectPairing() {
    if (!pairing?.session_id || !pairing?.device_token) return;
    if (!window.confirm("Disconnect this device from the NOX pairing session?")) return;
    setPairBusy(true);
    try {
      const response = await fetch("/api/pairing/disconnect?session_id=" + encodeURIComponent(pairing.session_id), {
        method: "POST", headers: { "X-NOX-Device-Token": pairing.device_token }
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Disconnect failed");
      localStorage.removeItem("nox-pairing"); setPairing(null);
      setPairNotice("This device has been disconnected.");
    } catch (error) { setPairNotice("Disconnect failed: " + error.message); }
    finally { setPairBusy(false); }
  }

  function resolveWebsiteCommand(rawGoal) {
    const input = rawGoal.trim().replace(/[.!?]+$/, "");
    const search = input.match(/^(?:please\s+)?(?:search(?:\s+the\s+web)?(?:\s+for)?|google|find\s+online|internet\s+par)\s+(.+?)(?:\s+(?:on|using)\s+(google|youtube|bing))?$/i);
    if (search) {
      const query = search[1].trim();
      if (!query) return null;
      const engine = (search[2] || "google").toLowerCase();
      const base = engine === "youtube" ? "https://www.youtube.com/results?search_query=" : engine === "bing" ? "https://www.bing.com/search?q=" : "https://www.google.com/search?q=";
      return { url: base + encodeURIComponent(query), label: engine === "youtube" ? "YouTube search: " + query : "Web search: " + query };
    }
    const match = input.match(/^(?:please\s+)?(?:(?:open|launch|visit|go to|browse to|khol|kholo|khul)\s+)?(.+?)$/i);
    if (!match) return null;
    const target = match[1].trim().replace(/[.!?]+$/, "");
    if (/^(?:app|application)\s+/i.test(target)) return null;
    const knownSites = {
      youtube: "https://www.youtube.com/", google: "https://www.google.com/",
      gmail: "https://mail.google.com/", github: "https://github.com/",
      instagram: "https://www.instagram.com/", facebook: "https://www.facebook.com/",
      "whatsapp web": "https://web.whatsapp.com/", wikipedia: "https://www.wikipedia.org/",
      reddit: "https://www.reddit.com/", linkedin: "https://www.linkedin.com/",
      chatgpt: "https://chatgpt.com/", render: "https://dashboard.render.com/",
      "google drive": "https://drive.google.com/", bing: "https://www.bing.com/",
      netflix: "https://www.netflix.com/", amazon: "https://www.amazon.in/",
      "amazon prime": "https://www.primevideo.com/", "prime video": "https://www.primevideo.com/",
      spotify: "https://open.spotify.com/", discord: "https://discord.com/app",
      telegram: "https://web.telegram.org/", pinterest: "https://www.pinterest.com/",
      stackoverflow: "https://stackoverflow.com/", "google docs": "https://docs.google.com/",
      "google photos": "https://photos.google.com/", "google maps": "https://maps.google.com/",
      "google meet": "https://meet.google.com/", "microsoft teams": "https://teams.microsoft.com/",
      outlook: "https://outlook.live.com/", twitter: "https://x.com/", x: "https://x.com/",
      threads: "https://www.threads.net/", twitch: "https://www.twitch.tv/",
      "epic games": "https://store.epicgames.com/", "play store": "https://play.google.com/store",
      "google play": "https://play.google.com/store"
    };
    const key = target.toLowerCase().replace(/^website\s+/i, "");
    if (knownSites[key]) return { url: knownSites[key], label: target };
    if (/^https?:\/\//i.test(target)) {
      try { const url = new URL(target); if (!["https:", "http:"].includes(url.protocol)) return null; return { url: url.href, label: url.hostname }; }
      catch { return null; }
    }
    if (/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}(?::\d{1,5})?(?:[/?#][^\s]*)?$/i.test(target)) {
      try { const url = new URL("https://" + target); return { url: url.href, label: url.hostname }; }
      catch { return null; }
    }
    return null;
  }

  async function submitTask(event, directGoal = taskGoal) {
    event?.preventDefault();
    const goal = directGoal.trim();
    if (!goal || taskBusy) return;

    // Route supported device-control phrases to a live paired companion, never to the
    // research agent where they could be mistaken for an executed action.
    const deviceActionCommand = /^(?:(?:turn|switch)\s+(?:on|off)\s+.+|.+\s+(?:on|off)\s+(?:kar do|karo|please)|(?:lights?|all lights?|tv|television)\s+(?:on|off)|(?:list|show|status of|what are my)\s+(?:devices|lights|switches|plugs|tvs|cameras|climate|thermostats|blinds|covers|fans|vacuums|scenes)|(?:set|make)\s+(?:the\s+)?(?:ac|air conditioner|thermostat|climate).+|(?:ac|temperature|thermostat)\s+(?:ko\s+)?\d{2}(?:\.\d)?\s*(?:degree|degrees|°?c)?\s+(?:kar do|set karo)|(?:tv|television|media player)(?:\s+.+)?\s+(?:on|off|play|pause|toggle)|(?:open|close)\s+.+\b(?:blinds?|curtains?|shutters?|covers?)\b|(?:start|stop|pause|dock|return)\s+(?:the\s+)?(?:vacuum|robot vacuum|robot cleaner)|(?:activate|apply|run)\s+(?:the\s+)?scene\s+.+)$/i.test(goal);
    // Discover installed Windows apps through the opt-in local companion.
    const openVerb = /\b(open|launch|start|khol|kholo|khul|chalao|chalu karo)\b|खोल|चला/i.test(goal);
    const normalizedGoal = goal.toLowerCase().replace(/[.!?]+$/, "").trim();
    const websiteCommand = resolveWebsiteCommand(goal);
    const commandTarget = normalizedGoal
      .replace(/^(please\s+)?(open|launch|start|khol|kholo|khul|chalao|chalu karo|खोलो|खोल)\s+/i, "")
      .replace(/\s+(please|khol|kholo|khul|chalao|chalu karo|खोलो|खोल)$/i, "")
      .replace(/^(app|application)\s+/i, "")
      .replace(/^the\s+/i, "")
      .replace(/\s+app$/i, "")
      .trim();
    const normalizeAppName = (value) => value.toLowerCase().replace(/[^a-z0-9]/g, "");
    const explicitAppCommand = /\b(app|application)\b/i.test(goal) || /\b(app|application)\s*$/i.test(goal);
    const pairedTarget = (pairing?.devices || []).find((device) => device.device_id === pairTargetDevice && /companion/i.test(device.name) && !device.disconnected);
    if (pairing?.session_id && pairing?.device_token && pairedTarget) {
      setTaskBusy(true);
      setTaskNotice("Sending command to " + pairedTarget.name + "…");
      try {
        const query = new URLSearchParams({ session_id: pairing.session_id, target_device: pairTargetDevice, command: goal });
        const response = await fetch("/api/pairing/commands?" + query.toString(), {
          method: "POST", headers: { "X-NOX-Device-Token": pairing.device_token }
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not send command to paired device");
        setTaskGoal("");
        setTaskNotice("Command queued for " + pairedTarget.name + ". Waiting for its result…");
        for (let attempt = 0; attempt < 20; attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 2000));
          const statusResponse = await fetch("/api/pairing/commands/" + encodeURIComponent(data.command_id) + "?session_id=" + encodeURIComponent(pairing.session_id), {
            headers: { "X-NOX-Device-Token": pairing.device_token }
          });
          if (!statusResponse.ok) continue;
          const statusData = await statusResponse.json();
          const commandStatus = statusData.command?.status;
          if (["completed", "reported", "failed"].includes(commandStatus)) {
            let result = {};
            try { result = JSON.parse(statusData.command.result || "{}"); } catch {}
            let outcome;
            if (commandStatus === "completed") {
              outcome = "SUCCESS · " + pairedTarget.name + ": " + (result.message || result.output || "Action completed and companion reported success.");
            } else if (commandStatus === "reported") {
              outcome = "REQUEST ACCEPTED, NOT VERIFIED · " + pairedTarget.name + ": " + (result.message || "The operating system accepted the launch request, but NOX cannot confirm the app became visible.");
            } else {
              outcome = "ACTION FAILED · " + pairedTarget.name + ": " + (result.message || result.output || result.status || "The companion reported that it could not complete the action.") + " NOX did not report this as a success.";
            }
            setTaskNotice(outcome);
            return outcome;
          }
        }
        const pendingOutcome = "NO CONFIRMATION YET · The command was queued, but " + pairedTarget.name + " has not returned a result within 40 seconds. Check that its companion is running and online. NOX will not pretend the action succeeded.";
        setTaskNotice(pendingOutcome);
        return pendingOutcome;
      } catch (error) {
        const failure = "Could not reach paired device: " + error.message;
        setTaskNotice(failure);
        return failure;
      } finally {
        setTaskBusy(false);
      }
    }
    if (deviceActionCommand) {
      const failure = "NOT EXECUTED · No online paired companion is selected. Pair and start the Windows/Android companion, then choose it under SEND CHAT COMMANDS TO. NOX did not claim the device action ran.";
      setTaskNotice(failure);
      return failure;
    }

    if (/Android/i.test(navigator.userAgent) && openVerb && (explicitAppCommand || !websiteCommand)) {
      setTaskGoal("");
      setTaskNotice("Sending command to NOX Android Companion. A unique app match opens directly; ambiguous matches show a chooser.");
      const companionUrl = "nox://launch?query=" + encodeURIComponent(commandTarget);
      window.location.href = companionUrl;
      window.setTimeout(() => {
        if (document.visibilityState === "visible") {
          setTaskNotice("If NOX Companion did not open, install it from the NOX GitHub repository. This browser cannot enumerate all installed apps by itself.");
        }
      }, 1400);
      return;
    }

    if (openVerb && (explicitAppCommand || !websiteCommand) && /Windows/i.test(navigator.userAgent)) {
      let token = "";
      try { token = sessionStorage.getItem("nox-companion-token") || ""; } catch {}
      if (!token) {
        token = window.prompt("First-time setup: enter your local NOX companion token. It will be kept only for this browser session.");
        if (!token) {
          setTaskNotice("App launch needs the local companion token once per browser session.");
          return;
        }
        try { sessionStorage.setItem("nox-companion-token", token); } catch {}
      }
      setTaskBusy(true);
      setTaskNotice("Finding installed apps from your Windows Start Menu…");
      try {
        const response = await fetch("http://127.0.0.1:8765/v1/apps", { headers: { "X-NOX-Token": token } });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not list local apps");
        const requestedName = normalizeAppName(commandTarget);
        const aliases = { vscode: "visualstudiocode", code: "visualstudiocode", chrome: "googlechrome", edge: "microsoftedge", explorer: "fileexplorer", calc: "calculator" };
        const query = aliases[requestedName] || requestedName;
        const matches = (data.apps || []).filter((app) => {
          const name = normalizeAppName(app.name);
          return name === query || name.startsWith(query) || query.startsWith(name);
        }).slice(0, 12);
        if (!matches.length) throw new Error('No Start Menu shortcut matched "' + commandTarget + '". Check the app name or install its Start Menu shortcut.');
        // Keep routine app launches one-command: prefer an exact match, else the best first match.
        const selected = matches.find((app) => normalizeAppName(app.name) === query) || matches[0];
        const launch = await fetch("http://127.0.0.1:8765/v1/actions/open", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-NOX-Token": token },
          body: JSON.stringify({ target: selected.id, confirmed: true })
        });
        const result = await launch.json();
        if (!launch.ok) throw new Error(result.detail || "App launch request failed");
        setTaskGoal("");
        setTaskNotice("Launch request sent for " + selected.name + ". Check the PC window.");
      } catch (error) {
        setTaskNotice("Could not launch app: " + error.message + ". Companion/browser local-network policies may block the connection.");
      } finally {
        setTaskBusy(false);
      }
      return;
    }

    // A clear user command to open a known website is sufficient intent; avoid a redundant confirmation.
    // A hosted Render worker still cannot directly control other apps or the desktop.
    const website = websiteCommand;
    if (website) {
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

  function stopGeneration() {
    if (!chatAbortRef.current) return;
    chatAbortReasonRef.current = "user";
    chatAbortRef.current.abort();
    setStatus("GENERATION STOPPING");
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

  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const loadVoices = () => setAvailableVoices(window.speechSynthesis.getVoices());
    loadVoices();
    window.speechSynthesis.addEventListener?.("voiceschanged", loadVoices);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", loadVoices);
  }, []);

  useEffect(() => () => {
    voiceModeRef.current = false;
    voiceMutedRef.current = true;
    listeningRef.current = false;
    recognitionRef.current?.stop();
    voiceRecognitionRef.current?.stop();
    window.clearTimeout(voiceDebounceRef.current);
    window.clearTimeout(voiceRestartRef.current);
    stopMicMeter();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    stopTtsAudio();
    window.clearTimeout(ttsDecayRef.current);
  }, []);

  function stopTtsAudio() {
    if (ttsMeterFrameRef.current) cancelAnimationFrame(ttsMeterFrameRef.current);
    ttsMeterFrameRef.current = 0;
    const audio = ttsAudioRef.current;
    ttsAudioRef.current = null;
    if (audio) {
      audio.onplay = null;
      audio.onended = null;
      audio.onerror = null;
      audio.pause();
      audio.removeAttribute("src");
      try { audio.load(); } catch {}
    }
    const audioContext = ttsAudioContextRef.current;
    ttsAudioContextRef.current = null;
    ttsAnalyserRef.current = null;
    if (audioContext && audioContext.state !== "closed") audioContext.close().catch(() => {});
    if (ttsObjectUrlRef.current) URL.revokeObjectURL(ttsObjectUrlRef.current);
    ttsObjectUrlRef.current = "";
    ttsAudioReactiveRef.current = false;
    ttsLevelRef.current = 0;
  }

  function finishSpeechPlayback() {
    voiceSpeakingRef.current = false;
    ttsLevelRef.current = 0;
    setCoreMode("IDLE");
    setStatus("AI LINK ACTIVE");
    if (voiceModeRef.current && !voiceMutedRef.current) {
      setVoiceState("listening");
      scheduleVoiceRecognition(180);
    } else if (!voiceModeRef.current) {
      setVoiceState("idle");
    }
  }

  function speakWithBrowserSynthesis(text, lang) {
    if (!("speechSynthesis" in window)) {
      setStatus("NEURAL TTS UNAVAILABLE · BROWSER VOICE UNSUPPORTED");
      setVoiceState(voiceModeRef.current ? "error" : "idle");
      setCoreMode("ERROR");
      return;
    }
    const synth = window.speechSynthesis;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = voiceSpeed;
    utterance.volume = voiceVolume;
    let spoken = false;
    const chooseVoiceAndSpeak = () => {
      if (spoken) return;
      spoken = true;
      const voices = synth.getVoices();
      const prefix = lang.toLowerCase().split("-")[0];
      const selected = voices.find((voice) => voice.name === selectedVoiceName && voice.lang?.toLowerCase().startsWith(prefix));
      utterance.voice = selected
        || voices.find((voice) => voice.lang?.toLowerCase() === lang.toLowerCase())
        || voices.find((voice) => voice.lang?.toLowerCase().startsWith(prefix))
        || null;
      synth.speak(utterance);
    };
    utterance.onstart = () => {
      ttsAudioReactiveRef.current = false;
      voiceSpeakingRef.current = true;
      setVoiceState("speaking");
      setCoreMode("NOX_SPEAKING");
      setStatus("BROWSER VOICE ACTIVE · AMPLITUDE ESTIMATED");
      // Browser speechSynthesis does not expose its output waveform. This is a
      // clearly-labelled low-energy fallback, never presented as measured audio.
      ttsLevelRef.current = 0.18;
    };
    utterance.onboundary = (event) => {
      const chars = Math.max(1, Number(event.charLength) || 3);
      ttsLevelRef.current = Math.min(0.72, 0.2 + chars * 0.025);
      window.clearTimeout(ttsDecayRef.current);
      ttsDecayRef.current = window.setTimeout(() => { ttsLevelRef.current = 0.08; }, 140);
    };
    utterance.onerror = (event) => {
      voiceSpeakingRef.current = false;
      window.clearTimeout(ttsDecayRef.current);
      ttsLevelRef.current = 0;
      if (event?.error === "canceled" || event?.error === "interrupted") return;
      setCoreMode("ERROR");
      setStatus("VOICE PLAYBACK ISSUE");
      if (voiceModeRef.current) setVoiceState("error");
      window.setTimeout(() => { if (!voiceSpeakingRef.current) setCoreMode("IDLE"); }, 900);
    };
    utterance.onend = finishSpeechPlayback;
    const voices = synth.getVoices();
    if (voices.length) chooseVoiceAndSpeak();
    else {
      synth.addEventListener?.("voiceschanged", chooseVoiceAndSpeak, { once: true });
      window.setTimeout(chooseVoiceAndSpeak, 900);
    }
  }

  async function speakText(text) {
    if (!text?.trim()) return;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    window.clearTimeout(ttsDecayRef.current);
    stopTtsAudio();
    const lang = getSpeechLanguage(text);
    if (text.length > 2500) {
      speakWithBrowserSynthesis(text, lang);
      return;
    }
    let fallbackStarted = false;
    const startFallbackOnce = () => {
      if (fallbackStarted) return;
      fallbackStarted = true;
      stopTtsAudio();
      speakWithBrowserSynthesis(text, lang);
    };

    try {
      const ttsController = new AbortController();
      const ttsTimeoutId = window.setTimeout(() => ttsController.abort(), 12000);
      let response;
      try {
        response = await fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, language: lang, rate: voiceSpeed }),
          signal: ttsController.signal
        });
      } finally {
        window.clearTimeout(ttsTimeoutId);
      }
      if (!response.ok) throw new Error("Neural TTS endpoint unavailable");
      const blob = await response.blob();
      if (!blob.size) throw new Error("Neural TTS returned empty audio");
      const objectUrl = URL.createObjectURL(blob);
      const audio = new Audio(objectUrl);
      audio.preload = "auto";
      audio.volume = voiceVolume;
      ttsAudioRef.current = audio;
      ttsObjectUrlRef.current = objectUrl;

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      let analyser = null;
      if (AudioContextClass) {
        try {
          const audioContext = new AudioContextClass();
          analyser = audioContext.createAnalyser();
          analyser.fftSize = 512;
          analyser.smoothingTimeConstant = 0.78;
          const source = audioContext.createMediaElementSource(audio);
          source.connect(analyser);
          analyser.connect(audioContext.destination);
          await audioContext.resume();
          ttsAudioContextRef.current = audioContext;
          ttsAnalyserRef.current = analyser;
          ttsAudioReactiveRef.current = true;
        } catch {
          ttsAudioReactiveRef.current = false;
        }
      }

      audio.onplay = () => {
        if (ttsAudioRef.current !== audio) return;
        voiceSpeakingRef.current = true;
        setVoiceState("speaking");
        setCoreMode("NOX_SPEAKING");
        setStatus(ttsAudioReactiveRef.current ? "LIVE NEURAL AUDIO · REACTIVE" : "NEURAL VOICE ACTIVE");
        if (!analyser || !ttsAudioReactiveRef.current) return;
        const samples = new Float32Array(analyser.fftSize);
        const measureOutput = () => {
          if (ttsAudioRef.current !== audio || !ttsAnalyserRef.current) return;
          analyser.getFloatTimeDomainData(samples);
          let sum = 0;
          for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i];
          const rms = Math.sqrt(sum / samples.length);
          // RMS is measured from the actual neural TTS audio element output.
          ttsLevelRef.current = Math.max(0, Math.min(1, rms * 16));
          ttsMeterFrameRef.current = requestAnimationFrame(measureOutput);
        };
        measureOutput();
      };
      audio.onended = () => {
        if (ttsAudioRef.current !== audio) return;
        stopTtsAudio();
        finishSpeechPlayback();
      };
      audio.onerror = () => {
        if (ttsAudioRef.current !== audio) return;
        startFallbackOnce();
      };
      await audio.play();
    } catch {
      startFallbackOnce();
    }
  }

  async function sendMessage(text = input, fromVoice = false) {
    const value = text.trim();
    if (!value || busy) return;
    if (fromVoice || voiceModeRef.current) {
      voiceRequestPendingRef.current = true;
      if (!fromVoice) {
        window.clearTimeout(voiceDebounceRef.current);
        voiceTranscriptRef.current = "";
      }
      if (fromVoice) setVoiceTranscript(value);
      setVoiceState("thinking");
      setCoreMode("PROCESSING");
      try { voiceRecognitionRef.current?.stop(); } catch {}
    }

    // Route explicit action/search commands from chat through the same real command handler as Task Orchestrator.
    // Ordinary conversational messages continue to the AI chat endpoint.
    const commandLike = /^(?:please\s+)?(?:open|launch|start|visit|go to|browse to|search(?:\s+the\s+web)?(?:\s+for)?|google|find online|internet par|khol|kholo|khul|chalao|chalu karo|खोलो|खोल|चलाओ|(?:turn|switch)\s+(?:on|off)|(?:lights?|all lights?|tv|television)\s+(?:on|off)|(?:list|show|status of|what are my)\s+(?:devices|lights|switches|plugs|tvs|cameras|climate|thermostats|blinds|covers|fans|vacuums|scenes)|(?:set|make)\s+(?:the\s+)?(?:ac|air conditioner|thermostat|climate)|(?:tv|television|media player).*(?:on|off|play|pause|toggle)|(?:open|close)\s+.*(?:blinds?|curtains?|shutters?|covers?)|(?:start|stop|pause|dock|return)\s+(?:the\s+)?(?:vacuum|robot vacuum|robot cleaner)|(?:activate|apply|run)\s+(?:the\s+)?scene)\b/i.test(value)
      || /^.+\s+(?:kholo|open|launch|chalao|खोलो|चलाओ)$/i.test(value)
      || /^.+\s+(?:on|off)\s+(?:kar do|karo|please)$/i.test(value);
    if (commandLike) {
      setInput("");
      setMessages((old) => [...old, { role: "user", content: value }]);
      setBusy(true);
      try {
        const outcome = await submitTask(null, value);
        const commandReply = typeof outcome === "string" ? outcome : "Command handled. Check the task status for details.";
        setMessages((old) => [...old, { role: "assistant", content: commandReply }]);
        if (voiceModeRef.current || (speakReplies && !fromVoice)) speakText(commandReply);
      } catch (error) {
        setMessages((old) => [...old, { role: "assistant", content: "Command failed: " + error.message }]);
      } finally {
        setBusy(false);
        if (fromVoice || voiceModeRef.current) voiceRequestPendingRef.current = false;
      }
      return;
    }

    const history = messages.slice(-12).map(({ role, content }) => ({ role, content }));
    setMessages((old) => [...old, { role: "user", content: value }]);
    setInput("");
    setBusy(true);
    setStatus("PROCESSING REQUEST");
    try {
      const controller = new AbortController();
      chatAbortRef.current = controller;
      chatAbortReasonRef.current = "";
      const timeoutId = window.setTimeout(() => controller.abort(), 55000);
      let response;
      let data;
      try {
        response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: value, language, history }),
          signal: controller.signal
        });
        const responseText = await response.text();
        if (!responseText.trim()) {
          throw new Error("Server returned an empty response (HTTP " + response.status + "). Check Render logs for the backend crash.");
        }
        try {
          data = JSON.parse(responseText);
        } catch {
          throw new Error("Server returned an invalid response (HTTP " + response.status + "). Check Render logs.");
        }
      } catch (requestError) {
        if (requestError.name === "AbortError") {
          if (chatAbortReasonRef.current === "user") throw new Error("Generation stopped by you.");
          throw new Error("AI response timed out. Please try again; if it repeats, check the Render logs and OpenRouter model/key.");
        }
        throw requestError;
      } finally {
        window.clearTimeout(timeoutId);
        if (chatAbortRef.current === controller) chatAbortRef.current = null;
      }
      if (!response.ok) throw new Error(data.detail || "Request failed");
      setMessages((old) => [...old, { role: "assistant", content: data.reply, mode: data.mode }]);
      setStatus(data.mode === "ai" ? "AI LINK ACTIVE" : "DEMO MODE");
      if (voiceModeRef.current || (speakReplies && !fromVoice)) speakText(data.reply);
    } catch (error) {
      if (chatAbortReasonRef.current === "user") {
        setStatus("GENERATION STOPPED");
      } else {
        const detail = error?.message || "Network request failed";
        setMessages((old) => [...old, { role: "assistant", content: "NOX couldn't get a reply: " + detail }]);
        setStatus("CONNECTION ISSUE");
      }
    } finally {
      if (chatAbortRef.current) chatAbortRef.current = null;
      chatAbortReasonRef.current = "";
      setBusy(false);
      if (fromVoice || voiceModeRef.current) voiceRequestPendingRef.current = false;
    }
  }

  sendMessageRef.current = sendMessage;

  function scheduleVoiceRecognition(delay = 350) {
    window.clearTimeout(voiceRestartRef.current);
    voiceRestartRef.current = window.setTimeout(() => {
      if (voiceModeRef.current && !voiceMutedRef.current && !voiceRequestPendingRef.current && !voiceSpeakingRef.current) {
        startVoiceRecognition();
      }
    }, delay);
  }

  function startVoiceRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition || !voiceModeRef.current || voiceMutedRef.current || voiceRequestPendingRef.current || voiceSpeakingRef.current) return;
    try { voiceRecognitionRef.current?.abort(); } catch {}
    const recognition = new SpeechRecognition();
    const lang = language === "hi" ? "hi-IN" : language === "ur" ? "ur-PK" : language === "hinglish" ? "hi-IN" : language === "en" ? "en-US" : "en-IN";
    recognition.lang = lang;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      if (voiceModeRef.current && !voiceMutedRef.current) {
        setVoiceState("listening");
        setListening(true);
        listeningRef.current = true;
        setCoreMode("USER_LISTENING");
      }
    };
    recognition.onresult = (event) => {
      let finalChunk = "";
      let interimChunk = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const item = event.results[i];
        if (item.isFinal) finalChunk += item[0].transcript + " ";
        else interimChunk += item[0].transcript;
      }
      if (finalChunk.trim()) {
        voiceTranscriptRef.current = (voiceTranscriptRef.current + " " + finalChunk).trim();
        setVoiceTranscript(voiceTranscriptRef.current);
        window.clearTimeout(voiceDebounceRef.current);
        voiceDebounceRef.current = window.setTimeout(async () => {
          const transcript = voiceTranscriptRef.current.trim();
          if (!transcript || !voiceModeRef.current || voiceMutedRef.current || voiceRequestPendingRef.current) return;
          voiceTranscriptRef.current = "";
          voiceRequestPendingRef.current = true;
          try { voiceRecognitionRef.current?.stop(); } catch {}
          try { await sendMessageRef.current?.(transcript, true); }
          finally { voiceRequestPendingRef.current = false; }
        }, 850);
      } else if (interimChunk.trim()) {
        setVoiceTranscript((voiceTranscriptRef.current ? voiceTranscriptRef.current + " " : "") + interimChunk.trim());
      }
    };
    recognition.onerror = (event) => {
      if (!voiceModeRef.current) return;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setVoiceState("error");
        setStatus("MICROPHONE PERMISSION DENIED");
        stopVoiceMode();
      } else if (event.error !== "no-speech" && event.error !== "aborted") {
        setVoiceState("error");
        setStatus("VOICE CONNECTION ISSUE");
      }
    };
    recognition.onend = () => {
      if (voiceRecognitionRef.current === recognition) voiceRecognitionRef.current = null;
      listeningRef.current = false;
      setListening(false);
      if (voiceModeRef.current && !voiceMutedRef.current && !voiceRequestPendingRef.current && !voiceSpeakingRef.current) scheduleVoiceRecognition(300);
    };
    voiceRecognitionRef.current = recognition;
    try { recognition.start(); }
    catch { if (voiceModeRef.current) scheduleVoiceRecognition(700); }
  }

  async function startVoiceMode() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceState("error");
      setStatus("VOICE RECOGNITION NOT SUPPORTED");
      setVoiceTranscript("This browser does not support continuous speech recognition. Text chat remains available; try a supported desktop Chrome browser.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceState("error");
      setVoiceTranscript("Microphone access requires HTTPS and a browser that supports audio capture.");
      return;
    }
    try {
      setVoiceState("connecting");
      setVoiceTranscript("Requesting microphone permission…");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (!stream.getAudioTracks().length) throw new Error("No microphone track is available.");
      startMicMeter(stream);
      voiceTranscriptRef.current = "";
      voiceModeRef.current = true;
      voiceMutedRef.current = false;
      setVoiceMode(true);
      setVoiceMuted(false);
      setVoiceState("listening");
      setVoiceTranscript("Listening. Speak naturally; NOX will respond automatically.");
      setStatus("VOICE SESSION ACTIVE");
      startVoiceRecognition();
    } catch (error) {
      stopMicMeter();
      voiceModeRef.current = false;
      setVoiceMode(false);
      setVoiceState("error");
      setStatus("MICROPHONE UNAVAILABLE");
      setVoiceTranscript(error?.name === "NotAllowedError" ? "Microphone permission was denied. Allow microphone access in your browser settings, then try again." : "Could not start the microphone. Check that a microphone is connected and not blocked by another app.");
    }
  }

  function stopVoiceMode() {
    voiceModeRef.current = false;
    voiceMutedRef.current = false;
    voiceSpeakingRef.current = false;
    voiceRequestPendingRef.current = false;
    setVoiceMode(false);
    setVoiceMuted(false);
    setVoiceState("idle");
    setListening(false);
    listeningRef.current = false;
    window.clearTimeout(voiceDebounceRef.current);
    window.clearTimeout(voiceRestartRef.current);
    voiceTranscriptRef.current = "";
    try { voiceRecognitionRef.current?.abort(); } catch {}
    voiceRecognitionRef.current = null;
    try { recognitionRef.current?.stop(); } catch {}
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    stopTtsAudio();
    stopMicMeter();
    setCoreMode("IDLE");
    setStatus("VOICE SESSION ENDED");
  }

  function toggleVoiceMute() {
    if (!voiceModeRef.current) return;
    const nextMuted = !voiceMutedRef.current;
    voiceMutedRef.current = nextMuted;
    setVoiceMuted(nextMuted);
    window.clearTimeout(voiceRestartRef.current);
    if (nextMuted) {
      window.clearTimeout(voiceDebounceRef.current);
      voiceTranscriptRef.current = "";
      try { voiceRecognitionRef.current?.abort(); } catch {}
      voiceRecognitionRef.current = null;
      stopMicMeter();
      setListening(false);
      listeningRef.current = false;
      setVoiceState("muted");
      setVoiceTranscript("Microphone muted.");
    } else {
      setVoiceState("connecting");
      navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
        .then((stream) => { if (!voiceModeRef.current || voiceMutedRef.current) { stream.getTracks().forEach((track) => track.stop()); return; } startMicMeter(stream); startVoiceRecognition(); })
        .catch(() => { setVoiceState("error"); setVoiceTranscript("Microphone could not be re-enabled. Check browser permissions."); });
    }
  }

  function interruptVoice() {
    window.clearTimeout(voiceDebounceRef.current);
    voiceTranscriptRef.current = "";
    voiceSpeakingRef.current = false;
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    stopTtsAudio();
    setVoiceState("interrupted");
    setCoreMode("IDLE");
    setVoiceTranscript("Playback stopped. You can speak now.");
    if (voiceModeRef.current && !voiceMutedRef.current) scheduleVoiceRecognition(150);
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
    <MotionEnhancements />
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Zap size={20} fill="currentColor" /></div><div><b>NOX<span>AI</span></b><small>PERSONAL INTELLIGENCE</small></div></div>
      <div className="side-label">WORKSPACE</div>
      <button className="nav-item active"><Command size={17} /> Command Center <span className="nav-dot" /></button>
      <button className="nav-item" onClick={startNewChat}><Sparkles size={17} /> New chat</button>
      <div className="side-label">CHAT HISTORY</div>
      <div className="chat-history-list">{chatHistory.map((chat) => <div className={"chat-history-item" + (chat.id === currentChatId ? " current" : "")} key={chat.id}><button type="button" title={chat.title} onClick={() => openSavedChat(chat)}>{chat.title || "New conversation"}</button><button type="button" className="chat-history-delete" aria-label={"Delete chat " + (chat.title || "")} title="Delete chat" onClick={() => deleteSavedChat(chat.id)}>×</button></div>)}</div>
      <button className="nav-item" onClick={() => jumpToSection("pairing-panel")}><ShieldCheck size={17} /> Pair devices <span className="nav-dot" style={{ background: pairing ? "#65d7a1" : "#777" }} /></button>
      <div className="side-bottom"><div className="secure"><ShieldCheck size={17} /><div><b>Private by design</b><small>Keys stay on the server</small></div></div><div className="version">NOX CORE <span>v0.1.0</span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumb">NOX / <span>COMMAND CENTER</span></div><div className="topbar-tools"><label className="accent-picker">ACCENT <select aria-label="Interface accent color" value={accentColor} onChange={(event) => setAccentColor(event.target.value)}><option value="#9b8cff">Violet</option><option value="#38bdf8">Ice blue</option><option value="#34d399">Emerald</option><option value="#fbbf24">Amber</option><option value="#ff3e4d">Crimson</option></select></label><div className="top-status"><i /> {status}</div></div></header>
      <section className="hero"><div className="eyebrow"><span /> PERSONAL AI INTERFACE</div><h1>Think beyond.<br /><em>Move with intent.</em></h1><p>Your space to reason, create, and get things done.</p>
      </section>
      <SpatialDashboard
        status={status} coreMode={coreMode} busy={busy} micLevelRef={micLevelRef} ttsLevelRef={ttsLevelRef} ttsAudioReactiveRef={ttsAudioReactiveRef}
        voiceMode={voiceMode} voiceMuted={voiceMuted} voiceState={voiceState} voiceTranscript={voiceTranscript}
        input={input} onInputChange={setInput} onSendMessage={() => sendMessage()}
        chatHistory={chatHistory} currentChatId={currentChatId} onNewChat={startNewChat} onOpenChat={openSavedChat}
        onJump={jumpToSection}
        capabilities={capabilities} capabilityError={capabilityError} tasks={tasks} taskNotice={taskNotice} pairing={pairing}
        onStartVoiceMode={startVoiceMode} onStopVoiceMode={stopVoiceMode} onToggleVoiceMute={toggleVoiceMute} onInterruptVoice={interruptVoice} onControlTask={controlTask} onStopGeneration={stopGeneration} canStopGeneration={Boolean(chatAbortRef.current)}
      />
      <section className="pairing-panel" id="pairing-panel">
        <div className="task-panel-heading"><div><span className="tiny-icon"><ShieldCheck size={16} /></span><b>Device Pairing</b><small>Connect your PC and mobile to the same NOX session</small></div><span className={"pair-status " + (pairing ? "paired" : "")}>{pairing ? "SESSION SAVED" : "NOT PAIRED"}</span></div>
        {pairing ? <div className="pairing-active">
          <div><span className="pair-label">PAIRING SESSION</span><code>{pairing.session_id}</code></div>
          {pairing.pair_code && <div><span className="pair-label">PAIR CODE · SHARE ONLY WITH YOUR DEVICE</span><strong className="pair-code">{pairing.pair_code}</strong><small>Code expires at {new Date(pairing.expires_at).toLocaleTimeString()}.</small></div>}
          <div className="paired-devices"><b>Known devices</b>{(pairing.devices || []).map((device) => <div className="paired-device" key={device.device_id}><span className={"pair-online-dot " + (isDeviceOnline(device) ? "online" : "offline")} />{device.name}<small>{isDeviceOnline(device) ? "ONLINE · heartbeat received" : "OFFLINE · no recent heartbeat"}{device.device_id === pairing.current_device_id || device.device_id === pairing.device_id ? " · This device" : ""}</small></div>)}</div>
          <label className="pair-target-label">SEND CHAT COMMANDS TO<select value={pairTargetDevice} onChange={(e) => setPairTargetDevice(e.target.value)}><option value="">This browser / this device</option>{(pairing.devices || []).filter((device) => /companion/i.test(device.name) && !device.disconnected).map((device) => <option key={device.device_id} value={device.device_id}>{device.name}</option>)}</select></label>
          <p className="pairing-note">Choose a paired companion to route commands from the main chat to that device. The Windows companion supports app shortcuts and web searches only; it reconnects to the relay automatically while running. Pairing does not enable arbitrary shell commands or hidden remote control.</p>
          <button className="pair-disconnect" type="button" onClick={disconnectPairing} disabled={pairBusy}>Disconnect this device</button>
        </div> : <div className="pairing-controls">
          <label>DEVICE NAME<input value={pairDeviceName} maxLength={80} onChange={(e) => setPairDeviceName(e.target.value)} placeholder="e.g. My PC" /></label>
          <button type="button" className="pair-primary" onClick={createPairing} disabled={pairBusy || !pairDeviceName.trim()}>{pairBusy ? "Working…" : "Create pairing code"}</button>
          <div className="pair-divider"><span>OR JOIN AN EXISTING SESSION</span></div>
          <label>6-DIGIT PAIR CODE<input inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={pairCode} onChange={(e) => setPairCode(e.target.value.split("").filter((char) => char >= "0" && char <= "9").join("").slice(0, 6))} placeholder="123456" /></label>
          <button type="button" className="pair-secondary" onClick={joinPairing} disabled={pairBusy || pairCode.length !== 6 || !pairDeviceName.trim()}>Pair this device</button>
        </div>}
        {pairNotice && <p className="pair-notice" role="status">{pairNotice}</p>}
      </section>

      <section className="capability-panel" id="capability-panel"><div className="capability-heading"><div><span className="tiny-icon"><ShieldCheck size={16} /></span><b>System Capabilities</b><small>Live backend-reported status · no simulated completion</small></div><button type="button" className="refresh-status" onClick={() => { setCapabilities(null); setCapabilityError(false); fetch("/api/capabilities").then((response) => { if (!response.ok) throw new Error("Status unavailable"); return response.json(); }).then(setCapabilities).catch(() => setCapabilityError(true)); }}>Refresh</button></div>{capabilityError ? <p className="capability-message">Capability status is unavailable. Check that the latest backend deployment has finished.</p> : !capabilities ? <p className="capability-message">Loading verified module status…</p> : <><div className="capability-summary"><span>{capabilities.modules.filter((module) => module.status === "ready").length} READY</span><span>{capabilities.modules.filter((module) => module.status === "limited").length} LIMITED</span><span>{capabilities.modules.filter((module) => module.status === "setup_required").length} SETUP REQUIRED</span></div><div className="capability-grid">{capabilities.modules.map((module) => <article className={"capability-card status-" + module.status} key={module.id}><div className="capability-card-top"><b>{module.name}</b><span>{statusLabel(module.status)}</span></div><p>{module.detail}</p></article>)}</div></>}</section>

      <section className="task-panel" id="task-panel"><div className="task-panel-heading"><div><span className="tiny-icon"><Activity size={16} /></span><b>Task Orchestrator</b><small>Queued AI tasks · progress, events and controls</small></div><button type="button" className="refresh-status" onClick={refreshTasks}>Refresh</button></div>
        <form className="task-create" onSubmit={submitTask}><textarea value={taskGoal} onChange={(e) => setTaskGoal(e.target.value)} maxLength={6000} placeholder="Describe a task for NOX… e.g. create a step-by-step plan for my project" aria-label="Task goal" /><button type="submit" disabled={taskBusy || taskGoal.trim().length < 3}><Play size={15} /> {taskBusy ? "Adding…" : "Run task"}</button></form>
        <p className="task-safety-note">NOX executes clear, low-risk open/search commands without repeated confirmation. Windows app launch still requires the opt-in local companion and its token; ambiguous app matches may ask you to choose. High-impact actions still require confirmation. Website navigation opens a tab and does not automate page actions.</p>
        {taskNotice && <p className="task-notice" role="status">{taskNotice}</p>}
        <div className="task-list">{tasks.length === 0 ? <p className="capability-message">No tasks yet. Create one above to test the queue.</p> : tasks.slice(0,8).map((task) => <article className="task-row" key={task.id}><div className="task-row-main"><div className="task-row-title"><b>{task.goal}</b><span className={"task-status task-" + task.status}>{task.status.replace("_"," ").toUpperCase()}</span></div><div className="task-progress"><span style={{width: task.progress + "%"}} /></div><div className="task-meta"><span>{task.progress}% · {task.attempts} attempt(s)</span><span>{new Date(task.updated_at).toLocaleTimeString()}</span></div>{task.error && <p className="task-error">{task.error}</p>}{task.result && <details className="task-result"><summary>View result</summary><p>{task.result}</p></details>}{task.events?.length > 0 && <details className="task-events"><summary>Execution log ({task.events.length})</summary>{task.events.slice(-5).map((entry,index)=><p key={index}><time>{new Date(entry.at).toLocaleTimeString()}</time> {entry.message}</p>)}</details>}</div><div className="task-actions">{task.status === "paused" ? <button title="Resume task" aria-label="Resume task" onClick={() => controlTask(task.id,"resume")}><Play size={14}/></button> : ["queued","running"].includes(task.status) ? <button title="Pause task" aria-label="Pause task" onClick={() => controlTask(task.id,"pause")}><Pause size={14}/></button> : null}{["queued","running","paused"].includes(task.status) && <button title="Cancel task" aria-label="Cancel task" onClick={() => controlTask(task.id,"cancel")}><XCircle size={14}/></button>}</div></article>)}</div>
      </section>
      <section className="chat-panel" id="chat-panel"><div className="panel-heading"><div><span className="tiny-icon"><AudioLines size={16} /></span><b>Conversation</b><small>Encrypted transport · API keys remain server-side</small></div><label className="language">LANGUAGE <select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="auto">Auto detect</option><option value="en">English</option><option value="hi">Hindi</option><option value="ur">Urdu</option><option value="hinglish">Hinglish</option></select></label></div>
        <div className="messages" ref={messagesContainerRef} onScroll={(event) => { const el = event.currentTarget; shouldFollowChatRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 96; }}>{messages.map((m, i) => <div className={"message " + m.role} key={i}><div className="avatar">{m.role === "assistant" ? <Bot size={17} /> : "YOU"}</div><div className="bubble"><div className="message-label">{m.role === "assistant" ? "NOX" : "YOU"}{m.mode === "demo" && <span className="demo-tag">DEMO</span>}</div><p>{m.content}</p>{m.role === "assistant" && <button type="button" className="message-speak" title="Play this reply aloud" aria-label="Play this reply aloud" onClick={() => speakText(m.content)}><Volume2 size={15} /> Listen</button>}</div></div>)}{busy && <div className="message assistant"><div className="avatar"><Bot size={17} /></div><div className="bubble"><div className="message-label">NOX</div><p className="typing">Processing<span>.</span><span>.</span><span>.</span></p></div></div>}<div ref={endRef} /></div>
        <div className={"voice-mode-panel " + (voiceMode ? "voice-mode-active" : "")} data-state={voiceState}>
          <div className="voice-orb-wrap"><div className={"voice-orb voice-orb-" + voiceState}><span /><span /><span /></div></div>
          <div className="voice-mode-copy"><b>{({ idle: "VOICE MODE", connecting: "CONNECTING", listening: "LISTENING", thinking: "THINKING", speaking: "NOX IS SPEAKING", interrupted: "PLAYBACK INTERRUPTED", muted: "MICROPHONE MUTED", error: "VOICE MODE ERROR" })[voiceState] || "VOICE MODE"}</b><small>{voiceMode ? "Mic active only in this session; your browser may process speech remotely." : "Start a hands-free conversation with NOX."}</small>{voiceMode && <p className="voice-transcript" aria-live="polite">{voiceTranscript}</p>}</div>
          <div className="voice-mode-controls">{!voiceMode ? <button type="button" className="voice-primary" onClick={startVoiceMode} disabled={voiceState === "connecting"}><Mic size={15} /> {voiceState === "connecting" ? "Connecting…" : "Start Voice Mode"}</button> : <><button type="button" className={"voice-control " + (voiceMuted ? "active" : "")} onClick={toggleVoiceMute} title={voiceMuted ? "Unmute microphone" : "Mute microphone"} aria-label={voiceMuted ? "Unmute microphone" : "Mute microphone"}>{voiceMuted ? <VolumeX size={16} /> : <Mic size={16} />}</button><button type="button" className="voice-control" onClick={interruptVoice} title="Interrupt AI speech" aria-label="Interrupt AI speech"><Pause size={16} /></button><button type="button" className="voice-end" onClick={stopVoiceMode}><XCircle size={15} /> End</button></>}</div>
          <div className="voice-settings"><label>Speed <input aria-label="Voice speed" type="range" min="0.75" max="1.25" step="0.05" value={voiceSpeed} onChange={(e) => setVoiceSpeed(Number(e.target.value))} /><span>{voiceSpeed.toFixed(2)}×</span></label><label>Volume <input aria-label="Voice volume" type="range" min="0" max="1" step="0.1" value={voiceVolume} onChange={(e) => setVoiceVolume(Number(e.target.value))} /><span>{Math.round(voiceVolume * 100)}%</span></label><label>Voice <select aria-label="Speech voice" value={selectedVoiceName} onChange={(e) => setSelectedVoiceName(e.target.value)}><option value="">Auto select</option>{availableVoices.map((voice) => <option key={voice.voiceURI || voice.name} value={voice.name}>{voice.name} · {voice.lang}</option>)}</select></label></div>
        </div>
        <form className="composer" onSubmit={(e) => { e.preventDefault(); sendMessage(); }}><button type="button" className={"icon-button mic " + (listening ? "recording" : "")} title="Voice input (single turn)" aria-label="Voice input (single turn)" onClick={toggleMic}><Mic size={18} /></button><button type="button" className={"icon-button voice-mode-trigger " + (voiceMode ? "active" : "")} title={voiceMode ? "End Voice Mode" : "Start hands-free Voice Mode"} aria-label={voiceMode ? "End Voice Mode" : "Start hands-free Voice Mode"} onClick={() => voiceMode ? stopVoiceMode() : startVoiceMode()} disabled={!voiceMode && voiceState === "connecting"}>{voiceMode ? <XCircle size={18} /> : <AudioLines size={18} />}</button><input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Message NOX... / NOX से कुछ पूछें" /><button type="button" className={"icon-button voice " + (speakReplies ? "enabled" : "")} title="Toggle voice replies" aria-label="Toggle voice replies" onClick={() => setSpeakReplies(!speakReplies)}>{speakReplies ? <Volume2 size={18} /> : <VolumeX size={18} />}</button><button className="send-button" type="submit" disabled={busy || !input.trim()}><Send size={17} /><span>Send</span></button></form>
        <div className="composer-foot"><span><Activity size={13} /> {voiceMode ? (voiceMuted ? "MICROPHONE MUTED" : voiceState.toUpperCase()) : listening ? "LISTENING…" : "READY FOR INPUT"}</span><span>{voiceMode ? "VOICE SESSION · BROWSER SPEECH ENGINE" : speakReplies ? "VOICE REPLIES ON" : "VOICE REPLIES OFF"} · AI quality depends on configured provider</span></div>
      </section>
      <footer><span>© 2026 NOX AI</span><span>BUILT FOR FOCUS <ChevronDown size={12} /></span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById("root")).render(<App />);
