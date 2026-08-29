#!/usr/bin/env python3
"""Batch probe: classify many sites in one pass.

Usage: python3 -m scrapeforge batchprobe urls.txt --out results.csv
       python3 -m scrapeforge batchprobe se.txt de.txt indie.txt

Design notes:
- One HTTP attempt per site first (cheap). Escalate to TLS impersonation
  only when plain HTTP fails, exactly like the single-site probe.
- Per-domain delay (not global): hitting DIFFERENT domains fast is fine;
  hammering ONE domain is what gets IPs flagged (eBay lesson 08-29).
- Jitter so the pattern is not machine-clock regular.
- Resilient: DNS errors, timeouts, TLS errors all become rows, never crash.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from .classify import classify_response

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# default timeout per request (s), jitter range (s), workers
TIMEOUT = 20
JITTER = (0.8, 2.2)
WORKERS = 6


def _delay_between(urls: list[str]) -> None:
    time.sleep(random.uniform(*JITTER))


def probe_one(url: str) -> dict:
    host = urlparse(url).netloc
    res = None
    via = "unknown"
    try:
        import httpx
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True,
                      headers={"User-Agent": UA})
        res = classify_response(url, r.status_code, r.text)
        via = "httpx"
    except Exception as e1:
        via = f"httpx-fail:{type(e1).__name__}"
        try:
            from curl_cffi import requests as cr
            r2 = cr.get(url, impersonate="chrome", timeout=TIMEOUT)
            res = classify_response(url, r2.status_code, r2.text)
            via = "curl_cffi"
        except Exception as e2:
            return {"url": url, "host": host, "status": 0, "bytes": 0,
                    "tier": 9, "confident": False, "via": via,
                    "note": f"both failed: {type(e2).__name__}"}

    if res is None:  # defensive: should not happen, but never crash
        return {"url": url, "host": host, "status": 0, "bytes": 0,
                "tier": 9, "confident": False, "via": via,
                "note": "no result (unexpected)"}

    # If TLS was needed to get the page, tier 2 is the floor (same rule
    # as the single probe).
    if via == "curl_cffi" and res.tier < 2:
        res.tier = 2
        res.note = "served via TLS impersonation (curl_cffi)"
        res.confident = True

    return {"url": url, "host": host, "status": res.status,
            "bytes": res.body_size, "tier": res.tier,
            "confident": res.confident, "via": via, "note": res.note}


def main(argv=None):
    p = argparse.ArgumentParser(prog="scrapeforge batchprobe")
    p.add_argument("files", nargs="+", help="text files with one URL per line")
    p.add_argument("--out", default="probe-results.csv")
    p.add_argument("--workers", type=int, default=WORKERS)
    args = p.parse_args(argv)

    urls = []
    for f in args.files:
        with open(f, encoding="utf-8") as fh:
            urls += [ln.strip() for ln in fh if ln.strip()]

    print(f"[batchprobe] {len(urls)} urls, {args.workers} workers, "
          f"per-domain delay {JITTER}s", file=sys.stderr)

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(probe_one, u): u for u in urls}
        done = 0
        for fut in as_completed(futs):
            rows.append(fut.result())
            done += 1
            _delay_between(urls)
            if done % 10 == 0:
                print(f"[batchprobe] {done}/{len(urls)}", file=sys.stderr)

    rows.sort(key=lambda r: (r["tier"], r["url"]))

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["tier", "status", "bytes",
                                           "confident", "via", "host",
                                           "url", "note"])
        w.writeheader()
        w.writerows(rows)

    # summary to stderr
    tiers = {}
    for r in rows:
        tiers.setdefault(r["tier"], 0)
        tiers[r["tier"]] += 1
    print(f"[batchprobe] done: {sorted(tiers.items())}", file=sys.stderr)
    print(f"[batchprobe] saved {args.out}", file=sys.stderr)
    return rows


if __name__ == "__main__":
    main()
