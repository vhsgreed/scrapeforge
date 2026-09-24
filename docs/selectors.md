# Writing selectors

A scrapeforge config needs two kinds of selector: one that matches **each item** on the page (a product card, a table row, a search result) and, inside each item, one per **field** (title, price, link). This guide gets you from a URL to a working config, and explains what to do when a selector matches nothing.

## The five-minute workflow

```bash
scrapeforge init https://books.toscrape.com/          # guess a config, preview it
scrapeforge try https://books.toscrape.com/ "p.price_color" --in "article.product_pod"
scrapeforge run books-toscrape.yaml --out books.csv
```

1. **`init`** finds the block repeated most on the page, writes a commented config, and prints a coverage report:

   ```
   field coverage on this page:
     title          20/20 (100%)
     price          20/20 (100%)
     rating          6/20 (30%)   <- check this one
   ```

   A field below 90% either is optional on the site or has a selector that is too specific. Check it with `try`.

2. **`try`** tests one selector. With `--in`, it resolves the selector inside each item, just as a field is resolved, and tells you how many items lack it. When nothing matches, it prints hints, such as similar class names on the page, "this page is rendered by JavaScript", or "this page carries embedded JSON".

3. **`fetch`** saves the page once so you can iterate offline, without hitting the site on every attempt:

   ```bash
   scrapeforge fetch https://books.toscrape.com/ --out page.html
   scrapeforge try page.html "h3 a" --in "article.product_pod" --attr title
   scrapeforge init page.html
   ```

   A config's `url:` can also be a `file://` path while you develop it.

## Your browser shows a different page than scrapeforge gets

The browser's DevTools (Inspect Element) show the page **after** JavaScript ran. scrapeforge's tiers 1 and 2 get the HTML the server sent, **before** JavaScript runs. When a selector works in DevTools but `try` finds 0 matches:

- Look at what scrapeforge actually receives: `scrapeforge fetch <url>`, then open `page.html` in an editor. Or use the browser's **View Page Source** (not Inspect), which shows the same thing.
- If the items are not in that HTML, look for [embedded JSON](#embedded-json) before reaching for a browser tier.

## Choosing an item selector

A good item selector matches every item and nothing else, and survives small changes to the page.

| Prefer | Avoid | Why |
|---|---|---|
| `article.product_pod` | `ol > li:nth-child(3)` | Position-based selectors pin one element and shift when anything above it changes. |
| `div.product-card` | `div.css-1x9f2k` | Hashed class names (`css-…`, `sc-…`, long hex) are regenerated on every site deploy. |
| `div.product-card` | `div.p-4.flex.mt-2` | Utility classes (`p-4`, `flex`, `col-md-3`) describe layout and are shared by unrelated elements. |
| `tr.athing` | `#main > div > table > tbody > tr` | DevTools **Copy selector** paths break easily. `try` warns when it sees one. |

When the items have no useful class, anchor on a stable parent: `#results > div`, `ul.products > li`.

## CSS in five minutes

| Selector | Matches |
|---|---|
| `h3` | every `<h3>` |
| `.price` | elements with class `price` |
| `p.price` | `<p>` elements with class `price` |
| `#results` | the element with `id="results"` |
| `div.card a` | `<a>` anywhere inside `div.card` (descendant) |
| `ul > li` | `<li>` that are direct children of `<ul>` |
| `a[href]` | links that have an `href` |
| `a[rel~=next]` | `rel` attribute contains the word `next` |
| `[class*=price]` | class attribute contains `price` anywhere |
| `img[src$=".jpg"]` | `src` ends with `.jpg` |
| `li:nth-of-type(2)` | second `<li>` among its siblings |
| `div:has(> span.sale)` | divs with a direct `span.sale` child |
| `a:-soup-contains("Next")` | links whose text contains `Next` |

## Fields

```yaml
fields:
  title: { selector: "h3 a", attr: title }            # an attribute
  url:   { selector: "h3 a", attr: href, absolute: true }
  price: { selector: "p.price_color", type: float }   # "£51.77" -> 51.77
  tags:  { selector: "a.tag", all: true, join: "|" }  # every match, joined
  sku:   { selector: "span.meta", regex: "SKU: (\\w+)" }
  stock: { selector: "p.availability", default: "unknown" }
```

| Key | Meaning |
|---|---|
| `selector` | CSS selector, resolved inside each item. Omit to use the item itself. |
| `attr` | `text` (default), `html` (inner HTML), or any attribute: `href`, `src`, `title`, `data-src`, `content` |
| `scope` | `item` (default); `next` for data in the item's next sibling (the Hacker News score row); `global` to pair document-wide matches by position, which is only safe when every item has exactly one match |
| `all` / `join` | collect every match instead of the first, joined with `join` (default `", "`) |
| `strip` | `true` (default) trims whitespace; a string trims those characters |
| `regex` | keep group 1, or the whole match if the pattern has no group. No match means missing. |
| `type` | `str` (default), `int`, or `float`. Reads the first number in the text: `"1,299 kr"` gives 1299 |
| `decimal` | `","` for European numbers: `"1.299,50 kr"` gives 1299.5 |
| `default` | value when the field is missing or does not parse. Without it, a missing text field is `""` and a missing number is empty (null in JSON). |
| `absolute` | resolve a relative link against the page URL |

Lazy-loaded images often put a placeholder in `src` and the real URL in `data-src`, `data-original` or `srcset`. `init` picks the lazy attribute when `src` is a `data:` URI.

## Embedded JSON

Many pages that render with JavaScript still ship their data inside the HTML:

| Source | Where it lives | Typical sites |
|---|---|---|
| `ld+json` | `<script type="application/ld+json">` | product and article pages, recipes, events (schema.org) |
| `next_data` | `<script id="__NEXT_DATA__">` | Next.js sites |
| `nuxt` | `<script id="__NUXT_DATA__">` | Nuxt 3 sites (raw payload) |
| `var:NAME` | `window.NAME = {...}` in a script | many React and Vue storefronts (`__INITIAL_STATE__`, `__APOLLO_STATE__`) |
| a CSS selector | the text of that `<script>` | anything else, e.g. `script#product-data` |

`scrapeforge probe <url>` lists what it finds, including paths to the longest lists. Then:

```yaml
items:
  json: next_data
  path: props.pageProps.results.hits     # dotted path to the list of items
fields:
  title: { path: title }
  price: { path: price.value, type: float }
  tags:  { path: "tags.*.name", all: true }
```

```yaml
items:
  json: ld+json
  where: { "@type": Product }            # keep only these objects
fields:
  name:  { path: name }
  price: { path: offers.price, type: float }
```

Paths are dotted keys. A number indexes a list (`images.0`), and `*` fans out over a list or object (`itemListElement.*.item`). `scrapeforge init --json` builds this kind of config for you.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `try` finds 0 matches, DevTools finds them | content rendered by JavaScript | `probe` for embedded JSON; otherwise tier 3 |
| 0 matches, and the class is visible in `page.html` | a typo, or the class is on a different tag | the hint lists similar classes; drop the tag (`.price` rather than `span.price`) |
| every row has the same value | the field selector escapes the item, or `scope: global` | keep the default `scope: item`, and select inside the item |
| values belong to the neighbouring row | `scope: global` with a missing match | use `scope: next`, or restructure the item selector |
| a field is empty but visible | the value is in an attribute | `attr: title`, `attr: content`, `attr: data-…` |
| a price reads 1.299 instead of 1299 | European number format | add `decimal: ","` to the field |
| page 2 is missing | no `paginate:` block, or the wrong next-link selector | `try <url> "a[rel~=next]"`; `pageprobe` certifies it advances |
