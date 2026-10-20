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
    $("accountRegisterFields").hidden = mode !== "register";
    $("accountIdentifierLabel").textContent = mode === "login" ? "Username, email, or mobile number" : "Create a username, then enter your email and mobile below";
    $("accountIdentifierLabel").hidden = mode !== "login";
    $("accountEmail").hidden = mode !== "login";
    $("accountRememberWrap").hidden = mode !== "login";
    $("accountForgot").hidden = mode !== "login";
    $("accountRecoveryView").hidden = true;
    $("accountAuthForm").hidden = false;
    $("accountEmail").required = mode === "login";
    $("accountFullName").required = mode === "register";
    $("accountUsername").required = mode === "register";
    $("accountRegisterEmail").required = mode === "register";
    $("accountCountryCode").required = mode === "register";
    $("accountPhoneNumber").required = mode === "register";
    $("accountLoginCountryWrap").hidden = mode !== "login" || !/^\d{10}$/.test($("accountEmail").value.trim());
    notice("");
  }

  function ensureBackupButton() {
    const bind = (id, event, handler) => {
      const element = $(id);
      if (element && !element.dataset.noxBound) {
        element.addEventListener(event, handler);
        element.dataset.noxBound = "1";
      }
    };
    bind("accountExportBackup", "click", exportBrainBackup);
    bind("accountImportBackup", "click", () => $("accountBackupFile").click());
    bind("accountBackupFile", "change", importBrainBackup);
    bind("accountLogoutOthers", "click", revokeOtherSessions);
    bind("accountVerifyEmail", "click", () => verifyChannel("email"));
    bind("accountVerifyPhone", "click", () => verifyChannel("sms"));
    bind("accountResendEmail", "click", () => resendChannel("email"));
    bind("accountResendPhone", "click", () => resendChannel("sms"));
    bind("accountForgot", "click", () => {
      $("accountRecoveryView").hidden = false;
      $("accountAuthForm").hidden = true;
      $("accountForgot").hidden = true;
    });
    bind("accountRecoveryClose", "click", () => {
      $("accountRecoveryView").hidden = true;
      $("accountAuthForm").hidden = false;
      $("accountForgot").hidden = false;
    });
    bind("accountRecoveryRequest", "click", requestRecoveryCode);
    bind("accountRecoveryReset", "click", resetRecoveredPassword);
    bind("accountProfileForm", "submit", saveProfile);
    bind("accountEmailForm", "submit", changeEmail);
    bind("accountEmail", "input", () => {
      $("accountLoginCountryWrap").hidden = mode !== "login" || !/^\d{10}$/.test($("accountEmail").value.trim());
    });
  }

  async function verifyChannel(channel) {
    const code = $(channel === "email" ? "accountEmailCode" : "accountPhoneCode").value.trim();
    if (!/^\d{6}$/.test(code)) { notice("Enter the six-digit " + (channel === "email" ? "email" : "SMS") + " code.", true); return; }
    try {
      const result = await api("/api/account/verify", { method: "POST", body: JSON.stringify({ channel, code }) });
      showState(result.account);
      notice(channel === "email" ? "Email verified." : "Mobile number verified.");
      if (result.status === "active") window.location.reload();
    } catch (error) { notice(error.message, true); }
  }

  async function resendChannel(channel) {
    const button = $(channel === "email" ? "accountResendEmail" : "accountResendPhone");
    if (button) { button.disabled = true; button.textContent = "Requesting…"; }
    try {
      const result = await api("/api/account/verification/resend", { method: "POST", body: JSON.stringify({ channel }) });
      const messages = {
        sent: "Verification code sent. Check your " + (channel === "email" ? "email inbox" : "SMS messages") + ".",
        setup_required: channel === "email" ? "Email delivery is not configured. Set SMTP_HOST and SMTP_FROM on the server." : "SMS delivery is not configured. Set the Twilio server-side credentials.",
        delivery_failed: "The provider is configured but delivery failed. Check server-side provider settings and try later.",
        profile_required: "Complete your profile and save a mobile number before requesting an SMS code.",
        already_verified: "This verification step is already complete."
      };
      notice(messages[result.delivery] || "Delivery status: " + result.delivery, result.delivery === "setup_required" || result.delivery === "delivery_failed");
    } catch (error) { notice(error.message, true); }
    finally { if (button) { button.disabled = false; button.textContent = channel === "email" ? "Send / resend email code" : "Send / resend SMS code"; } }
  }

  async function requestRecoveryCode() {
    const channel = $("accountRecoveryChannel").value;
    const identifier = $("accountRecoveryIdentifier").value.trim();
    if (!identifier) { notice("Enter your registered email or mobile number.", true); return; }
    try {
      const result = await api("/api/account/recovery/request", {
        method: "POST", body: JSON.stringify({ channel, identifier, country_code: $("accountRecoveryCountry").value })
      });
      const channelLabel = channel === "email" ? "Email" : "SMS";
      if (result.provider_status === "setup_required") {
        notice(result.message + " " + channelLabel + " provider setup is required before recovery codes can be delivered.", true);
      } else {
        notice(result.message + " If the details match, check the selected channel.");
      }
    } catch (error) { notice(error.message, true); }
  }

  async function resetRecoveredPassword() {
    const channel = $("accountRecoveryChannel").value;
    try {
      const result = await api("/api/account/recovery/reset", {
        method: "POST",
        body: JSON.stringify({
          channel, identifier: $("accountRecoveryIdentifier").value.trim(),
          country_code: $("accountRecoveryCountry").value,
          code: $("accountRecoveryCode").value.trim(),
          new_password: $("accountRecoveryNewPassword").value
        })
      });
      notice(result.message);
      $("accountRecoveryView").hidden = true;
      $("accountAuthForm").hidden = false;
      $("accountForgot").hidden = false;
    } catch (error) { notice(error.message, true); }
  }

  async function saveProfile(event) {
    event.preventDefault();
    try {
      const result = await api("/api/account/profile", {
        method: "PUT",
        body: JSON.stringify({
          full_name: $("accountProfileFullName").value.trim(),
          username: $("accountProfileUsername").value.trim().toLowerCase(),
          country_code: $("accountProfileCountry").value,
          phone_number: $("accountProfilePhone").value.trim(),
          password: $("accountProfilePassword").value
        })
      });
      showState(result.account);
      $("accountProfilePassword").value = "";
      if (result.phone_delivery === "setup_required") notice("Profile saved, but SMS is not configured. Mobile remains unverified.", true);
      else if (result.phone_delivery === "delivery_failed") notice("Profile saved, but SMS delivery failed. Check provider settings.", true);
      else if (result.phone_delivery === "sent") notice("Profile saved. A new mobile verification code was sent.");
      else notice("Profile saved.");
    } catch (error) { notice(error.message, true); }
  }

  async function changeEmail(event) {
    event.preventDefault();
    try {
      const result = await api("/api/account/email", {
        method: "PUT",
        body: JSON.stringify({ email: $("accountNewEmail").value.trim(), password: $("accountEmailPassword").value })
      });
      showState(result.account);
      $("accountEmailPassword").value = "";
      const status = result.email_delivery;
      if (status === "sent") notice("Email changed. A verification code was sent to the new address.");
      else if (status === "setup_required") notice("Email changed, but SMTP is not configured; the new address remains unverified.", true);
      else if (status === "delivery_failed") notice("Email changed, but delivery failed. Check server settings.", true);
      else notice("Email settings saved.");
    } catch (error) { notice(error.message, true); }
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
    if (!signedIn) {
      $("accountOpen").textContent = "Sign in";
      $("accountSubtitle").textContent = "Your memories, linked to your account";
      return;
    }
    $("accountFullNameLabel").textContent = account.full_name || "Complete your profile";
    $("accountEmailLabel").textContent = account.email || "";
    $("accountUsernameLabel").textContent = account.username ? "@" + account.username : "Username not set";
    $("accountStatusLabel").textContent = "Account status: " + (account.status || "pending_verification");
    $("accountOpen").textContent = account.full_name || "Account";
    $("accountSubtitle").textContent = account.status === "active" ? "Verified NOX account" : "Verification required to unlock NOX features";
    $("accountEmailStatus").textContent = account.email_verified ? "✓ Email verified" :
      (account.verification_providers?.email ? "○ Email not verified" : "⚠ Email verification setup required (SMTP)");
    $("accountPhoneStatus").textContent = account.phone_verified ? "✓ Mobile verified" :
      (account.verification_providers?.sms ? "○ Mobile not verified" : "⚠ SMS setup required (Twilio)");
    $("accountProfileFullName").value = account.full_name || "";
    $("accountProfileUsername").value = account.username || "";
    $("accountProfileCountry").value = account.country_code || "+91";
    $("accountProfilePhone").value = account.phone_number || "";
    $("accountNewEmail").value = account.email || "";
    $("accountVerificationPanel").hidden = account.status === "active";
    $("accountProfileDetails").open = !account.profile_complete;
    ensureBackupButton();
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

  $("accountAuthForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = $("accountSubmit");
    submit.disabled = true;
    notice(mode === "login" ? "Signing in…" : "Creating account…");
    try {
      let payload;
      if (mode === "login") {
        payload = {
          identifier: $("accountEmail").value.trim(),
          password: $("accountPassword").value,
          country_code: $("accountLoginCountryCode").value,
          remember_me: $("accountRemember").checked
        };
      } else {
        payload = {
          full_name: $("accountFullName").value.trim(),
          username: $("accountUsername").value.trim().toLowerCase(),
          email: $("accountRegisterEmail").value.trim(),
          country_code: $("accountCountryCode").value,
          phone_number: $("accountPhoneNumber").value.trim(),
          password: $("accountPassword").value
        };
      }
      const result = await api("/api/account/" + (mode === "login" ? "login" : "register"), {
        method: "POST", body: JSON.stringify(payload)
      });
      if (result.account) {
        showState(result.account);
        if (mode === "register") {
          const delivery = result.delivery || {};
          const emailMessage = delivery.email === "sent" ? "Email code sent." :
            delivery.email === "setup_required" ? "Email provider setup required." :
            delivery.email === "delivery_failed" ? "Email delivery failed." : "";
          const phoneMessage = delivery.phone === "sent" ? "SMS code sent." :
            delivery.phone === "setup_required" ? "SMS provider setup required." :
            delivery.phone === "delivery_failed" ? "SMS delivery failed." : "";
          notice(["Account created, but verification is still required.", emailMessage, phoneMessage].filter(Boolean).join(" "));
        } else if (result.verification_required) {
          notice("Signed in. Complete both verification steps to unlock NOX AI features.");
        } else {
          notice("Signed in successfully.");
        }
      }
    } catch (error) { notice(error.message, true); }
    finally { submit.disabled = false; }
  });


  $("accountLoginMode").addEventListener("click", () => setMode("login"));
  $("accountRegisterMode").addEventListener("click", () => setMode("register"));

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

  ensureBackupButton();
  setMode("login");
  refreshAccount();
})();
