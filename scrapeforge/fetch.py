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
    """Returns (status_code, html). Raises FetchError on hard failure."""
    if tier == 1:
        return _fetch_httpx(url, timeout, proxy, cookies)
    if tier == 2:
        return _fetch_curl_cffi(url, timeout, proxy, cookies)
    return _fetch_browser(url, timeout, proxy, cookies)


class FetchError(RuntimeError):
    pass


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


def _fetch_browser(url, timeout, proxy, cookies) -> tuple[int, str]:
    """Amazon-class. Try cloakbrowser, then playwright stealth."""
    try:
        from cloakbrowser import launch
        ctx = launch(headless=True, proxy=proxy)
        try:
            page = ctx.new_page()
            if cookies:
                for name, value in cookies.items():
                    page.context.add_cookies([{"name": name, "value": value,
                                               "url": url}])
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            return 200, page.content()
        finally:
            ctx.close()
    except ImportError:
        pass
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            html = page.content()
            browser.close()
            return 200, html
    except ImportError as e:
        raise FetchError("tier 3 needs cloakbrowser or playwright "
                         "+ invisible_playwright") from e
