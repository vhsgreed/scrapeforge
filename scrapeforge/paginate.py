"""Pagination loop: follow next-page links/selectors up to max_pages."""
from __future__ import annotations

import time
from urllib.parse import urljoin


def paginate(get_html, base_url: str, cfg: dict, on_page) -> int:
    """Calls get_html(url) -> html, on_page(html) per page.

    cfg pagination keys:
      selector, attribute (default 'href'), next_text (optional), max_pages
    Returns number of pages fetched.
    """
    pag = cfg.get("paginate") or {}
    max_pages = min(cfg.get("max_pages", 10), 100)
    rate = cfg.get("rate_limit_sec", 2.0)

    url = cfg["url"]
    pages = 0
    from bs4 import BeautifulSoup

    while url and pages < max_pages:
        status, html = get_html(url)
        if status >= 400:
            break
        pages += 1
        on_page(html)

        if not pag:
            break
        soup = BeautifulSoup(html, "html.parser")
        sel = pag.get("selector")
        attr = pag.get("attribute", "href")
        next_el = None
        if pag.get("next_text"):
            for el in soup.select(sel or "a"):
                if pag["next_text"].lower() in el.get_text(" ", strip=True).lower():
                    next_el = el
                    break
        else:
            next_el = soup.select_one(sel) if sel else None
        if next_el is None:
            break
        href = next_el.get(attr)
        if not href or href.startswith("javascript:"):
            break
        url = urljoin(base_url, href)
        if rate:
            time.sleep(rate)
    return pages
