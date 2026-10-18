"""Opt-in Home Assistant adapter for NOX Windows Companion.

Only a small, explicit set of device actions is allowed. No arbitrary service
calls, URLs, shell commands, or camera stream URLs are accepted from chat.
"""
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import quote


def execute_home_assistant_command(command: str):
    """Return a result for recognized HA commands, or None if not an HA command."""
    base = os.getenv("NOX_HOME_ASSISTANT_URL", "").strip().rstrip("/")
    token = os.getenv("NOX_HOME_ASSISTANT_TOKEN", "").strip()
    if not base or not token:
        return None

    raw = command.strip()
    text = re.sub(r"[.!?]+$", "", raw, flags=re.UNICODE).strip().casefold()
    # Deliberately only parse a limited command grammar.
    list_match = re.fullmatch(r"(?:list|show|status of|what are my)\s+(devices|lights|switches|plugs|tvs|cameras|climate|thermostats|blinds|covers|fans|vacuums|scenes)", text)
    toggle_match = re.fullmatch(r"(?:(?:turn|switch)\s+)?(on|off)\s+(.+?)(?:\s+please)?", text)
    toggle_match_hi = re.fullmatch(r"(.+?)\s+(on|off)\s+(?:kar do|karo|please)", text)
    temp_match = re.fullmatch(r"(?:set|make)\s+(?:the\s+)?(?:ac|air conditioner|thermostat|climate)(?:\s+(.+?))?\s+(?:to\s+)?(\d{2}(?:\.\d)?)\s*(?:degrees?|°?c)?", text)
    temp_match_hi = re.fullmatch(r"(?:ac|temperature|thermostat)\s+(?:ko\s+)?(\d{2}(?:\.\d)?)\s*(?:degree|degrees|°?c)?\s+(?:kar do|set karo)", text)
    media_match = re.fullmatch(r"(?:tv|television|media player)(?:\s+(.+?))?\s+(on|off|play|pause|toggle)", text)
    cover_match = re.fullmatch(r"(?:open|close)\s+(.+?\b(?:blinds?|curtains?|shutters?|covers?)\b)(?:\s+please)?", text)
    vacuum_match = re.fullmatch(r"(?:start|stop|pause|dock|return)\s+(?:the\s+)?(?:vacuum|robot vacuum|robot cleaner)(?:\s+(.+?))?", text)
    scene_match = re.fullmatch(r"(?:activate|apply|run)\s+(?:the\s+)?scene\s+(.+)", text)
    if not any((list_match, toggle_match, toggle_match_hi, temp_match, temp_match_hi, media_match, cover_match, vacuum_match, scene_match)):
        # Also recognize simple natural-language aliases for common home devices.
        if not re.fullmatch(r"(?:lights?|all lights?)\s+(?:on|off)|(?:tv|television)\s+(?:on|off)|(?:cameras?|camera status)", text):
            return None

    def api(path: str, method="GET", payload=None):
        if not base.startswith(("http://", "https://")):
            raise ValueError("NOX_HOME_ASSISTANT_URL must begin with http:// or https://")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            base + path,
            data=data,
            method=method,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError("Home Assistant rejected its token. Check NOX_HOME_ASSISTANT_TOKEN.") from exc
            raise RuntimeError("Home Assistant API returned HTTP " + str(exc.code) + ".") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError("Home Assistant is unreachable from this PC. Check its URL and network connection.") from exc

    try:
        states = api("/api/states")
        if not isinstance(states, list):
            return {"status": "error", "message": "Home Assistant returned an unexpected device list."}

        def friendly(state):
            attrs = state.get("attributes") or {}
            return str(attrs.get("friendly_name") or state.get("entity_id") or "")

        def matches(domain, hint=""):
            wanted = re.sub(r"[^a-z0-9]", "", hint.casefold())
            items = [s for s in states if str(s.get("entity_id", "")).startswith(domain + ".")]
            if wanted and wanted not in ("all", "everything", "the"):
                items = [s for s in items if wanted in re.sub(r"[^a-z0-9]", "", friendly(s).casefold()) or wanted in re.sub(r"[^a-z0-9]", "", s.get("entity_id", "").casefold())]
            return items

        if list_match or re.fullmatch(r"(?:cameras?|camera status)", text):
            group = list_match.group(1) if list_match else "cameras"
            domains = {"devices": ("light", "switch", "media_player", "climate", "camera", "cover", "fan", "vacuum"), "lights": ("light",), "switches": ("switch",), "plugs": ("switch",), "tvs": ("media_player",), "cameras": ("camera",), "climate": ("climate",), "thermostats": ("climate",), "blinds": ("cover",), "covers": ("cover",), "fans": ("fan",), "vacuums": ("vacuum",), "scenes": ("scene",)}
            result = []
            for domain in domains[group]:
                for state in matches(domain):
                    result.append({"name": friendly(state), "entity_id": state.get("entity_id"), "state": state.get("state"), "domain": domain})
            return {"status": "success", "message": ("Found " + str(len(result)) + " compatible Home Assistant entities." if result else "No matching entities found in Home Assistant."), "devices": result[:80]}

        if temp_match or temp_match_hi:
            temperature = float((temp_match or temp_match_hi).group(2) if temp_match else temp_match_hi.group(1))
            if temperature < 10 or temperature > 35:
                return {"status": "rejected", "message": "For safety, choose a thermostat target between 10°C and 35°C."}
            climates = matches("climate")
            if not climates:
                return {"status": "not_found", "message": "No Home Assistant climate entity found."}
            api("/api/services/climate/set_temperature", "POST", {"entity_id": [s["entity_id"] for s in climates], "temperature": temperature})
            return {"status": "success", "message": "Set " + str(len(climates)) + " climate device(s) to " + str(temperature) + "°C."}

        if media_match:
            hint, action = media_match.groups()
            media = matches("media_player", hint or "tv")
            if not media:
                return {"status": "not_found", "message": "No matching Home Assistant TV/media player found."}
            service = {"on": "turn_on", "off": "turn_off", "play": "media_play", "pause": "media_pause", "toggle": "media_play_pause"}[action]
            api("/api/services/media_player/" + service, "POST", {"entity_id": [s["entity_id"] for s in media]})
            return {"status": "success", "message": "Sent " + action + " to " + ", ".join(friendly(s) for s in media[:5]) + "."}

        if cover_match:
            verb, hint = text.split(" ", 1)
            covers = matches("cover", hint)
            if not covers:
                return {"status": "not_found", "message": "No matching Home Assistant blind/cover found: " + hint}
            service = "open_cover" if verb == "open" else "close_cover"
            api("/api/services/cover/" + service, "POST", {"entity_id": [s["entity_id"] for s in covers]})
            return {"status": "success", "message": "Sent " + verb + " to " + ", ".join(friendly(s) for s in covers[:5]) + "."}

        if vacuum_match:
            action, hint = vacuum_match.groups()
            vacuum_devices = matches("vacuum", hint or "")
            if not vacuum_devices:
                return {"status": "not_found", "message": "No matching Home Assistant vacuum found."}
            service = {"start": "start", "stop": "stop", "pause": "pause", "dock": "return_to_base", "return": "return_to_base"}[action]
            api("/api/services/vacuum/" + service, "POST", {"entity_id": [s["entity_id"] for s in vacuum_devices]})
            return {"status": "success", "message": "Sent " + action + " to " + ", ".join(friendly(s) for s in vacuum_devices[:5]) + "."}

        if scene_match:
            hint = scene_match.group(1).strip()
            scenes = matches("scene", hint)
            if len(scenes) != 1:
                return {"status": "needs_choice" if scenes else "not_found", "message": ("More than one scene matches. Use its exact name: " if scenes else "No matching scene found: ") + hint, "devices": [{"name": friendly(s), "entity_id": s.get("entity_id")} for s in scenes[:10]]}
            api("/api/services/scene/turn_on", "POST", {"entity_id": scenes[0]["entity_id"]})
            return {"status": "success", "message": "Activated scene " + friendly(scenes[0]) + "."}

        action = None
        hint = ""
        if toggle_match:
            action, hint = toggle_match.groups()
        elif toggle_match_hi:
            hint, action = toggle_match_hi.groups()
        elif re.fullmatch(r"(?:lights?|all lights?)\s+(?:on|off)", text):
            action = text.split()[-1]
            hint = "all"
        elif re.fullmatch(r"(?:tv|television)\s+(?:on|off)", text):
            action = text.split()[-1]
            hint = "tv"
        if action:
            action = action.casefold()
            if action not in ("on", "off"):
                return None
            hint = re.sub(r"^(?:the|my)\s+", "", hint.strip(), flags=re.I)
            if any(word in hint for word in ("camera", "lock", "door", "alarm", "security")):
                return {"status": "rejected", "message": "Security-sensitive devices are not operated through free-form chat. Use their dedicated app or a separately configured, confirmed control."}
            if "light" in hint or hint in ("all", "everything"):
                domain = "light"
            elif any(word in hint for word in ("plug", "switch", "socket")):
                domain = "switch"
            elif any(word in hint for word in ("tv", "television", "media player")):
                domain = "media_player"
            elif any(word in hint for word in ("fan", "pankha")):
                domain = "fan"
            else:
                return {"status": "unsupported", "message": "I recognized a device-control request, but specify a supported light, plug/switch, TV/media player, or fan by its Home Assistant name."}
            target_hint = "all" if hint in ("all", "everything") or "all " in hint else re.sub(r"\b(lights?|plugs?|switches|sockets|tv|television|media player|fans?|pankha)\b", " ", hint).strip()
            entities = matches(domain, target_hint)
            if not entities:
                return {"status": "not_found", "message": "No matching " + domain + " entity found in Home Assistant for: " + hint}
            service = "turn_on" if action == "on" else "turn_off"
            api("/api/services/" + domain + "/" + service, "POST", {"entity_id": [s["entity_id"] for s in entities]})
            return {"status": "success", "message": "Sent " + action + " to " + ", ".join(friendly(s) for s in entities[:5]) + (" and more" if len(entities) > 5 else ".")}

        return None
    except (RuntimeError, ValueError) as exc:
        return {"status": "error", "message": str(exc)}
