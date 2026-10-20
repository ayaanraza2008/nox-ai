(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const report = $("connectivityReport");
  if (!report) return;

  const STORAGE_KEY = "nox.connectivity.issue-state.v1";
  let lastObservations = null;
  let selectedBluetooth = null;
  let sceneState = null;
  let animationFrame = 0;

  function readIssueState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_) { return {}; }
  }
  function saveIssueState(state) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (_) {}
  }
  function escapeHTML(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[ch]);
  }
  function observeBrowserNetwork() {
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection || null;
    const effective = connection && ["slow-2g", "2g", "3g", "4g", "5g"].includes(connection.effectiveType)
      ? connection.effectiveType : (connection ? "unknown" : null);
    const type = connection && ["wifi", "cellular", "ethernet", "bluetooth", "other"].includes(connection.type)
      ? connection.type : (connection ? "unknown" : null);
    return {
      online: typeof navigator.onLine === "boolean" ? navigator.onLine : null,
      effective_type: effective,
      downlink_mbps: connection && Number.isFinite(connection.downlink) ? connection.downlink : null,
      rtt_ms: connection && Number.isFinite(connection.rtt) ? connection.rtt : null,
      type,
      sampled_at: new Date().toISOString()
    };
  }
  async function ensureSession() {
    const response = await fetch("/api/session", { credentials: "same-origin" });
    if (!response.ok) throw new Error("NOX session could not be initialized (" + response.status + ").");
  }
  function renderReport(data, newlyObserved) {
    const observations = data.observations || {};
    const online = observations.online === true ? "ONLINE FLAG" : observations.online === false ? "OFFLINE FLAG" : "UNKNOWN";
    $("connectivityOnline").textContent = online;
    const lines = [];
    lines.push('<div class="finding"><strong>Browser-visible observations</strong>' +
      "Online flag: " + escapeHTML(online) + "<br>" +
      "Connection class: " + escapeHTML(observations.effective_type || "not exposed") + "<br>" +
      "Estimated downlink: " + (observations.downlink_mbps == null ? "not exposed" : escapeHTML(observations.downlink_mbps) + " Mbps") + "<br>" +
      "Reported RTT: " + (observations.rtt_ms == null ? "not exposed" : escapeHTML(observations.rtt_ms) + " ms") + "</div>");
    const findings = Array.isArray(data.findings) ? data.findings : [];
    const state = readIssueState();
    const current = {};
    findings.filter(item => item && item.code && item.severity !== "info").forEach(item => {
      const fingerprint = String(item.code);
      current[fingerprint] = { code: fingerprint, title: String(item.title || "Network finding"), detail: String(item.detail || ""), severity: String(item.severity || "info") };
      const wasActive = state.active && state.active[fingerprint];
      if (!wasActive) {
        current[fingerprint].firstSeen = Date.now();
        if (!state.acknowledged || !state.acknowledged[fingerprint]) {
          // One concise notice per newly observed issue; never claim more than the evidence shows.
          if ("Notification" in window && Notification.permission === "granted") {
            try {
              new Notification("NOX AI: " + current[fingerprint].title, { body: current[fingerprint].detail, tag: "nox-connectivity-" + fingerprint, renotify: false });
              current[fingerprint].notificationSent = true;
            } catch (_) {}
          }
        }
      } else {
        current[fingerprint].firstSeen = wasActive.firstSeen || Date.now();
      }
    });
    const previous = state.active || {};
    const acknowledged = state.acknowledged || {};
    Object.keys(previous).forEach(code => { if (!current[code]) delete acknowledged[code]; });
    Object.keys(current).forEach(code => { if (!previous[code]) delete acknowledged[code]; });
    saveIssueState({ active: current, acknowledged, updatedAt: Date.now() });

    findings.forEach(item => {
      const cls = item.severity === "high" ? "high" : item.severity === "warning" ? "warning" : "";
      lines.push('<div class="finding ' + cls + '"><strong>' + escapeHTML(item.title) + ' · ' + escapeHTML(item.certainty) + '</strong>' +
        escapeHTML(item.detail) + '</div>');
    });
    if (!findings.length) lines.push('<div class="finding"><strong>No issues detected in available browser data</strong>This is not a Wi-Fi security audit and does not prove the router or internet is secure.</div>');
    if (Object.keys(current).length) {
      lines.push('<div class="connectivity-actions"><button class="secondary" id="connectivityNotifyPermission" type="button">Enable browser notifications</button><button class="secondary" id="connectivityAcknowledge" type="button">Mark current findings understood</button></div>');
    }
    lines.push('<p class="connectivity-muted">Checked on ' + escapeHTML(new Date().toLocaleString()) + '. Only browser-exposed data was used; SSID, radio signal strength, security mode, gateway, DNS and router clients were not inspected.</p>');
    report.innerHTML = lines.join("");
    const permissionButton = $("connectivityNotifyPermission");
    if (permissionButton) permissionButton.addEventListener("click", async () => {
      if (!("Notification" in window)) { report.insertAdjacentHTML("beforeend", '<div class="finding warning">This browser does not support notifications. Findings remain visible here.</div>'); return; }
      const permission = await Notification.requestPermission();
      if (permission === "granted") {
        const current = readIssueState();
        current.active = current.active || {};
        Object.keys(current.active).forEach(code => {
          const item = current.active[code];
          if (!item.notificationSent && !(current.acknowledged || {})[code]) {
            try {
              new Notification("NOX AI: " + item.title, { body: item.detail, tag: "nox-connectivity-" + code, renotify: false });
              item.notificationSent = true;
            } catch (_) {}
          }
        });
        saveIssueState(current);
      }
      report.insertAdjacentHTML("beforeend", '<div class="finding">Browser notification permission: ' + escapeHTML(permission) + '.</div>');
    });
    const ackButton = $("connectivityAcknowledge");
    if (ackButton) ackButton.addEventListener("click", () => {
      const latest = readIssueState();
      latest.acknowledged = latest.acknowledged || {};
      Object.keys(latest.active || {}).forEach(code => { latest.acknowledged[code] = true; });
      saveIssueState(latest);
      ackButton.textContent = "Understood";
      ackButton.disabled = true;
    });
    if (newlyObserved) {
      const warn = findings.find(item => item.severity === "high" || item.severity === "warning");
      if (warn) report.setAttribute("data-last-notice", warn.code);
    }
  }
  async function inspect() {
    $("connectivityInspect").disabled = true;
    $("connectivityInspect").textContent = "Inspecting…";
    report.textContent = "Reading only browser-visible connection information…";
    try {
      const observations = observeBrowserNetwork();
      lastObservations = observations;
      await ensureSession();
      const response = await fetch("/api/connectivity/analyze", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ observations })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Connectivity analysis failed (" + response.status + ").");
      renderReport(data, true);
      if (typeof navigator.onLine === "boolean") $("connectivityOnline").textContent = navigator.onLine ? "ONLINE FLAG" : "OFFLINE FLAG";
      const signal = $("connectivityHoloMeasurements");
      if (signal) signal.textContent = "Last browser sample: " + (observations.effective_type || "no connection API") +
        " · estimated downlink " + (observations.downlink_mbps == null ? "unavailable" : observations.downlink_mbps + " Mbps") +
        " · RTT " + (observations.rtt_ms == null ? "unavailable" : observations.rtt_ms + " ms") +
        ". These are browser network estimates, not Wi-Fi RSSI.";
    } catch (error) {
      report.innerHTML = '<div class="finding warning"><strong>Inspection unavailable</strong>' + escapeHTML(error.message) + '</div>' +
        '<div class="connectivity-muted">No device control was attempted. Check your connection and try again.</div>';
    } finally {
      $("connectivityInspect").disabled = false;
      $("connectivityInspect").textContent = "Inspect connection";
    }
  }

  $("connectivityInspect").addEventListener("click", inspect);
  window.addEventListener("online", () => { $("connectivityOnline").textContent = "ONLINE EVENT"; });
  window.addEventListener("offline", () => { $("connectivityOnline").textContent = "OFFLINE EVENT"; });

  $("connectivityBluetoothBtn").addEventListener("click", async () => {
    const output = $("connectivityBluetooth");
    if (!navigator.bluetooth || typeof navigator.bluetooth.requestDevice !== "function") {
      output.textContent = "UNSUPPORTED";
      report.insertAdjacentHTML("beforeend", '<div class="finding warning"><strong>Bluetooth discovery unavailable</strong>This browser or platform does not expose Web Bluetooth. Use a supported native companion for device management.</div>');
      return;
    }
    if (!window.isSecureContext) {
      output.textContent = "HTTPS REQUIRED";
      report.insertAdjacentHTML("beforeend", '<div class="finding warning"><strong>Secure context required</strong>Web Bluetooth requires HTTPS or a trusted local development origin.</div>');
      return;
    }
    try {
      output.textContent = "WAITING FOR CHOOSER";
      // Explicit click opens the browser's native chooser. This does not enumerate every nearby device.
      const device = await navigator.bluetooth.requestDevice({ acceptAllDevices: true });
      selectedBluetooth = { name: device.name || "Unnamed device", id: device.id || "browser-redacted-id" };
      output.textContent = "USER SELECTED";
      report.insertAdjacentHTML("afterbegin", '<div class="finding"><strong>Bluetooth device selected by you</strong>' +
        escapeHTML(selectedBluetooth.name) + '<br><span class="connectivity-muted">Browser identifier: ' + escapeHTML(selectedBluetooth.id) +
        '. Selection is not pairing and does not grant access to files, messages, sensors, camera or microphone.</span></div>');
    } catch (error) {
      output.textContent = error && error.name === "NotFoundError" ? "NO SELECTION" : "NOT AVAILABLE";
      if (error && error.name !== "NotFoundError" && error.name !== "AbortError") {
        report.insertAdjacentHTML("afterbegin", '<div class="finding warning"><strong>Bluetooth chooser did not complete</strong>' + escapeHTML(error.message || error.name) + '</div>');
      }
    }
  });

  $("connectivityLocationBtn").addEventListener("click", () => {
    if (!navigator.geolocation) {
      report.insertAdjacentHTML("afterbegin", '<div class="finding warning"><strong>Location unavailable</strong>This browser does not expose device geolocation.</div>');
      return;
    }
    report.insertAdjacentHTML("afterbegin", '<div class="finding"><strong>Waiting for device location permission</strong>Nothing is sent to NOX servers or saved by this panel. Your browser may show a permission prompt.</div>');
    navigator.geolocation.getCurrentPosition(position => {
      const coords = position.coords;
      // Display only in this page; never send coordinates to the backend or localStorage.
      const item = document.createElement("div");
      item.className = "finding";
      item.innerHTML = "<strong>Device location · user-approved</strong>Latitude: " + escapeHTML(coords.latitude.toFixed(5)) +
        "<br>Longitude: " + escapeHTML(coords.longitude.toFixed(5)) +
        "<br>Reported accuracy: ±" + escapeHTML(Math.round(coords.accuracy)) + " m" +
        "<br>Timestamp: " + escapeHTML(new Date(position.timestamp).toLocaleString()) +
        '<br><span class="connectivity-muted">Source: browser device geolocation; this is not Wi-Fi-based positioning. Location is displayed only and not retained.</span>';
      report.prepend(item);
    }, error => {
      const messages = { 1: "Permission denied. No location was read.", 2: "The device could not determine a location.", 3: "Location request timed out." };
      report.insertAdjacentHTML("afterbegin", '<div class="finding warning"><strong>Location not available</strong>' + escapeHTML(messages[error.code] || "The location request failed.") + '</div>');
    }, { enableHighAccuracy: false, maximumAge: 0, timeout: 12000 });
  });

  const overlay = $("connectivityHolo");
  $("connectivityHologram").addEventListener("click", () => {
    overlay.classList.add("open");
    document.body.style.overflow = "hidden";
    startHologram();
  });
  function closeHologram() {
    overlay.classList.remove("open");
    document.body.style.overflow = "";
    if (animationFrame) cancelAnimationFrame(animationFrame);
    animationFrame = 0;
    if (sceneState && sceneState.renderer) {
      sceneState.renderer.dispose();
      if (sceneState.renderer.domElement.parentNode) sceneState.renderer.domElement.parentNode.removeChild(sceneState.renderer.domElement);
    }
    sceneState = null;
  }
  $("connectivityHoloClose").addEventListener("click", closeHologram);
  overlay.addEventListener("click", event => { if (event.target === overlay) closeHologram(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && overlay.classList.contains("open")) closeHologram(); });
  $("connectivityRoom").addEventListener("change", () => { if (sceneState) configureScene($("connectivityRoom").value); });
  $("connectivityHoloReset").addEventListener("click", () => {
    if (!sceneState) return;
    sceneState.camera.position.set(5.6, 4.2, 7.2);
    sceneState.camera.lookAt(0, 0, 0);
  });

  function configureScene(preset) {
    if (!sceneState) return;
    const { THREE: T, roomGroup } = sceneState;
    while (roomGroup.children.length) {
      const child = roomGroup.children.pop();
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) child.material.forEach(m => m.dispose());
        else child.material.dispose();
      }
    }
    const width = preset === "open" ? 8 : preset === "corridor" ? 3 : 6;
    const depth = preset === "corridor" ? 10 : preset === "open" ? 8 : 6;
    const floor = new T.Mesh(new T.PlaneGeometry(width, depth), new T.MeshBasicMaterial({ color: 0x14304a, transparent: true, opacity: .28, side: T.DoubleSide }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -1.5;
    roomGroup.add(floor);
    const grid = new T.GridHelper(Math.max(width, depth), Math.max(width, depth), 0x3979a2, 0x24435f);
    grid.position.y = -1.48;
    roomGroup.add(grid);
    const wallMaterial = new T.MeshBasicMaterial({ color: 0x4e88bd, transparent: true, opacity: .11, wireframe: true });
    const walls = [
      [width, 3, .08, 0, 0, -depth / 2],
      [width, 3, .08, 0, 0, depth / 2],
      [.08, 3, depth, -width / 2, 0, 0],
      [.08, 3, depth, width / 2, 0, 0]
    ];
    walls.forEach(values => {
      const wall = new T.Mesh(new T.BoxGeometry(values[0], values[1], values[2]), wallMaterial.clone());
      wall.position.set(values[3], 0, values[5] || values[4] || 0);
      // Preserve explicit z for the first two wall coordinates.
      if (values[5] !== 0) wall.position.z = values[5];
      if (values[3] !== 0) wall.position.x = values[3];
      roomGroup.add(wall);
    });
    const ap = new T.Mesh(new T.OctahedronGeometry(.23, 1), new T.MeshBasicMaterial({ color: 0x72f2ff, wireframe: true }));
    ap.position.set(-width * .25, -.7, -depth * .22);
    roomGroup.add(ap);
    const point = new T.PointLight(0x63e9ff, 1.7, 8);
    point.position.copy(ap.position);
    roomGroup.add(point);
    sceneState.waves.forEach(wave => { if (wave.parent) wave.parent.remove(wave); });
    sceneState.waves = [];
    for (let i = 0; i < 5; i++) {
      const wave = new T.Mesh(new T.SphereGeometry(1 + i * .43, 32, 20),
        new T.MeshBasicMaterial({ color: i % 2 ? 0x9c7cff : 0x63e9ff, transparent: true, opacity: .12 - i * .014, wireframe: true }));
      wave.position.copy(ap.position);
      roomGroup.add(wave);
      sceneState.waves.push(wave);
    }
    sceneState.ap = ap;
    sceneState.width = width;
    sceneState.depth = depth;
  }
  function startHologram() {
    if (!window.THREE) {
      $("connectivityHoloView").innerHTML = '<div style="padding:24px;color:#ffd27b">Three.js is not available, so the 3D hologram cannot render. No substitute live data is shown.</div>';
      return;
    }
    if (sceneState) return;
    const T = window.THREE;
    const view = $("connectivityHoloView");
    view.querySelectorAll("canvas").forEach(canvas => canvas.remove());
    const scene = new T.Scene();
    scene.fog = new T.FogExp2(0x07111c, .035);
    const camera = new T.PerspectiveCamera(52, 1, .1, 100);
    camera.position.set(5.6, 4.2, 7.2);
    const renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setSize(view.clientWidth || 600, view.clientHeight || 450);
    renderer.setClearColor(0x07111c, .1);
    view.appendChild(renderer.domElement);
    const ambient = new T.AmbientLight(0x8bbbe8, 1.3);
    scene.add(ambient);
    const roomGroup = new T.Group();
    scene.add(roomGroup);
    sceneState = { THREE: T, scene, camera, renderer, roomGroup, waves: [], rotation: 0, dragging: false, pointer: null };
    configureScene($("connectivityRoom").value);
    const canvas = renderer.domElement;
    canvas.addEventListener("pointerdown", event => {
      sceneState.dragging = true; sceneState.pointer = { x: event.clientX, y: event.clientY };
      canvas.setPointerCapture && canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", event => {
      if (!sceneState || !sceneState.dragging || !sceneState.pointer) return;
      const dx = event.clientX - sceneState.pointer.x;
      const dy = event.clientY - sceneState.pointer.y;
      sceneState.pointer = { x: event.clientX, y: event.clientY };
      roomGroup.rotation.y += dx * .008;
      camera.position.y = Math.max(1.5, Math.min(8, camera.position.y - dy * .025));
    });
    canvas.addEventListener("pointerup", () => { if (sceneState) sceneState.dragging = false; });
    canvas.addEventListener("pointercancel", () => { if (sceneState) sceneState.dragging = false; });
    canvas.addEventListener("wheel", event => {
      event.preventDefault();
      camera.position.multiplyScalar(event.deltaY > 0 ? 1.06 : .94);
      camera.position.clampLength(4, 18);
    }, { passive: false });
    function render() {
      if (!sceneState || !overlay.classList.contains("open")) return;
      const width = Math.max(1, view.clientWidth);
      const height = Math.max(1, view.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.lookAt(0, 0, 0);
      camera.updateProjectionMatrix();
      const t = performance.now() / 1000;
      sceneState.waves.forEach((wave, i) => {
        const scale = 1 + ((t * .28 + i * .21) % 1) * 1.6;
        wave.scale.setScalar(scale);
        wave.material.opacity = .12 * (1 - ((t * .28 + i * .21) % 1));
      });
      sceneState.ap.rotation.y = t * .55;
      if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) roomGroup.rotation.y += .0008;
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(render);
    }
    render();
  }
})();