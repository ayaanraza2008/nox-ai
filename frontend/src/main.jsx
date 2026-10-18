import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, AudioLines, Bot, ChevronDown, Command, Mic, Send, ShieldCheck, Sparkles, Volume2, VolumeX, Zap } from "lucide-react";
import "./style.css";

function App() {
  const [messages, setMessages] = useState([{ role: "assistant", content: "Systems initialized. I'm NOX. What are we working on today?" }]);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [speakReplies, setSpeakReplies] = useState(false);
  const [status, setStatus] = useState("ALL SYSTEMS READY");
  const endRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

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
      if (speakReplies && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(data.reply);
        utterance.lang = language === "hi" ? "hi-IN" : language === "ur" ? "ur-PK" : "en-US";
        window.speechSynthesis.speak(utterance);
      }
    } catch (error) {
      setMessages((old) => [...old, { role: "assistant", content: "Connection error: " + error.message }]);
      setStatus("CONNECTION ISSUE");
    } finally {
      setBusy(false);
    }
  }

  function toggleMic() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMessages((old) => [...old, { role: "assistant", content: "Speech recognition is not supported by this browser. Try a supported browser or type your message." }]);
      return;
    }
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = language === "hi" ? "hi-IN" : language === "ur" ? "ur-PK" : "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setInput(transcript);
      setListening(false);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
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
      <header className="topbar"><div className="breadcrumb">NOX / <span>COMMAND CENTER</span></div><div className="top-status"><i /> {status}</div></header>
      <section className="hero"><div className="eyebrow"><span /> PERSONAL AI INTERFACE</div><h1>Think beyond.<br /><em>Move with intent.</em></h1><p>Your space to reason, create, and get things done.</p>
        <div className="core-wrap"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="core"><div className="core-inner"><Bot size={38} /></div></div><div className="core-caption"><span className="pulse" /> NOX CORE <small>READY TO ASSIST</small></div></div>
      </section>
      <section className="chat-panel"><div className="panel-heading"><div><span className="tiny-icon"><AudioLines size={16} /></span><b>Conversation</b><small>Encrypted transport · API keys remain server-side</small></div><label className="language">LANGUAGE <select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="auto">Auto detect</option><option value="en">English</option><option value="hi">Hindi</option><option value="ur">Urdu</option><option value="hinglish">Hinglish</option></select></label></div>
        <div className="messages">{messages.map((m, i) => <div className={"message " + m.role} key={i}><div className="avatar">{m.role === "assistant" ? <Bot size={17} /> : "YOU"}</div><div className="bubble"><div className="message-label">{m.role === "assistant" ? "NOX" : "YOU"}{m.mode === "demo" && <span className="demo-tag">DEMO</span>}</div><p>{m.content}</p></div></div>)}{busy && <div className="message assistant"><div className="avatar"><Bot size={17} /></div><div className="bubble"><div className="message-label">NOX</div><p className="typing">Processing<span>.</span><span>.</span><span>.</span></p></div></div>}<div ref={endRef} /></div>
        <form className="composer" onSubmit={(e) => { e.preventDefault(); sendMessage(); }}><button type="button" className={"icon-button mic " + (listening ? "recording" : "")} title="Voice input" onClick={toggleMic}><Mic size={18} /></button><input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Message NOX... / NOX से कुछ पूछें" /><button type="button" className={"icon-button voice " + (speakReplies ? "enabled" : "")} title="Toggle voice replies" onClick={() => setSpeakReplies(!speakReplies)}>{speakReplies ? <Volume2 size={18} /> : <VolumeX size={18} />}</button><button className="send-button" type="submit" disabled={busy || !input.trim()}><Send size={17} /><span>Send</span></button></form>
        <div className="composer-foot"><span><Activity size={13} /> {listening ? "LISTENING…" : "READY FOR INPUT"}</span><span>AI quality depends on configured provider</span></div>
      </section>
      <footer><span>© 2026 NOX AI</span><span>BUILT FOR FOCUS <ChevronDown size={12} /></span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById("root")).render(<App />);
