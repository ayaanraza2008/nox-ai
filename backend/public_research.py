"""Privacy-conscious, evidence-linked public-information research helpers.

No private account access, breach dumps, face matching, or hidden metadata extraction.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email.utils import parseaddr
from urllib.parse import urlparse

import httpx

from backend.autonomous_agent import web_search

MAX_RESULTS = 6
SOCIAL_HOSTS = {
    "instagram.com", "www.instagram.com", "x.com", "www.x.com",
    "twitter.com", "www.twitter.com", "tiktok.com", "www.tiktok.com",
    "facebook.com", "www.facebook.com", "linkedin.com", "www.linkedin.com",
    "youtube.com", "www.youtube.com", "youtu.be", "threads.net",
    "www.threads.net", "reddit.com", "www.reddit.com",
}
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
PHONE_RE = re.compile(r"^\+?[0-9().\-\s]{7,30}$")


def _search_results(raw: str) -> list[dict]:
    try:
        items = json.loads(raw)
    except (TypeError, ValueError):
        return []
    results = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        title = str(item.get("title") or "").strip()[:240]
        snippet = str(item.get("snippet") or "").strip()[:600]
        if url.startswith(("https://", "http://")) and title:
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= MAX_RESULTS:
            break
    return results


async def _domain_metadata(domain: str) -> dict:
    out = {"domain": domain, "mx_records": [], "a_records": [], "source": "Cloudflare public DNS-over-HTTPS"}
    async with httpx.AsyncClient(timeout=7, follow_redirects=False, headers={"accept": "application/dns-json"}) as client:
        for record_type, key in (("MX", "mx_records"), ("A", "a_records")):
            try:
                response = await client.get("https://cloudflare-dns.com/dns-query", params={"name": domain, "type": record_type})
                response.raise_for_status()
                data = response.json()
                out[key] = [str(x.get("data", ""))[:255] for x in data.get("Answer", [])[:8] if isinstance(x, dict)]
            except (httpx.HTTPError, ValueError):
                out[key] = []
                out.setdefault("warnings", []).append(f"{record_type} DNS lookup unavailable")
    return out


async def research_email(value: str) -> dict:
    address = value.strip()
    valid = bool(EMAIL_RE.fullmatch(address)) and parseaddr(address)[1] == address
    result = {"kind": "email", "input_examined": address[:254], "checked_at": datetime.now(timezone.utc).isoformat(),
              "syntax_valid": valid, "confirmed_facts": [], "possible_matches": [], "warnings": [],
              "sources": [], "limits": ["DNS records do not prove a mailbox exists or who controls it.",
              "No inbox access, password reset, private breach data, or account enumeration was attempted."]}
    if not valid:
        result["warnings"].append("Email syntax is invalid or unsupported; public search was not performed.")
        return result
    domain = address.rsplit("@", 1)[1].lower()
    dns = await _domain_metadata(domain)
    result["domain_metadata"] = dns
    if dns.get("mx_records"):
        result["confirmed_facts"].append("The domain publishes MX DNS records.")
    elif dns.get("a_records"):
        result["possible_matches"].append("The domain resolves to an A record, but no MX record was returned.")
    else:
        result["warnings"].append("No MX/A record was returned; DNS can be temporarily unavailable.")
    try:
        result["sources"] = _search_results(await web_search('"' + address.replace('"', "") + '"'))
    except Exception:
        result["warnings"].append("Public webpage search is currently unavailable.")
    result["evidence_note"] = "Search results are leads, not proof that an address belongs to a specific person."
    return result


async def research_phone(value: str) -> dict:
    raw = value.strip()
    result = {"kind": "phone", "input_examined": raw[:40], "checked_at": datetime.now(timezone.utc).isoformat(),
              "normalized_number": None, "number_type": "unknown", "country": None,
              "confirmed_facts": [], "possible_matches": [], "warnings": [], "sources": [],
              "limits": ["A phone number alone does not reveal a subscriber's identity, private address, or live location."]}
    if not PHONE_RE.fullmatch(raw):
        result["warnings"].append("Number format is not recognized; include a country calling code such as +91.")
        return result
    try:
        import phonenumbers
        parsed = phonenumbers.parse(raw, None)
        if not phonenumbers.is_possible_number(parsed):
            result["warnings"].append("The number is not a possible number for the parsed numbering plan.")
            return result
        result["normalized_number"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        result["country"] = phonenumbers.region_code_for_number(parsed)
        number_type = phonenumbers.number_type(parsed)
        result["number_type"] = {
            phonenumbers.PhoneNumberType.MOBILE: "mobile",
            phonenumbers.PhoneNumberType.FIXED_LINE: "fixed_line",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_line_or_mobile",
            phonenumbers.PhoneNumberType.VOIP: "voip",
            phonenumbers.PhoneNumberType.TOLL_FREE: "toll_free",
        }.get(number_type, "other_or_unknown")
        result["confirmed_facts"].append("Numbering metadata parsed from the public numbering plan; this does not verify current assignment or ownership.")
    except (ImportError, Exception) as exc:
        result["warnings"].append("Phone metadata library unavailable or number could not be parsed.")
        return result
    try:
        result["sources"] = _search_results(await web_search('"' + result["normalized_number"] + '"'))
    except Exception:
        result["warnings"].append("Public webpage search is currently unavailable.")
    return result


def _validate_social(value: str) -> tuple[str, str]:
    raw = value.strip()
    if len(raw) > 500:
        raise ValueError("Username or profile URL is too long.")
    if "://" in raw:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or host not in SOCIAL_HOSTS or parsed.username or parsed.password:
            raise ValueError("Use an HTTPS public profile URL from a supported social platform.")
        if not parsed.path.strip("/"):
            raise ValueError("The profile URL must include a public username or profile path.")
        return raw, host.removeprefix("www.")
    username = raw.lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", username):
        raise ValueError("Enter a public username or HTTPS profile URL.")
    return username, ""


async def research_social(value: str) -> dict:
    query, host = _validate_social(value)
    if host:
        search_query = 'site:' + host + ' "' + query.replace('"', "") + '"'
        profile = query
    else:
        search_query = '"' + query + '" public profile'
        profile = None
    result = {"kind": "social", "input_examined": value[:500], "profile_url": profile,
              "checked_at": datetime.now(timezone.utc).isoformat(), "confirmed_facts": [],
              "possible_matches": [], "warnings": [], "sources": [],
              "limits": ["Only public search results are shown. Private profiles, login-only content, and restricted APIs are not accessed.",
                         "A matching username or display name does not prove two accounts belong to the same person."]}
    try:
        result["sources"] = _search_results(await web_search(search_query))
    except Exception:
        result["warnings"].append("Public webpage search is currently unavailable.")
    return result


async def research_image_context(value: str) -> dict:
    text = " ".join(value.split())[:1500]
    result = {"kind": "image", "input_examined": text, "checked_at": datetime.now(timezone.utc).isoformat(),
              "confirmed_facts": [], "possible_matches": [], "warnings": [], "sources": [],
              "limits": ["OCR text can be incomplete or wrong. No face identification, face matching, hidden EXIF/GPS extraction, or private-person profiling is performed."]}
    if len(text) < 3:
        result["warnings"].append("No useful visible text/context was supplied. Run local OCR on the image or add a visible landmark, product, logo, or sign description.")
        return result
    try:
        result["sources"] = _search_results(await web_search('"' + text.replace('"', "")[:250] + '"'))
        if not result["sources"]:
            result["sources"] = _search_results(await web_search(text[:250] + " landmark OR product OR logo"))
    except Exception:
        result["warnings"].append("Public webpage search is currently unavailable.")
    return result
