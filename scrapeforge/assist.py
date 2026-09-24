"""Commands that help write a config: fetch, try, init."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse

from .extract import extract_page
from .fetch import fetch, to_url
from .suggest import explain_matches, suggest

EXIT_NOTHING = 2


def load_page(target: str, tier: str = "auto", log=sys.stderr) -> tuple[str, str, int]:
    """(url, html, tier) for a URL or a saved file. Exits 1 on fetch failure."""
    url = to_url(target)
    if url.startswith("file://"):
        status, html = fetch(url, 1)
        if status != 200:
            print(f"[fetch] {target}: file not found", file=log)
            sys.exit(1)
        return url, html, 1
    if tier == "auto":
        from .classify import probe
        res = probe(url)
        t = res.tier
        print(f"[probe] {url} -> tier {t} ({res.note})", file=log)
        if t >= 3:
            print("[probe] walled: tiers 1-2 get a challenge page. Results "
                  "below come from that page, not the real one.", file=log)
    else:
        t = int(tier)
    try:
        status, html = fetch(url, t)
    except Exception as e:  # noqa: BLE001 - network errors end the command cleanly
        print(f"[fetch] {url}: {type(e).__name__}: {e}", file=log)
        sys.exit(1)
    if status >= 400:
        print(f"[fetch] {url}: HTTP {status}", file=log)
    return url, html, t


# ---- fetch -----------------------------------------------------------------

def add_fetch_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("url")
    p.add_argument("--out", default="page.html",
                   help="where to save the HTML (default page.html)")
    p.add_argument("--tier", default="auto", choices=["auto", "1", "2", "3"])


def run_fetch(args) -> None:
    url, html, _ = load_page(args.url, args.tier)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[saved] {args.out} ({len(html)} chars). Iterate offline with:\n"
          f"  scrapeforge try {args.out} \"<selector>\"\n"
          f"  scrapeforge init {args.out}")


# ---- try -------------------------------------------------------------------

def add_try_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("target", help="URL or saved HTML file")
    p.add_argument("selector", help="CSS selector to test")
    p.add_argument("--in", dest="within", metavar="ITEMS",
                   help="item selector: test SELECTOR inside each item, the "
                        "way a field is resolved")
    p.add_argument("--attr", default="text",
                   help="text (default), html, or an attribute such as href")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--tier", default="auto", choices=["auto", "1", "2", "3"])


def run_try(args) -> None:
    _, html, _ = load_page(args.target, args.tier)
    try:
        res = explain_matches(html, args.selector, args.attr, args.within,
                              args.limit)
    except Exception as e:  # noqa: BLE001 - soupsieve raises on bad syntax
        print(f"[try] invalid selector: {e}", file=sys.stderr)
        sys.exit(1)
    if args.within:
        print(f"{res['items']} items match {args.within!r}; "
              f"{args.selector!r} found in {res['matches']}, "
              f"missing in {res['missing']}")
    else:
        print(f"{res['matches']} elements match {args.selector!r}")
        if res.get("tags"):
            print("  as: " + ", ".join(f"{t} ({n})" for t, n in res["tags"]))
    for i, v in enumerate(res["values"] if res["matches"] else [], 1):
        shown = "(missing)" if v is None else json.dumps(_short(v), ensure_ascii=False)
        print(f"  {i}. {shown}")
    for w in res["warnings"]:
        print(f"warning: {w}")
    for h in res.get("hints", []):
        print(f"hint: {h}")
    if res["matches"] == 0:
        sys.exit(EXIT_NOTHING)


def _short(v: str, n: int = 100) -> str:
    return v if len(v) <= n else v[:n - 1] + "…"


# ---- init ------------------------------------------------------------------

def add_init_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("target", help="URL (or saved HTML file) of a listing page")
    p.add_argument("--out", help="config path (default <name>.yaml)")
    p.add_argument("--name", help="config name (default from the URL)")
    p.add_argument("--json", action="store_true",
                   help="prefer embedded JSON over CSS selectors when present")
    p.add_argument("--force", action="store_true",
                   help="overwrite an existing config file")
    p.add_argument("--tier", default="auto", choices=["auto", "1", "2", "3"])


def _name_for(url: str) -> str:
    u = urlparse(url)
    if u.scheme == "file":
        base = os.path.splitext(os.path.basename(u.path))[0]
    else:
        host = u.hostname or "site"
        host = re.sub(r"^www\.", "", host).split(".")[0]
        path = re.sub(r"[^a-z0-9]+", "-", u.path.lower()).strip("-")
        base = f"{host}-{path}" if path else host
    return re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-")[:40] or "site"


def run_init(args) -> None:
    url, html, tier = load_page(args.target, args.tier)
    s = suggest(html, prefer_json=args.json)
    if s is None:
        print("[init] no repeated item blocks found on this page.", file=sys.stderr)
        for h in explain_matches(html, "div.__none__")["hints"]:
            print(f"hint: {h}", file=sys.stderr)
        sys.exit(EXIT_NOTHING)

    is_web = not url.startswith("file://")
    if is_web:
        for name in ("url", "image"):
            if name in s.fields and "path" not in s.fields[name]:
                s.fields[name]["absolute"] = True

    name = args.name or _name_for(url)
    out = args.out or f"{name}.yaml"
    if os.path.exists(out) and not args.force:
        print(f"[init] {out} exists; pass --force to overwrite or --out to "
              "choose another path", file=sys.stderr)
        sys.exit(1)

    cfg = {"items": s.items, "fields": s.fields}
    rows = extract_page(html, cfg, url)
    text = render_config(name, url, tier if is_web else "auto", s, rows)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"[init] wrote {out}: {len(rows)} items on this page "
          f"({', '.join(s.why)})")
    print(coverage_report(rows, s.fields))
    for row in rows[:3]:
        print("  " + json.dumps(row, ensure_ascii=False, default=str))
    if s.alternatives:
        print("other repeated blocks (in the config as comments):")
        for g in s.alternatives:
            print(f"  {g.selector}  ({', '.join(g.why)})")
    if s.embedded and "json" not in s.items:
        print("this page also carries embedded JSON; `--json` builds the "
              "config from it instead")
    first_field = next(iter(s.fields.values()), {})
    print("next:")
    if "selector" in s.items and first_field.get("selector"):
        print(f"  scrapeforge try {args.target} \"{first_field['selector']}\" "
              f"--in \"{s.items['selector']}\"   # test or tweak a field")
    print(f"  scrapeforge run {out} --out {name}.csv")


def coverage_report(rows: list[dict], fields: dict) -> str:
    lines = ["field coverage on this page:"]
    for name in fields:
        filled = sum(1 for r in rows if r.get(name) not in ("", None))
        pct = 100 * filled // len(rows) if rows else 0
        flag = "" if pct >= 90 else "   <- check this one"
        lines.append(f"  {name:<14} {filled:>3}/{len(rows)} ({pct}%){flag}")
    return "\n".join(lines)


_BARE = re.compile(r"[a-z][a-z0-9_+-]*")
_YAML_WORDS = {"y", "n", "yes", "no", "on", "off", "true", "false", "null"}


def _q(v) -> str:
    """A YAML scalar: JSON strings are valid YAML double-quoted strings.
    Plain words (text, href, float, ld+json) stay bare for readability."""
    if isinstance(v, str) and _BARE.fullmatch(v) and v not in _YAML_WORDS:
        return v
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


def _flow(d: dict) -> str:
    return "{ " + ", ".join(f"{k}: {_q(v) if not isinstance(v, dict) else _flow(v)}"
                            for k, v in d.items()) + " }"


def render_config(name: str, url: str, tier, s, rows: list[dict]) -> str:
    L = [f"# Generated by `scrapeforge init` from {url}",
         f"# {len(rows)} items found on the first page ({', '.join(s.why)}).",
         "# These are guesses: check the coverage report, then test any field with",
         "#   scrapeforge try <url> \"<selector>\" --in \"<items selector>\"",
         "# Selector guide: docs/selectors.md", "",
         f"name: {_q(name)}", f"url: {_q(url)}",
         f"tier: {tier}            # auto | 1 | 2 | 3",
         "max_pages: 5", "rate_limit_sec: 2.0"]
    if s.paginate:
        L += ["paginate:"] + [f"  {k}: {_q(v)}" for k, v in s.paginate.items()]
    else:
        L += ["# paginate:            # no next-page link found; add one if the list continues",
              "#   selector: \"a[rel~=next]\""]
    L.append("items:")
    for k, v in s.items.items():
        L.append(f"  {k}: {_flow(v) if isinstance(v, dict) else _q(v)}")
    if s.alternatives:
        L.append("  # other repeated blocks on the page:")
        for g in s.alternatives:
            L.append(f"  # selector: {_q(g.selector)}   ({', '.join(g.why)})")
    L.append("fields:")
    width = max((len(n) for n in s.fields), default=0) + 1
    for n, spec in s.fields.items():
        L.append(f"  {(n + ':').ljust(width)} {_flow(spec)}")
    L += ["output: csv           # csv | json | jsonl", ""]
    return "\n".join(L)
