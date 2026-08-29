"""CSS selector extraction. Handles text, attribute, and HTML fields."""
from __future__ import annotations

from bs4 import BeautifulSoup


def extract_items(html: str, item_selector: str,
                  fields: dict) -> list[dict]:
    """Extract a list of item dicts from HTML.

    fields: {name: {"selector": str, "attr": "text"|"href"|"src"|...}}
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(item_selector)
    out = []
    for node in items:
        row = {}
        for name, spec in fields.items():
            sel = spec["selector"]
            attr = spec.get("attr", "text")
            el = node.select_one(sel) if sel else node
            if el is None:
                row[name] = ""
                continue
            if attr == "text":
                row[name] = el.get_text(" ", strip=True)
            else:
                row[name] = el.get(attr, "").strip()
        out.append(row)
    return out
