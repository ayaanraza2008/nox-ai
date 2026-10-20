"""Truthful capability registry for NOX's currently wired adapters.

Statuses describe code/configuration readiness, not a guarantee that an external
provider, device, or website is reachable at this instant.
"""
from __future__ import annotations
import os
from typing import Any


def get_automation_capabilities(ai_configured: bool | None = None, browser_available: bool | None = None) -> dict[str, Any]:
    """Return capabilities with environment-dependent setup reflected explicitly."""
    if ai_configured is None:
        ai_configured = any(os.getenv(key, "").strip() for key in ("OPENROUTER_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"))
    if browser_available is None:
        try:
            from backend.browser_automation import async_playwright
            browser_available = async_playwright is not None
        except Exception:
            browser_available = False
    adapters = [
        {"id":"public_web_research","name":"Public web research","platforms":["cloud"],
         "status":"ready" if ai_configured else "setup_required",
         "actions":["search_public_web","read_public_html_or_text","summarize_public_sources"],
         "requires":[] if ai_configured else ["configure OPENROUTER_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY"],
         "limitations":["Bounded tool rounds; public pages only","Does not sign in, submit forms, or send messages","Page content is untrusted input and cannot override user intent"]},
        {"id":"remote_browser_automation","name":"Remote Playwright browser","platforms":["cloud"],
         "status":"implemented_with_setup" if browser_available else "setup_required",
         "actions":["open_public_url","search_web","inspect_page","click_accessible_control","fill_non_sensitive_field","scroll","navigate_history","download_with_confirmation","verify_visible_page_change"],
         "requires":[] if browser_available else ["install Playwright and its Chromium browser"],
         "limitations":["Uses an isolated remote browser, not the user's local browser profile","Bounded command parser; not arbitrary website compatibility","Passwords, OTPs, payment details and secrets are not auto-filled","CAPTCHA, MFA, passkeys and authentication challenges require user interaction","Consequential clicks and downloads require explicit confirmation","Private/local network destinations are blocked"]},
        {"id":"windows_app_launch","name":"Windows desktop companion","platforms":["windows"],"status":"implemented_with_setup",
         "actions":["discover_start_menu_shortcuts","launch_selected_shortcut","open_supported_website","run_allowlisted_diagnostics"],
         "requires":["install and run desktop-companion locally","pair device with NOX"],
         "limitations":["Launch and allowlisted diagnostics only; not general desktop click/type control","Only apps with discoverable Start Menu shortcuts are listed","Arbitrary shell commands are not accepted through the relay"]},
        {"id":"android_app_intents","name":"Native Android companion","platforms":["android"],"status":"implemented_with_setup",
         "actions":["open_supported_app_intent","open_supported_website","pair_device","receive_command_relay"],
         "requires":["install android-companion app","pair device","keep required foreground service enabled"],
         "limitations":["Small supported app/website set; does not enumerate or control every installed app","Background launches may require tapping an Android notification","No general cross-app screen automation or private app-data access"]},
        {"id":"browser_navigation","name":"Dashboard browser handoff","platforms":["web"],"status":"limited",
         "actions":["open_known_website","open_explicit_http_https_url"],"requires":[],
         "limitations":["Opens a page in the user's browser; does not automate that local browser's DOM","Does not control the browser after the dashboard is closed"]},
        {"id":"ios_app_control","name":"iOS and iPadOS handoff","platforms":["ios","ipados"],"status":"not_implemented","actions":[],
         "requires":["a future Shortcuts/App Intents or Universal Links integration"],
         "limitations":["No iOS companion is currently included","iOS does not permit unrestricted arbitrary app or background UI control"]},
        {"id":"authenticated_service_connectors","name":"Email, calendar, Drive and messaging connectors","platforms":["cloud","web"],"status":"not_implemented","actions":[],
         "requires":["individual official API/OAuth integrations and explicit account authorization"],
         "limitations":["No connected email, calendar, Drive, or messaging OAuth adapter is currently registered","Browser automation is not a substitute for a supported provider API"]},
        {"id":"media_generation","name":"Image and video generation","platforms":["cloud","local"],"status":"not_implemented","actions":[],
         "requires":["a configured media model/service and verified runtime dependencies"],
         "limitations":["No image/video generation provider is wired to the production execution path"]},
        {"id":"local_model_runtime","name":"Local model runtime","platforms":["windows","linux","macos"],"status":"not_implemented","actions":[],
         "requires":["an installed model server such as Ollama or llama.cpp plus a configured endpoint"],
         "limitations":["NOX does not install or launch a local model server on the user's device"]},
    ]
    return {"registry_version":2,
            "principle":"Only wired capabilities are described as implemented; configured does not guarantee external availability.",
            "runtime":{"ai_provider_configured":bool(ai_configured),"playwright_package_available":bool(browser_available),
                       "browser_session_isolated":True,"server_can_detect_local_companion_online":False},
            "adapters":adapters}
