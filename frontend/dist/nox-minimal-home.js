(() => {
  "use strict";
  if (window.NOXMinimalHome) return;
  const $ = (id) => document.getElementById(id);
  const style = document.createElement("style");
  style.id = "nox-minimal-home-style";
  style.textContent = `
    html,body{width:100%;height:100%;min-height:0!important;overflow:hidden!important;overscroll-behavior:none}
    body{position:relative}
    .topbar{height:62px!important;min-height:62px!important;padding:0 18px!important;position:relative!important;z-index:30}
    .topright #clock,.topright #layoutBtn,.topright #motionBtn,.topright [data-scroll="visualIntelligencePanel"],.topright [data-scroll="godsEyeViewPanel"]{display:none!important}
    .mobiletabs{display:none!important}
    #dashboard.layout.nox-home-layout{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:0!important;padding:0!important;margin:0!important;width:100%!important;max-width:none!important;height:calc(100dvh - 62px)!important;min-height:0!important;overflow:hidden!important}
    #dashboard.nox-home-layout>.leftstack,#dashboard.nox-home-layout>.rightstack{display:none!important}
    #dashboard.nox-home-layout>.mainstack{display:block!important;grid-column:1!important;width:100%!important;height:100%!important;min-height:0!important;overflow:hidden!important;padding:0!important;margin:0!important}
    #dashboard.nox-home-layout>.mainstack>.panel:not(#corePanel){display:none!important}
    #corePanel{position:relative!important;display:block!important;width:100%!important;height:100%!important;min-height:0!important;margin:0!important;border:0!important;border-radius:0!important;overflow:hidden!important;background:radial-gradient(ellipse at 50% 46%,rgba(26,54,86,.52),rgba(7,11,19,.2) 38%,#070b13 76%)!important;box-shadow:none!important;backdrop-filter:none!important}
    #corePanel .coretop,#corePanel .coretitle,#corePanel .corebottom{display:none!important}
    #corePanel .corecanvas{position:absolute!important;inset:0!important;display:block!important;width:100%!important;height:100%!important;min-height:0!important;margin:0!important;pointer-events:none}
    .nox-home-control{position:fixed;z-index:5000;display:flex;align-items:center;justify-content:center;gap:9px;min-height:48px;border:1px solid rgba(113,234,255,.4);border-radius:16px;background:linear-gradient(135deg,rgba(12,29,47,.94),rgba(17,17,40,.94));color:#e8faff;box-shadow:0 10px 40px #0007,0 0 26px rgba(79,211,255,.09);backdrop-filter:blur(18px);font:750 11px/1 ui-monospace,monospace;letter-spacing:.11em;padding:0 18px;cursor:pointer;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}
    .nox-home-control:hover,.nox-home-control:focus-visible{transform:translateY(-2px);border-color:#71eaff;box-shadow:0 12px 42px #0008,0 0 28px rgba(79,211,255,.18)}
    .nox-home-control .control-icon{font-size:17px;line-height:1}
    .nox-emergency-control{top:74px!important;right:12px!important;bottom:auto!important;max-width:calc(100vw - 24px)!important;z-index:6000!important}
    .nox-emergency-control button{padding:8px 10px!important;font-size:9px!important}
    .nox-emergency-status{min-width:60px!important;font-size:8px!important}

    #noxPersonalityHome{left:12px;top:74px;min-width:142px;min-height:46px;padding:0 12px;border-color:rgba(161,139,255,.55);background:linear-gradient(135deg,rgba(22,28,50,.96),rgba(28,19,53,.96))}
    #noxPersonalityHome small{display:block;font-size:8px;letter-spacing:.06em;color:#b9a9ff;font-weight:500;margin-top:5px}
    #noxVoiceHome{left:50%;bottom:max(22px,env(safe-area-inset-bottom));transform:translateX(-50%);min-width:174px;min-height:54px;border-radius:999px;background:linear-gradient(115deg,rgba(14,47,64,.97),rgba(31,24,67,.97));border-color:#71eaff88;box-shadow:0 8px 38px #0008,0 0 30px #56ddff17}
    #noxVoiceHome:hover{transform:translate(-50%,-2px)}
    #noxVoiceHome[data-active="true"]{border-color:#9fffe0;box-shadow:0 0 0 1px #9fffe055,0 0 32px #62e9cb30}
    #noxVoiceHome small{display:block;font-size:8px;letter-spacing:.08em;color:#9ab8cb;font-weight:500;margin-top:5px}
    #noxTextChatHome{right:max(18px,env(safe-area-inset-right));top:50%;transform:translateY(-50%);writing-mode:vertical-rl;min-height:148px;min-width:48px;padding:16px 12px;gap:10px}
    #noxTextChatHome:hover{transform:translateY(calc(-50% - 2px))}
    #noxChatLayer{position:fixed;inset:0;z-index:12000;display:none;align-items:stretch;justify-content:flex-end}
    #noxChatLayer.open{display:flex}
    #noxChatBackdrop{position:absolute;inset:0;width:100%;height:100%;border:0;background:rgba(2,7,15,.72);backdrop-filter:blur(5px)}
    #noxChatSheet{position:relative;z-index:1;width:min(560px,100vw);height:100dvh;max-height:100dvh;min-height:0;display:flex;flex-direction:column;border-radius:0;border-top:0;border-right:0;border-bottom:0;border-left:1px solid rgba(113,234,255,.32);background:linear-gradient(160deg,#0d1726,#070c16 72%);box-shadow:-25px 0 90px #0009;transform:translateX(102%);transition:transform .24s cubic-bezier(.2,.75,.25,1)}
    #noxChatLayer.open #noxChatSheet{transform:translateX(0)}
    #noxChatSheet .nox-chat-slot{display:flex;flex:1;min-height:0;overflow:hidden}
    #noxChatSheet .chatpanel{display:flex!important;flex:1;min-height:0!important;height:100%;overflow:hidden;border:0;border-radius:0;background:transparent;box-shadow:none}
    #noxChatSheet .panelhead{flex:0 0 auto;padding:16px}
    #noxChatSheet .chatmessages{flex:1;min-height:0;max-height:none!important;overflow-y:auto;overscroll-behavior:contain}
    #noxChatSheet .chatinput{flex:0 0 auto;padding-bottom:max(12px,env(safe-area-inset-bottom))}
    #noxChatSheet .chatinput textarea{resize:none;max-height:24vh}
    #noxChatSheet .chatpanel>.tiny{flex:0 0 auto}
    #noxChatClose{width:36px;height:36px;border:1px solid #315067;border-radius:10px;background:#101e2d;color:#dffaff;font-size:21px}
    body.nox-chat-open #noxVoiceHome,body.nox-chat-open #noxTextChatHome{visibility:hidden;pointer-events:none}
    @media(max-width:720px){
      .topbar{height:56px!important;min-height:56px!important;padding:0 10px!important;gap:8px!important}
      .brand{gap:7px!important}.brandmark{width:28px!important;height:28px!important;border-radius:8px!important}
      .brandname{font-size:12px!important;letter-spacing:.14em!important}.brandname small{font-size:7px!important}
      .topright{gap:6px!important}.topright #accountOpen{font-size:9px;padding:7px 8px}
      #dashboard.layout.nox-home-layout{height:calc(100dvh - 56px)!important}
      #noxTextChatHome{right:max(10px,env(safe-area-inset-right));min-height:124px;min-width:42px;padding:13px 9px;font-size:9px;border-radius:13px}
      #noxPersonalityHome{left:10px;top:66px;min-height:42px;min-width:128px;font-size:9px;padding:0 9px}
      #noxVoiceHome{bottom:max(18px,env(safe-area-inset-bottom));min-height:50px;min-width:158px}
      #noxChatSheet{width:100vw;border-left:0}
    }
    @media(prefers-reduced-motion:reduce){.nox-home-control,#noxChatSheet{transition:none!important}}
  `;
  document.head.appendChild(style);

  const dashboard = $("dashboard");
  const core = $("corePanel");
  const chat = $("chatPanel");
  if (!dashboard || !core || !chat) {
    console.error("NOX minimal home could not initialize: required dashboard panels are missing.");
    return;
  }
  dashboard.classList.add("nox-home-layout");
  document.querySelector(".mobiletabs")?.setAttribute("aria-hidden", "true");

  // Move the real chat panel instead of cloning it; existing handlers and state stay intact.
  const chatLayer = document.createElement("div");
  chatLayer.id = "noxChatLayer";
  chatLayer.setAttribute("aria-hidden", "true");
  chatLayer.innerHTML = `
    <button id="noxChatBackdrop" type="button" aria-label="Close text chat"></button>
    <section id="noxChatSheet" role="dialog" aria-modal="true" aria-label="NOX Text Chat">
      <button id="noxChatClose" type="button" aria-label="Close text chat" style="position:absolute;right:12px;top:10px;z-index:3">×</button>
      <div class="nox-chat-slot"></div>
    </section>`;
  document.body.appendChild(chatLayer);
  chatLayer.querySelector(".nox-chat-slot").appendChild(chat);
  chat.hidden = false;
  chat.style.display = "flex";
  chat.style.flex = "1";
  chat.style.minHeight = "0";
  const chatHead = chat.querySelector(".panelhead");
  if (chatHead) chatHead.style.paddingRight = "58px";

  const voiceButton = document.createElement("button");
  voiceButton.id = "noxVoiceHome";
  voiceButton.type = "button";
  voiceButton.className = "nox-home-control";
  voiceButton.setAttribute("aria-pressed", "false");
  voiceButton.innerHTML = '<span class="control-icon" aria-hidden="true">◖</span><span>VOICE TALK<small id="noxVoiceHomeStatus">TAP TO SPEAK</small></span>';
  document.body.appendChild(voiceButton);

  const personalityButton = document.createElement("button");
  personalityButton.id = "noxPersonalityHome";
  personalityButton.type = "button";
  personalityButton.className = "nox-home-control";
  personalityButton.setAttribute("aria-label", "Switch between NOX and LUMI");
  personalityButton.innerHTML = '<span class="control-icon" aria-hidden="true">✧</span><span id="noxPersonalityHomeLabel">NOX ACTIVE<small>SWITCH TO LUMI</small></span>';
  document.body.appendChild(personalityButton);
  function syncPersonalityHome() {
    const active = $("personalitySelect")?.value === "lumi" ? "lumi" : "nox";
    const label = $("noxPersonalityHomeLabel");
    if (label) label.innerHTML = (active === "lumi" ? "LUMI ACTIVE" : "NOX ACTIVE") + '<small>SWITCH TO ' + (active === "lumi" ? "NOX" : "LUMI") + '</small>';
    personalityButton.style.borderColor = active === "lumi" ? "#b9a4ff" : "#71eaff88";
    personalityButton.setAttribute("aria-label", "Currently " + (active === "lumi" ? "LUMI" : "NOX") + "; switch to " + (active === "lumi" ? "NOX" : "LUMI"));
  }
  personalityButton.addEventListener("click", () => {
    const selector = $("personalitySelect");
    if (!selector) return;
    selector.value = selector.value === "lumi" ? "nox" : "lumi";
    selector.dispatchEvent(new Event("change", { bubbles: true }));
    syncPersonalityHome();
  });
  $("personalitySelect")?.addEventListener("change", syncPersonalityHome);
  syncPersonalityHome();

  const chatButton = document.createElement("button");
  chatButton.id = "noxTextChatHome";
  chatButton.type = "button";
  chatButton.className = "nox-home-control";
  chatButton.setAttribute("aria-haspopup", "dialog");
  chatButton.setAttribute("aria-expanded", "false");
  chatButton.innerHTML = '<span class="control-icon" aria-hidden="true">▤</span><span>TEXT CHAT</span>';
  document.body.appendChild(chatButton);

  const closeChat = () => {
    chatLayer.classList.remove("open");
    chatLayer.setAttribute("aria-hidden", "true");
    chatButton.setAttribute("aria-expanded", "false");
    document.body.classList.remove("nox-chat-open");
    chatButton.focus({ preventScroll: true });
  };
  const openChat = () => {
    chatLayer.classList.add("open");
    chatLayer.setAttribute("aria-hidden", "false");
    chatButton.setAttribute("aria-expanded", "true");
    document.body.classList.add("nox-chat-open");
    window.setTimeout(() => $("messageInput")?.focus({ preventScroll: true }), 80);
  };
  chatButton.addEventListener("click", openChat);
  $("noxChatClose").addEventListener("click", closeChat);
  $("noxChatBackdrop").addEventListener("click", closeChat);

  const voiceControl = $("voiceToggle") || $("voiceStart") || $("chatVoiceBtn");
  voiceButton.addEventListener("click", () => {
    if (!voiceControl) {
      if ($("voiceStatus")) $("voiceStatus").textContent = "UNAVAILABLE";
      $("noxVoiceHomeStatus").textContent = "VOICE CONTROL UNAVAILABLE";
      return;
    }
    voiceControl.click();
    window.setTimeout(updateVoiceState, 100);
    window.setTimeout(updateVoiceState, 500);
  });
  function updateVoiceState() {
    const status = ($("voiceStatus")?.textContent || $("voiceSub")?.textContent || "STANDBY").trim().toUpperCase();
    const active = /LISTENING|THINKING|SPEAKING|PAUSED|PROCESSING/.test(status);
    voiceButton.dataset.active = active ? "true" : "false";
    voiceButton.setAttribute("aria-pressed", active ? "true" : "false");
    $("noxVoiceHomeStatus").textContent = active ? status.slice(0, 28) : (/ERROR|UNSUPPORTED|UNAVAILABLE/.test(status) ? status.slice(0, 28) : "TAP TO SPEAK");
  }
  const voiceStatus = $("voiceStatus");
  if (voiceStatus && typeof MutationObserver !== "undefined") {
    new MutationObserver(updateVoiceState).observe(voiceStatus, { childList: true, subtree: true, characterData: true });
  }
  updateVoiceState();

  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && chatLayer.classList.contains("open")) closeChat();
  });
  window.NOXMinimalHome = { openChat, closeChat, updateVoiceState };
})();