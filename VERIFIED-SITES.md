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
| eBay | 200 | **HARD BLOCK 14:14 (IP flagged after ~10 probes today):** homepage + search both return "SORRY" / "Pardon Our Interruption" Akamai challenge to curl_cffi, playwright, cloakbrowser AND scrapling stealth. Home IP burned — cools off hours/days |
| Etsy | 403 | Captcha page, 779 bytes |
| Booking | 202 | Challenge page |
| IMDB | 202 | Challenge page |
| StackOverflow | 403 | Cloudflare "Just a moment" JS challenge — scrapling solve_cloudflare did NOT crack it (14:14) |

## Tier-3 tooling status (tested 14:14)

| Tool | Result | Verdict |
|---|---|---|
| playwright (plain) | Blocked by eBay | Detected immediately |
| cloakbrowser (C++ source patches) | Blocked by eBay | Good tool, IP was already flagged; fonts needed (installed) |
| scrapling StealthySession (patchright) | Blocked by eBay + SO | Best tier-3 addition (auto-cloudflare), but not magic; hard JS challenges win |
| curl_cffi | WORKS tier 2 | The workhorse — verified 8 sites |

## Hard-won lessons (from 14:00-14:15 testing)

1. **IP reputation is the real gate.** eBay flagged our home IP after ~10 probes in an hour. Once flagged, EVERY tool fails (even homepage). Probe gently, rate-limit, don't burn targets.
2. **Never promise a site without probing it first.** The probe-first flow is not optional — it's the product.
3. **Tier 3 is an arms race.** JS-proof challenges (Akamai POTI, Cloudflare managed) beat every open-source tool from a single IP. Residential proxy + rotation is the only reliable answer, and that's a cost/scale decision per order.

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
