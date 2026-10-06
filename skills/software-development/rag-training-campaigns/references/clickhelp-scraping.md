# ClickHelp portal scraping — proven working recipe

Applies to ClickHelp-hosted documentation portals (documentation.neutrinos.com is
one). The key insight generalizes to most ClickHelp installs.

## The auth trick

The reader URL `https://portal/articles/#!publication/slug` is a login-walled SPA.
But `https://portal/article/{publication}/{slug}` serves complete
server-rendered HTML with NO authentication. Always fetch the `/article/` form.
Verify per-portal first: an unknown slug returns 404, a real one returns ~12 KB
with content starting after `<span id="__clhTop"></span>`.

## Change detection

`/sitemaps/sitemap.xml` is a sitemap index -> per-publication sitemaps
(`/sitemaps/sitemap_publication_{id}.xml`) -> every topic with `lastmod`.
Store full-precision lastmod strings (never truncate to date — same-day second
edits would be lost forever) AND a sha256 of the extracted text: lastmod
decides what to FETCH (cheap), the hash decides what CHANGED (expensive
downstream). Portal-wide republish bumps all lastmods; the hash absorbs it.

Also keep a sanity floor: if discovered topics < ~80% of known topics, refuse
to prune anything and fail loudly — a renamed sitemap pattern otherwise wipes
the whole corpus while reporting success.

## Extraction

Article body = everything between `<span id="__clhTop"></span>` and `<footer>`
(search for footer FROM the content start, not offset 0). Strip
`<a class="CHHeadingLink">` anchors (heading deep-link furniture). Bounded
edge cases to test: anchors with that class on non-<a> tags (use a tag-name
skip stack, not a counter — a counter never decrements on empty elements and
silently swallows the rest of the page), loose text directly under the marker
span with no wrapping block element, tables (emit row-buffered markdown with
`|---|` separator after the first row), and placeholder pages that exist in
the sitemap with empty bodies (record them, don't retry forever).

## Transport

- stdlib urllib + ThreadPoolExecutor works; no browser, no wait.
- robots.txt: typically comments only. Retries with linear backoff on 5xx.
- Full corpus (3k+ pages) ~2 min at concurrency 8; no-change sitemap diff ~3 s.

## Scheduling / self-healing

No cron inside the container. One process loops forever: on startup, if today's
scheduled run hasn't succeeded yet, run immediately, then sleep until the next
slot. Pair with docker `restart: unless-stopped` and a healthcheck that reads
the last-run status file (which must record failure honestly — a healthcheck
on file freshness alone shows green through daily failures).
