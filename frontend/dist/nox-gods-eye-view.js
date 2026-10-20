(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let busy = false;
  function status(message, error = false) {
    const el = $("godsEyeStatus");
    if (el) {
      el.textContent = message;
      el.dataset.state = error ? "error" : "normal";
    }
  }
  function reveal() {
    const panel = $("godsEyeViewPanel");
    if (!panel) return;
    panel.classList.remove("off");
    panel.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }
  async function refresh() {
    if (busy) return;
    busy = true;
    status("CHECKING NATIVE INTEGRATION…");
    try {
      const response = await fetch("/api/integrations/gods-eye-view", {
        credentials: "same-origin",
        headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const config = await response.json();
      const commit = $("godsEyeCommit");
      if (commit) commit.textContent = (config.upstream_commit || "Unknown").slice(0, 12);
      status("NATIVE INTEGRATION PENDING", true);
      const detail = $("godsEyeConnectionDetail");
      if (detail) {
        detail.textContent = "The upstream source is identified, but its Cesium application is not yet mounted as a native NOX module. To honor NOX-only navigation, external launch is disabled. No live globe or live feed is claimed here.";
      }
      const nativeStatus = $("godsEyeNativeStatus");
      if (nativeStatus) {
        nativeStatus.textContent = "Native integration pending. No external dashboard will be opened.";
      }
    } catch (error) {
      status("INTEGRATION STATUS UNAVAILABLE", true);
      const detail = $("godsEyeConnectionDetail");
      if (detail) detail.textContent = "NOX could not read integration metadata: " + error.message + ". External navigation remains disabled.";
    } finally {
      busy = false;
    }
  }
  const refreshButton = $("godsEyeRefresh");
  if (refreshButton) refreshButton.addEventListener("click", refresh);
  document.querySelectorAll('[data-scroll="godsEyeViewPanel"]').forEach((el) => {
    el.addEventListener("click", reveal);
  });
  window.NOXGodsEyeView = { refresh, open: reveal, handleCommand(message) {
    if (!/\b(god'?s eye view|gods eye view|godseyeview|globe workspace)\b/i.test(String(message || ""))) return false;
    reveal();
    status("NATIVE INTEGRATION PENDING", true);
    return true;
  }};
  refresh();
})();
