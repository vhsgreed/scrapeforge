# scrapeforge — config-driven scraping for gig 2

Tiered Python scraper built for the Fiverr automation gig. Probe the site
first, pick the right fetch tier automatically, extract with CSS selectors,
output CSV/JSON. New sites are a YAML file, not code.

## Tiers (auto-selected by probe)

| Tier | Tool | Handles | Example |
|---|---|---|---|
| 1 | `httpx` (plain) | Static HTML pages | Blogs, directories |
| 2 | `curl_cffi` (TLS impersonation) | JS-heavy + bot-protected pages | AliExpress (verified 08-29) |
| 3 | `CloakBrowser` / Playwright stealth | Amazon-class anti-bot | Amazon (heavy, fragile, ToS risk) |

The probe (classify.py) fetches the target, scores the response, and picks
the tier. We never promise tier 3 in a gig; it's the escalation path we
discuss with the buyer if tier 2 gets blocked.

## Install

```bash
pip install curl_cffi httpx pyyaml
# optional, tier 3 only:
pip install cloakbrowser   # or playwright + invisible_playwright
```

## Usage

```bash
# probe a site to see what tier it needs
python -m scrapeforge probe https://www.aliexpress.com/

# run a config
python -m scrapeforge run examples/aliexpress.yaml --out data.csv
```

## Config format

```yaml
name: aliexpress-search
url: https://www.aliexpress.com/w/wholesale-led-strip.html
tier: auto            # auto | 1 | 2 | 3
max_pages: 50
paginate:
  selector: ".next-pagination-item"
  attribute: href
  next_text: "Next"
items:
  selector: "div.list-item"
fields:
  title: { selector: ".title", attr: text }
  price: { selector: ".price-current", attr: text }
  url:   { selector: "a", attr: href }
rate_limit_sec: 2.0
output: csv           # csv | json | jsonl
```

## Legal note

Public data only. We respect robots.txt and rate limits. No login-gated
content, no credential abuse. If a site forbids scraping, we flag it and
discuss with the buyer before continuing.

## Repo map

- `scrapeforge/classify.py` — probe + tier selection
- `scrapeforge/fetch.py` — tier 1/2/3 fetchers (one import each)
- `scrapeforge/extract.py` — CSS selector extraction
- `scrapeforge/paginate.py` — pagination loop
- `scrapeforge/output.py` — CSV/JSON writers
- `scrapeforge/cli.py` — probe/run commands
- `examples/aliexpress.yaml` — verified config (tested live 08-29)
