"""CLI: probe and run."""
from __future__ import annotations

import argparse
import sys

import yaml

from .classify import probe
from .extract import extract_items
from .fetch import fetch
from .output import write
from .paginate import paginate


def cmd_probe(args):
    res = probe(args.url)
    print(f"url:      {res.url}")
    print(f"status:   {res.status}")
    print(f"body:     {res.body_size} bytes")
    print(f"tier:     {res.tier}")
    print(f"confident:{res.confident}")
    print(f"markers:  {res.markers}")
    if res.note:
        print(f"note:     {res.note}")


def _run_batch(args):
    from .batchprobe import main as batch_main
    import sys as _sys
    _sys.argv = ["scrapeforge", *args.files, "--out", args.out,
                 "--workers", str(args.workers)]
    batch_main()


def cmd_run(args):
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    tier = cfg.get("tier", "auto")
    if tier == "auto":
        res = probe(cfg["url"])
        tier = res.tier
        print(f"[probe] {cfg['url']} -> tier {tier} "
              f"({res.note})", file=sys.stderr)

    rows: list[dict] = []
    dedup = set()

    def on_page(html):
        for item in extract_items(html, cfg["items"]["selector"],
                                  cfg["fields"]):
            key = json_dump(item)
            if key in dedup:
                continue
            dedup.add(key)
            rows.append(item)

    pages = paginate(
        lambda u: fetch(u, tier, timeout=cfg.get("timeout", 30),
                        proxy=cfg.get("proxy"),
                        cookies=cfg.get("cookies")),
        cfg["url"], cfg, on_page,
    )
    print(f"[done] {pages} pages, {len(rows)} unique items", file=sys.stderr)

    out = args.out or "out.csv"
    write(rows, out, cfg.get("output", "csv"))
    print(f"[saved] {out} ({len(rows)} rows)")


def json_dump(item):
    import json
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def main(argv=None):
    p = argparse.ArgumentParser(prog="scrapeforge")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe", help="classify a site's anti-bot tier")
    p_probe.add_argument("url")
    p_probe.set_defaults(func=cmd_probe)

    p_batch = sub.add_parser("batchprobe", help="classify many sites (see batchprobe.py)")
    p_batch.add_argument("files", nargs="+")
    p_batch.add_argument("--out", default="probe-results.csv")
    p_batch.add_argument("--workers", type=int, default=6)
    p_batch.set_defaults(func=lambda a: _run_batch(a))

    p_run = sub.add_parser("run", help="run a YAML scrape config")
    p_run.add_argument("config")
    p_run.add_argument("--out", default=None)
    p_run.set_defaults(func=cmd_run)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
