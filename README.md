# scrapeforge

Probe the target first, then fetch it with the cheapest tier that actually works. CSV or JSON out, one YAML file per site.

scrapeforge is a small, dependency-light Python scraper for public web pages. It classifies a site's anti-bot defenses before it extracts anything, tells you which fetch tier the site needs, extracts records with CSS selectors, writes CSV/JSON, and then verifies the row count so an empty result fails loudly instead of reporting success.

## Quickstart (three commands)

```bash
git clone https://github.com/vhsgreed/scrapeforge && cd scrapeforge
pip install -e .
scrapeforge run examples/hn-front.yaml --out hn.csv
```

`pip install -e .` installs the `scrapeforge` command; `python3 -m scrapeforge` works the same way. `pip install -r requirements.txt` still works if you only want the dependencies. Add `.[tier3]` for the optional browser tier, `.[dev]` for pytest.

The third command probes Hacker News, picks tier 1, follows the "More" link for up to 10 pages, writes `hn.csv`, and prints a sample of the rows it extracted.

## Why not just use X

| Approach | Strength | What you still do yourself |
|---|---|---|
| plain `requests` / `httpx` | Simple, tiny | Everything. No TLS impersonation, so protected sites return a challenge page and you get zero rows. |
| `curl_cffi` alone | TLS fingerprint impersonation | Know which sites need it, select it per target, and check the body is real rather than a challenge page. |
| Scrapling | Stealth browser sessions | Heavier install, browser stack, and you still decide per site which mode to use. |
| Crawlee | Full crawling framework | Larger dependency tree and a framework to learn for what is often a single page or two. |
| scrapeforge | Probe first, pick the tier, extract, verify | Nothing beyond a YAML config. The probe decides the tier, and the run asserts it actually got rows. |

## Tiers

| Tier | Tool | Handles |
|---|---|---|
| 1 | `httpx` (plain HTTP) | Static HTML: blogs, docs, directories, most indie sites |
| 2 | `curl_cffi` (TLS impersonation) | Sites that reject the Python TLS fingerprint but serve real HTML to a browser fingerprint |
| 3 | `scrapling` / `cloakbrowser` / `playwright` | Browser-class walls. Heavy, fragile, escalation only, and never promised for a specific site |

`probe` fetches the target, scores the response, and picks the tier. Tier 3 is an escalation path, not a default. If a site is out of reach, scrapeforge says so before you build anything on it.

## Capability table (measured claims only)

Verified live in this session, 2026-09-11, from a home IP in Europe/Stockholm:

| Target | Tier | Result |
|---|---|---|
| `example.com` | 1 | 200, 559 bytes, static |
| `docs.python.org/3/` | 1 | 200, 19.4 KB, static |
| `news.ycombinator.com` | 1 | 200, 35 KB, static |
| `books.toscrape.com` | 1 | 200, 51 KB, static |
| `quotes.toscrape.com` | 1 | 200, 11 KB, static |
| `www.aliexpress.com` | 2 | 200, 506 KB real page served via curl_cffi TLS impersonation |

Prior evidence, dated, not re-verified today:

| Target | Tier | Evidence | Date |
|---|---|---|---|
| AliExpress, eBay, Reddit, Indeed, Walmart, Zillow | 2 | Real pages served to curl_cffi | 2026-08-29 |
| Wikipedia, Hacker News | 1 | Static | 2026-08-29 |
| Google Jobs vertical (`udm=8`) | n/a | Plain HTTP returned a 91 KB JavaScript shell, 0 job postings | 2026-09-07 |

Walled from this network, dated:

| Target | Wall | Date |
|---|---|---|
| eBay | Akamai "Pardon Our Interruption", all tools, IP flagged after a burst of probes | 2026-08-29 |
| Etsy, Booking, IMDb | Challenge pages (403 / 202) | 2026-08-29 |
| Stack Overflow | Cloudflare "Just a moment", not cracked by scrapling's cloudflare solve | 2026-08-29 |
| Indeed | Cloudflare 403 across curl, headless Chromium, and proxy tiers | 2026-09-07 |
| Reddit, Google, Amazon Seller Central | Cloudflare / PerimeterX / DataDome walls and `/sorry/` CAPTCHA | 2026-09-07 to 2026-09-09 |

Reachability is IP- and time-dependent. A verdict from one network or one day does not carry over. Probe per job with `python3 -m scrapeforge probe <url>`. UNBLOCKER and residential proxies change the calculus for walled sites, but they cost money and are a per-job decision, not a default.

## Verify by data, not by exit code

A process that exits 0 with an empty dataset has proven nothing. Every `run` asserts a row count and prints a sample after writing:

```bash
python3 -m scrapeforge run examples/hn-front.yaml --out hn.csv --min-rows 10 --sample 3
```

Exit codes are the contract:

| Code | Meaning |
|---|---|
| 0 | at least `--min-rows` records written |
| 2 | fewer than `--min-rows` records, including the empty result |
| 1 | config or I/O error |

Verify any dataset file after the fact:

```bash
python3 -m scrapeforge verify hn.csv --min-rows 10 --sample 5
```

`verify` reads CSV, JSON, or JSONL (by extension, or `--format`), counts records, prints a sample, and exits 2 on an empty or short result. This is the lesson that cost the most across the fleet that produced this tool: a status of SUCCEEDED with zero rows means the extraction failed, no matter what the process said.

## Output contract

Every dataset scrapeforge writes has a machine-readable schema:

