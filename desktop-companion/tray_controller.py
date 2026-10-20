"""Optional Windows notification-area controls for the local NOX companion."""
from __future__ import annotations

import os
import webbrowser

from emergency_state import get_state, set_stopped

DASHBOARD_URL = os.getenv("NOX_DASHBOARD_URL", "https://nox-ai-vcqx.onrender.com")


def _image(stopped: bool):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (64, 64), (7, 11, 19))
    draw = ImageDraw.Draw(image)
    draw.ellipse((7, 7, 57, 57), fill=(128, 16, 42) if stopped else (13, 75, 82),
                 outline=(255, 92, 118) if stopped else (113, 234, 255), width=3)
    draw.text((23, 19), "N", fill=(255, 255, 255))
    draw.text((15, 43), "STOP" if stopped else "AI", fill=(255, 255, 255))
    return image


def start_tray():
    """Start a tray icon only on Windows; API operation does not depend on it."""
    if os.name != "nt":
        return False
    import pystray

    def refresh(icon):
        stopped = get_state()["stopped"]
        icon.title = "NOX AI — STOPPED" if stopped else "NOX AI — READY"
        icon.icon = _image(stopped)
        try:
            icon.update_menu()
        except Exception:
            pass

    def stop_action(icon, item):
        set_stopped(True, "windows_tray_emergency_stop")
        refresh(icon)

    def resume_action(icon, item):
        set_stopped(False, "windows_tray_explicit_resume")
        refresh(icon)

    def open_dashboard(icon, item):
        webbrowser.open(DASHBOARD_URL, new=2, autoraise=True)

    menu = pystray.Menu(
        pystray.MenuItem("EMERGENCY STOP", stop_action, default=False),
        pystray.MenuItem("Resume NOX", resume_action, default=False),
        pystray.MenuItem("Open NOX Dashboard", open_dashboard, default=True),
    )
    icon = pystray.Icon("nox_ai_companion", _image(get_state()["stopped"]), "NOX AI", menu)
    icon.run_detached()
    return True
