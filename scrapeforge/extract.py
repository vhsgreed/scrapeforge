"""Extraction: CSS selectors or embedded JSON in, cleaned records out."""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from .embedded import get_path, items_from_json

_NUMBER = re.compile(r"-?\d[\d,'  ]*(?:\.\d+)?")


def extract_page(html: str, cfg: dict) -> list[dict]:
    """Records for one page, per the config's `items:` and `fields:` blocks.

    items.selector -> CSS mode: fields use selector/attr/scope.
    items.json     -> embedded JSON mode: fields use path.
    Either way, fields may add regex/strip/type/default post-processing.
    """
    items_cfg = cfg["items"]
    fields = cfg["fields"]
    if "json" in items_cfg:
        return [{name: clean(_json_value(obj, spec), spec)
                 for name, spec in fields.items()}
                for obj in items_from_json(html, items_cfg)]
    return extract_items(html, items_cfg["selector"], fields)


def extract_items(html: str, item_selector: str,
                  fields: dict) -> list[dict]:
    """Extract a list of item dicts from HTML with CSS selectors.

    fields: {name: {"selector": str, "attr": "text"|"html"|"href"|...,
                     "scope": "item"|"next"|"global", "all": bool,
                     "join": str, plus the clean() keys}}
    scope=item (default): selector resolves inside each matched item node.
    scope=next: selector resolves inside the item's next sibling element (for
    data in a companion row, like HN scores). Stays aligned when a companion
    row lacks the field, because each item only looks at its own sibling.
    scope=global: selector resolves against the whole document and pairs up
    by index. Only safe when every item has exactly one match; one missing
    match shifts every later value onto the wrong row.
    all: true collects every match (joined with `join`, default ", ")
    instead of the first.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(item_selector)
    out = []
    global_els = {}
    for name, spec in fields.items():
        if spec.get("scope") == "global":
            sel = spec.get("selector")
            global_els[name] = soup.select(sel) if sel else []
    for i, node in enumerate(items):
        row = {}
        for name, spec in fields.items():
            sel = spec.get("selector")
            attr = spec.get("attr", "text")
            scope = spec.get("scope", "item")
            if scope == "global":
                els = global_els[name]
                els = [els[i]] if i < len(els) else []
            else:
                root = node.find_next_sibling() if scope == "next" else node
                if root is None:
                    els = []
                elif not sel:
                    els = [root]
                else:
                    els = root.select(sel) if spec.get("all") else \
                        [e for e in [root.select_one(sel)] if e is not None]
            values = [_node_value(el, attr) for el in els]
            raw = spec.get("join", ", ").join(values) if spec.get("all") \
                else (values[0] if values else None)
            row[name] = clean(raw, spec)
        out.append(row)
    return out


def _node_value(el, attr: str) -> str:
    if attr == "text":
        return el.get_text(" ", strip=True)
    if attr == "html":
        return el.decode_contents().strip()
    val = el.get(attr, "")
    if isinstance(val, list):  # multi-valued attributes such as class
        val = " ".join(val)
    return val.strip()


def _json_value(obj, spec: dict):
    vals = get_path(obj, spec.get("path"))
    if spec.get("all"):
        return spec.get("join", ", ").join(_scalar(v) for v in vals) if vals else None
    return vals[0] if vals else None


def _scalar(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def clean(value, spec: dict):
    """Apply a field's post-processing: strip, regex, type, default.

    - strip: true trims whitespace; a string trims those characters.
    - regex: keep group 1 if the pattern has a group, else the whole match;
      no match means missing.
    - type: str (default) | int | float. Numbers are read from the first
      number in the text: "£1,299.00" -> 1299.0, "10 points" -> 10.
    - default: value for a missing or unparseable field. Without it, a
      missing str field is "" and a missing number is null (empty in CSV).
    """
    typ = spec.get("type", "str")
    has_default = "default" in spec
    missing = spec.get("default") if has_default else ("" if typ == "str" else None)

    if value is None:
        return missing
    if typ in ("int", "float") and isinstance(value, (int, float)) \
            and not isinstance(value, bool) and not spec.get("regex"):
        return int(value) if typ == "int" else float(value)

    text = _scalar(value)
    strip = spec.get("strip", True)
    if strip is True:
        text = text.strip()
    elif isinstance(strip, str):
        text = text.strip(strip)

    if spec.get("regex"):
        m = re.search(spec["regex"], text)
        if not m:
            return missing
        text = m.group(1) if m.re.groups else m.group(0)
        if text is None:
            return missing

    if typ == "str":
        return text if (text or not has_default) else missing
    if typ in ("int", "float"):
        m = _NUMBER.search(text)
        if not m:
            return missing
        num = float(re.sub(r"[,'  ]", "", m.group(0)))
        return int(num) if typ == "int" else num
    raise ValueError(f"unknown field type: {typ!r} (use str, int or float)")
