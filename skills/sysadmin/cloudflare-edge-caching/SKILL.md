---
name: cloudflare-edge-caching
description: "Use when optimizing Cloudflare CDN edge caching."
---

# Cloudflare edge caching (kurama-core)

All jitinnair.com hostnames ride the `jitinnair-personal` Cloudflare tunnel. This skill covers the CDN/edge caching layer — what happens after traffic reaches Cloudflare's edge.

## Credentials

Stored at `~/.config/cloudflare/credentials.env` (chmod 600):
```
CLOUDFLARE_API_TOKEN=...
CLOUDFLARE_ACCESS_KEY_ID=...
CLOUDFLARE_SECRET_ACCESS_KEY=...
```
Source before API calls: `source ~/.config/cloudflare/credentials.env`

Zone ID for jitinnair.com: `52a4d6a1d562826ff02bc51efd56c963`

## Workflow — edge caching audit + implementation

### 1. Check current cache status
```bash
curl -sI https://<host>/ | grep -i 'cf-cache-status\|cache-control\|cdn-cache'
curl -sI https://<host>/_next/static/chunks/<file>.js | grep -i 'cf-cache-status\|cache-control'
curl -sI https://<host>/_next/image?url=%2F<asset>.png&w=640&q=75 | grep -i 'cf-cache-status\|cache-control'
```
- `cf-cache-status: HIT` = served from edge cache (good)
- `cf-cache-status: DYNAMIC` = hit origin every time (needs cache rule)
- `cf-cache-status: REVALIDATED` = cached but revalidated (short TTL)

### 2. Set origin cache headers (Next.js)
In `next.config.mjs`:
- `CDN-Cache-Control` header on all routes — tells Cloudflare how to cache at edge
- `Cache-Control: public, max-age=31536000, immutable` for static assets (images, fonts)
- `images.minimumCacheTTL: 31536000` — 1-year cache for optimized images
- `images.formats: ['image/avif', 'image/webp']` — modern formats

### 3. Edit the zone cache ruleset (cache rules API)
The `http_request_cache_settings` entrypoint is a MANAGED ruleset: **PUT replaces the
ENTIRE rules array** — always GET the current entrypoint first, save a backup JSON,
and PUT back the full array (existing rules + your new one). POST to this endpoint is
not the write path. Rules execute in array order (first match wins), so bypass rules
must sit ABOVE the catch-all.

Baseline rule order for the jitinnair.com zone (proven set — keep this shape when
editing):
1. `starts_with(http.request.uri.path, "/api/")` → `{"cache": false}` (bypass;
   auth-gated per-user JSON must never sit in the edge).
2. HTML revalidation for `astra.*`/`test.*` hosts: GET/HEAD, not `/api/`, and
   `not (http.request.uri.path contains ".")` (dotless path = document; dotted =
   hashed asset) → cache true, edge/browser TTL override 60s. Deploys become visible
   within a minute without giving up asset caching.
3. Catch-all cache-everything for GET/HEAD on `*jitinnair.com` → override_origin
   31536000. Keep this scoped to GET/HEAD and to the zone's hosts.

```bash
curl -s -X PUT \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/zones/<zone_id>/rulesets/phases/http_request_cache_settings/entrypoint" \
  -d @backup-plus-new-rule.json
```

After ANY ruleset change: `POST /zones/<zone_id>/purge_cache` with
`{"purge_everything":true}` — new rules do not evict existing entries.

### 4. Verify
```bash
curl -sI https://<host>/ | grep 'cf-cache-status'
# Should show HIT after first request populates cache
```

## Pitfalls

- **API token permissions**: Creating cache rules requires `Zone / Zone / Edit` + `Zone / Cache Rules / Edit` (or `Ruleset / Ruleset / Edit`). A token with only zone-read permissions will fail with `10405: Method not allowed for this authentication scheme`. Check with `curl -s -H "Authorization: Bearer $TOKEN" https://api.cloudflare.com/client/v4/user/tokens/verify`.
- **Wirefilter limits on non-Business plans**: the `matches` operator is Business/WAF-Advanced only (`not entitled` error on PUT). Classify dotless-path-vs-asset with `not (http.request.uri.path contains ".")` instead. `http.request.method` is a plain string field — write `http.request.method in {"GET" "HEAD"}`; an `any(...)`/index form fails to parse.
- **Ruleset changes propagate lazily per PoP**: immediately after a PUT + purge, one PoP can still serve a cached entry (a bypass rule reads as HIT for minutes). Re-probe before concluding a rule is wrong, and re-run the verification after the lag clears.
- **Proving a cache fix with a bogus cookie proves nothing**: Cloudflare does not cache 401s, so an unauthenticated probe shows BYPASS even when the authed 200 IS cached. Verify authed GETs (real login, cookie jar) — that is the traffic class the cache actually poisons.
- **Access key pair ≠ API token**: `X-Auth-Key` / `X-Auth-Secret` headers are for legacy Global API Keys, not API tokens. Don't mix them.
- **Stale chunks after rebuild**: `next build` renames chunk files. The running `next start` server still references old chunks → `ChunkLoadError` + `ERR_BLOCKED_BY_CLIENT`. Always restart the server after rebuild. Enumerate with `ss -tlnp | grep <port>` and kill by PID.
- **CDN-Cache-Control alone is not enough**: The header tells Cloudflare *how* to cache, but a Cache Rule with "Cache Everything" is what actually makes it cache HTML. Without the rule, HTML stays `DYNAMIC`.
- **Image optimizer TTL**: Next.js defaults to `max-age=60, must-revalidate` for optimized images. Set `minimumCacheTTL: 31536000` in `images` config or every image revalidates at the edge every minute.
- **Static asset pattern**: Use `headers()` in next.config with a regex like `/(.*)\.(png|jpg|jpeg|gif|webp|avif|svg|ico|woff2?|ttf|eot)` to apply immutable caching to all static assets.
- **override_origin beats origin headers.** When the zone's catch-all rule sets an edge TTL override (this zone's does), origin `no-store`/`max-age` headers are IGNORED at the edge for covered hosts — an origin-side cache fix alone never protects mutable files there. Levers: a dedicated higher-priority cache rule for the host, or purge after every content change; verify with cache-busted requests (`?nocache=$(date +%s)`), because a plain curl happily reads the poisoned entry and sends you debugging a healthy origin.

## Relationship to tunnel hosting

See `cloudflare-tunnel-hosting` for tunnel ingress config, DNS routing, and restart hygiene. This skill covers the caching layer on top of the tunnel.