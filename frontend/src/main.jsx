import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, AudioLines, Bot, ChevronDown, Command, Mic, Pause, Play, Send, ShieldCheck, Sparkles, Volume2, VolumeX, XCircle, Zap } from "lucide-react";
import "./style.css";
import HolographicCore from "./HolographicCore.jsx";

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
      return Array.isArray(saved) ? saved.slice(0, 30) : [];
    } catch { return []; }
  });
  const [currentChatId, setCurrentChatId] = useState(() => {
    try { return localStorage.getItem("nox-current-chat-id") || crypto.randomUUID(); }
    catch { return String(Date.now()); }
  });
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
    try {
      localStorage.setItem("nox-current-chat", JSON.stringify(messages.slice(-300)));
      localStorage.setItem("nox-current-chat-id", currentChatId);
      const titleMessage = messages.find((item) => item.role === "user")?.content || "New conversation";
      const entry = { id: currentChatId, title: titleMessage.slice(0, 64), updatedAt: new Date().toISOString(), messages: messages.slice(-300) };
      setChatHistory((old) => {
        const next = [entry, ...old.filter((item) => item.id !== currentChatId)].slice(0, 30);
        try { localStorage.setItem("nox-chat-history", JSON.stringify(next)); } catch {}
        return next;
      });
    } catch {}
  }, [messages, currentChatId]);

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

  function deleteSavedChat(id) {
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
          const companionDevices = (data.devices || []).filter((device) => /companion/i.test(device.name) && !device.disconnected);
          setPairing((current) => current ? { ...current, devices: data.devices || [], current_device_id: data.current_device_id } : current);
          setPairTargetDevice((current) => current && companionDevices.some((device) => device.device_id === current) ? current : (companionDevices[0]?.device_id || ""));
        }
      } catch { if (active) setPairNotice("Pairing server temporarily unreachable. NOX will retry automatically."); }
    };
    checkPairing();
    const timer = window.setInterval(checkPairing, 10000);
    return () => { active = false; window.clearInterval(timer); };
  }, [pairing?.session_id, pairing?.device_token]);

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
        for (let attempt = 0; attempt < 10; attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 1500));
          const statusResponse = await fetch("/api/pairing/commands/" + encodeURIComponent(data.command_id) + "?session_id=" + encodeURIComponent(pairing.session_id), {
            headers: { "X-NOX-Device-Token": pairing.device_token }
          });
          if (!statusResponse.ok) continue;
          const statusData = await statusResponse.json();
          if (statusData.command?.status === "completed") {
            let result = {};
            try { result = JSON.parse(statusData.command.result || "{}"); } catch {}
            const outcome = pairedTarget.name + ": " + (result.message || result.status || "Command completed.");
            setTaskNotice(outcome);
            return outcome;
          }
        }
        const pendingOutcome = "Command is still queued or running on " + pairedTarget.name + ". Check that its companion is online and paired.";
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
      const token = window.prompt("Enter your local NOX companion token. It is not saved by this page:");
      if (!token) {
        setTaskNotice("App launch cancelled: companion token not provided.");
        return;
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
        let selected = matches[0];
        if (matches.length > 1) {
          const choices = matches.map((app, index) => (index + 1) + ". " + app.name).join("\n");
          const answer = window.prompt("Which app should NOX open?\n" + choices + "\n\nEnter a number:", "1");
          const index = Number(answer) - 1;
          if (answer === null || !Number.isInteger(index) || index < 0 || index >= matches.length) {
            setTaskNotice("App launch cancelled.");
            return;
          }
          selected = matches[index];
        }
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

    // Route explicit action/search commands from chat through the same real command handler as Task Orchestrator.
    // Ordinary conversational messages continue to the AI chat endpoint.
    const commandLike = /^(?:please\s+)?(?:open|launch|start|visit|go to|browse to|search(?:\s+the\s+web)?(?:\s+for)?|google|find online|internet par|khol|kholo|khul|chalao|chalu karo|खोलो|खोल|चलाओ)\b/i.test(value)
      || /^(?:youtube|google|gmail|github|instagram|facebook|whatsapp web|wikipedia|reddit|linkedin|chatgpt|render|google drive|bing)\s+(?:kholo|open|launch)$/i.test(value);
    if (commandLike) {
      setInput("");
      setMessages((old) => [...old, { role: "user", content: value }]);
      setBusy(true);
      try {
        const outcome = await submitTask(null, value);
        setMessages((old) => [...old, { role: "assistant", content: typeof outcome === "string" ? outcome : "Command handled. Check the task status for details." }]);
      } catch (error) {
        setMessages((old) => [...old, { role: "assistant", content: "Command failed: " + error.message }]);
      } finally {
        setBusy(false);
      }
      return;
    }

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
      <button className="nav-item" onClick={startNewChat}><Sparkles size={17} /> New chat</button>
      <div className="side-label">CHAT HISTORY</div>
      <div className="chat-history-list">{chatHistory.map((chat) => <div className={"chat-history-item" + (chat.id === currentChatId ? " current" : "")} key={chat.id}><button type="button" title={chat.title} onClick={() => openSavedChat(chat)}>{chat.title || "New conversation"}</button><button type="button" className="chat-history-delete" aria-label={"Delete chat " + (chat.title || "")} title="Delete chat" onClick={() => deleteSavedChat(chat.id)}>×</button></div>)}</div>
      <button className="nav-item" onClick={() => document.getElementById("pairing-panel")?.scrollIntoView({ behavior: "smooth", block: "center" })}><ShieldCheck size={17} /> Pair devices <span className="nav-dot" style={{ background: pairing ? "#65d7a1" : "#777" }} /></button>
      <div className="side-bottom"><div className="secure"><ShieldCheck size={17} /><div><b>Private by design</b><small>Keys stay on the server</small></div></div><div className="version">NOX CORE <span>v0.1.0</span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumb">NOX / <span>COMMAND CENTER</span></div><div className="topbar-tools"><label className="accent-picker">ACCENT <select aria-label="Interface accent color" value={accentColor} onChange={(event) => setAccentColor(event.target.value)}><option value="#ff3e4d">Crimson</option><option value="#a78bfa">Violet</option><option value="#38bdf8">Ice blue</option><option value="#34d399">Emerald</option><option value="#fbbf24">Amber</option></select></label><div className="top-status"><i /> {status}</div></div></header>
      <section className="hero"><div className="eyebrow"><span /> PERSONAL AI INTERFACE</div><h1>Think beyond.<br /><em>Move with intent.</em></h1><p>Your space to reason, create, and get things done.</p>
        <div className="core-wrap"><HolographicCore mode={coreMode === "NOX_SPEAKING" ? coreMode : busy ? "PROCESSING" : coreMode} micLevelRef={micLevelRef} ttsLevelRef={ttsLevelRef} /></div>
      </section>
      <section className="pairing-panel" id="pairing-panel">
        <div className="task-panel-heading"><div><span className="tiny-icon"><ShieldCheck size={16} /></span><b>Device Pairing</b><small>Connect your PC and mobile to the same NOX session</small></div><span className={"pair-status " + (pairing ? "paired" : "")}>{pairing ? "SESSION SAVED" : "NOT PAIRED"}</span></div>
        {pairing ? <div className="pairing-active">
          <div><span className="pair-label">PAIRING SESSION</span><code>{pairing.session_id}</code></div>
          {pairing.pair_code && <div><span className="pair-label">PAIR CODE · SHARE ONLY WITH YOUR DEVICE</span><strong className="pair-code">{pairing.pair_code}</strong><small>Code expires at {new Date(pairing.expires_at).toLocaleTimeString()}.</small></div>}
          <div className="paired-devices"><b>Known devices</b>{(pairing.devices || []).map((device) => <div className="paired-device" key={device.device_id}><span className="pair-online-dot" />{device.name}<small>{device.device_id === pairing.current_device_id || device.device_id === pairing.device_id ? "This device" : "Paired session"}</small></div>)}</div>
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

      <section className="capability-panel"><div className="capability-heading"><div><span className="tiny-icon"><ShieldCheck size={16} /></span><b>System Capabilities</b><small>Live backend-reported status · no simulated completion</small></div><button type="button" className="refresh-status" onClick={() => { setCapabilities(null); setCapabilityError(false); fetch("/api/capabilities").then((response) => { if (!response.ok) throw new Error("Status unavailable"); return response.json(); }).then(setCapabilities).catch(() => setCapabilityError(true)); }}>Refresh</button></div>{capabilityError ? <p className="capability-message">Capability status is unavailable. Check that the latest backend deployment has finished.</p> : !capabilities ? <p className="capability-message">Loading verified module status…</p> : <><div className="capability-summary"><span>{capabilities.modules.filter((module) => module.status === "ready").length} READY</span><span>{capabilities.modules.filter((module) => module.status === "limited").length} LIMITED</span><span>{capabilities.modules.filter((module) => module.status === "setup_required").length} SETUP REQUIRED</span></div><div className="capability-grid">{capabilities.modules.map((module) => <article className={"capability-card status-" + module.status} key={module.id}><div className="capability-card-top"><b>{module.name}</b><span>{statusLabel(module.status)}</span></div><p>{module.detail}</p></article>)}</div></>}</section>

      <section className="task-panel"><div className="task-panel-heading"><div><span className="tiny-icon"><Activity size={16} /></span><b>Task Orchestrator</b><small>Queued AI tasks · progress, events and controls</small></div><button type="button" className="refresh-status" onClick={refreshTasks}>Refresh</button></div>
        <form className="task-create" onSubmit={submitTask}><textarea value={taskGoal} onChange={(e) => setTaskGoal(e.target.value)} maxLength={6000} placeholder="Describe a task for NOX… e.g. create a step-by-step plan for my project" aria-label="Task goal" /><button type="submit" disabled={taskBusy || taskGoal.trim().length < 3}><Play size={15} /> {taskBusy ? "Adding…" : "Run task"}</button></form>
        <p className="task-safety-note">NOX executes clear, low-risk open/search commands without repeated confirmation. Windows app launch still requires the opt-in local companion and its token; ambiguous app matches may ask you to choose. High-impact actions still require confirmation. Website navigation opens a tab and does not automate page actions.</p>
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
