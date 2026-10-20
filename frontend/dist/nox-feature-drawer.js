(() => {
  "use strict";
  if (window.NOXFeatureDrawer) return;
  const $ = (id) => document.getElementById(id);
  const groups = [
    { title: "AI WORKSPACE", subtitle: "Voice, tasks and creation", ids: ["voicePanel", "taskPanel", "researchPanel", "knowledgePanel", "codePanel"] },
    { title: "VISION & RESEARCH", subtitle: "Camera intelligence and public-source research", ids: ["visionPanel", "publicResearchPanel", "analyticsPanel"] },
    { title: "SYSTEM & PREFERENCES", subtitle: "Memory, connected tools, privacy and diagnostics", ids: ["memoryPanel", "toolsPanel", "networkPanel", "systemPanel"] }
  ,{ title: "AUTOMATION & DEVOPS", subtitle: "Agent execution, project changes and repository health", ids: [] }
  ];
  const layer = document.createElement("div");
  layer.id = "noxFeatureLayer";
  layer.className = "nox-feature-layer";
  layer.setAttribute("aria-hidden", "true");
  layer.innerHTML = `
    <button class="nox-feature-backdrop" type="button" aria-label="Close feature panel"></button>
    <aside class="nox-feature-drawer" role="dialog" aria-modal="true" aria-labelledby="noxFeatureTitle" tabindex="-1">
      <header class="nox-feature-head">
        <div><div class="nox-feature-kicker">NOX MODULES</div><h2 id="noxFeatureTitle">Feature Center</h2><p>Dedicated tools, grouped in one place.</p></div>
        <button class="nox-feature-close" type="button" aria-label="Close features">×</button>
      </header>
      <nav class="nox-feature-nav" aria-label="Feature groups">
        <button type="button" data-group-target="noxGroup0">AI Workspace</button>
        <button type="button" data-group-target="noxGroup1">Vision & Research</button>
        <button type="button" data-group-target="noxGroup2">System</button>
        <button type="button" data-group-target="noxGroup3">Automation & DevOps</button>
      </nav>
      <div class="nox-feature-content"></div>
      <footer class="nox-feature-foot">Modules open only when selected. Camera access still requires your explicit permission.</footer>
    </aside>`;
  const style = document.createElement("style");
  style.textContent = `
    .nox-feature-layer{position:fixed;inset:0;z-index:10000;pointer-events:none;visibility:hidden}
    .nox-feature-layer.open{pointer-events:auto;visibility:visible}
    .nox-feature-backdrop{position:absolute;inset:0;width:100%;height:100%;border:0;background:rgba(2,7,15,.72);opacity:0;transition:opacity .22s;backdrop-filter:blur(5px)}
    .nox-feature-layer.open .nox-feature-backdrop{opacity:1}
    .nox-feature-drawer{position:absolute;right:0;top:0;bottom:0;width:min(600px,94vw);padding:20px 18px 14px;background:linear-gradient(160deg,#0d1726f7,#070c16fc 72%);border-left:1px solid rgba(90,210,236,.25);box-shadow:-25px 0 90px #0009;display:flex;flex-direction:column;transform:translateX(102%);transition:transform .26s cubic-bezier(.2,.75,.25,1);overflow:hidden}
    .nox-feature-layer.open .nox-feature-drawer{transform:translateX(0)}
    .nox-feature-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:3px 2px 15px;border-bottom:1px solid var(--line,#203145)}
    .nox-feature-kicker{font-size:9px;letter-spacing:.22em;color:var(--cyan,#6ee7f9);font-weight:800}
    .nox-feature-head h2{font-size:20px;letter-spacing:.02em;margin:5px 0}
    .nox-feature-head p{font-size:11px;color:var(--muted,#8ea2b8);margin:0}
    .nox-feature-close{width:36px;height:36px;border-radius:11px;border:1px solid var(--line,#203145);background:#111e30;color:#d7f8ff;font-size:24px;cursor:pointer}
    .nox-feature-nav{display:flex;gap:7px;overflow:auto;padding:12px 0;flex-shrink:0}
    .nox-feature-nav button{white-space:nowrap;border:1px solid var(--line,#203145);border-radius:999px;background:#0e1b2b;color:#b8c9da;padding:8px 11px;font-size:10px;cursor:pointer}
    .nox-feature-nav button:hover,.nox-feature-nav button:focus-visible{border-color:var(--cyan,#6ee7f9);color:var(--cyan,#6ee7f9)}
    .nox-feature-content{overflow:auto;min-height:0;flex:1;padding:0 2px 18px;scroll-behavior:smooth}
    .nox-feature-group{scroll-margin-top:10px;margin:8px 0 20px}
    .nox-feature-group-head{padding:8px 2px 10px}
    .nox-feature-group-head h3{font-size:10px;letter-spacing:.16em;color:var(--cyan,#6ee7f9);margin:0 0 5px}
    .nox-feature-group-head p{font-size:11px;color:var(--muted,#8ea2b8);margin:0}
    .nox-feature-group .panel{margin:0 0 10px;width:100%;min-width:0}
    .nox-feature-group .panelbody{min-width:0}
    .nox-feature-group-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
    .nox-feature-back-to-group{flex-shrink:0;border:1px solid #29435a;border-radius:8px;background:#0d1b2b;color:#bdefff;padding:8px 10px;font-size:10px}
    .nox-feature-list,.nox-launch-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:6px}
    .nox-launch-card{min-width:0;text-align:left;border:1px solid #29435a;border-radius:12px;background:linear-gradient(145deg,#101f31,#0a1422);color:#d9f4ff;padding:14px;cursor:pointer}
    .nox-launch-card strong{display:block;font-size:11px;margin-bottom:6px}
    .nox-launch-card span{display:block;font-size:10px;line-height:1.5;color:#91a8bd}
    .nox-launch-card:hover,.nox-launch-card:focus-visible{border-color:var(--cyan,#6ee7f9);box-shadow:0 0 18px #4bdcf21a}
    .nox-feature-group .nox-drawer-panel[hidden]{display:none!important}
    .nox-feature-group.feature-open .nox-feature-list{display:none}
    .nox-feature-group.feature-open .nox-feature-group-head p{display:none}
    .nox-feature-group.feature-open .nox-feature-group-head h3{font-size:12px}.nox-feature-foot{padding:11px 2px 2px;border-top:1px solid var(--line,#203145);font-size:10px;color:var(--muted,#8ea2b8);flex-shrink:0}
    .nox-feature-trigger{display:inline-flex;align-items:center;gap:7px}#noxSwarmOpen,#noxProjectOpen,#noxGithubOpen,#noxCiOpen{display:none!important}
    .nox-feature-trigger .feature-count{font-size:9px;border:1px solid #254154;border-radius:20px;padding:2px 6px;color:var(--cyan,#6ee7f9)}
    .mobiletabs{display:none!important}
    .layout.nox-home-layout{grid-template-columns:minmax(0,1fr);max-width:1500px}
    .layout.nox-home-layout .leftstack[hidden],.layout.nox-home-layout .rightstack[hidden]{display:none!important}
    .layout.nox-home-layout .mainstack{grid-column:1;display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.78fr);align-items:start;gap:12px}
    .layout.nox-home-layout #corePanel{grid-row:span 2}
    .layout.nox-home-layout #chatPanel{min-width:0}
    .layout.nox-home-layout #corePanel,.layout.nox-home-layout #chatPanel{width:100%;min-width:0}
    @media(max-width:760px){.nox-feature-drawer{width:100%;padding:14px 12px 10px}.layout.nox-home-layout .mainstack{display:flex;flex-direction:column}.layout.nox-home-layout #corePanel{order:0}.layout.nox-home-layout #chatPanel{order:1}.nox-feature-group .panel{border-radius:12px}}
    @media(prefers-reduced-motion:reduce){.nox-feature-backdrop,.nox-feature-drawer{transition:none}}
  `;
  document.head.append(style);
  document.body.append(layer);
  const content = layer.querySelector(".nox-feature-content");
  const groupSections = [];
  groups.forEach((group, index) => {
    const section = document.createElement("section");
    section.className = "nox-feature-group";
    section.id = "noxGroup" + index;
    section.innerHTML = '<div class="nox-feature-group-head"><div><h3></h3><p></p></div><button type="button" class="nox-feature-back-to-group hidden">← All features</button></div><div class="nox-feature-list"></div>';
    section.querySelector("h3").textContent = group.title;
    section.querySelector("p").textContent = group.subtitle;
    const list = section.querySelector(".nox-feature-list");
    group.ids.forEach(id => {
      const panel = $(id);
      if (!panel) return;
      const heading = panel.querySelector(".ptitle");
      const title = heading ? heading.textContent.trim() : id.replace(/Panel$/, "").replace(/([A-Z])/g, " $1").trim();
      const meta = panel.querySelector(".pmeta");
      const description = meta ? meta.textContent.trim() : "Open this dedicated NOX module.";
      const card = document.createElement("button");
      card.type = "button";
      card.className = "nox-launch-card nox-panel-launch";
      card.innerHTML = '<strong></strong><span></span>';
      card.querySelector("strong").textContent = title;
      card.querySelector("span").textContent = description || "Open this dedicated NOX module.";
      card.setAttribute("aria-controls", id);
      card.addEventListener("click", () => showFeature(section, panel, title));
      list.append(card);
      panel.classList.add("nox-drawer-panel");
      panel.hidden = true;
      section.append(panel);
    });
    section.querySelector(".nox-feature-back-to-group").addEventListener("click", () => showGroup(index));
    groupSections.push(section);
    content.append(section);
  });
  const launchGrid = document.createElement("div");
  launchGrid.className = "nox-launch-grid";
  const launchers = [
    ["AGENT SWARM", "Run specialist agents with task history and safe tools.", () => window.NOXAgentSwarm && window.NOXAgentSwarm.open()],
    ["PROJECT WORKSPACE", "Review file snapshots and approve proposed changes.", () => window.NOXProjectWorkspace && window.NOXProjectWorkspace.open()],
    ["GITHUB BRIDGE", "Inspect repository files and prepare draft pull requests.", () => window.NOXGitHubBridge && window.NOXGitHubBridge.open()],
    ["CI / TEST STATUS", "Inspect real GitHub Actions workflow and step states.", () => window.NOXGitHubCIDashboard && window.NOXGitHubCIDashboard.open()]
  ];
  launchers.forEach(([title, description, action]) => {
    const button = document.createElement("button");
    button.type = "button"; button.className = "nox-launch-card";
    const strong = document.createElement("strong"); strong.textContent = title;
    const span = document.createElement("span"); span.textContent = description;
    button.append(strong, span);
    button.addEventListener("click", () => { if (typeof action === "function") action(); });
    launchGrid.append(button);
  });
  const devopsGroup = $("noxGroup3");
  if (devopsGroup) devopsGroup.append(launchGrid);
  const layout = $("dashboard");
  if (layout) {
    layout.classList.add("nox-home-layout");
    layout.querySelectorAll(":scope > .leftstack, :scope > .rightstack").forEach(stack => {
      if (!stack.querySelector(".panel")) stack.hidden = true;
    });
  }
  const mobileTabs = document.querySelector(".mobiletabs");
  if (mobileTabs) mobileTabs.setAttribute("aria-hidden", "true");
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.id = "noxFeatureTrigger";
  trigger.className = "iconbtn nox-feature-trigger";
  trigger.innerHTML = '<span aria-hidden="true">☷</span> Features <span class="feature-count">16</span>';
  trigger.setAttribute("aria-haspopup", "dialog");
  trigger.setAttribute("aria-expanded", "false");
  const topRight = document.querySelector(".topright");
  if (topRight) topRight.prepend(trigger);
  const closeButton = layer.querySelector(".nox-feature-close");
  const backdrop = layer.querySelector(".nox-feature-backdrop");
  let previousFocus = null;
  function close() {
    layer.classList.remove("open");
    layer.setAttribute("aria-hidden", "true");
    trigger.setAttribute("aria-expanded", "false");
    document.body.style.overflow = "";
    if (previousFocus && previousFocus.isConnected) previousFocus.focus();
  }
  function showGroup(index) {
    groupSections.forEach((section, i) => {
      section.hidden = i !== index;
      section.classList.remove("feature-open");
      section.querySelector(".nox-feature-list").hidden = false;
      section.querySelector(".nox-feature-back-to-group").classList.add("hidden");
      section.querySelectorAll(".nox-drawer-panel").forEach(panel => { panel.hidden = true; });
    });
    layer.querySelectorAll("[data-group-target]").forEach(button => {
      const active = button.dataset.groupTarget === "noxGroup" + index;
      button.setAttribute("aria-current", active ? "true" : "false");
      button.classList.toggle("active", active);
    });
    content.scrollTop = 0;
  }
  function showFeature(section, panel, title) {
    groupSections.forEach(other => { if (other !== section) other.hidden = true; });
    section.classList.add("feature-open");
    section.querySelector(".nox-feature-list").hidden = true;
    section.querySelector(".nox-feature-back-to-group").classList.remove("hidden");
    section.querySelectorAll(".nox-drawer-panel").forEach(item => { item.hidden = item !== panel; });
    layer.querySelector("#noxFeatureTitle").textContent = title;
    content.scrollTop = 0;
    panel.scrollTop = 0;
  }
  function open(panelId) {
    previousFocus = document.activeElement;
    layer.classList.add("open");
    layer.setAttribute("aria-hidden", "false");
    trigger.setAttribute("aria-expanded", "true");
    document.body.style.overflow = "hidden";
    if (panelId) {
      const panel = $(panelId);
      const section = panel && panel.closest(".nox-feature-group");
      const index = groupSections.indexOf(section);
      if (index >= 0) {
        showGroup(index);
        const heading = panel.querySelector(".ptitle");
        showFeature(section, panel, heading ? heading.textContent.trim() : "NOX Feature");
      } else showGroup(0);
    } else {
      layer.querySelector("#noxFeatureTitle").textContent = "Feature Center";
      showGroup(0);
    }
    closeButton.focus();
  }
  trigger.addEventListener("click", () => open());
  closeButton.addEventListener("click", close);
  backdrop.addEventListener("click", close);
  layer.querySelectorAll("[data-group-target]").forEach(button => button.addEventListener("click", () => {
    const index = Number(button.dataset.groupTarget.replace("noxGroup", ""));
    if (Number.isInteger(index) && groupSections[index]) {
      layer.querySelector("#noxFeatureTitle").textContent = "Feature Center";
      showGroup(index);
    }
  }));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && layer.classList.contains("open")) close();
    if (event.key === "Tab" && layer.classList.contains("open")) {
      const focusable = [...layer.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),textarea:not(:disabled),select:not(:disabled),[tabindex="0"]')].filter(el => el.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  // Legacy quick-launch controls still work, but open the feature drawer first.
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-open]");
    if (!button) return;
    const id = button.dataset.open;
    if ($(id) && !layer.classList.contains("open")) open(id);
  }, true);
  showGroup(0);
  window.NOXFeatureDrawer = { open, close, showGroup };
})();