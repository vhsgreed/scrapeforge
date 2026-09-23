"""Tier 3 fetcher tests with fake browser backends (no browser, no network).
Run: python3 -m pytest tests/ -q"""
import sys
import types

sys.path.insert(0, ".")

import pytest

from scrapeforge import fetch as fetch_mod


class _Resp:
    def __init__(self, status):
        self.status = status


@pytest.fixture
def no_backends(monkeypatch):
    # A None entry in sys.modules makes the import raise ImportError.
    for name in ("scrapling", "scrapling.fetchers", "cloakbrowser",
                 "playwright", "playwright.sync_api"):
        monkeypatch.setitem(sys.modules, name, None)
    return monkeypatch


def test_scrapling_gets_proxy_cookies_timeout_and_real_status(no_backends):
    seen = {}

    class StealthySession:
        def __init__(self, **kw):
            seen["init"] = kw

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def fetch(self, url, **kw):
            seen["url"] = url
            return types.SimpleNamespace(status=403, html_content="<html>wall</html>")

    no_backends.setitem(sys.modules, "scrapling.fetchers",
                        types.SimpleNamespace(StealthySession=StealthySession))
    status, html = fetch_mod.fetch("https://s/x", 3, timeout=12,
                                   proxy="http://p:8080", cookies={"sid": "1"})
    assert (status, html) == (403, "<html>wall</html>")
    assert seen["init"]["timeout"] == 12000
    assert seen["init"]["proxy"] == "http://p:8080"
    assert seen["init"]["cookies"] == [{"name": "sid", "value": "1", "url": "https://s/x"}]


def test_playwright_fallback_gets_proxy_cookies_and_real_status(no_backends):
    seen = {"closed": False}

    class Page:
        def goto(self, url, timeout, wait_until):
            seen["goto_timeout"] = timeout
            return _Resp(503)

        def content(self):
            return "<html>busy</html>"

    class Ctx:
        def add_cookies(self, c):
            seen["cookies"] = c

        def new_page(self):
            return Page()

    class Browser:
        def new_context(self):
            return Ctx()

        def close(self):
            seen["closed"] = True

    class Chromium:
        def launch(self, **kw):
            seen["launch"] = kw
            return Browser()

    class PW:
        chromium = Chromium()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    no_backends.setitem(sys.modules, "playwright.sync_api",
                        types.SimpleNamespace(sync_playwright=PW))
    status, html = fetch_mod.fetch("https://s/x", 3, timeout=5,
                                   proxy="http://u:pw@p.example:3128",
                                   cookies={"a": "b"})
    assert (status, html) == (503, "<html>busy</html>")
    assert seen["launch"]["proxy"] == {"server": "http://p.example:3128",
                                       "username": "u", "password": "pw"}
    assert seen["cookies"] == [{"name": "a", "value": "b", "url": "https://s/x"}]
    assert seen["goto_timeout"] == 5000
    assert seen["closed"]


def test_no_backend_raises_fetch_error(no_backends):
    with pytest.raises(fetch_mod.FetchError):
        fetch_mod.fetch("https://s/x", 3)
