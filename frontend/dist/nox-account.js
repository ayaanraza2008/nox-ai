(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const modal = $("accountModal");
  if (!modal || !$("accountOpen")) return;
  let mode = "login";

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) }
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.detail || data.message || ("Request failed (" + response.status + ")"));
    return data;
  }

  function notice(message, error = false) {
    $("accountNotice").textContent = message || "";
    $("accountNotice").style.color = error ? "var(--red)" : "var(--green)";
  }

  function setMode(next) {
    mode = next;
    $("accountLoginMode").classList.toggle("primary", mode === "login");
    $("accountRegisterMode").classList.toggle("primary", mode === "register");
    $("accountSubmit").textContent = mode === "login" ? "Sign in" : "Create account";
    $("accountTitle").textContent = mode === "login" ? "NOX ACCOUNT · SIGN IN" : "NOX ACCOUNT · CREATE";
    $("accountPassword").autocomplete = mode === "login" ? "current-password" : "new-password";
    $("accountPassword").minLength = mode === "register" ? 10 : 1;
    notice("");
  }

  function ensureBackupButton() {
    const signedView = $("accountSignedView");
    if (!signedView || $("accountExportBackup")) return;
    const button = document.createElement("button");
    button.id = "accountExportBackup";
    button.type = "button";
    button.className = "secondary";
    button.textContent = "Export NOX Brain backup (JSON)";
    button.style.cssText = "width:100%;margin:8px 0";
    const logout = $("accountLogout");
    if (logout && logout.parentNode) logout.parentNode.insertBefore(button, logout);
    else signedView.appendChild(button);
    button.addEventListener("click", exportBrainBackup);
  }

  async function exportBrainBackup() {
    const button = $("accountExportBackup");
    if (button) { button.disabled = true; button.textContent = "Preparing backup…"; }
    notice("Collecting account-linked Brain records. Nothing will be deleted.");
    try {
      const paths = [
        ["overview", "/api/brain/overview"],
        ["settings", "/api/brain/settings"],
        ["memories", "/api/brain/memories?limit=100"],
        ["devices", "/api/brain/devices"],
        ["skills", "/api/brain/skills"],
        ["proposals", "/api/brain/proposals"],
        ["audit", "/api/brain/audit?limit=100"]
      ];
      const entries = await Promise.all(paths.map(async ([key, path]) => [key, await api(path, { headers: {} })]));
      const payload = {
        format: "nox-brain-backup",
        schema_version: 1,
        exported_at: new Date().toISOString(),
        account_email: $("accountEmailLabel").textContent || null,
        note: "This backup contains NOX Brain data exposed by the current API. It does not include passwords, session tokens, full chat history, or indexed document contents. Keep this file private.",
        data: Object.fromEntries(entries)
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "nox-brain-backup-" + new Date().toISOString().slice(0, 10) + ".json";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
      notice("Backup exported. Store it somewhere private; exporting does not change saved data.");
    } catch (error) {
      notice("Backup failed: " + error.message, true);
    } finally {
      if (button) { button.disabled = false; button.textContent = "Export NOX Brain backup (JSON)"; }
    }
  }

  function showState(account) {
    const signedIn = Boolean(account);
    $("accountAuthView").classList.toggle("hidden", signedIn);
    $("accountSignedView").classList.toggle("hidden", !signedIn);
    $("accountEmailLabel").textContent = account?.email || "";
    $("accountOpen").textContent = account ? "Account" : "Sign in";
    $("accountSubtitle").textContent = account ? "Memory linked to this account" : "Your memories, linked to your account";
    if (signedIn) ensureBackupButton();
  }

  async function refreshAccount() {
    try {
      const result = await api("/api/account/me", { headers: {} });
      showState(result.authenticated ? result.account : null);
    } catch (error) {
      showState(null);
      if (!modal.classList.contains("hidden")) notice(error.message, true);
    }
  }

  $("accountOpen").addEventListener("click", async () => {
    modal.classList.remove("hidden");
    await refreshAccount();
  });
  $("accountClose").addEventListener("click", () => modal.classList.add("hidden"));
  modal.addEventListener("click", (event) => {
    if (event.target === modal) modal.classList.add("hidden");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") modal.classList.add("hidden");
  });
  $("accountLoginMode").addEventListener("click", () => setMode("login"));
  $("accountRegisterMode").addEventListener("click", () => setMode("register"));

  $("accountAuthForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = $("accountSubmit");
    submit.disabled = true;
    notice(mode === "login" ? "Signing in…" : "Creating account…");
    try {
      await api("/api/account/" + (mode === "login" ? "login" : "register"), {
        method: "POST",
        body: JSON.stringify({ email: $("accountEmail").value.trim(), password: $("accountPassword").value })
      });
      notice("Account ready. Loading your saved memories…");
      window.location.reload();
    } catch (error) {
      notice(error.message, true);
    } finally {
      submit.disabled = false;
    }
  });

  $("accountLogout").addEventListener("click", async () => {
    try {
      await api("/api/account/logout", { method: "POST", body: "{}" });
      window.location.reload();
    } catch (error) {
      notice(error.message, true);
    }
  });

  $("accountDeleteForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!window.confirm("Permanently delete this account and its saved NOX Brain records?")) return;
    const button = event.submitter;
    if (button) button.disabled = true;
    try {
      await api("/api/account", {
        method: "DELETE",
        body: JSON.stringify({
          password: $("accountDeletePassword").value,
          confirmation: $("accountDeleteConfirm").value.trim()
        })
      });
      notice("Account and saved Brain records deleted.");
      window.location.reload();
    } catch (error) {
      notice(error.message, true);
    } finally {
      if (button) button.disabled = false;
    }
  });

  setMode("login");
  refreshAccount();
})();
