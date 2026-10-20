(() => {
  "use strict";
  if (window.NOXCognitive) return;
  const $ = (id) => document.getElementById(id);
  const form = $("cognitiveForm");
  const mode = $("cognitiveMode");
  const input = $("cognitiveInput");
  const run = $("cognitiveRun");
  const status = $("cognitiveStatus");
  const output = $("cognitiveOutput");
  if (!form || !mode || !input || !run || !status || !output) return;

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
    status.textContent = "Analyzing with the configured NOX provider…";
    output.textContent = "Working…";
    try {
      const response = await fetch("/api/cognitive/analyze", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: mode.value, content, language: languageValue() })
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
      output.textContent = parts.join("\n\n");
      status.textContent = (data.provider_status === "response_received" ? "Response received" : "Local pattern scan only") + " · profile saved: no · scope: submitted text only";
    } catch (error) {
      output.textContent = error && error.message ? error.message : "Unable to contact NOX Cognitive Intelligence.";
      status.textContent = "Analysis unavailable · check provider configuration and service logs";
    } finally {
      run.disabled = false;
    }
  });

  window.NOXCognitive = { analyze: () => form.requestSubmit() };
})();
