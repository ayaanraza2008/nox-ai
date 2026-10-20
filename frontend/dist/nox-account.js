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

  function showState(account) {
    const signedIn = Boolean(account);
    $("accountAuthView").classList.toggle("hidden", signedIn);
    $("accountSignedView").classList.toggle("hidden", !signedIn);
    $("accountEmailLabel").textContent = account?.email || "";
    $("accountOpen").textContent = account ? "Account" : "Sign in";
    $("accountSubtitle").textContent = account ? "Memory linked to this account" : "Your memories, linked to your account";
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
