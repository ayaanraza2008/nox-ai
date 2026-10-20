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
    if (!signedView) return;
    const logout = $("accountLogout");
    if (!$("accountExportBackup")) {
      const button = document.createElement("button");
      button.id = "accountExportBackup";
      button.type = "button";
      button.className = "secondary";
      button.textContent = "Export NOX Brain backup (JSON)";
      button.style.cssText = "width:100%;margin:8px 0";
      if (logout && logout.parentNode) logout.parentNode.insertBefore(button, logout);
      else signedView.appendChild(button);
      button.addEventListener("click", exportBrainBackup);
    }
    if (!$("accountLogoutOthers")) {
      const button = document.createElement("button");
      button.id = "accountLogoutOthers";
      button.type = "button";
      button.className = "secondary";
      button.textContent = "Sign out other sessions";
      button.style.cssText = "width:100%;margin:0 0 8px";
      if (logout && logout.parentNode) logout.parentNode.insertBefore(button, logout);
      else signedView.appendChild(button);
      button.addEventListener("click", revokeOtherSessions);
    }
    if (!$("accountImportBackup")) {
      const button = document.createElement("button");
      button.id = "accountImportBackup";
      button.type = "button";
      button.className = "secondary";
      button.textContent = "Restore from JSON backup";
      button.style.cssText = "width:100%;margin:0 0 8px";
      const input = document.createElement("input");
      input.id = "accountBackupFile";
      input.type = "file";
      input.accept = ".json,application/json";
      input.hidden = true;
      signedView.appendChild(input);
      if (logout && logout.parentNode) logout.parentNode.insertBefore(button, logout);
      else signedView.appendChild(button);
      button.addEventListener("click", () => input.click());
      input.addEventListener("change", importBrainBackup);
    }
  }

  async function importBrainBackup(event) {
    const input = event.currentTarget;
    const file = input.files && input.files[0];
    if (!file) return;
    input.value = "";
    if (file.size > 2 * 1024 * 1024) {
      notice("Backup file is too large. Maximum size is 2 MB.", true);
      return;
    }
    if (!window.confirm("Restore records from this backup? NOX will merge records and will not delete existing data. Imported skills/proposals remain pending review. Settings and audit history are not restored.")) return;
    const button = $("accountImportBackup");
    if (button) { button.disabled = true; button.textContent = "Restoring…"; }
    notice("Reading and validating backup…");
    try {
      const raw = await file.text();
      let backup;
      try { backup = JSON.parse(raw); } catch (_) { throw new Error("This file is not valid JSON."); }
      if (!backup || backup.format !== "nox-brain-backup" || backup.schema_version !== 1 || !backup.data) {
        throw new Error("Unsupported NOX backup format or schema version.");
      }
      const result = await api("/api/brain/backup/restore", {
        method: "POST",
        body: JSON.stringify({ backup })
      });
      const summary = "Restore complete — memories added: " + result.memories_added +
        ", duplicates merged: " + result.memories_merged + ", devices: " + result.devices_restored +
        ", skills queued for review: " + result.skills_restored + ", proposals queued for review: " +
        result.proposals_restored + ", skipped: " + result.records_skipped + ".";
      notice(summary + (result.errors && result.errors.length ? " Details: " + result.errors.join(" · ") : ""));
      if (result.records_skipped && result.errors && result.errors.length) console.warn("NOX backup restore skipped records", result.errors);
    } catch (error) {
      notice("Restore failed: " + error.message, true);
    } finally {
      if (button) { button.disabled = false; button.textContent = "Restore from JSON backup"; }
    }
  }

  async function exportBrainBackup() {
    const button = $("accountExportBackup");
    if (button) { button.disabled = true; button.textContent = "Preparing backup…"; }
    notice("Collecting account-linked Brain records. Nothing will be deleted.");
    try {
      const paths = [
        ["overview", "/api/brain/overview"],
        ["settings", "/api/brain/settings"],
        ["memories", "/api/brain/memories?limit=1000"],
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

  async function revokeOtherSessions() {
    if (!window.confirm("Sign out NOX on all other devices and browsers? This browser will stay signed in.")) return;
    const button = $("accountLogoutOthers");
    if (button) { button.disabled = true; button.textContent = "Revoking sessions…"; }
    try {
      const result = await api("/api/account/logout-others", { method: "POST", body: "{}" });
      notice("Signed out " + result.sessions_revoked + " other session(s). This session remains active.");
    } catch (error) {
      notice("Could not revoke other sessions: " + error.message, true);
    } finally {
      if (button) { button.disabled = false; button.textContent = "Sign out other sessions"; }
    }
  }

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
