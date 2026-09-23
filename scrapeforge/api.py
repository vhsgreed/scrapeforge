"""Python API: the same pipeline `scrapeforge run` uses, callable from code.

    from scrapeforge import scrape
    result = scrape("examples/hn-front.yaml")
    for row in result.rows:
        ...

`config` is a path to a YAML file or an already-loaded dict with the same
keys. Nothing is written to disk; use `scrapeforge.output.write` for that.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Callable

import yaml

from .extract import extract_page
from .fetch import fetch as _fetch
from .paginate import paginate

Fetcher = Callable[[str], "tuple[int, str]"]


@dataclass
class ScrapeResult:
    rows: list[dict]
    pages: int
    tier: int
    config: dict = field(repr=False, default_factory=dict)


def load_config(config: str | dict) -> dict:
    if isinstance(config, dict):
        return config
    with open(config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"{config}: config must be a YAML mapping")
    return cfg


def resolve_tier(cfg: dict, log=None) -> int:
    tier = cfg.get("tier", "auto")
    if tier != "auto":
        return int(tier)
    if str(cfg["url"]).startswith("file://"):
        return 1
    from .classify import probe
    res = probe(cfg["url"])
    if log:
        print(f"[probe] {cfg['url']} -> tier {res.tier} ({res.note})", file=log)
    return res.tier


def scrape(config: str | dict, *, tier: int | None = None,
           fetcher: Fetcher | None = None, log=sys.stderr) -> ScrapeResult:
    """Fetch every page the config paginates over and extract its items.

    tier: override the config's tier (skips the probe).
    fetcher: callable url -> (status, html); replaces the tiered fetcher,
             which is how tests and custom transports plug in.
    log: stream for progress lines, or None for silence.
    """
    cfg = load_config(config)
    if tier is None:
        tier = 1 if fetcher else resolve_tier(cfg, log)
    if fetcher is None:
        def fetcher(u):
            return _fetch(u, tier, timeout=cfg.get("timeout", 30),
                          proxy=cfg.get("proxy"), cookies=cfg.get("cookies"))

    rows: list[dict] = []
    seen: set[str] = set()

    def on_page(html):
        for item in extract_page(html, cfg):
            key = json.dumps(item, ensure_ascii=False, sort_keys=True,
                             default=str)
            if key not in seen:
                seen.add(key)
                rows.append(item)

    pages = paginate(fetcher, cfg["url"], cfg, on_page)
    if log:
        print(f"[done] {pages} pages, {len(rows)} unique items", file=log)
    return ScrapeResult(rows, pages, tier, cfg)
