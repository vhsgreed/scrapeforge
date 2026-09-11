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
from .verify import (EXIT_EMPTY, print_report, verify_file,
                     verify_records)

EXIT_BLOCKED = 3


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
    # --fail-blocked makes the probe path usable in scripts: a walled target
    # is a loud non-zero exit, not a silent success.
    if args.fail_blocked and (res.tier >= 3 or not res.confident):
        print(f"[probe] FAIL: tier {res.tier}, not confidently reachable",
              file=sys.stderr)
        sys.exit(EXIT_BLOCKED)


def _run_batch(args):
    from .batchprobe import main as batch_main
    import sys as _sys
    _sys.argv = ["scrapeforge", *args.files, "--out", args.out,
                 "--workers", str(args.workers)]
    batch_main()


def _run_page(args):
    from .pageprobe import main as page_main
    import sys as _sys
    argv = ["scrapeforge", *args.files, "--out", args.out,
            "--workers", str(args.workers)]
    if args.tiers:
        argv += ["--tiers", args.tiers]
    _sys.argv = argv
    page_main()


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

    # Verify by data, not by exit code: assert the row count and show a
    # sample. Empty output is a loud failure, not a quiet success.
    res = verify_records(rows, min_rows=args.min_rows, sample=args.sample,
                         source=out)
    print_report(res, stream=sys.stderr)
    if not res.ok:
        sys.exit(EXIT_EMPTY)


def cmd_verify(args):
    res = verify_file(args.path, fmt=args.format,
                      min_rows=args.min_rows, sample=args.sample)
    print_report(res)
    if not res.ok:
        sys.exit(EXIT_EMPTY)


def json_dump(item):
    import json
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def main(argv=None):
    p = argparse.ArgumentParser(prog="scrapeforge")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe", help="classify a site's anti-bot tier")
    p_probe.add_argument("url")
    p_probe.add_argument("--fail-blocked", action="store_true",
                         help="exit non-zero (3) when the target is walled")
    p_probe.set_defaults(func=cmd_probe)

    p_batch = sub.add_parser("batchprobe", help="classify many sites (see batchprobe.py)")
    p_batch.add_argument("files", nargs="+")
    p_batch.add_argument("--out", default="probe-results.csv")
    p_batch.add_argument("--workers", type=int, default=6)
    p_batch.set_defaults(func=lambda a: _run_batch(a))

    p_page = sub.add_parser("pageprobe", help="pagination-advance matrix (see pageprobe.py)")
    p_page.add_argument("files", nargs="+")
    p_page.add_argument("--out", default="pagination-matrix.csv")
    p_page.add_argument("--tiers", default=None)
    p_page.add_argument("--workers", type=int, default=5)
    p_page.set_defaults(func=lambda a: _run_page(a))

    p_run = sub.add_parser("run", help="run a YAML scrape config")
    p_run.add_argument("config")
    p_run.add_argument("--out", default=None)
    p_run.add_argument("--min-rows", type=int, default=1,
                       help="fail if fewer rows are extracted (default 1)")
    p_run.add_argument("--sample", type=int, default=3,
                       help="records to print as a sample (default 3)")
    p_run.set_defaults(func=cmd_run)

    p_verify = sub.add_parser(
        "verify", help="assert a dataset file is non-empty and show a sample")
    p_verify.add_argument("path", help="CSV / JSON / JSONL dataset file")
    p_verify.add_argument("--format", choices=["csv", "json", "jsonl"],
                          default=None, help="default: infer from extension")
    p_verify.add_argument("--min-rows", type=int, default=1)
    p_verify.add_argument("--sample", type=int, default=3)
    p_verify.set_defaults(func=cmd_verify)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
