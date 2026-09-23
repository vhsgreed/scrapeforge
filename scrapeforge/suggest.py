"""Selector help: guess a config from a page, and explain selector matches.

`init` looks for the thing almost every scrape target has: a block of HTML
repeated many times (product cards, table rows, search results). It picks
the most item-like repeated block, derives a CSS selector for it, guesses
fields inside it (title, url, image, price, plus a few labelled extras),
finds a next-page link, and reports how often each field actually filled.

Guesses are a starting point, not a verdict: the coverage report says
which fields to check by hand.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

from .embedded import discover, load_documents, get_path

SKIP_TAGS = {"script", "style", "noscript", "svg", "path", "head", "meta",
             "link", "br", "hr", "option", "template", "iframe"}
CHROME_WORDS = re.compile(r"nav|menu|footer|header|breadcrumb|pagination|"
                          r"pager|cookie|banner|sidebar|social|share|modal",
                          re.I)
PRICE = re.compile(r"(?:[$€£¥₹]|\b(?:USD|EUR|GBP|SEK|NOK|DKK|kr)\b)\s?\d|"
                   r"\d[\d.,]*\s?(?:[$€£¥₹]|\b(?:USD|EUR|GBP|SEK|NOK|DKK|kr)\b)",
                   re.I)
# Utility/state classes and generated hashes make brittle selectors.
UNSTABLE = re.compile(r"^(?:css|sc|jsx|emotion|styled|tw)-|[0-9a-f]{5,}|\d{3,}|"
                      r"^(?:active|selected|hover|focus|open|show|hidden|"
                      r"visible|is-|has-|js-|col-|row$|d-|p[xytblr]?-\d|"
                      r"m[xytblr]?-\d|w-\d|h-\d|flex|grid|clearfix)", re.I)


def stable_classes(el: Tag) -> list[str]:
    return [c for c in el.get("class", []) if re.fullmatch(r"-?[A-Za-z_][\w-]*", c)
            and not UNSTABLE.search(c)]


def simple_selector(el: Tag) -> str:
    """tag.class1.class2 using only stable classes (or #id when it is clean)."""
    cls = stable_classes(el)
    return el.name + "".join(f".{c}" for c in cls[:3])


def _is_chrome(el: Tag) -> bool:
    for node in [el, *el.parents]:
        if not isinstance(node, Tag) or node.name in ("body", "html", "[document]"):
            break
        if node.name in ("nav", "header", "footer", "aside"):
            return True
        label = " ".join(node.get("class", [])) + " " + (node.get("id") or "")
        if CHROME_WORDS.search(label):
            return True
    return False


@dataclass
class Group:
    selector: str
    elements: list[Tag]
    score: float
    why: list[str] = field(default_factory=list)


def find_item_groups(soup: BeautifulSoup, limit: int = 3) -> list[Group]:
    """Repeated sibling blocks, most item-like first."""
    buckets: dict[tuple, list[Tag]] = defaultdict(list)
    for el in soup.find_all(True):
        if el.name in SKIP_TAGS or el.parent is None:
            continue
        buckets[(id(el.parent), el.name, tuple(stable_classes(el)))].append(el)

    groups = []
    for (_, tag, _cls), els in buckets.items():
        if len(els) < 3 or tag in ("a", "span", "b", "i", "em", "strong",
                                   "td", "th", "p", "img", "option"):
            continue
        if _is_chrome(els[0]):
            continue
        texts = [len(e.get_text(" ", strip=True)) for e in els]
        med = sorted(texts)[len(texts) // 2]
        if med < 15:
            continue
        with_link = sum(1 for e in els if e.find("a", href=True)) / len(els)
        with_img = sum(1 for e in els if e.find("img")) / len(els)
        depth = sum(1 for _ in els[0].descendants if isinstance(_, Tag))
        score = (len(els) ** 0.5) * min(med, 400) ** 0.5 \
            * (1 + with_link) * (1 + 0.5 * with_img) * min(depth, 12) / 12
        els = _descend_wrappers(els)
        sel = _unique_group_selector(soup, els)
        if not sel:
            continue
        why = [f"{len(els)} repeats", f"median text {med} chars"]
        if with_link >= 0.8:
            why.append("each has a link")
        if with_img >= 0.8:
            why.append("each has an image")
        groups.append(Group(sel, els, score, why))
    groups.sort(key=lambda g: -g.score)
    # Drop groups nested inside a better group's items.
    kept: list[Group] = []
    for g in groups:
        if any(g.elements[0] in list(k.elements[0].descendants) or
               k.elements[0] in list(g.elements[0].descendants) for k in kept):
            continue
        kept.append(g)
        if len(kept) == limit:
            break
    return kept


def _descend_wrappers(els: list[Tag]) -> list[Tag]:
    """<li class="col-md-3"><article class="product">…: use the article.

    Layout wrappers carry only utility classes; the element inside with a
    real class name is the item a human would point at."""
    while not stable_classes(els[0]):
        kids = [[c for c in e.children if isinstance(c, Tag)] for e in els]
        if not all(len(k) == 1 for k in kids):
            break
        inner = [k[0] for k in kids]
        sig = (inner[0].name, tuple(stable_classes(inner[0])))
        if not sig[1] or any((i.name, tuple(stable_classes(i))) != sig for i in inner):
            break
        els = inner
    return els


def _unique_group_selector(soup, els: list[Tag]) -> str | None:
    """A selector that matches this group and (almost) nothing else."""
    want = set(map(id, els))
    base = simple_selector(els[0])
    parent = els[0].parent
    candidates = [base]
    if parent is not None and parent.name not in ("body", "html", "[document]"):
        pid = parent.get("id")
        if pid and re.fullmatch(r"[A-Za-z][\w-]*", pid) and not UNSTABLE.search(pid):
            candidates.append(f"#{pid} > {base}")
        candidates.append(f"{simple_selector(parent)} > {base}")
        gp = parent.parent
        if gp is not None and gp.name not in ("html", "[document]"):
            candidates.append(f"{simple_selector(gp)} > {simple_selector(parent)} > {base}")
    for sel in candidates:
        try:
            got = soup.select(sel)
        except Exception:  # noqa: BLE001 - odd class names can break soupsieve
            continue
        hit = sum(1 for g in got if id(g) in want)
        if hit == len(els) and len(got) <= len(els) * 1.2:
            return sel
    return None


def _relative_selector(item: Tag, el: Tag) -> str | None:
    """Shortest selector that picks `el` as the first match inside `item`."""
    tries = [simple_selector(el)]
    if el.name == "a":
        tries.append("a[href]")
    parent = el.parent
    if parent is not None and parent is not item:
        tries.append(f"{simple_selector(parent)} {simple_selector(el)}")
    tries.append(el.name)
    for sel in tries:
        try:
            if item.select_one(sel) is el:
                return sel
        except Exception:  # noqa: BLE001
            continue
    return None


def _coverage(items: list[Tag], sel: str) -> float:
    ok = 0
    for it in items:
        try:
            if it.select_one(sel) is not None:
                ok += 1
        except Exception:  # noqa: BLE001
            return 0.0
    return ok / len(items)


def guess_fields(items: list[Tag]) -> dict[str, dict]:
    """Title, url, image, price, and up to three labelled extras."""
    first = items[0]
    fields: dict[str, dict] = {}
    used: set[str] = set()

    def add(name, el, attr="text", **extra):
        if el is None or name in fields:
            return
        sel = _relative_selector(first, el)
        if not sel or _coverage(items, sel) < 0.5:
            return
        spec = {"selector": sel, "attr": attr, **extra}
        fields[name] = spec
        used.add(sel)

    heading = first.find(re.compile(r"^h[1-6]$"))
    links = [a for a in first.find_all("a", href=True)
             if not a["href"].startswith(("#", "javascript:"))]
    titled = next((a for a in links if a.get("title")), None)
    longest = max(links, key=lambda a: len(a.get_text(strip=True)), default=None)
    named = first.find(class_=re.compile(r"title|name|heading", re.I))
    if named is not None:
        # <td class="title"><span>1.</span><a>Story</a></td>: the link is the title.
        inner = max(named.find_all("a"), default=None,
                    key=lambda a: len(a.get_text(strip=True)))
        if inner is not None and len(inner.get_text(strip=True)) >= \
                0.5 * len(named.get_text(strip=True)):
            named = inner

    shown = titled.get_text(strip=True) if titled is not None else ""
    if titled is not None and titled["title"].strip() != shown and (
            shown.endswith(("...", "…")) or len(titled["title"]) > len(shown)):
        add("title", titled, "title")   # truncated text, full title attribute
    for cand in (heading, named, longest):
        if cand is not None and cand.get_text(strip=True):
            add("title", cand)
    link = None
    if heading is not None:
        link = heading.find("a", href=True)
    link = link or titled or longest
    add("url", link, "href")

    img = first.find("img")
    if img is not None:
        src = img.get("src") or ""
        attr = "src"
        for lazy in ("data-src", "data-original", "data-lazy-src", "srcset"):
            if (not src or src.startswith("data:")) and img.get(lazy):
                attr = lazy
                break
        add("image", img, attr)

    for el in first.find_all(True):
        own = el.get_text(" ", strip=True)
        if PRICE.search(own) and len(own) < 40 and not el.find(
                lambda t: isinstance(t, Tag) and PRICE.search(t.get_text(" ", strip=True) or "")):
            add("price", el, "text", type="float")
            break

    extras = 0
    for el in first.find_all(True):
        if extras >= 3:
            break
        if el.name in ("button", "input", "select", "textarea", "label", "form") \
                or el.find_parent(("button", "form")):
            continue
        cls = stable_classes(el)
        text = el.get_text(" ", strip=True)
        if not cls or not text or len(text) > 200 or any(
                isinstance(c, Tag) and c.get_text(strip=True) for c in el.children):
            continue
        name = re.sub(r"[^a-z0-9]+", "_",
                      cls[-1].split("__")[-1].lower()).strip("_")
        if not name or name in fields or any(
                w in name for w in ("title", "name", "price", "link", "img", "image")):
            continue
        sel = _relative_selector(first, el)
        if not sel or sel in used or _coverage(items, sel) < 0.6:
            continue
        fields[name] = {"selector": sel, "attr": "text"}
        used.add(sel)
        extras += 1
    return fields


NEXT_CANDIDATES = [
    ("a[rel~=next]", None),
    ("li.next a", None),
    ("a.next", None),
    ("a.pagination__next", None),
    ("a[aria-label*=next i]", None),
    ("a[class*=next]", None),
    ("a", "Next"),
    ("a", "More"),
    ("a", "›"),
    ("a", "»"),
]


def guess_pagination(soup: BeautifulSoup) -> dict | None:
    for sel, text in NEXT_CANDIDATES:
        try:
            els = soup.select(sel)
        except Exception:  # noqa: BLE001
            continue
        for el in els:
            href = el.get("href")
            if not href or href.startswith(("#", "javascript:")):
                continue
            if text is None:
                return {"selector": sel}
            if el.get_text(" ", strip=True).lower() in (text.lower(), text.lower() + " »",
                                                        text.lower() + " ›", text.lower() + " >"):
                return {"selector": sel, "next_text": text}
    return None


def guess_json_config(html: str) -> tuple[dict, dict] | None:
    """items/fields for the biggest embedded JSON list, if there is one."""
    for found in discover(html):
        src = found["source"]
        if src == "ld+json":
            types = found["types"]
            best = max(types, key=types.get)
            objs = [o for o in load_documents(html, src)
                    if isinstance(o, dict) and o.get("@type") == best]
            if len(objs) < 2 and best != "ItemList":
                continue
            items = {"json": src, "where": {"@type": best}}
            if best == "ItemList":
                items["path"] = "itemListElement.*.item"
                objs = [o for d in objs for o in get_path(d, "itemListElement.*.item")]
            return items, _json_fields(objs)
        if found.get("lists"):
            path, _ = found["lists"][0]
            docs = load_documents(html, src)
            objs = [o for d in docs for o in get_path(d, path)]
            objs = [x for o in objs for x in (o if isinstance(o, list) else [o])]
            return {"json": src, "path": path}, _json_fields(objs)
    return None


def _json_fields(objs: list) -> dict:
    counts: Counter = Counter()
    kinds: dict[str, set] = defaultdict(set)

    def note(path, v):
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            return
        counts[path] += 1
        kinds[path].add(type(v).__name__)

    for o in objs[:20]:
        if not isinstance(o, dict):
            continue
        for k, v in o.items():
            if k.startswith("@"):
                continue
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if not kk.startswith("@"):
                        note(f"{k}.{kk}", vv)
            else:
                note(k, v)
    fields = {}
    for path, _ in counts.most_common(8):
        name = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_")
        spec = {"path": path}
        if kinds[path] == {"int"}:
            spec["type"] = "int"
        elif kinds[path] <= {"int", "float"}:
            spec["type"] = "float"
        fields[name] = spec
    return fields


@dataclass
class Suggestion:
    items: dict
    fields: dict
    paginate: dict | None
    alternatives: list[Group]
    item_count: int
    why: list[str]
    embedded: list[dict]


def suggest(html: str, prefer_json: bool = False) -> Suggestion | None:
    soup = BeautifulSoup(html, "html.parser")
    embedded = discover(html)
    groups = find_item_groups(soup)
    json_cfg = guess_json_config(html) if (prefer_json or not groups) else None
    if json_cfg:
        items, fields = json_cfg
        from .embedded import items_from_json
        n = len(items_from_json(html, items))
        return Suggestion(items, fields, guess_pagination(soup), groups, n,
                          [f"embedded JSON ({items['json']})"], embedded)
    if not groups:
        return None
    g = groups[0]
    return Suggestion({"selector": g.selector}, guess_fields(g.elements),
                      guess_pagination(soup), groups[1:], len(g.elements),
                      g.why, embedded)


def explain_matches(html: str, selector: str, attr: str = "text",
                    within: str | None = None, limit: int = 5) -> dict:
    """What a selector matches, for `scrapeforge try`."""
    soup = BeautifulSoup(html, "html.parser")
    out = {"selector": selector, "within": within, "warnings": []}
    if re.search(r":nth-(?:child|of-type)\(\d+\)", selector) or selector.count(">") >= 4:
        out["warnings"].append(
            "this looks like a DevTools 'Copy selector' path: it pins one "
            "element by position and breaks when the page shifts. Prefer "
            "a class that every item shares (see docs/selectors.md).")
    from .extract import _node_value
    if within:
        items = soup.select(within)
        out["items"] = len(items)
        rows, missing = [], 0
        for it in items:
            el = it.select_one(selector)
            if el is None:
                missing += 1
            rows.append(None if el is None else _node_value(el, attr))
        out["matches"] = len(items) - missing
        out["missing"] = missing
        out["values"] = rows[:limit]
    else:
        els = soup.select(selector)
        out["matches"] = len(els)
        out["values"] = [_node_value(e, attr) for e in els[:limit]]
        out["tags"] = Counter(simple_selector(e) for e in els).most_common(3)
    if out["matches"] == 0:
        out["hints"] = _zero_match_hints(soup, html, selector)
    return out


def _zero_match_hints(soup, html: str, selector: str) -> list[str]:
    hints = []
    words = set(re.findall(r"[.#]([\w-]+)", selector))
    near = Counter()
    for el in soup.find_all(True):
        for c in el.get("class", []):
            if any(w.lower() in c.lower() or c.lower() in w.lower() for w in words):
                near[f"{el.name}.{c}"] += 1
    if near:
        hints.append("similar classes on this page: " + ", ".join(
            f"{s} ({n})" for s, n in near.most_common(5)))
    body = soup.body or soup
    body_text = len(" ".join(t for t in body.find_all(string=True)
                             if t.parent.name not in ("script", "style", "noscript")).strip())
    if body_text < 200:
        hints.append(f"the page body has only {body_text} characters of text: "
                     "the content is probably rendered by JavaScript.")
    if discover(html):
        hints.append("the page carries embedded JSON: run `scrapeforge probe` "
                     "or `scrapeforge init --json` to read it without a browser.")
    if not hints:
        hints.append("0 matches in the HTML the server sent. The browser's "
                     "DevTools show the page after JavaScript ran, which can "
                     "differ: `scrapeforge fetch <url>` saves what scrapeforge sees.")
    return hints
