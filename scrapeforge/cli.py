"""CLI: probe, batchprobe, pageprobe, run, verify."""
from __future__ import annotations

import argparse
import sys

import yaml

from . import batchprobe, pageprobe
from .api import scrape
from .classify import probe
from .output import write
from .since import diff_rows
from .verify import (EXIT_EMPTY, EXIT_ERROR, print_report, read_records,
                     verify_file, verify_records)

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
    for e in res.embedded:
        detail = e.get("types") or ", ".join(
            f"{path} ({n})" for path, n in e.get("lists", []))
        print(f"json:     {e['source']}: {detail or 'present'}")
    if res.embedded:
        print("          -> items: {json: <source>, path: ...} reads these "
              "without a browser (see docs/selectors.md)")
    # --fail-blocked makes the probe path usable in scripts: a walled target
    # is a loud non-zero exit, not a silent success.
    if args.fail_blocked and (res.tier >= 3 or not res.confident):
        print(f"[probe] FAIL: tier {res.tier}, not confidently reachable",
              file=sys.stderr)
        sys.exit(EXIT_BLOCKED)


def cmd_run(args):
    try:
        result = scrape(args.config, log=sys.stderr)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as e:
        print(f"[run] config error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)
    cfg, rows = result.config, result.rows

    # Verify by data, not by exit code: assert the row count on everything
    # scraped (before --since filtering, so a quiet day with no new rows is
    # not a failure but a broken selector still is).
    res = verify_records(rows, min_rows=args.min_rows, sample=args.sample,
                         source=args.out)

    out_rows = rows
    if args.since:
        try:
            previous = read_records(args.since)
        except FileNotFoundError:
            previous = []
            print(f"[since] {args.since} not found: every row is new",
                  file=sys.stderr)
        out_rows, counts = diff_rows(rows, previous, args.key)
        print(f"[since] {counts['new']} new, {counts['changed']} changed, "
              f"{counts['unchanged']} unchanged vs {args.since}",
              file=sys.stderr)

    write(out_rows, args.out, cfg.get("output", "csv"))
    if args.snapshot:
        write(rows, args.snapshot, _format_for(args.snapshot, cfg))
        print(f"[snapshot] {args.snapshot} ({len(rows)} rows)", file=sys.stderr)
    saved = f"[saved] {args.out} ({len(out_rows)} rows)"
    print(saved, file=sys.stderr if args.out == "-" else sys.stdout)

    print_report(res, stream=sys.stderr)
    if not res.ok:
        sys.exit(EXIT_EMPTY)


def _format_for(path: str, cfg: dict) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext if ext in ("csv", "json", "jsonl") else cfg.get("output", "csv")


def cmd_verify(args):
    res = verify_file(args.path, fmt=args.format,
                      min_rows=args.min_rows, sample=args.sample)
    print_report(res)
    if not res.ok:
        sys.exit(EXIT_EMPTY)


def main(argv=None):
    p = argparse.ArgumentParser(prog="scrapeforge")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe", help="classify a site's anti-bot tier")
    p_probe.add_argument("url")
    p_probe.add_argument("--fail-blocked", action="store_true",
                         help="exit non-zero (3) when the target is walled")
    p_probe.set_defaults(func=cmd_probe)

    p_batch = sub.add_parser("batchprobe", help="classify many sites -> CSV")
    batchprobe.add_arguments(p_batch)
    p_batch.set_defaults(func=batchprobe.run)

    p_page = sub.add_parser("pageprobe", help="certify pagination advances -> CSV")
    pageprobe.add_arguments(p_page)
    p_page.set_defaults(func=pageprobe.run)

    p_run = sub.add_parser("run", help="run a YAML scrape config")
    p_run.add_argument("config")
    p_run.add_argument("--out", default="out.csv",
                       help="dataset path, or - for stdout (default out.csv)")
    p_run.add_argument("--min-rows", type=int, default=1,
                       help="fail if fewer rows are extracted (default 1)")
    p_run.add_argument("--sample", type=int, default=3,
                       help="records to print as a sample (default 3)")
    p_run.add_argument("--since", metavar="PREVIOUS",
                       help="only output rows new or changed vs this earlier "
                            "dataset (adds a _change column)")
    p_run.add_argument("--key", action="append", metavar="FIELD",
                       help="field(s) identifying a row for --since "
                            "(repeatable; default: the whole row)")
    p_run.add_argument("--snapshot", metavar="PATH",
                       help="also write every scraped row here; pass the "
                            "same path as --since to keep a rolling state file")
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
