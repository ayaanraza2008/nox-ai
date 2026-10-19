import React, { useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import HolographicCore from "./HolographicCore.jsx";

function CoreSmokeHarness() {
  const [mode, setMode] = useState("IDLE");
  const micLevelRef = useRef(0);
  const ttsLevelRef = useRef(0);
  const ttsAudioReactiveRef = useRef(false);
  const setState = (next) => {
    setMode(next);
    document.querySelectorAll("[data-mode]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.mode === next));
    });
  };
  window.__noxCoreTestSetMode = setState;
  return <HolographicCore
    mode={mode}
    micLevelRef={micLevelRef}
    ttsLevelRef={ttsLevelRef}
    ttsAudioReactiveRef={ttsAudioReactiveRef}
    motionIntensity={0.8}
  />;
}

createRoot(document.getElementById("root")).render(<CoreSmokeHarness />);
