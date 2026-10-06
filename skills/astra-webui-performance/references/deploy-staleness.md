# Deploy staleness — the CF edge pins index.html (astra.jitinnair.com)

## The failure shape

A user reports a known-fixed bug 'still visible' on the web UI right after a deploy.
The fix IS in source AND in the freshly built dist. The cause is upstream of the app:
the zone's cache-everything rule (catch-all, edge/browser TTL 31536000) applies to
HTML documents too — the origin's `cache-control: no-cache` for index.html is
REWRITTEN to `max-age=31536000` at the edge, and the edge serves its pinned copy
(`cf-cache-status: HIT`, age in hours). Every reload hands back the old bundle.

Two independent layers of armour exist; know which one covers the case:

1. **HTML revalidation rule** (zone ruleset): dotless paths on astra./test. hosts
   cache for only 60s — deploys should be visible within a minute.
2. **Client build-check** (`src/lib/build-check.ts` + server `/api/build-id`):
   the running bundle polls every 90s (visible tabs) and hard-reloads ONCE when
   the server's stamp differs. Reload is guarded by sessionStorage so a broken
   deploy cannot loop the tab. Only fixes tabs running a bundle that HAS the
   check — an older bundle never self-heals and needs a forced reload.

## The staleness ladder — run in this order

1. **What is the tab actually running?** `curl -s https://astra.jitinnair.com/ |
   grep -o 'index-[A-Za-z0-9_-]*\.js'` and compare with `ls dist/assets/index-*.js`.
   A different hash than dist = the user is seeing a stale html entry.
2. **Check the metadata, not just the body**: `curl -sD - -o /dev/null <url>` —
   `cf-cache-status: HIT` + `age:` in hours on `/` is the smoking gun. Origin
   headers (via `127.0.0.1:3011`) prove the mismatch: origin says `no-cache`.
3. **Purge**: `source ~/.config/cloudflare/credentials.env`, zone id in the
   `cloudflare-edge-caching` skill, then
   `POST /zones/<zone_id>/purge_cache` with `{"purge_everything":true}` —
   success:true. Re-probe `/` after a few seconds; the first fetch is MISS and
   the second HIT (fresh entry).
4. **If purges recur**: check the zone ruleset covers HTML (the revalidation
   rule) before reaching for the build-check to paper over a ruleset gap.

## Build-check mechanics (when touching it)

- **Stamp source is git HEAD, not file mtimes.** Stamping by dist/index.html
  mtime fails by construction: vite reads the mtime BEFORE writing the new
  files, so build N ships build N-1's stamp and every deploy triggers two
  reload rounds. Both sides must read the same fact: vite.config.ts injects
  `__ASTRA_BUILD_ID__` (git short hash) via `define`; server `/api/build-id`
  runs the same `git rev-parse`. Same tree → same stamp; no drift.
- **After ANY commit, rebuild**: the bundle stamps the commit that was HEAD at
  build time — a build taken pre-commit stamps the parent, then the fresh
  server stamp differs and every tab reloads once pointlessly. Build AFTER the
  final commit, verify client vs server stamps match (`/api/build-id` vs grep
  the minified bundle for the backticked hash beside the `api/build-id` fetch).
- **Cache key excludes the query string** (measured: `?b=<nonce>` MISSes every
  time = fresh origin fetch). A nonce PATH pins after one fetch; a nonce QUERY
  never pins. Useful for diagnosis fetches; navigation cannot use it.
- Reload strategy: `location.replace` once per new stamp, sessionStorage guard
  keyed by the departed stamp. Failures must stay silent — an unreachable
  server must never reload-loop.

## Related fix in the same class

`/api/hx` GETs: the same zone filters overrode origin no-store and edge-cached
sessions lists per URL (hours-old list). Fix there: minute-epoch `_r=` buster on
the WIRE url that does NOT change the coalescing cache key (see
`src/lib/sessions-cache.ts` normalise()). Same disease, different surface.
