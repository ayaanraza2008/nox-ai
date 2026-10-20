(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const api = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Request failed (" + response.status + ")");
    return data;
  };
  let activityReset = null;
  const setBrainActivity = (state) => {
    if (!document.body) return;
    document.body.dataset.noxBrainState = state;
    window.dispatchEvent(new CustomEvent("nox:brain-state", { detail: { state } }));
    if (activityReset) clearTimeout(activityReset);
    if (!["idle", "error"].includes(state)) {
      activityReset = setTimeout(() => {
        document.body.dataset.noxBrainState = "idle";
        window.dispatchEvent(new CustomEvent("nox:brain-state", { detail: { state: "idle" } }));
      }, 2200);
    }
  };
  const notice = (message, good = true) => {
    const el = $("brainNotice");
    if (!el) return;
    el.textContent = message;
    el.className = "footnote " + (good ? "brain-notice-good" : "brain-notice-error");
  };
  const safeText = (tag, text, className) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    el.textContent = text == null ? "" : String(text);
    return el;
  };
  const renderMemories = (items) => {
    const root = $("brainMemoryList");
    if (!root) return;
    root.replaceChildren();
    if (!items.length) {
      root.append(safeText("div", "No saved memories match this search.", "tiny"));
      return;
    }
    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "brain-memory-item";
      const title = safeText("strong", item.category + " · " + item.verification);
      const body = safeText("p", item.content);
      const meta = safeText("div", "Source: " + item.source + " · confidence " + Math.round(item.confidence * 100) + "% · " +
        (item.last_validated_at ? "validated " + new Date(item.last_validated_at).toLocaleDateString() + " · " : "") +
        (item.expires_at ? "expires " + new Date(item.expires_at).toLocaleDateString() : "no expiry") +
        (item.stale ? " · stale" : ""));
      meta.className = "brain-memory-meta";
      const remove = safeText("button", "Delete memory", "secondary");
      remove.type = "button";
      remove.addEventListener("click", async () => {
        if (!confirm("Delete this saved memory? This cannot be undone.")) return;
        try {
          await api("/api/brain/memories/" + encodeURIComponent(item.id), { method: "DELETE" });
          notice("Memory deleted.");
          await refresh();
        } catch (error) { notice(error.message, false); }
      });
      card.append(title, body, meta);
      const review = safeText("button", item.stale ? "Revalidate memory" : "Mark stale", "secondary");
      review.type = "button";
      review.style.marginRight = "6px";
      review.addEventListener("click", async () => {
        const decision = item.stale ? "revalidate" : "mark_stale";
        try {
          await api("/api/brain/memories/" + encodeURIComponent(item.id) + "/review", {
            method: "POST", body: JSON.stringify({ decision })
          });
          notice(decision === "revalidate" ? "Memory marked as user-confirmed and current." : "Memory marked stale; chat retrieval will skip it.");
          await refresh();
        } catch (error) { notice(error.message, false); }
      });
      card.append(review, remove);
      root.append(card);
    });
  };
  const renderDevices = (items) => {
    const root = $("brainDeviceList");
    if (!root) return;
    root.replaceChildren();
    if (!items.length) { root.append(safeText("div", "No capability summary shared yet.", "tiny")); return; }
    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "brain-memory-item";
      card.append(safeText("strong", item.label));
      card.append(safeText("p", Object.entries(item.capabilities || {}).map(([k,v]) => k.replaceAll("_"," ") + ": " + (typeof v === "object" ? JSON.stringify(v) : v)).join(" · ")));
      card.append(safeText("div", "Updated " + new Date(item.updated_at).toLocaleString(), "brain-memory-meta"));
      root.append(card);
    });
  };
  const renderAudit = (items) => {
    const root = $("brainAuditList");
    if (!root) return;
    root.replaceChildren();
    if (!items.length) { root.append(safeText("div", "No recorded brain changes yet.", "tiny")); return; }
    items.slice(0, 20).forEach((item) => {
      const card = document.createElement("article");
      card.className = "brain-memory-item";
      card.append(safeText("strong", item.action.replaceAll("_", " ") + " · " + item.item_type));
      card.append(safeText("div", new Date(item.created_at).toLocaleString(), "brain-memory-meta"));
      root.append(card);
    });
  };
  const renderProposals = (items) => {
    const root = $("brainProposalList");
    if (!root) return;
    root.replaceChildren();
    if (!items.length) { root.append(safeText("div", "No improvement proposals yet.", "tiny")); return; }
    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "brain-memory-item";
      card.append(safeText("strong", item.title + " · " + item.status));
      card.append(safeText("p", item.summary));
      if (item.status === "pending") {
        ["approved", "rejected"].forEach((decision) => {
          const button = safeText("button", decision === "approved" ? "Approve proposal" : "Reject proposal", "secondary");
          button.type = "button";
          button.style.marginRight = "6px";
          button.addEventListener("click", async () => {
            try {
              await api("/api/brain/proposals/" + encodeURIComponent(item.id) + "/review", {
                method: "POST", body: JSON.stringify({ decision })
              });
              notice("Proposal " + decision + ". Approval records authorization only; it does not execute code.");
              await refresh();
            } catch (error) { notice(error.message, false); }
          });
          card.append(button);
        });
      }
      root.append(card);
    });
  };
  async function loadMemories(query = "") {
    setBrainActivity("retrieving");
    const params = new URLSearchParams({ limit: "100" });
    if (query.trim()) params.set("query", query.trim());
    const data = await api("/api/brain/memories?" + params.toString());
    renderMemories(data.results || []);
    setBrainActivity("idle");
  }
  async function refresh() {
    setBrainActivity("retrieving");
    try {
      const [overview, memories, devices, proposals, skills, audit] = await Promise.all([
        api("/api/brain/overview"),
        api("/api/brain/memories?limit=100"),
        api("/api/brain/devices"),
        api("/api/brain/proposals"),
        api("/api/brain/skills"),
        api("/api/brain/audit?limit=20")
      ]);
      const counts = overview.counts || {};
      $("brainStatus").innerHTML = '<i class="led ' + (overview.status === "ready" ? "good" : "bad") + '"></i> ' + (overview.status || "UNKNOWN").toUpperCase();
      $("brainMemoryCount").textContent = counts.memories ?? 0;
      $("brainSkillCount").textContent = counts.skills ?? 0;
      $("brainOutcomeCount").textContent = counts.outcomes ?? 0;
      $("brainStorageUsage").textContent = Number(counts.storage_bytes || 0).toLocaleString() + " bytes";
      $("brainEnabled").checked = !!overview.settings.enabled;
      $("brainSyncMode").value = overview.settings.sync_mode || "local_only";
      $("brainRetention").value = String(overview.settings.retention_days || 365);
      const categories = new Set(overview.settings.categories || []);
      $("brainCatOperational").checked = categories.has("operational");
      $("brainCatExperience").checked = categories.has("experience");
      $("brainCatPreference").checked = categories.has("preference");
      $("brainCatProject").checked = categories.has("project");
      $("brainCatTemporary").checked = categories.has("temporary");
      renderMemories(memories.results || []);
      renderDevices(devices.devices || []);
      renderProposals(proposals.proposals || []);
      renderAudit(audit.events || []);
      setBrainActivity("idle");
      if (!skills.skills || !skills.skills.length) notice("Brain is online, but no skill definitions were returned.");
      else if (overview.capabilities && !overview.capabilities.semantic_vectors) {
        // Keep limitations visible rather than implying vector retrieval or model training.
        $("brainStatus").title = "Keyword retrieval active. Semantic vectors and model-weight training are not configured.";
      }
    } catch (error) {
      setBrainActivity("error");
      $("brainStatus").textContent = "UNAVAILABLE";
      notice(error.message + " — refresh NOX and check the backend session.", false);
    }
  }
  function discoverCapabilities() {
    let webgl = false;
    try {
      const canvas = document.createElement("canvas");
      webgl = !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
    } catch (_) {}
    const ua = navigator.userAgent || "";
    const browser = /Edg\//.test(ua) ? "Edge" : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "Unknown";
    const platform = navigator.userAgentData?.platform || navigator.platform || "Unknown";
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    return {
      platform: String(platform).slice(0, 80), browser,
      language: String(navigator.language || "unknown").slice(0, 80),
      viewport: { width: window.innerWidth, height: window.innerHeight },
      webgl, online: navigator.onLine,
      hardware_threads: Number.isInteger(navigator.hardwareConcurrency) ? navigator.hardwareConcurrency : 0,
      approx_device_memory_gb: typeof navigator.deviceMemory === "number" ? navigator.deviceMemory : 0,
      microphone_available: !!navigator.mediaDevices?.getUserMedia,
      camera_available: !!navigator.mediaDevices?.getUserMedia,
      speech_recognition: !!Recognition,
      speech_synthesis: !!window.speechSynthesis,
      reduced_motion: !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    };
  }
  document.addEventListener("DOMContentLoaded", () => {
    $("brainSaveMemory")?.addEventListener("click", async () => {
      setBrainActivity("saving");
      const content = $("brainMemoryContent").value.trim();
      if (!content) { notice("Write a concise memory first.", false); return; }
      try {
        const result = await api("/api/brain/memories", {
          method: "POST", body: JSON.stringify({ content, category: $("brainMemoryCategory").value })
        });
        $("brainMemoryContent").value = "";
        setBrainActivity("saved");
        notice(result.duplicate ? "Existing memory refreshed; no duplicate created." : "Memory saved to this browser session's NOX brain.");
        await refresh();
      } catch (error) { notice(error.message, false); }
    });
    $("brainSearchButton")?.addEventListener("click", async () => {
      try { await loadMemories($("brainMemorySearch").value); }
      catch (error) { notice(error.message, false); }
    });
    $("brainMemorySearch")?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); $("brainSearchButton").click(); }
    });
    $("brainSaveSettings")?.addEventListener("click", async () => {
      try {
        const result = await api("/api/brain/settings", {
          method: "PUT",
          body: JSON.stringify({
            enabled: $("brainEnabled").checked,
            sync_mode: $("brainSyncMode").value,
            retention_days: Number($("brainRetention").value),
            categories: [
              $("brainCatOperational").checked ? "operational" : null,
              $("brainCatExperience").checked ? "experience" : null,
              $("brainCatPreference").checked ? "preference" : null,
              $("brainCatProject").checked ? "project" : null,
              $("brainCatTemporary").checked ? "temporary" : null
            ].filter(Boolean)
          })
        });
        notice("Privacy settings saved. Sync selection is a preference only; cross-device sync is not implemented.", true);
        await refresh();
      } catch (error) { notice(error.message, false); }
    });
    $("brainExportMemories")?.addEventListener("click", async () => {
      try {
        const data = await api("/api/brain/memories?limit=1000");
        const exportData = {
          exported_at: new Date().toISOString(),
          notice: "Contains only saved NOX memory entries. Store this file privately.",
          memories: data.results || []
        };
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url; link.download = "nox-brain-memories.json";
        document.body.append(link); link.click(); link.remove();
        URL.revokeObjectURL(url);
        notice("Memory export created. Keep the file private.");
      } catch (error) { notice(error.message, false); }
    });
    $("brainDiscoverDevice")?.addEventListener("click", async () => {
      setBrainActivity("synchronizing");
      try {
        const result = await api("/api/brain/device-context", {
          method: "POST",
          body: JSON.stringify({
            label: $("brainDeviceLabel").value.trim() || "This browser",
            capabilities: discoverCapabilities()
          })
        });
        setBrainActivity("synchronized");
        notice("Shared an allowlisted capability summary only. No sensor permission was requested.");
        const data = await api("/api/brain/devices");
        renderDevices(data.devices || []);
      } catch (error) { notice(error.message, false); }
    });
    $("brainRecordOutcome")?.addEventListener("click", async () => {
      setBrainActivity("evaluating");
      const task_type = $("brainOutcomeType").value.trim();
      const requested_outcome = $("brainOutcomeGoal").value.trim();
      const result_summary = $("brainOutcomeResult").value.trim();
      if (!task_type || !requested_outcome || !result_summary) {
        notice("Enter task type, requested outcome, and actual result.", false); return;
      }
      try {
        const outcome = await api("/api/brain/outcomes", {
          method: "POST",
          body: JSON.stringify({
            task_type, requested_outcome, result_summary,
            status: $("brainOutcomeStatus").value,
            evidence: $("brainOutcomeEvidence").value.trim() || null
          })
        });
        setBrainActivity("evaluated");
        notice("Outcome recorded. " + (outcome.requires_validation_before_memory
          ? "Evidence is attached, but a lesson still needs validation before becoming durable memory."
          : "No verified lesson was automatically stored."));
        $("brainOutcomeResult").value = "";
        $("brainOutcomeEvidence").value = "";
        await refresh();
      } catch (error) { notice(error.message, false); }
    });
    $("brainCreateProposal")?.addEventListener("click", async () => {
      setBrainActivity("planning");
      const title = $("brainProposalTitle").value.trim();
      const summary = $("brainProposalSummary").value.trim();
      if (!title || !summary) { notice("Enter a proposal title and validation/rollback summary.", false); return; }
      try {
        await api("/api/brain/proposals", {
          method: "POST",
          body: JSON.stringify({
            title, summary,
            proposal: {
              kind: "workflow_or_skill",
              rationale: summary,
              validation_plan: "Run the stated checks and regression tests before adopting.",
              rollback_plan: "Keep the current version and revert the proposal if checks fail."
            }
          })
        });
        $("brainProposalTitle").value = "";
        $("brainProposalSummary").value = "";
        setBrainActivity("proposal-created");
        notice("Improvement proposal created for review; nothing was executed automatically.");
        await refresh();
      } catch (error) { notice(error.message, false); }
    });
    $("brainRefresh")?.addEventListener("click", refresh);
    refresh();
  });
})();