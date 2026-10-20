# NOX Cybersecurity Center and KaliGPT compatibility

## Integration decision

The upstream repository is [SudoHopeX/KaliGPT](https://github.com/SudoHopeX/KaliGPT), branch hackerx. Its README describes a Linux CLI assistant with Gemini, OpenAI, OpenRouter, Ollama and LiteLLM providers. Its tool registry includes a generic Linux command executor implemented with subprocess argument splitting. Installer scripts can invoke distribution package managers and request elevated permissions.

NOX reviewed the upstream source, README, requirements, installer and tool modules before integrating. **No KaliGPT source code or dependencies are copied into NOX by this integration.** The upstream LICENSE is a custom non-commercial license with attribution and redistribution requirements; any future code-level redistribution or hosted bundling needs a separate license review and, if commercial, written permission from the copyright holder. The disclaimer says MIT in one place, but the checked-in LICENSE differs; do not assume MIT rights.

## Current modules

- backend/cybersecurity.py: read-only code heuristic review, pasted-log triage, command explanation (never executes commands), server-only tool discovery, and explicit lab-scope validation.
- desktop-companion/cybersecurity_worker.py: local executable discovery and a bounded Nmap service-discovery adapter. It uses fixed argv, shell=False, a private/local lab target or exact NOX_CYBER_ALLOWED_HOSTS entry, an explicit authorization boolean, a scope note, exact confirmation phrase, a 45-second limit, output limits, and a cancellation event.
- frontend/dist/nox-cybersecurity.js: a Cybersecurity Center drawer, live API status, code/log review, command explanations, scope validation, and JSON report export.
- backend/tests/test_cybersecurity.py and desktop-companion/tests/test_cybersecurity_worker.py: regression tests.

## Runtime boundaries

The public Render service does not execute KaliGPT, arbitrary shell commands, Nmap, ZAP, packet capture, or local filesystem scans. /api/cybersecurity/status describes the server only; it cannot see tools installed on a user's PC or phone. Browser-only deployments cannot access the user's OS. Active network scans must be run by a local companion after the user configures and installs the appropriate tools. No scanner is auto-installed.

The local Nmap adapter is a bounded lab service-discovery example, not a general penetration-testing engine. It does not run exploits, brute force, stealth/evasion, persistence, destructive actions, or arbitrary AI-generated commands. Public targets require exact entries in NOX_CYBER_ALLOWED_HOSTS; only set this variable for assets you administer and are authorized to assess. Scope validation is not a legal authorization record and is not persisted.

## Provider support

NOX continues to use its existing provider configuration. The module only reports whether supported environment variables are present; it never returns secret values. Ollama is detected on the machine where the adapter runs, not remotely. Provider presence is not proof that a key is valid or that a model is reachable.

## Setup

1. Merge the PR only after CI passes.
2. Redeploy the NOX backend and confirm /api/cybersecurity/status.
3. For local scanning, run NOX Companion on the target workstation, install Nmap using the official installer for that OS, and set NOX_CYBER_ALLOWED_HOSTS only for explicitly authorized non-lab assets. Do not run unknown installers as root.
4. Windows users should use the local companion natively where supported, or WSL2 for Linux-only tools. Termux support is not assumed for the NOX desktop companion.
5. Set provider keys only in the existing secret/environment configuration. Never commit .env files or API keys.

## Test commands

    python -m unittest backend.tests.test_cybersecurity -v
    python -m unittest discover -s desktop-companion/tests -v
    python -m compileall -q backend desktop-companion
    node --check frontend/dist/nox-cybersecurity.js

## Rollback

Revert the merge commit to remove the router import, UI script include, and new files. Do not remove unrelated NOX modules. If a Render Blueprint was synced, redeploy the previous known-good commit and verify /api/health.
