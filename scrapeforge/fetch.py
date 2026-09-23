"""Tiered fetchers. Each tier is one import, lazy-loaded so light installs
only pay for what they use.

tier 1: httpx (plain)
tier 2: curl_cffi (TLS impersonation, verified on AliExpress 08-29)
tier 3: cloakbrowser (source-patched Chromium, Amazon-class) or
        playwright + invisible_playwright fallback
"""
from __future__ import annotations


def fetch(url: str, tier: int, timeout: int = 30, proxy: str | None = None,
          cookies: dict | None = None) -> tuple[int, str]:
    """Returns (status_code, html). Raises FetchError on hard failure.

    file:// URLs read a saved page from disk (any tier), so a config can be
    developed against a page saved once with `scrapeforge fetch`."""
    if url.startswith("file://"):
        return _read_file(url)
    if tier == 1:
        return _fetch_httpx(url, timeout, proxy, cookies)
    if tier == 2:
        return _fetch_curl_cffi(url, timeout, proxy, cookies)
    return _fetch_browser(url, timeout, proxy, cookies)


class FetchError(RuntimeError):
    pass


def _read_file(url: str) -> tuple[int, str]:
    from urllib.parse import unquote, urlparse
    path = unquote(urlparse(url).path)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return 200, f.read()
    except FileNotFoundError:
        return 404, ""


def to_url(target: str) -> str:
    """A URL stays a URL; an existing local path becomes a file:// URL."""
    import os
    from pathlib import Path
    if "://" not in target and os.path.exists(target):
        return Path(target).resolve().as_uri()
    return target


def _fetch_httpx(url, timeout, proxy, cookies) -> tuple[int, str]:
    import httpx
    kwargs = dict(timeout=timeout, follow_redirects=True,
                  headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                                         "Chrome/126.0 Safari/537.36"})
    if proxy:
        kwargs["proxy"] = proxy
    if cookies:
        kwargs["cookies"] = cookies
    r = httpx.get(url, **kwargs)
    return r.status_code, r.text


def _fetch_curl_cffi(url, timeout, proxy, cookies) -> tuple[int, str]:
    try:
        from curl_cffi import requests as cr
    except ImportError as e:
        raise FetchError("tier 2 needs curl_cffi: pip install curl_cffi") from e
    kwargs = dict(impersonate="chrome", timeout=timeout)
    if proxy:
        kwargs["proxy"] = proxy
    if cookies:
        kwargs["cookies"] = cookies
    r = cr.get(url, **kwargs)
    return r.status_code, r.text


def _cookie_params(url: str, cookies: dict | None) -> list[dict]:
    """Config cookies ({name: value}) as Playwright cookie params."""
    return [{"name": k, "value": str(v), "url": url}
            for k, v in (cookies or {}).items()]


def _playwright_proxy(proxy: str | None) -> dict | None:
    """'http://user:pass@host:port' -> Playwright's proxy dict."""
    if not proxy:
        return None
    from urllib.parse import urlparse
    u = urlparse(proxy)
    out = {"server": f"{u.scheme}://{u.hostname}" + (f":{u.port}" if u.port else "")}
    if u.username:
        out["username"] = u.username
    if u.password:
        out["password"] = u.password
    return out


def _fetch_browser(url, timeout, proxy, cookies) -> tuple[int, str]:
    """Amazon/eBay-class. Try scrapling (patchright stealth + cloudflare
    solve), then cloakbrowser, then plain playwright. None are magic; the
    probe-first flow decides whether tier 3 is even offered.

    Every backend honours proxy, cookies and timeout, and returns the real
    HTTP status of the navigation (0 when the browser reports none), so a
    403 challenge page is not passed off as a 200."""
    try:
        from scrapling.fetchers import StealthySession
    except ImportError:
        pass
    else:
        kwargs = dict(headless=True, timeout=timeout * 1000)
        if proxy:
            kwargs["proxy"] = proxy
        if cookies:
            kwargs["cookies"] = _cookie_params(url, cookies)
        with StealthySession(**kwargs) as session:
            page = session.fetch(url, solve_cloudflare=True)
            return page.status, str(page.html_content)

    try:
        from cloakbrowser import launch
    except ImportError:
        pass
    else:
        ctx = launch(headless=True, proxy=proxy)
        try:
            page = ctx.new_page()
            if cookies:
                page.context.add_cookies(_cookie_params(url, cookies))
            resp = page.goto(url, timeout=timeout * 1000,
                             wait_until="domcontentloaded")
            return (resp.status if resp else 0), page.content()
        finally:
            ctx.close()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise FetchError("tier 3 needs scrapling or cloakbrowser or playwright "
                         "+ stealth deps") from e
    with sync_playwright() as p:
        launch_kwargs = {"headless": True}
        pw_proxy = _playwright_proxy(proxy)
        if pw_proxy:
            launch_kwargs["proxy"] = pw_proxy
        browser = p.chromium.launch(**launch_kwargs)
        try:
            ctx = browser.new_context()
            if cookies:
                ctx.add_cookies(_cookie_params(url, cookies))
            page = ctx.new_page()
            resp = page.goto(url, timeout=timeout * 1000,
                             wait_until="domcontentloaded")
            return (resp.status if resp else 0), page.content()
        finally:
            browser.close()