- `schema/dataset_schema.json` describes the record shapes: item records from `run` (one row per item, keys from the config, every value a string) plus the fixed fields for `batchprobe` and `pageprobe` output.
- `schema/output_schema.json` describes the `run` command contract: artifacts, stdout/stderr lines, and exit codes.

Only fields the code actually emits are listed. Item-record field names come from the `fields:` block in the config; the schema names each view's concrete fields.

## Config format

```yaml
name: hn-front
url: https://news.ycombinator.com/news
tier: auto            # auto | 1 | 2 | 3
max_pages: 10
rate_limit_sec: 1.0
paginate:
  selector: "a.morelink"
  attribute: href
  next_text: "More"
items:
  selector: "tr.athing"
fields:
  title: { selector: "span.titleline a", attr: text }
  url:   { selector: "span.titleline a", attr: href }
  score: { selector: "span.score", attr: text, scope: next }
output: csv           # csv | json | jsonl
```

Fields default to `scope: item` (the selector resolves inside each matched item). `scope: next` resolves inside the item's next sibling element, which is how the HN score column above is joined to its row: HN puts the score in the row after the title. `scope: global` resolves against the whole document and pairs results by index; use it only when every item has exactly one match, because a single missing match (an HN job post has no score) shifts every later value onto the wrong row.

## Commands

```bash
# classify one site: tier, confidence, markers, note
python3 -m scrapeforge probe https://www.aliexpress.com/
python3 -m scrapeforge probe https://www.aliexpress.com/ --fail-blocked   # exit 3 if walled

# classify many sites in one pass -> CSV
python3 -m scrapeforge batchprobe urls.txt --out results.csv

# certify that pagination actually advances on a target -> CSV
python3 -m scrapeforge pageprobe urls.txt --tiers results.csv --out matrix.csv

# run a YAML config -> dataset, with row-count verification
python3 -m scrapeforge run examples/hn-front.yaml --out data.csv

# verify an existing dataset file
python3 -m scrapeforge verify data.csv --min-rows 1 --sample 3
```

## Pagination

Two layers:

1. Config-driven pagination (`paginate.py`): the runner follows next-page links from the `paginate:` block until `max_pages` or no next link. `rate_limit_sec` inserts a pause between page fetches. Next links resolve against the page they were found on, and the loop stops if a next link points back at a page it already fetched.

2. Pagination certification (`pageprobe.py`): verifies that a target actually paginates before you rely on it, by fetching page 1, finding the next link, fetching page 2, and checking the visible text changed. Verdicts: `PAGINATED_OK`, `NO_NEXT_LINK`, `BLOCKED_AT_DEPTH`, `NO_CONTENT_CHANGE`, `ERROR`. Run it on the exact URLs a job needs (category pages, not homepages).

## What it will not do

- It will not log in, defeat login walls, or use credentials that are not yours.
- It will not defeat Cloudflare managed challenges, PerimeterX, or DataDome from a single IP. Those need paid residential proxy rotation, and even then they are an arms race.
- It will not turn a JavaScript shell into data. If the listings are rendered client side and not in the response body, tiers 1 and 2 return the shell with zero rows. That is what tier 3 and, often, a paid unblocker are for.
- It will not promise that a site works today because it worked on a previous day.
- It does not ship a dataset of scraped content. It ships the tool.

## The 150-site dataset

`results-stress-test-2026-08-29.csv` holds reachability verdicts for 150 live e-commerce and indie-web sites probed on 2026-08-29: tier per site, response size, and notes. 103 deliverable, 37 blocked, 10 unreachable. `pagination-matrix-homepages-2026-08-29.csv` is the pagination-advance matrix from the same set. These are dated snapshots, not live guarantees.

## Legal note

Public data only. Respect robots.txt and rate limits. No login-gated content, no credential abuse. If a site forbids scraping, scrapeforge flags it and you decide with the site's terms in mind.

## Repo metadata

Description and topics for the repository page (set via the GitHub API, or paste these by hand):

- Description: `Probe-first, tiered Python scraper: classify a site's anti-bot defenses, fetch with the cheapest tier that works (httpx, curl_cffi TLS impersonation, browser), extract via YAML + CSS selectors, verify row counts. CSV/JSON. MIT.`
- Topics: `python`, `scraping`, `web-scraping`, `curl-cffi`, `tls-impersonation`, `anti-bot`, `yaml`, `csv`, `mit-license`

## Repo map

- `scrapeforge/classify.py` classify a target and pick the tier
- `scrapeforge/batchprobe.py` concurrent multi-site classification
- `scrapeforge/pageprobe.py` pagination certification
- `scrapeforge/fetch.py` tier 1/2/3 fetchers, one import each
- `scrapeforge/extract.py` CSS selector extraction (item, next-sibling, and global scope)
- `scrapeforge/paginate.py` config-driven pagination loop
- `scrapeforge/output.py` CSV/JSON/JSONL writers
- `scrapeforge/verify.py` row-count verification and exit codes
- `scrapeforge/cli.py` probe, batchprobe, pageprobe, run, verify
- `pyproject.toml` package metadata and the `scrapeforge` command
- `.github/workflows/tests.yml` CI: pytest on Python 3.11-3.14
- `schema/dataset_schema.json` record contract for every dataset
- `schema/output_schema.json` run output and exit-code contract
- `examples/hn-front.yaml` tier 1, paginated, verified live
- `examples/4chan-g.yaml` tier 2, verified live 2026-08-29
- `examples/aliexpress.yaml` tier 2, verified live 2026-08-29

## Links

Part of the [vhsgreed](https://vhsgreed.win) toolset: browser actors and scraping work at [vhsgreed.win/actor](https://vhsgreed.win/actor/).
