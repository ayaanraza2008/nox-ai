"""Truthful application-control capability registry for NOX AI.

This registry describes implemented adapters, not aspirational features. Keep
statuses aligned with code that exists and clearly label setup requirements.
"""
from __future__ import annotations

from typing import Any


def get_automation_capabilities() -> dict[str, Any]:
    """Return supported control surfaces and their verified implementation scope."""
    adapters = [
        {
            "id": "public_web_research",
            "name": "Public web research",
            "platforms": ["cloud"],
            "status": "implemented",
            "actions": ["search_public_web", "read_public_html_or_text"],
            "requires": ["configured AI provider for agent reasoning"],
            "limitations": [
                "Bounded tool rounds; public pages only",
                "Does not sign in, submit forms, or send messages",
                "Page content is untrusted input",
            ],
        },
        {
            "id": "windows_app_launch",
            "name": "Windows app launcher",
            "platforms": ["windows"],
            "status": "implemented_with_setup",
            "actions": ["discover_start_menu_shortcuts", "launch_selected_shortcut", "open_supported_website", "run_allowlisted_diagnostics"],
            "requires": ["running local desktop companion", "local companion token", "user confirmation for app launch"],
            "limitations": [
                "Launch-only; no general click/type/window control",
                "Only apps with discoverable Start Menu shortcuts",
                "A launch response does not prove the app window opened",
            ],
        },
        {
            "id": "android_app_intents",
            "name": "Android app intents",
            "platforms": ["android"],
            "status": "limited",
            "actions": ["open_supported_app_intent"],
            "requires": ["Android browser/device support"],
            "limitations": [
                "Small fixed app list; cannot enumerate or control every installed app",
                "No general cross-app screen automation",
            ],
        },
        {
            "id": "browser_navigation",
            "name": "Browser navigation from the web dashboard",
            "platforms": ["web"],
            "status": "limited",
            "actions": ["open_known_website", "open_explicit_http_https_url"],
            "requires": [],
            "limitations": [
                "Opens a page in the user's browser; does not automate its DOM",
                "Does not control the browser after the dashboard is closed",
            ],
        },
        {
            "id": "ios_app_control",
            "name": "iOS app control",
            "platforms": ["ios", "ipados"],
            "status": "not_implemented",
            "actions": [],
            "requires": ["a future Shortcuts/App Intents integration"],
            "limitations": [
                "No unrestricted background execution or arbitrary app control",
            ],
        },
        {
            "id": "authenticated_service_connectors",
            "name": "Authenticated productivity connectors",
            "platforms": ["cloud", "web"],
            "status": "not_implemented",
            "actions": [],
            "requires": ["individual official API/OAuth integrations"],
            "limitations": [
                "No connected email, calendar, Drive, or messaging OAuth adapter is currently registered",
            ],
        },
        {
            "id": "general_browser_automation",
            "name": "Authenticated browser automation",
            "platforms": ["windows", "cloud"],
            "status": "not_implemented",
            "actions": [],
            "requires": ["dedicated Playwright worker and explicit session authorization"],
            "limitations": [
                "No general Playwright click/type/form automation worker is currently exposed",
            ],
        },
    ]
    return {
        "registry_version": 1,
        "principle": "Only capabilities listed as implemented are currently wired to an execution path.",
        "adapters": adapters,
    }
