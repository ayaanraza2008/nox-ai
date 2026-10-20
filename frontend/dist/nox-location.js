(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const api = async (path, options = {}) => {
    const response = await fetch(path, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Request failed (HTTP " + response.status + ")");
    return body;
  };
  const state = { authenticated: false, map: null, styleUrl: null, markers: new Map(), devices: [] };
  const notice = (message, bad = false) => {
    const el = $("noxLocationNotice");
    if (!el) return;
    el.textContent = message;
    el.style.color = bad ? "var(--red)" : "var(--muted)";
  };
  const timeLabel = value => {
    if (!value) return "Never";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Unknown";
    const age = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
    if (age < 60) return age + "s ago";
    if (age < 3600) return Math.floor(age / 60) + "m ago";
    if (age < 86400) return Math.floor(age / 3600) + "h ago";
    return date.toLocaleString();
  };
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  function initMap(config) {
    const holder = $("noxLocationMap");
    const msg = $("noxLocationMapMessage");
    state.styleUrl = config.map_style_url;
    if (!config.configured || !state.styleUrl) {
      msg.textContent = config.message || "Configure NOX_MAP_STYLE_URL to enable the interactive map.";
      holder.replaceChildren(el("span", "muted", "Interactive map setup required."));
      return;
    }
    if (!window.maplibregl) {
      msg.textContent = "Map library did not load. Check the network or content-security policy.";
      return;
    }
    msg.textContent = "Live markers are shown only for active, fresh consented locations. Stale locations remain listed as last known.";
    holder.replaceChildren();
    state.map = new maplibregl.Map({
      container: holder,
      style: state.styleUrl,
      center: [78.9629, 22.5937],
      zoom: 4,
      attributionControl: true
    });
    state.map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    state.map.on("error", () => { msg.textContent = "Map style or tile provider could not load. Check NOX_MAP_STYLE_URL and provider access."; });
  }
  function updateMap(devices) {
    if (!state.map || !window.maplibregl) return;
    const live = devices.filter(d => d.sharing_active && !d.location_stale &&
      Number.isFinite(Number(d.latitude)) && Number.isFinite(Number(d.longitude)));
    const liveIds = new Set(live.map(d => d.id));
    for (const [id, marker] of state.markers) {
      if (!liveIds.has(id)) { marker.remove(); state.markers.delete(id); }
    }
    for (const device of live) {
      const coords = [Number(device.longitude), Number(device.latitude)];
      const popupNode = document.createElement("div");
      popupNode.appendChild(el("strong", "", device.label || "NOX device"));
      popupNode.appendChild(el("div", "", "Accuracy ±" + Math.round(Number(device.accuracy_m) || 0) + " m"));
      popupNode.appendChild(el("div", "", "Updated " + timeLabel(device.last_location_at)));
      if (state.markers.has(device.id)) {
        const marker = state.markers.get(device.id);
        marker.setLngLat(coords);
        marker.getPopup().setDOMContent(popupNode);
      } else {
        const marker = new maplibregl.Marker({ color: device.is_owner ? "#71eaff" : "#a18bff" })
          .setLngLat(coords).setPopup(new maplibregl.Popup({ offset: 20 }).setDOMContent(popupNode)).addTo(state.map);
        state.markers.set(device.id, marker);
      }
    }
    if (live.length === 1 && !state.map.__noxCentered) {
      state.map.flyTo({ center: [Number(live[0].longitude), Number(live[0].latitude)], zoom: 13, essential: false });
      state.map.__noxCentered = true;
    } else if (live.length > 1 && !state.map.__noxCentered) {
      const bounds = new maplibregl.LngLatBounds();
      live.forEach(d => bounds.extend([Number(d.longitude), Number(d.latitude)]));
      state.map.fitBounds(bounds, { padding: 45, maxZoom: 13, duration: 500 });
      state.map.__noxCentered = true;
    }
  }
  async function history(device) {
    try {
      const result = await api("/api/location/devices/" + encodeURIComponent(device.id) + "/history?limit=50");
      const lines = (result.points || []).map(point =>
        timeLabel(point.captured_at) + " • " + Number(point.latitude).toFixed(5) + ", " +
        Number(point.longitude).toFixed(5) + " • ±" + Math.round(Number(point.accuracy_m)) + " m"
      );
      notice(lines.length ? "Recent history for " + device.label + ":\n" + lines.join("\n") : "No retained history is available for this device.");
    } catch (error) { notice(error.message, true); }
  }
  function renderDevices(devices) {
    const list = $("noxLocationDevices");
    list.replaceChildren();
    if (!devices.length) {
      list.appendChild(el("div", "footnote", "No enrolled or shared devices yet. Generate a one-time code for your own Android phone, or invite someone who can explicitly accept."));
      return;
    }
    for (const d of devices) {
      const card = el("div", "metric");
      card.style.display = "grid";
      card.style.gap = "7px";
      const title = el("strong", "", d.label || "NOX device");
      title.style.fontSize = "13px";
      card.appendChild(title);
      const stateText = !d.is_owner && !d.sharing_active ? "SHARING INACTIVE" :
        d.sharing_active && d.online && !d.location_stale ? "LIVE • CONSENT ACTIVE" :
        d.location_stale ? "STALE / NO FRESH FIX" : "OFFLINE OR PAUSED";
      card.appendChild(el("div", "tiny", (d.platform || "device").toUpperCase() + " · " + stateText));
      card.appendChild(el("small", "muted", "Last device report: " + timeLabel(d.last_seen_at)));
      card.appendChild(el("small", "muted", "Last location: " + timeLabel(d.last_location_at) +
        (d.accuracy_m != null ? " · accuracy ±" + Math.round(Number(d.accuracy_m)) + " m" : "")));
      if (d.consent_expires_at) card.appendChild(el("small", "muted", "Consent expiry: " + new Date(d.consent_expires_at).toLocaleString()));
      if (d.location_stale) card.appendChild(el("small", "", "Not live: last-known coordinates may be outdated."));
      const actions = el("div", "");
      actions.style.display = "flex";
      actions.style.gap = "6px";
      actions.style.flexWrap = "wrap";
      const historyButton = el("button", "secondary", "History");
      historyButton.type = "button";
      historyButton.addEventListener("click", () => history(d));
      actions.appendChild(historyButton);
      if (d.is_owner) {
        const toggle = el("button", "secondary", d.sharing_active ? "Pause sharing" : "Start / resume");
        toggle.type = "button";
        toggle.addEventListener("click", async () => {
          const enabled = !d.sharing_active;
          let expires = 24;
          if (enabled) {
            const raw = window.prompt("Share location for how many hours? Enter 1–168.", "24");
            if (raw === null) return;
            expires = Number(raw);
            if (!Number.isInteger(expires) || expires < 1 || expires > 168) { notice("Expiry must be a whole number from 1 to 168 hours.", true); return; }
          }
          toggle.disabled = true;
          try {
            await api("/api/location/devices/" + encodeURIComponent(d.id) + "/sharing", {
              method: "POST", body: JSON.stringify({ enabled, expires_hours: expires })
            });
            notice(enabled ? "Sharing enabled for a limited time. Android uploads only while this consent is active." : "Sharing paused. New location uploads are rejected.");
            await refreshDevices();
          } catch (error) { notice(error.message, true); }
          finally { toggle.disabled = false; }
        });
        actions.appendChild(toggle);
        const revoke = el("button", "secondary", "Revoke device");
        revoke.type = "button";
        revoke.addEventListener("click", async () => {
          if (!window.confirm("Revoke this device token and stop future uploads?")) return;
          try {
            await api("/api/location/devices/" + encodeURIComponent(d.id), { method: "DELETE" });
            notice("Device token revoked.");
            await refreshDevices();
          } catch (error) { notice(error.message, true); }
        });
        actions.appendChild(revoke);
      } else if (d.share_id) {
        const revokeAccess = el("button", "secondary", "Revoke my access");
        revokeAccess.type = "button";
        revokeAccess.addEventListener("click", async () => {
          if (!window.confirm("Revoke your access to this person's shared location?")) return;
          try {
            await api("/api/location/shares/" + encodeURIComponent(d.share_id), { method: "DELETE" });
            notice("Your access has been revoked.");
            await refreshDevices();
          } catch (error) { notice(error.message, true); }
        });
        actions.appendChild(revokeAccess);
      }
      card.appendChild(actions);
      list.appendChild(card);
    }
  }
  async function refreshDevices() {
    if (!state.authenticated) return;
    const result = await api("/api/location/devices");
    state.devices = result.devices || [];
    renderDevices(state.devices);
    updateMap(state.devices);
    const active = state.devices.filter(d => d.sharing_active && !d.location_stale).length;
    $("noxLocationStatus").textContent = active ? active + " FRESH LOCATION(S)" : "NO FRESH LIVE LOCATIONS";
  }
  async function refresh() {
    try {
      const account = await api("/api/account/me");
      state.authenticated = Boolean(account.authenticated);
      if (!state.authenticated) {
        $("noxLocationStatus").textContent = "SIGN IN REQUIRED";
        notice("Sign in to your NOX account to enroll a device, create an invitation, or manage consent.");
        $("noxLocationDevices").replaceChildren(el("div", "footnote", "Sign in first. Open the NOX Account panel from Features."));
        return;
      }
      await refreshDevices();
    } catch (error) {
      $("noxLocationStatus").textContent = "SERVICE UNAVAILABLE";
      notice(error.message, true);
    }
  }
  $("noxLocationEnroll").addEventListener("click", async () => {
    try {
      if (!state.authenticated) { notice("Sign in to NOX first.", true); return; }
      const label = window.prompt("Label this phone (example: My Android)", "My Android");
      if (label === null) return;
      const result = await api("/api/location/enrollment-code", { method: "POST", body: JSON.stringify({ label: label || "NOX device" }) });
      $("noxLocationCode").textContent = result.code;
      $("noxLocationEnrollment").style.display = "block";
      notice("One-time enrollment code generated. It expires in five minutes and does not start sharing.");
    } catch (error) { notice(error.message, true); }
  });
  $("noxLocationInvite").addEventListener("click", async () => {
    try {
      if (!state.authenticated) { notice("Sign in to NOX first.", true); return; }
      const result = await api("/api/location/invitations", { method: "POST", body: "{}" });
      $("noxLocationInviteUrl").value = result.invite_url;
      $("noxLocationInviteBox").style.display = "block";
      notice("Invitation created. The recipient must sign in and explicitly accept; this does not enable their location.");
    } catch (error) { notice(error.message, true); }
  });
  $("noxLocationCopyInvite").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("noxLocationInviteUrl").value);
      notice("Invitation link copied.");
    } catch (_) {
      $("noxLocationInviteUrl").select();
      notice("Select and copy the invitation link manually.");
    }
  });
  $("noxLocationAcceptInvite").addEventListener("click", async () => {
    try {
      if (!state.authenticated) { notice("Sign in before accepting an invitation.", true); return; }
      let token = $("noxLocationInviteToken").value.trim();
      try { const url = new URL(token); token = url.searchParams.get("location_invite") || token; } catch (_) {}
      const result = await api("/api/location/invitations/accept", { method: "POST", body: JSON.stringify({ token }) });
      $("noxLocationInviteToken").value = "";
      notice(result.message || "Invitation accepted. Sharing remains off until explicitly enabled.");
      await refreshDevices();
      const url = new URL(window.location.href);
      url.searchParams.delete("location_invite");
      window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    } catch (error) { notice(error.message, true); }
  });
  $("noxLocationRefresh").addEventListener("click", refresh);
  async function start() {
    try {
      const config = await api("/api/location/config");
      initMap(config);
    } catch (_) {
      $("noxLocationMapMessage").textContent = "Could not load map configuration. Check server setup.";
    }
    const url = new URL(window.location.href);
    const invite = url.searchParams.get("location_invite");
    if (invite) $("noxLocationInviteToken").value = invite;
    await refresh();
    window.setInterval(refresh, 30_000);
  }
  start();
  window.NOXLocationSharing = { refresh, refreshDevices };
})();