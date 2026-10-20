"""Privacy-first, evidence-based connectivity issue classification.

This module only classifies browser-visible observations supplied after an explicit
user action. It does not scan networks, query routers, collect credentials, or
control Wi-Fi/Bluetooth hardware.
"""
from __future__ import annotations

from typing import Any


def analyze_browser_observations(observations: dict[str, Any]) -> dict[str, Any]:
    """Return findings supported by browser-visible network observations only."""
    if not isinstance(observations, dict):
        raise ValueError("Observations must be a JSON object.")

    online = observations.get("online")
    if online is not None and not isinstance(online, bool):
        raise ValueError("online must be true, false, or omitted.")

    connection_type = observations.get("effective_type")
    if connection_type not in (None, "slow-2g", "2g", "3g", "4g", "5g", "unknown"):
        raise ValueError("Unsupported effective connection type.")

    downlink = observations.get("downlink_mbps")
    if downlink is not None and (
        isinstance(downlink, bool) or not isinstance(downlink, (int, float))
        or downlink < 0 or downlink > 10000
    ):
        raise ValueError("downlink_mbps is outside the accepted range.")

    rtt = observations.get("rtt_ms")
    if rtt is not None and (
        isinstance(rtt, bool) or not isinstance(rtt, (int, float))
        or rtt < 0 or rtt > 600000
    ):
        raise ValueError("rtt_ms is outside the accepted range.")

    findings: list[dict[str, str]] = []
    if online is False:
        findings.append({
            "code": "browser_offline",
            "severity": "high",
            "certainty": "observed",
            "title": "Browser reports offline",
            "detail": "The browser's online flag is false. This does not identify the router or explain the cause.",
        })
    elif online is True:
        findings.append({
            "code": "browser_online_flag",
            "severity": "info",
            "certainty": "observed",
            "title": "Browser reports online",
            "detail": "The browser reports an online connection; this flag does not guarantee that a specific website or service is reachable.",
        })

    if connection_type in ("slow-2g", "2g"):
        findings.append({
            "code": "slow_connection_estimate",
            "severity": "warning",
            "certainty": "estimated",
            "title": "Connection may be slow",
            "detail": "The browser reports a slow effective connection class. This is an estimate, not a Wi-Fi signal-strength reading.",
        })
    if isinstance(rtt, (int, float)) and rtt >= 800:
        findings.append({
            "code": "high_rtt_estimate",
            "severity": "warning",
            "certainty": "observed",
            "title": "High reported round-trip time",
            "detail": "The browser connection API reports high round-trip time; this value may be rounded or privacy-restricted.",
        })
    if isinstance(downlink, (int, float)) and downlink < 1:
        findings.append({
            "code": "low_downlink_estimate",
            "severity": "warning",
            "certainty": "estimated",
            "title": "Low estimated downlink",
            "detail": "The browser estimates less than 1 Mbps downlink. This is not a direct radio measurement.",
        })

    return {
        "source": "browser_network_information_api",
        "observations": {
            "online": online,
            "effective_type": connection_type,
            "downlink_mbps": downlink,
            "rtt_ms": rtt,
            "type": observations.get("type") if observations.get("type") in
                (None, "wifi", "cellular", "ethernet", "bluetooth", "other", "unknown") else None,
            "sampled_at": str(observations.get("sampled_at", ""))[:40],
        },
        "findings": findings,
        "limitations": [
            "Websites cannot reliably read Wi-Fi SSID, RSSI, channel, encryption mode, gateway, DNS, or hotspot clients.",
            "This report does not scan nearby networks or prove router security.",
            "Wi-Fi and Bluetooth control require a supported native companion and explicit OS permissions.",
        ],
    }
