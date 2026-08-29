#!/usr/bin/env python3
"""Pagination-advance probe: certify that pagination WORKS on a site.

For each URL: fetch page 1, find a next-page link, fetch page 2, verify:
  (a) next-link exists
  (b) content changed between pages
  (c) page 2 is not a block page

Outputs a matrix CSV: PAGINATED_OK / NO_NEXT_LINK / BLOCKED_AT_DEPTH /
NO_CONTENT_CHANGE / ERROR.

Usage: python3 -m scrapeforge pageprobe urls.txt --out matrix.csv [--tiers tiers.csv]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

from .classify import classify_response

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 20
JITTER = (1.5, 3.5)
WORKERS = 5

NEXT_PATTERNS = [
    # (selector-ish regex on the anchor tag, attr to read)
    (r'rel=["\']next["\']', "href"),
    (r'class=["\'][^"\']*\bnext\b[^"\']*["\']', "href"),
    (r'aria-label=["\'][^"\']*next[^"\']*["\']', "href"),
    (r'class=["\'][^"\']*pagination__next[^"\']*["\']', "href"),
    (r'class=["\'][^"\']*morelink[^"\']*["\']', "href"),
]

# page-2 markers: things that should NOT appear on a real page 2
BLOCK_MARKERS = ["captcha", "recaptcha", "verify you are human", "access denied",
                 "pardon our interruption", "just a moment", "unusual traffic"]


def _fetch(url: str, tier: int):
    if tier <= 1:
        import httpx
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True,
                      headers={"User-Agent": UA})
        return r.status_code, r.text
    from curl_cffi import requests as cr
    r = cr.get(url, impersonate="chrome", timeout=TIMEOUT)
    return r.status_code, r.text


def _find_next(html: str, base_url: str):
    """Find the next-page URL. Returns href or None."""
    # 1) rel=next link tag
    m = re.search(r'<link[^>]*rel=["\']next["\'][^>]*>', html, re.I)
    if m:
        h = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
        if h:
            return urljoin(base_url, h.group(1))
    # 2) anchor patterns
    for pat, attr in NEXT_PATTERNS:
        for am in re.finditer(r'<a[^>]*>', html):
            tag = am.group(0)
            if re.search(pat, tag, re.I):
                h = re.search(r'href=["\']([^"\']+)["\']', tag)
                if h:
                    href = h.group(1)
                    if href and not href.startswith("javascript:"):
                        return urljoin(base_url, href)
    # 3) query-param heuristic: ?page=2 / ?p=2 / &page=2
    parsed = urlparse(base_url)
    for param in ("page", "p", "pg", "offset", "start"):
        m = re.search(rf"[?&]{param}=\d+", base_url)
        if m:
            return base_url
    return None


def _content_hash(html: str) -> str:
    # hash the visible text only, to ignore boilerplate churn
    text = re.sub(r'<script.*?</script>|<style.*?</style>', " ", html,
                  flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return hashlib.md5(text.encode()).hexdigest()[:12]


def probe_pagination(url: str, tier: int) -> dict:
    host = urlparse(url).netloc
    try:
        s1, html1 = _fetch(url, tier)
        if s1 >= 400:
            return {"url": url, "host": host, "tier": tier, "status": s1,
                    "verdict": "ERROR", "note": f"page1 http {s1}"}
        low1 = html1.lower()
        if any(m in low1 for m in BLOCK_MARKERS) and len(html1) < 20000:
            return {"url": url, "host": host, "tier": tier, "status": s1,
                    "verdict": "BLOCKED_AT_DEPTH", "note": "page1 blocked"}

        next_url = _find_next(html1, url)
        if next_url is None:
            return {"url": url, "host": host, "tier": tier, "status": s1,
                    "verdict": "NO_NEXT_LINK", "note": "no pagination found"}
        if next_url == url:
            return {"url": url, "host": host, "tier": tier, "status": s1,
                    "verdict": "NO_NEXT_LINK", "note": "next == page1 (JS/param-less)"}

        time.sleep(random.uniform(*JITTER))
        s2, html2 = _fetch(next_url, tier)
        if s2 >= 400:
            return {"url": url, "host": host, "tier": tier, "status": s1,
                    "verdict": "BLOCKED_AT_DEPTH", "note": f"page2 http {s2}"}
        low2 = html2.lower()
        if any(m in low2 for m in BLOCK_MARKERS) and len(html2) < 20000:
            return {"url": url, "host": host, "tier": tier, "status": s1,
                    "verdict": "BLOCKED_AT_DEPTH", "note": "page2 blocked"}

        h1, h2 = _content_hash(html1), _content_hash(html2)
        if h1 == h2:
            return {"url": url, "host": host, "tier": tier, "status": s1,
                    "verdict": "NO_CONTENT_CHANGE", "note": "same content p1==p2"}
        return {"url": url, "host": host, "tier": tier, "status": s1,
                "verdict": "PAGINATED_OK", "note": f"next={next_url[:60]}"}
    except Exception as e:
        return {"url": url, "host": host, "tier": tier, "status": 0,
                "verdict": "ERROR", "note": f"{type(e).__name__}: {str(e)[:60]}"}


def main(argv=None):
    p = argparse.ArgumentParser(prog="scrapeforge pageprobe")
    p.add_argument("files", nargs="+", help="URL list files (one per line)")
    p.add_argument("--out", default="pagination-matrix.csv")
    p.add_argument("--tiers", default=None,
                   help="CSV from batchprobe to look up tiers (url,tier)")
    p.add_argument("--workers", type=int, default=WORKERS)
    args = p.parse_args(argv)

    urls = []
    for f in args.files:
        with open(f, encoding="utf-8") as fh:
            urls += [ln.strip() for ln in fh if ln.strip()]

    # tier lookup
    tier_map = {}
    if args.tiers:
        with open(args.tiers, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                tier_map[row["url"].strip().rstrip("/")] = int(row["tier"])
                tier_map[row["url"].strip()] = int(row["tier"])

    # only probe tier 1-2 (deliverable); tier 3/9 = already classified
    jobs = []
    for u in urls:
        t = tier_map.get(u.strip().rstrip("/"), tier_map.get(u.strip(), 1))
        if t in (1, 2):
            jobs.append((u, t))

    print(f"[pageprobe] {len(urls)} urls, {len(jobs)} deliverable (tier 1-2), "
          f"{args.workers} workers", file=sys.stderr)

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(probe_pagination, u, t): u for u, t in jobs}
        done = 0
        for fut in as_completed(futs):
            rows.append(fut.result())
            done += 1
            time.sleep(random.uniform(*JITTER))
            if done % 10 == 0:
                print(f"[pageprobe] {done}/{len(jobs)}", file=sys.stderr)

    rows.sort(key=lambda r: (r["verdict"], r["url"]))
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["verdict", "tier", "status",
                                           "host", "url", "note"])
        w.writeheader()
        w.writerows(rows)

    counts = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(f"[pageprobe] done: {dict(sorted(counts.items()))}", file=sys.stderr)
    print(f"[pageprobe] saved {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
