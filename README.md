# scrapeforge

[![tests](https://github.com/vhsgreed/scrapeforge/actions/workflows/tests.yml/badge.svg)](https://github.com/vhsgreed/scrapeforge/actions/workflows/tests.yml)
[![live check](https://github.com/vhsgreed/scrapeforge/actions/workflows/live.yml/badge.svg)](https://github.com/vhsgreed/scrapeforge/actions/workflows/live.yml)

**Turn a listing page into a CSV in two commands.** scrapeforge looks at the page, writes the config for you, fetches with the cheapest method that works, and fails loudly when it gets zero rows instead of reporting success.

![scrapeforge demo: init, try, run](docs/demo.gif)

## Quickstart

```bash
pip install git+https://github.com/vhsgreed/scrapeforge

scrapeforge init https://books.toscrape.com/catalogue/page-1.html --name books
scrapeforge run books.yaml --out books.csv
```

`init` probes the site, finds the block that repeats on the page (product cards, table rows, results), guesses the fields, finds the next-page link, and shows how many items each field filled:

```
[probe] https://books.toscrape.com/catalogue/page-1.html -> tier 1 (static page)
[init] wrote books.yaml: 20 items on this page (20 repeats, median text 51 chars, each has a link, each has an image)
field coverage on this page:
  title           20/20 (100%)
  url             20/20 (100%)
  image           20/20 (100%)
  price           20/20 (100%)
  availability    20/20 (100%)
```

(Real output from the daily live check. The run that follows fetches 5 pages and verifies 100 rows.)

The config is plain YAML you can read and edit:

```yaml
name: books
url: "https://books.toscrape.com/catalogue/page-1.html"
tier: 1
paginate:
  selector: "li.next a"
items:
  selector: "article.product_pod"
fields:
  title:        { selector: "h3 a", attr: title }
  url:          { selector: "h3 a", attr: href, absolute: true }
  price:        { selector: "p.price_color", attr: text, type: float }
  availability: { selector: "p.instock.availability", attr: text }
output: csv
```

## Help with selectors

You never have to open DevTools to get started, and when you do edit a selector, scrapeforge tells you whether it works:

```bash
scrapeforge try <url> "p.price_color" --in "article.product_pod"   # test a field
scrapeforge fetch <url> --out page.html                             # save once, iterate offline
scrapeforge try page.html "span.price"
```

```
0 elements match 'span.price'
hint: similar classes on this page: div.product_price (20), p.price_color (20)
```

`try` also flags pages rendered by JavaScript, points at embedded JSON when a page has it, and warns about brittle DevTools "Copy selector" paths. **[docs/selectors.md](docs/selectors.md)** is the full guide: the workflow, choosing selectors that survive site updates, a CSS cheat sheet, every field option, and a troubleshooting table.

## JavaScript pages without a browser

Many pages that render with JavaScript still ship their data inside the HTML: JSON-LD, Next.js `__NEXT_DATA__`, or `window.__INITIAL_STATE__ = {...}`. `probe` lists what a page carries, and `init` falls back to it when there is no HTML to select:

```yaml
url: https://quotes.toscrape.com/js/      # the HTML has no quotes; the script does
items:
  json: "var:data"
fields:
  text:   { path: text }
  author: { path: author.name }
  tags:   { path: "tags.*", all: true, join: "|" }
```

That is plain HTTP at tier 1. No browser, and checked daily.

## Clean values, not strings to fix later

```yaml
price:  { selector: ".price", type: float }                 # "£1,299.50" -> 1299.5
price:  { selector: ".pris", type: float, decimal: "," }    # "1.299,50 kr" -> 1299.5
sku:    { selector: ".meta", regex: "SKU: (\\w+)" }
tags:   { selector: "a.tag", all: true, join: "|" }
url:    { selector: "a", attr: href, absolute: true }
stock:  { selector: ".stock", default: "unknown" }
```

## Watch for changes

Output only what is new or changed since the last run. This is useful for prices, listings and job boards:

```bash
scrapeforge run shop.yaml --since state.csv --snapshot state.csv --key url --out changes.csv
```

`changes.csv` gets a `_change` column (`new` or `changed`). `state.csv` keeps the full picture for next time. The row-count check still applies to everything scraped, so a quiet day passes and a broken selector fails.

## Pipes and Python

```bash
scrapeforge run examples/quotes-toscrape.yaml --out - | jq -r .author | sort | uniq -c
```

```python
from scrapeforge import scrape

result = scrape("examples/books-toscrape.yaml")
cheap = [r for r in result.rows if r["price"] < 20]
```

`scrape()` accepts a YAML path or a dict, returns rows without writing files, and takes a `fetcher=` for custom transports.

## How it fetches

| Tier | Tool | Handles |
|---|---|---|
| 1 | `httpx` (plain HTTP) | Static HTML: blogs, docs, directories, most indie sites |
| 2 | `curl_cffi` (TLS impersonation) | Sites that reject Python's TLS fingerprint but serve real HTML to a browser fingerprint |
| 3 | `scrapling` / `cloakbrowser` / `playwright` | Browser-class walls. Optional (`pip install "scrapeforge[tier3] @ git+https://github.com/vhsgreed/scrapeforge"`), heavy, and never promised for a specific site |

`tier: auto` probes first and picks the lowest tier that returns a real page. `scrapeforge probe <url>` shows the verdict. If a site is out of reach, you find out before you build on it.

### What works (measured, never assumed)

| Target | Tier | Status |
|---|---|---|
| Hacker News, books.toscrape, quotes.toscrape, quotes.toscrape/js | 1 | checked daily by the [live check](.github/workflows/live.yml), including `init` from scratch |
| AliExpress, Walmart, Zillow | 2 | real pages via curl_cffi, 2026-08-29 to 2026-09-11 |
| eBay, Etsy, Booking, IMDb, Stack Overflow, Indeed, Reddit, Google | n/a | walled (Akamai, Cloudflare, PerimeterX, DataDome), 2026-08-29 to 2026-09-09 |

Reachability depends on your IP and the day. [VERIFIED-SITES.md](VERIFIED-SITES.md) has the dated evidence per site, and `results-stress-test-2026-08-29.csv` has verdicts for 150 sites (103 deliverable, 37 blocked, 10 unreachable). Probe per job.

## Verify by data, not by exit code

A run that exits 0 with an empty dataset has proven nothing, so every `run` asserts a row count and prints a sample:

| Exit code | Meaning |
|---|---|
| 0 | at least `--min-rows` records (default 1) |
| 1 | config, I/O or fetch error |
| 2 | fewer than `--min-rows` records, including the empty result |
| 3 | `probe --fail-blocked`: the target is walled |

`scrapeforge verify data.csv --min-rows 10` checks any CSV, JSON or JSONL file after the fact. The schemas in [`schema/`](schema) describe every dataset and the `run` contract.

## Commands

| Command | Does |
|---|---|
| `init <url\|file>` | guess a config from a listing page, preview it, report field coverage |
| `try <url\|file> <selector>` | test a selector (`--in ITEMS` to test it as a field) |
| `fetch <url>` | save the HTML scrapeforge sees, for offline work |
| `probe <url>` | tier verdict plus any embedded JSON (`--fail-blocked` exits 3 when walled) |
| `run <config>` | scrape, write CSV/JSON/JSONL (`--out -` for stdout), verify the row count |
| `verify <file>` | row-count check and sample for an existing dataset |
| `batchprobe <urls.txt>` | tier verdicts for many sites, to CSV |
| `pageprobe <urls.txt>` | certify that pagination actually advances (page 2 differs from page 1) |

Every command has `--help`.

## Why not just use X

| Approach | What you still do yourself |
|---|---|
| `requests` / `httpx` | Everything. Protected sites return a challenge page and you get zero rows without noticing. |
| `curl_cffi` alone | Know which sites need it, and check the body is real rather than a challenge page. |
| Scrapling | A browser stack to install, and a per-site decision about which mode to use. |
| Crawlee, Scrapy | A framework to learn for what is often one listing and its pages. |
| scrapeforge | Check the coverage report. The probe picks the tier, `init` writes the config, and `run` asserts it got rows. |

## What it will not do

- Log in, get past login walls, or use credentials that are not yours.
- Beat Cloudflare managed challenges, PerimeterX or DataDome from a single IP. That takes paid residential proxies, and even then it is an arms race.
- Promise that a site works today because it worked on another day.
- Ship scraped data. It ships the tool.

## Legal

Public data only. Respect each site's terms and rate limits. No login-gated content, no credential abuse.

## Development

```bash
git clone https://github.com/vhsgreed/scrapeforge && cd scrapeforge
pip install -e ".[dev]"
python -m pytest -q
```

Tests run offline against saved pages in `tests/fixtures/`. CI runs them on Python 3.11 to 3.14. The live check runs the examples against real sites daily, and pushing a `v*` tag builds and checks a release. Publishing to PyPI is opt-in, see [release.yml](.github/workflows/release.yml).

MIT licensed. Part of the [vhsgreed](https://vhsgreed.win) toolset.
