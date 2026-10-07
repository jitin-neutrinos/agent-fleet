# WebSocket connection churn — layer table and log signatures

Depth for SKILL.md §12. Read this when a connection complaint needs attributing to a
layer, or when a fix appears not to have landed on the device.

## The four layers, and what proves each one healthy

| Layer | Where it lives | Healthy proof |
|---|---|---|
| Page client | `src/lib/ws-engine.ts` | one `create`+`open` in the browser log, no closes over minutes |
| Native legs | `android/…/NtfyPushService.kt` | `ws-upgrade` UAs show `okhttp/…` connecting ~per app lifecycle, not per second |
| Proxy relay | `server/hermes-proxy.mjs` | `ws-open`/`ws-close` balance; `peers=` flat |
| CF edge + tunnel | `~/.cloudflared/*.yml`, zone cache rules | `ws-liveness-probe.mjs <host>` survives 100s+ |

A raw probe passing on BOTH local and tunnel endpoints while the app still churns
means layers 3 and 4 are clean — the fault is in 1 or 2. Do this before editing
server code; it is the difference between a two-minute answer and an hour of
speculative server changes.

## Log line shapes to grep

```
ws-upgrade filter=<0|1> since=<n|-> device=<tag|-> ua=<user agent>
ws-open    peers=<n> at=<iso>
ws-close   peers=<n> at=<iso>
ws-reap    peers=<n> dev=<tag|-> f=<0|1> lq=<iso> at=<iso>
```

- `filter=1` is the `?filter=complete` native background leg; `filter=0` is a page leg.
- `device=` is only populated when a client sends `?device=`. Absent means the client
  does not tag itself — add the tag if you need per-device attribution.
- `lq` is the socket's last pong. `lq == the socket's open time` means it never ponged
  once. Comparing `lq` to the open timestamp is the single most informative reading.

## Counting churn per minute

```bash
journalctl --user -u astra-webui.service --since "30 minutes ago" --no-pager \
  | grep "ws-upgrade" | awk '{print $3}' | cut -d: -f1,2 | uniq -c
```

Tens per minute on a single filter = a reconnect loop. One or two = normal lifecycle.
The per-minute histogram also shows exactly WHEN a fix took effect, which is how you
confirm a phone actually restarted onto the new build.

## Deployment gaps that look like the bug persisting

- Web deploy carries only `dist/` + `server/*.mjs`. Kotlin/manifest changes need
  `tools/deploy.sh android` plus an on-device install.
- `tools/deploy.sh android`'s native-change check keys on COMMITTED diffs. An
  uncommitted Kotlin edit means the gradle rebuild is skipped with a message saying
  the APK is current. Commit, then deploy.
- Installing an APK does not restart the running service process. The old socket
  behaviour persists until the app is force-stopped, so always re-measure after a
  force-stop rather than concluding the fix failed.
- Confirm which build the device is running: `curl -s https://<host>/api/build-id`
  and compare against the commit you shipped.

## Interval relationships (the arithmetic that causes phantom reaps)

| Setting | Wrong | Right | Why |
|---|---|---|---|
| Server reap threshold | 30s with a 30s ping | 65s | zero grace: a pong seconds late reaps a healthy socket |
| Client ping (OkHttp) | 60s | 20s | must be shorter than the server ping round, else it straddles two |
| Wake/zombie probe deadline | 3s | 8s | a tunnel RTT spike past the deadline kills a healthy socket |
| Backoff reset on open | always | only if last socket lived ≥5s | instant-die loops otherwise pin at the base delay forever |
