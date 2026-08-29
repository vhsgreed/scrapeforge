# Verified delivery matrix — tested live 2026-08-29

Probed from hub (home IP, Europe/Stockholm). Basis for what the Fiverr
scraping gig can honestly promise. Tier = scrapeforge tier needed.

## ✅ Deliverable now (tier 1-2, verified working)

| Site | Tier | Verdict |
|---|---|---|
| AliExpress | 2 | Full 388KB page, real title/links. NOTE: rate-limits after ~10 rapid requests — use delays |
| eBay | 2 | Full page served |
| Reddit | 2 | Full page (old/regular HTML served) |
| Indeed | 2 | Full page served |
| Walmart | 2 | Full page served |
| Zillow | 2 | Full page served |
| Wikipedia | 1 | Static, trivial |
| Hacker News | 1 | Static, trivial |

## ❌ Blocked from this IP (do NOT promise without tier 3 discussion)

| Site | Status | Block |
|---|---|---|
| Amazon | 202 | Empty/challenge, needs full browser emulation + ToS risk |
| Etsy | 403 | Captcha page, 779 bytes |
| Booking | 202 | Challenge page |
| IMDB | 202 | Challenge page |
| StackOverflow | 403 | Cloudflare challenge |

## Gig promises (grounded in this matrix)

- "Most public sites" + named examples (AliExpress, eBay, Reddit, Indeed,
  Walmart, Zillow, Wikipedia, HN)
- "I'll probe your target first and tell you honestly if it's reachable"
- No Amazon scraping (stated in FAQ)
- Tier 3 (Etsy/Booking/IMDB/SO) possible with browser emulation — discuss
  per-order, never a blanket promise

## Caveats

- Results are IP- and time-dependent. Datacenter IPs (VPS/proxy) get blocked
  more aggressively than home IPs. Home IP + delays = best odds.
- Rate limits: AliExpress-style sites challenge after bursts. scrapeforge
  rate_limit_sec config + probe-first flow handles this.
- Re-verify per order: `python3 -m scrapeforge probe <url>` before promising.
