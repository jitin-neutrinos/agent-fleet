---
name: cloudflare-tunnel-hosting
description: "Use when exposing a web app via the Cloudflare tunnel."
---

# Cloudflare tunnel hosting (kurama-core)

Multiple named tunnels serve this host, each with its own yml and its own
process. Identify the LIVE one before any edit — `ps aux | grep cloudflared`
shows each running process's `--config <path>`:
- ingress config: the per-tunnel yml named on the running process (back it up first)
- ingress changes hot-reload: `kill -HUP <cloudflared-pid>` — adding or re-pointing
  a hostname needs no restart; a full unit restart blips ALL hostnames on that
  tunnel and is for credential/tunnel-level changes only
- when re-pointing, KEEP the old hostname's ingress entry alongside so existing
  links never 404
- journal: `journalctl --user -u <unit> --since "-15 min"` — origin dial failures
  and stream errors land here; tunnel-disconnected errors are edge-side only

## Workflow — adding / re-pointing a hostname
1. Edit `~/.cloudflared/config.yml`: add the `hostname → service:` entry BEFORE the 404 catch-all. Additive edits only — never disturb other hostnames. Back up first.
2. Route DNS: `cloudflared tunnel route dns <tunnel-id> <hostname>` (the tunnel id is the `tunnel:` line at the top of config.yml). Ingress alone is NOT enough — without the CNAME the hostname never reaches the tunnel.
3. Hot-reload: `kill -HUP <cloudflared-pid>` (pid via `ps aux | grep cloudflared`). Full unit restart only for credential/tunnel-level changes — it blips every hostname on the tunnel.
4. Verify from the outside: `curl -sI https://<host>/<known-open-endpoint>` — pick a deterministic endpoint; auth-gated pages may legitimately 401/redirect.
5. If the zone has a catch-all cache rule, purge the zone cache after go-live — the pre-HUP window's responses (typically 404s) were already cached under the long edge TTL and otherwise serve stale for a year. Probe with cache-busted query strings (`?nocache=$(date +%s)`).

## Edge caching

See `cloudflare-edge-caching` for CDN cache rules, origin cache headers, and edge TTL configuration. The tunnel gets traffic to Cloudflare's edge; the caching layer controls what the edge stores.

## Credentials
- API token: `~/.config/cloudflare/credentials.env` (CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCESS_KEY_ID, CLOUDFLARE_SECRET_ACCESS_KEY)
- Zone ID for jitinnair.com: `52a4d6a1d562826ff02bc51efd56c963`
- Cache rule: "Cache Everything" for all of jitinnair.com (covers test.jitinnair.com), edge TTL 1 year, browser TTL 1 year

## Cache rules — two traps

- **A NEW hostname inherits the zone catch-all and caches HTML for a year.**
  With `cache_level=aggressive` the catch-all pins every response — including
  `index.html` — at a 1-year edge TTL. Deploy a new bundle behind such a
  hostname and users load the OLD one indefinitely (symptom: a working feature
  "disappears", or a page shows EMPTY because the stale bundle calls APIs that
  have since changed/401'd). Fix: add the hostname to the short-TTL
  HTML-revalidation rule in the zone's `default` cache ruleset (phase
  `http_request_cache_settings`), then purge `/` + `/index.html`.
- **`PUT /zones/<zone>/rulesets/<id>` REPLACES every rule in the ruleset.**
  GET the ruleset first and resend ALL existing rules plus your change; a PUT
  with only the new rule silently deletes the others (it clobbered the zone's
  catch-all + HTML-revalidation + /api-bypass rules in one call). Recoverable:
  `GET /zones/<zone>/rulesets/<id>/versions` then `/versions/<n>`, restore from
  there. Never PUT a ruleset you have not just GET.

## Rules that save debugging time
- **Ingress `service:` must use explicit `http://127.0.0.1:<port>`** — `localhost` may resolve to `[::1]`; the journal then shows `dial tcp [::1]:<port>: connect: connection refused` bursts that look like flaky downtime.
- **Never use quick `trycloudflare` tunnels from this network** — they register but return edge 404. Use the named tunnel for anything the user must reach.
- **cloudflared REPLACES any origin 5xx response body with its own plain-text `error code: 502` page** (HTML variant for browsers). Client-side symptom: JSON parse failures like `Unexpected token '<', "<!DOCTYPE "`. Apps behind the tunnel must express user-facing errors as 4xx (422 for "cannot process this input"); every status <500 passes through body-intact.
- **Layer isolation for "works locally, breaks publicly"**: send the identical request directly to the origin (`curl http://127.0.0.1:<port>/…`) and through the public URL; compare status + body. NOTE: cookies bound to the public domain are not sent to 127.0.0.1 — pass the session cookie manually (`-H "Cookie: name=value"`) when the endpoint is auth-gated.
- **Flush the local resolver cache before declaring a new hostname's DNS broken:** a freshly routed hostname still answers NXDOMAIN from systemd-resolved's negative cache for minutes (`curl` → HTTP 000 "Could not resolve") while `dig @1.1.1.1` already has it. `resolvectl flush-caches`, then re-test — the tunnel is usually already live.
- **Restart hygiene**: many app servers (Next.js `next start`) rename their argv (`next-server (vX)`), so `pkill`/`pgrep` by name misses stale instances. Enumerate with `readlink /proc/<pid>/cwd`, kill matches, then require exactly ONE listener (`ss -tlnp | grep <port>`) before declaring success. A stale instance + newer build on disk produces mixed-version flakiness that mimics app bugs.
