"""CSS selector extraction. Handles text, attribute, and HTML fields."""
from __future__ import annotations

from bs4 import BeautifulSoup


def extract_items(html: str, item_selector: str,
                  fields: dict) -> list[dict]:
    """Extract a list of item dicts from HTML.

    fields: {name: {"selector": str, "attr": "text"|"href"|"src"|...,
                     "scope": "item"|"next"|"global"}}
    scope=item (default): selector resolves inside each matched item node.
    scope=next: selector resolves inside the item's next sibling element (for
    data in a companion row, like HN scores). Stays aligned when a companion
    row lacks the field, because each item only looks at its own sibling.
    scope=global: selector resolves against the whole document and pairs up
    by index. Only safe when every item has exactly one match; one missing
    match shifts every later value onto the wrong row.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(item_selector)
    out = []
    global_els = {}
    for name, spec in fields.items():
        if spec.get("scope") == "global":
            sel = spec["selector"]
            global_els[name] = soup.select(sel) if sel else []
    for i, node in enumerate(items):
        row = {}
        for name, spec in fields.items():
            sel = spec["selector"]
            attr = spec.get("attr", "text")
            if spec.get("scope") == "global":
                els = global_els[name]
                el = els[i] if i < len(els) else None
            elif spec.get("scope") == "next":
                sib = node.find_next_sibling()
                el = None
                if sib is not None:
                    el = sib.select_one(sel) if sel else sib
            else:
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
