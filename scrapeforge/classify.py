"""Site probing: classify a target's anti-bot level and pick a fetch tier.

Tier 1: plain HTTP works (static HTML in response).
Tier 2: TLS impersonation needed (curl_cffi) — JS-heavy or Akamai-style.
Tier 3: full browser needed (CloakBrowser/Playwright stealth) — Amazon-class.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CHALLENGE_MARKERS = [
    "captcha", "recaptcha", "turnstile", "hcaptcha", "access denied",
    "robot check", "verify you are human", "unusual traffic", "attention required",
    "please enable javascript", "challenge", "cf-chl", "__cf_chl",
]

BLOCK_PATTERNS = [
    (r"<title>\s*Access Denied", "akamai"),
    (r"cf-browser-verification|challenges\.cloudflare", "cloudflare"),
    (r"punish\.xiao|\"/punish", "aliexpress-akamai"),
    (r"g-recaptcha|recaptcha/api", "recaptcha"),
]


@dataclass
class ProbeResult:
    url: str
    status: int
    body_size: int
    tier: int          # 1, 2, or 3
    confident: bool    # False when the signal is ambiguous
    markers: list[str]
    note: str = ""


def _markers_hit(text: str) -> list[str]:
    low = text.lower()
    return [m for m in CHALLENGE_MARKERS if m in low]


def _blocked_by(text: str) -> str | None:
    for pat, name in BLOCK_PATTERNS:
        if re.search(pat, text, re.I):
            return name
    return None


def classify_response(url: str, status: int, text: str) -> ProbeResult:
    markers = _markers_hit(text)
    block = _blocked_by(text)
    size = len(text)

    # Empty body on a real page (e.g. Amazon 202 with 0 bytes) = blocked.
    # Small-but-real static pages stay tier 1; only truly empty/challenged
    # bodies with non-200 status escalate.
    if (status in (202, 403, 429, 503) and size < 20000) or (size == 0):
        return ProbeResult(url, status, size, 3, True, markers,
                           f"blocked: {block or 'empty/challenged response'}")

    # Tiny body + challenge markers = classic block page (e.g. Amazon 202).
    # Always escalate to a higher tier when this is what plain HTTP returns.
    if size < 20000 and (markers or block):
        return ProbeResult(url, status, size, 3, True, markers,
                           f"blocked: {block or 'challenge'}")

    # Full-size body with real page markers = fine via TLS impersonation.
    # Akamai-class sites (AliExpress) only pass with curl_cffi.
    if size > 50000 and (block or markers or "punish" in text.lower()):
        return ProbeResult(url, status, size, 2, True, markers,
                           "real page served, TLS impersonation recommended")

    # Static HTML with no challenge markers: tier 1 is enough.
    # Small pages (like example.com) are fine too, as long as the body is
    # clean and we got it via plain HTTP in the probe.
    if not markers and not block:
        return ProbeResult(url, status, size, 1, True, [], "static page")


def probe(url: str, timeout: int = 25) -> ProbeResult:
    """Fetch once and classify. Tries plain first, then TLS impersonation."""
    try:
        import httpx
        r = httpx.get(url, timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        res = classify_response(url, r.status_code, r.text)
        if res.tier <= 1:
            return res
    except Exception as e:
        res = ProbeResult(url, 0, 0, 2, False, [], f"httpx failed: {e}")

    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate="chrome", timeout=timeout)
        res2 = classify_response(url, r.status_code, r.text)
        # The response only arrived via TLS impersonation, so tier 2 is the
        # honest floor even if the page looks like a plain static page.
        if res2.tier < 2:
            res2 = ProbeResult(res2.url, res2.status, res2.body_size, 2,
                               res2.confident, res2.markers,
                               "served via TLS impersonation (curl_cffi)")
        if res2.tier < res.tier or res2.confident:
            return res2
    except Exception as e:
        return ProbeResult(url, 0, 0, 3, False, [],
                           f"tls fetch failed: {e}")

    return res
