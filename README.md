# scrapeforge — config-driven scraping with probe-first honesty

Tiered Python scraper that probes the target first, picks the right fetch
tier automatically, extracts with CSS selectors, and outputs CSV/JSON.
New sites are a YAML file, not code.

## Tiers (auto-selected by probe)

| Tier | Tool | Handles | Example |
|---|---|---|---|
| 1 | `httpx` (plain) | Static HTML pages | Blogs, directories |
| 2 | `curl_cffi` (TLS impersonation) | JS-heavy + bot-protected pages | AliExpress (verified 08-29) |
| 3 | `CloakBrowser` / Playwright stealth | Amazon-class anti-bot | Amazon (heavy, fragile, ToS risk) |

The probe (`classify.py`) fetches the target, scores the response, and
picks the tier. Tier 3 is never promised blindly; it is an escalation path
with honest caveats. If a site is out of reach, scrapeforge says so before
you commit.

## Install

```bash
pip install curl_cffi httpx pyyaml beautifulsoup4
# optional, tier 3 only:
pip install scrapling   # or cloakbrowser / playwright
```

## Usage

```bash
# classify a single site (tier 1/2/3, confident, notes)
python -m scrapeforge probe https://www.aliexpress.com/

# batch-classify many sites -> results CSV
python -m scrapeforge batchprobe urls.txt --out results.csv

# certify pagination works on a target (next-link -> page 2 -> content change)
python -m scrapeforge pageprobe urls.txt --tiers results.csv --out matrix.csv

# run a scrape config
python -m scrapeforge run examples/hn-front.yaml --out data.csv
```

## Config format

```yaml
name: hn-front
url: https://news.ycombinator.com/news
tier: auto            # auto | 1 | 2 | 3
max_pages: 10
rate_limit_sec: 1.0
items:
  selector: "tr.athing"
fields:
  title: { selector: "span.titleline a", attr: text }
  url:   { selector: "span.titleline a", attr: href }
  score: { selector: "span.score", attr: text, scope: global }
output: csv           # csv | json | jsonl
```

## Pagination

Two layers:

**1. Config-driven pagination** (`paginate.py`) — the runner follows
next-page links from the YAML config. The `paginate` block is optional; if
absent, only the starting URL is fetched:

```yaml
paginate:
  selector: "a.morelink"    # CSS selector for the next-page link
  attribute: href           # attribute to read (default href)
  next_text: "More"         # optional: only follow links whose text matches
```

The loop fetches each page, extracts items, and follows the next link until
`max_pages` is reached or no next link exists. `rate_limit_sec` inserts a
pause between page fetches (recommended: keep it >= 1.0).

**2. Pagination certification** (`pageprobe.py`) — verifies that a target
actually paginates *before* you promise anything. For each URL it:

1. fetches page 1 and looks for a next-page link (`rel=next`, common
   `next`/`pagination__next`/`morelink` classes, or a page/offset query
   param)
2. fetches the next URL
3. verifies the content actually changed (hashes visible text)
4. flags block pages (captcha / "just a moment" / "access denied")

Verdicts: `PAGINATED_OK` / `NO_NEXT_LINK` / `BLOCKED_AT_DEPTH` /
`NO_CONTENT_CHANGE` / `ERROR`. Run it on the exact URLs a job needs (e.g.
category pages, not homepages: homepages usually have no next link).

## The 150-site dataset

`results-stress-test-2026-08-29.csv` contains reachability verdicts for 150
live e-commerce and indie-web sites (probed 2026-08-29): tier per site,
response size, and notes. 103 deliverable, 37 blocked, 10 unreachable.
`pagination-matrix-homepages-2026-08-29.csv` is the pagination-advance
matrix from the same set.

Reachability is IP- and time-dependent. Probe per job; never assume a
verdict carries over to another network or day.

## Legal note

Public data only. Respect robots.txt and rate limits. No login-gated
content, no credential abuse. If a site forbids scraping, scrapeforge flags
it and you decide with the site's terms in mind.

## Repo map

- `scrapeforge/classify.py` — probe + tier selection
- `scrapeforge/batchprobe.py` — concurrent multi-site classification
- `scrapeforge/pageprobe.py` — pagination certification
- `scrapeforge/fetch.py` — tier 1/2/3 fetchers (one import each)
- `scrapeforge/extract.py` — CSS selector extraction (item/global scope)
- `scrapeforge/paginate.py` — config-driven pagination loop
- `scrapeforge/output.py` — CSV/JSON writers
- `scrapeforge/cli.py` — probe/batchprobe/pageprobe/run commands
- `examples/hn-front.yaml` — working example (tier 1, paginated)
- `examples/4chan-g.yaml` — tier 2 example (verified live 08-29)
- `examples/aliexpress.yaml` — tier 2 example (verified live 08-29)
