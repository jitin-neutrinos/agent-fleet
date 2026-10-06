# agent-fleet observability

One system, three pieces — the store keeps itself honest and phones home.

```
 desktop (master)                          laptop / future nodes
 ┌──────────────────────────┐   scp (key) ┌──────────────────────────┐
 │ sync timer (6h)          │◀───────────│ update timer (6h)        │
 │   └─ fleet-health.sh     │  node json │   └─ update.sh           │
 │ health timer (hourly)    │            │        └─ node-report.sh │
 │ status-server.py :8003   │            └──────────────────────────┘
 └──────────┬───────────────┘
            ▼ Telegram (@Astral_Hermes_Alerts_bot) + web page
```

## Colours

| Colour | Meaning |
|---|---|
| 🟢 green | sync fresh (≤7h), repo == origin, installer site hash matches (local + public), timers up, store sane, every node reported ≤8h and is conformant |
| 🟡 yellow | late sync (7–14h), node quiet 8–30h, node store behind origin, node skills ≠ store, telegram delivery failing |
| 🔴 red | sync stale >14h, repo != origin, github unreachable, installer site down/mismatch, timer/service down, store near-empty, node silent >30h |

Only colour *changes*, store updates and the daily heartbeat are posted to Telegram —
no spam, no green noise.

## Files

| File | Where | Role |
|---|---|---|
| `fleet-health.sh` | master (kurama-core) | evaluate everything, write `~/agent-fleet-health/status.json` + `health.log` (5-day), notify Telegram |
| `node-report.sh` | every pull-node | collect local state → push `node-<name>.json` to master over SSH (key-based, no secrets on the node) |
| `status-server.py` | master, `:8003` | install.sh public + auth-gated status page / status.json / log dump |

Config (not in this repo, never committed): `~/.config/agent-fleet/health.env` (0600).
Master keys: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `STATUS_USER`, `STATUS_PASS`.
Node keys: `NODE_NAME`, `MASTER_SSH`.

## Wiring

- Desktop: `agent-fleet-health.timer` (hourly) runs `fleet-health.sh`; `sync-from-desktop.sh`
  stamps `~/agent-fleet-health/state/last-sync-success` and runs the checker after every sync.
- Nodes: `update.sh` ends with `node-report.sh` — every update cycle pushes a fresh report.
- Installer: `install.sh` runs `node-report.sh` at the end when a node is configured, and the
  status page verifies the served install.sh hash against the repo (the site is monitored too).

Web: `https://harness.jitinnair.com/` (basic auth) · `/logs` for the dump · `/install.sh` stays public.

## Manual use

```bash
bash health/fleet-health.sh            # one check, real notification behaviour
bash health/fleet-health.sh --selftest # resolve the chat + send a test message
bash health/node-report.sh             # push one report from this node
curl -u admin:$STATUS_PASS localhost:8003/status.json | jq
```

Telegram notes: a bot cannot open a conversation with a user — the owner must press START
in @Astral_Hermes_Alerts_bot (or add the bot to a channel) once. Until then sends fail with
"chat not found" and the check reports it as a yellow issue. The sender then auto-discovers
the chat from pending updates and wires it (a "✅ wired" message confirms). The resolved chat
is remembered in `~/agent-fleet-health/state/telegram-chat-id`.

