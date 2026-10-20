(() => {
  "use strict";
  if (window.NOXCognitive) return;
  const $ = (id) => document.getElementById(id);
  const form = $("cognitiveForm");
  const mode = $("cognitiveMode");
  const input = $("cognitiveInput");
  const useKnowledge = $("cognitiveUseKnowledge");
  const run = $("cognitiveRun");
  const status = $("cognitiveStatus");
  const output = $("cognitiveOutput");
  const continueChat = $("cognitiveContinueChat");
  if (!form || !mode || !input || !run || !status || !output || !continueChat || !useKnowledge) return;

  const languageValue = () => {
    const selected = $("language");
    const value = selected ? selected.value : "auto";
    return ["auto", "en", "hi", "ur", "hinglish"].includes(value) ? value : "auto";
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const content = input.value.trim();
    if (!content) {
      status.textContent = "Add a question or some material to analyze.";
      input.focus();
      return;
    }
    run.disabled = true;
    continueChat.hidden = true;
    status.textContent = "Analyzing with the configured NOX provider…";
    output.textContent = "Working…";
    try {
      const response = await fetch("/api/cognitive/analyze", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: mode.value, content, language: languageValue(), use_knowledge: useKnowledge.checked })
      });
      let data = {};
      try { data = await response.json(); } catch (_) {}
      if (!response.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "Cognitive analysis is unavailable.";
        throw new Error(detail);
      }
      const parts = [String(data.analysis || "The provider returned an empty analysis.")];
      if (data.observed_patterns) {
        const observed = data.observed_patterns;
        const entries = Array.isArray(observed.patterns) ? observed.patterns : [];
        parts.push("\n\nLOCAL REPEATED-TOKEN SIGNALS (descriptive only)");
        parts.push(entries.length
          ? entries.map(item => "• " + item.term + " — appears in " + item.sample_count + " samples [" + item.sample_indices.map(index => index + 1).join(", ") + "]").join("\n")
          : "No exact repeated terms found across the supplied lines or sentences.");
        if (observed.limitations) parts.push(observed.limitations);
      }
      if (data.knowledge_requested) {
        const sources = Array.isArray(data.knowledge_sources) ? data.knowledge_sources : [];
        parts.push("\n\nKNOWLEDGE INDEX SOURCES");
        parts.push(sources.length ? sources.map(source => "[" + source.citation_id + "] " + source.title + (source.filename ? " — " + source.filename : "") + (source.url ? "\n" + source.url : "")).join("\n\n") : "No matching indexed sources were found for this query.");
      }
      output.textContent = parts.join("\n\n");
      continueChat.hidden = false;
      status.textContent = (data.provider_status === "response_received" ? "Response received" : "Local pattern scan only") + " · knowledge used: " + (data.knowledge_used ? "yes" : (data.knowledge_requested ? "no matching sources" : "no")) + " · profile saved: no";
    } catch (error) {
      output.textContent = error && error.message ? error.message : "Unable to contact NOX Cognitive Intelligence.";
      continueChat.hidden = true;
      status.textContent = "Analysis unavailable · check provider configuration and service logs";
    } finally {
      run.disabled = false;
    }
  });

  continueChat.addEventListener("click", () => {
    const composer = $("messageInput");
    if (!composer) {
      status.textContent = "Conversation Workspace is unavailable on this page.";
      return;
    }
    composer.value = "Continue this Cognitive Intelligence analysis. Treat conclusions as hypotheses, note uncertainty, and suggest a practical next step:" + String.fromCharCode(10, 10) + output.textContent.slice(0, 9000);
    composer.dispatchEvent(new Event("input", { bubbles: true }));
    composer.focus();
    status.textContent = "Added to the chat composer. Review it and press Send when ready.";
  });

  window.NOXCognitive = { analyze: () => form.requestSubmit() };
})();
