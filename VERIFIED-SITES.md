# Verified delivery matrix

What scrapeforge can reach, and what is walled, with the date each verdict was
measured. Reachability is IP- and time-dependent, so treat every row as a
dated snapshot. Re-probe with `python3 -m scrapeforge probe <url>` before you
rely on a site.

Tier = the scrapeforge fetch tier the target needed.

## Tier definitions

| Tier | Tool | Meaning |
|---|---|---|
| 1 | `httpx` plain HTTP | Static HTML in the response body |
| 2 | `curl_cffi` TLS impersonation | A browser TLS fingerprint is enough to get real HTML |
| 3 | browser stealth (`scrapling` / `cloakbrowser` / `playwright`) | Browser-class wall, and often still not enough |

## Verified live in this session, 2026-09-11

Home IP, Europe/Stockholm. Single low-volume probes.

| Target | Tier | Result |
|---|---|---|
| example.com | 1 | 200, 559 bytes, static |
| docs.python.org/3/ | 1 | 200, 19.4 KB, static |
| news.ycombinator.com | 1 | 200, 35 KB, static |
| books.toscrape.com | 1 | 200, 51 KB, static |
| quotes.toscrape.com | 1 | 200, 11 KB, static |
| www.aliexpress.com | 2 | 200, 506 KB real page served via curl_cffi TLS impersonation |

AliExpress served a full 506 KB page through curl_cffi, which is the cleanest
demonstration that tier 2 does what tier 1 cannot on a protected site. It
rate-limits after a burst of rapid requests, so keep `rate_limit_sec` at 3.0
or higher.

## Prior evidence, dated, not re-verified today

Probed 2026-08-29 from the same hub.

| Target | Tier | Result | Date |
|---|---|---|---|
| AliExpress | 2 | Full 388 KB page, real title and links | 2026-08-29 |
| eBay | 2 | Full page served | 2026-08-29 |
| Reddit | 2 | Old/regular HTML served | 2026-08-29 |
| Indeed | 2 | Full page served | 2026-08-29 |
| Walmart | 2 | Full page served | 2026-08-29 |
| Zillow | 2 | Full page served | 2026-08-29 |
| Wikipedia | 1 | Static, trivial | 2026-08-29 |
| Hacker News | 1 | Static, trivial | 2026-08-29 |

Some of these later turned walled (Reddit and Indeed below). The 2026-08-29
rows show what the IP could reach that day, nothing more.

## Wall known, dated

| Target | Wall | Date |
|---|---|---|
| eBay | Akamai "Pardon Our Interruption". After a burst of about 10 probes the home IP was flagged and every tool failed, including the homepage | 2026-08-29 |
| Etsy | 403 CAPTCHA page, 779 bytes | 2026-08-29 |
| Booking | 202 challenge page | 2026-08-29 |
| IMDb | 202 challenge page | 2026-08-29 |
| Stack Overflow | Cloudflare "Just a moment" JS challenge. scrapling's cloudflare solve did not crack it | 2026-08-29 |
| Google Jobs vertical (`udm=8`) | Plain HTTP returned a 91 KB JavaScript shell with 0 job postings. Client-rendered, nothing in the body | 2026-09-07 |
| Indeed | 403 across the whole stack: datacenter curl (Cloudflare), local headless Chromium, and both proxy tiers | 2026-09-07 |
| Reddit | Cloudflare / DataDome wall observed during actor builds | 2026-09-07 to 2026-09-09 |
| Google | All bot challenge tiers returned `/sorry/` CAPTCHA. Unblocker and residential proxies included | 2026-09-09 |
| Amazon Seller Central | Cloudflare / PerimeterX / DataDome wall | 2026-09-07 to 2026-09-09 |

JS-shell pages are the quiet failure mode. Google Jobs returned a 91 KB shell
with HTTP 200 and zero listings, which a naive check reads as success. This is
why `run` now asserts a row count and `verify` fails on an empty result.

## Proxies change the calculus, at a cost

UNBLOCKER and residential proxy tiers get past some of the walls above, but
results still vary (Indeed 403 through both HTTP proxy tiers, Google still
`/sorry/`). Proxies cost money and are a per-job decision, never a default in
scrapeforge. Tier 3 with a good residential proxy is the only reliable answer
for the hardest walls, and even that is an ongoing arms race.

## Tier-3 tooling status (tested 2026-08-29)

| Tool | Result | Note |
|---|---|---|
| `playwright` plain | Blocked by eBay | Detected immediately |
| `cloakbrowser` | Blocked by eBay | Good tool, but the IP was already flagged by then |
| `scrapling` StealthySession | Blocked by eBay and Stack Overflow | Best tier-3 option (auto cloudflare), still not magic |
| `curl_cffi` | Works as tier 2 | The workhorse |

## Hard-won lessons

1. IP reputation is the real gate. eBay flagged the home IP after about 10 probes in an hour, then every tool failed. Probe gently, rate-limit, do not burn targets.
2. Never promise a site without probing it first. Probe-first is the product, not an option.
3. Tier 3 is an arms race. Managed JS challenges beat every open-source tool from a single IP. Residential proxy rotation is the reliable answer, and that is a cost and scale decision per job.
4. Exit code 0 with zero rows is not success. Verify by data.

## Re-verify per job

```bash
python3 -m scrapeforge probe <url>              # tier + confidence + note
python3 -m scrapeforge probe <url> --fail-blocked   # exit 3 when walled
```
