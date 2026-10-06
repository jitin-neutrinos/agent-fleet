---
name: cloudflare-tunnel-hosting
description: "Use when exposing a web app via the Cloudflare tunnel."
---

# Cloudflare tunnel hosting (kurama-core)

All public hostnames (neutrinos-mcp, astra, neutrinos-designer, agent-fleet, vdloader, …) ride ONE named tunnel:
- systemd user unit: `neutrinos-mcp-tunnel.service` — restart with `systemctl --user restart neutrinos-mcp-tunnel.service` (blips ALL hostnames briefly; do it deliberately)
- ingress config: `~/.cloudflared/config.yml` (back it up before edits)
- journal: `journalctl --user -u neutrinos-mcp-tunnel.service --since "-15 min"` — origin dial failures and stream errors land here; tunnel-disconnected errors are edge-side only

## Workflow — adding / re-pointing a hostname
1. Edit `~/.cloudflared/config.yml`: add the `hostname → service:` entry BEFORE the 404 catch-all. Additive edits only — never disturb other hostnames. Back up first.
2. Route DNS: `cloudflared tunnel route dns <tunnel-id> <hostname>` (the tunnel id is the `tunnel:` line at the top of config.yml). Ingress alone is NOT enough — without the CNAME the hostname never reaches the tunnel.
3. Restart the unit (above).
4. Verify from the outside: `curl -sI https://<host>/<known-open-endpoint>` — pick a deterministic endpoint; auth-gated pages may legitimately 401/redirect.

## Edge caching

See `cloudflare-edge-caching` for CDN cache rules, origin cache headers, and edge TTL configuration. The tunnel gets traffic to Cloudflare's edge; the caching layer controls what the edge stores.

## Credentials
- API token: `~/.config/cloudflare/credentials.env` (CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCESS_KEY_ID, CLOUDFLARE_SECRET_ACCESS_KEY)
- Zone ID for jitinnair.com: `52a4d6a1d562826ff02bc51efd56c963`
- Cache rule: "Cache Everything" for all of jitinnair.com (covers test.jitinnair.com), edge TTL 1 year, browser TTL 1 year

## Rules that save debugging time
- **Ingress `service:` must use explicit `http://127.0.0.1:<port>`** — `localhost` may resolve to `[::1]`; the journal then shows `dial tcp [::1]:<port>: connect: connection refused` bursts that look like flaky downtime.
- **Never use quick `trycloudflare` tunnels from this network** — they register but return edge 404. Use the named tunnel for anything the user must reach.
- **cloudflared REPLACES any origin 5xx response body with its own plain-text `error code: 502` page** (HTML variant for browsers). Client-side symptom: JSON parse failures like `Unexpected token '<', "<!DOCTYPE "`. Apps behind the tunnel must express user-facing errors as 4xx (422 for "cannot process this input"); every status <500 passes through body-intact.
- **Layer isolation for "works locally, breaks publicly"**: send the identical request directly to the origin (`curl http://127.0.0.1:<port>/…`) and through the public URL; compare status + body. NOTE: cookies bound to the public domain are not sent to 127.0.0.1 — pass the session cookie manually (`-H "Cookie: name=value"`) when the endpoint is auth-gated.
- **Flush the local resolver cache before declaring a new hostname's DNS broken:** a freshly routed hostname still answers NXDOMAIN from systemd-resolved's negative cache for minutes (`curl` → HTTP 000 "Could not resolve") while `dig @1.1.1.1` already has it. `resolvectl flush-caches`, then re-test — the tunnel is usually already live.
- **Restart hygiene**: many app servers (Next.js `next start`) rename their argv (`next-server (vX)`), so `pkill`/`pgrep` by name misses stale instances. Enumerate with `readlink /proc/<pid>/cwd`, kill matches, then require exactly ONE listener (`ss -tlnp | grep <port>`) before declaring success. A stale instance + newer build on disk produces mixed-version flakiness that mimics app bugs.
