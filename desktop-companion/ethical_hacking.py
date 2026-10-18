"""Passive, low-impact website security checks for authorized targets only.

This module checks a single public HTTP(S) page's response headers. It does not
scan ports, crawl links, brute-force, exploit vulnerabilities, or submit forms.
"""
import ipaddress
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request


SECURITY_HEADERS = {
    "strict-transport-security": ("HSTS", "Helps browsers require HTTPS after a secure visit."),
    "content-security-policy": ("CSP", "Helps limit which scripts and resources a page may load."),
    "x-content-type-options": ("MIME sniffing protection", "Usually set to nosniff."),
    "referrer-policy": ("Referrer policy", "Controls how much referrer information is shared."),
    "permissions-policy": ("Permissions policy", "Restricts selected browser features."),
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_public_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("For this passive check, enter a public HTTPS URL without embedded credentials.")
    if parsed.port not in (None, 443):
        raise ValueError("Only standard HTTPS port 443 is supported; no port scanning is performed.")
    host = parsed.hostname.rstrip(".")
    if host.casefold() in {"localhost", "localhost.localdomain"} or "." not in host:
        raise ValueError("Only publicly hosted domain names are supported.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise ValueError("Could not resolve that domain. Check the URL and try again.") from exc
    if not addresses:
        raise ValueError("The domain did not resolve to an address.")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global:
            raise ValueError("Private, local, and non-public network targets are blocked.")
    return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, ""))


def check_website_security(url: str):
    """Check HTTPS response headers once; return a concise, non-invasive report."""
    try:
        safe_url = _validate_public_url(url.strip())
        opener = urllib.request.build_opener(
            NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
        req = urllib.request.Request(
            safe_url,
            headers={"User-Agent": "NOX-Passive-Security-Check/1.0", "Accept": "text/html,application/xhtml+xml"},
            method="GET",
        )
        try:
            response = opener.open(req, timeout=8)
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:
                return {"status": "needs_review", "message": "The site redirects. Redirects are not followed by this checker; review the destination manually.", "url": safe_url}
            response = exc
        with response:
            status_code = getattr(response, "status", 200)
            headers = {key.casefold(): value for key, value in response.headers.items()}
            content_type = headers.get("content-type", "")
            if not (content_type.startswith("text/html") or content_type.startswith("application/xhtml+xml")):
                return {"status": "needs_review", "url": safe_url, "http_status": status_code, "message": "The URL did not return an HTML page, so header checks are limited."}
            checks = []
            missing = []
            for key, (name, note) in SECURITY_HEADERS.items():
                present = key in headers
                checks.append({"check": name, "status": "present" if present else "missing", "detail": note})
                if not present:
                    missing.append(name)
            if safe_url.startswith("https://"):
                checks.append({"check": "HTTPS", "status": "pass", "detail": "TLS certificate validation succeeded for this request."})
            return {
                "status": "success",
                "url": safe_url,
                "http_status": status_code,
                "checks": checks,
                "summary": (str(len(missing)) + " recommended security header(s) missing: " + ", ".join(missing)) if missing else "All checked security headers are present.",
                "limitations": "Passive, single-request check only. Missing headers are not proof of a vulnerability; this is not a penetration test.",
            }
    except (ValueError, OSError, urllib.error.URLError, TimeoutError) as exc:
        return {"status": "error", "message": str(exc)}
