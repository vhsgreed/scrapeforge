"""Pagination loop tests (no network). Run: python3 -m pytest tests/ -q"""
import sys

sys.path.insert(0, ".")

from scrapeforge.paginate import paginate


def _site(pages: dict):
    fetched = []

    def get_html(url):
        fetched.append(url)
        if url not in pages:
            return 404, ""
        return 200, pages[url]
    return get_html, fetched


def _next(href):
    return f'<html><body><a class="next" href="{href}">Next</a></body></html>'


CFG = {"max_pages": 10, "rate_limit_sec": 0,
       "paginate": {"selector": "a.next"}}


def test_relative_next_link_resolves_against_current_page():
    # Page 2 links "?page=3" relative to /cat/page/2/, not the start URL.
    pages = {
        "https://s/cat/": _next("page/2/"),
        "https://s/cat/page/2/": _next("?page=3"),
        "https://s/cat/page/2/?page=3": "<html>end</html>",
    }
    get_html, fetched = _site(pages)
    n = paginate(get_html, "https://s/cat/", CFG, lambda h: None)
    assert fetched == list(pages)
    assert n == 3


def test_stops_when_next_link_cycles_back():
    pages = {"https://s/a": _next("/b"), "https://s/b": _next("/a")}
    get_html, fetched = _site(pages)
    n = paginate(get_html, "https://s/a", CFG, lambda h: None)
    assert fetched == ["https://s/a", "https://s/b"]
    assert n == 2


def test_stops_on_error_status():
    get_html, fetched = _site({"https://s/a": _next("/missing")})
    n = paginate(get_html, "https://s/a", CFG, lambda h: None)
    assert fetched == ["https://s/a", "https://s/missing"]
    assert n == 1
