"""Embedded JSON: data many "JavaScript shell" pages already carry in the HTML.

A page that renders client side often ships its data in the response anyway:
JSON-LD blocks (<script type="application/ld+json">), Next.js's
<script id="__NEXT_DATA__">, or a `window.__INITIAL_STATE__ = {...}` style
assignment. Tier 1 or 2 can read those without a browser.

Sources (the `items.json:` config key):
  ld+json          every JSON-LD block; @graph arrays are expanded
  next_data        <script id="__NEXT_DATA__">
  nuxt             <script id="__NUXT_DATA__"> (raw payload, no unflattening)
  var:<name>       `<name> = {...}` / `window.<name> = [...]` in any script
  <css selector>   the text of the first matching <script> element

Paths are dotted: `props.pageProps.products`, `offers.price`, `items.0.name`.
`*` fans out over a list (or a dict's values): `itemListElement.*.item`.
"""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

_MISSING = object()


def load_documents(html: str, source: str) -> list:
    """Parse the JSON documents a source names. Unparseable blocks are skipped."""
    soup = BeautifulSoup(html, "html.parser")
    if source == "ld+json":
        docs = []
        for el in soup.find_all("script", type="application/ld+json"):
            doc = _loads(el.string or el.get_text())
            if doc is _MISSING:
                continue
            for d in doc if isinstance(doc, list) else [doc]:
                if isinstance(d, dict) and isinstance(d.get("@graph"), list):
                    docs.extend(d["@graph"])
                else:
                    docs.append(d)
        return docs
    if source == "next_data":
        return _script_by_css(soup, "script#__NEXT_DATA__")
    if source == "nuxt":
        return _script_by_css(soup, "script#__NUXT_DATA__")
    if source.startswith("var:"):
        return _assigned_var(html, source[4:].strip())
    return _script_by_css(soup, source)


def _loads(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return _MISSING


def _script_by_css(soup, selector: str) -> list:
    el = soup.select_one(selector)
    if el is None:
        return []
    doc = _loads(el.string or el.get_text())
    return [] if doc is _MISSING else [doc]


def _assigned_var(html: str, name: str) -> list:
    pat = re.compile(r"(?:window\.|var\s+|let\s+|const\s+|\b)"
                     + re.escape(name) + r"\s*=\s*")
    dec = json.JSONDecoder()
    for m in pat.finditer(html):
        rest = html[m.end():].lstrip()
        if rest.startswith("JSON.parse("):
            # window.X = JSON.parse("{\"a\":1}")
            try:
                inner, _ = dec.raw_decode(rest[len("JSON.parse("):])
                return [json.loads(inner)]
            except ValueError:
                continue
        try:
            doc, _ = dec.raw_decode(rest)
            return [doc]
        except ValueError:
            continue
    return []


def get_path(obj, path: str | None) -> list:
    """All values at a dotted path. `*` fans out; missing keys yield nothing."""
    if not path:
        return [obj]
    current = [obj]
    for part in str(path).split("."):
        nxt = []
        for node in current:
            if part == "*":
                if isinstance(node, list):
                    nxt.extend(node)
                elif isinstance(node, dict):
                    nxt.extend(node.values())
            elif isinstance(node, dict):
                if part in node:
                    nxt.append(node[part])
            elif isinstance(node, list) and part.lstrip("-").isdigit():
                i = int(part)
                if -len(node) <= i < len(node):
                    nxt.append(node[i])
        current = nxt
    return current


def _matches(obj, where: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    for key, want in where.items():
        got = get_path(obj, key)
        if not got:
            return False
        vals = got[0] if isinstance(got[0], list) else [got[0]]
        wants = want if isinstance(want, list) else [want]
        if not any(str(v) == str(w) for v in vals for w in wants):
            return False
    return True


def items_from_json(html: str, items_cfg: dict) -> list:
    """The item objects for a `items: {json: ..., path: ..., where: ...}` block."""
    out = []
    for doc in load_documents(html, items_cfg["json"]):
        for found in get_path(doc, items_cfg.get("path")):
            out.extend(found if isinstance(found, list) else [found])
    where = items_cfg.get("where")
    if where:
        out = [o for o in out if _matches(o, where)]
    return out


def discover(html: str) -> list[dict]:
    """Summarise embedded JSON on a page, for `probe` and `init`."""
    found = []
    ld = load_documents(html, "ld+json")
    if ld:
        types: dict[str, int] = {}
        for d in ld:
            t = d.get("@type", "?") if isinstance(d, dict) else type(d).__name__
            for tt in t if isinstance(t, list) else [t]:
                types[str(tt)] = types.get(str(tt), 0) + 1
        found.append({"source": "ld+json", "count": len(ld), "types": types})
    for src in ("next_data", "nuxt"):
        docs = load_documents(html, src)
        if docs:
            found.append({"source": src, "count": 1,
                          "lists": _biggest_lists(docs[0])})
    for name in set(re.findall(r"window\.(__[A-Z0-9_]+__)\s*=", html)):
        docs = load_documents(html, f"var:{name}")
        if docs:
            found.append({"source": f"var:{name}", "count": 1,
                          "lists": _biggest_lists(docs[0])})
    return found


def _biggest_lists(doc, limit: int = 3) -> list[tuple[str, int]]:
    """Paths to the longest lists of objects: the likely item arrays."""
    hits = []

    def walk(node, path, depth):
        if depth > 12:
            return
        if isinstance(node, list):
            if len(node) >= 2 and all(isinstance(x, dict) for x in node[:5]):
                hits.append((path, len(node)))
            for i, x in enumerate(node[:3]):
                walk(x, f"{path}.{i}" if path else str(i), depth + 1)
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else str(k), depth + 1)
    walk(doc, "", 0)
    hits.sort(key=lambda h: -h[1])
    return hits[:limit]
