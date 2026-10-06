---
name: hermes-messaging-triage
description: "Use when a Hermes chat channel stops responding."
version: 1.0.0
---

# Hermes messaging channel triage

Procedure for 'my chat with Hermes is not responding'. Diagnose from logs first, classify, probe the platform directly, clean up, verify. Do not restart the gateway as a first move.

## Procedure

1. **Confirm what is running.** `systemctl --user list-units '*hermes*' --no-pager` and `pgrep -af hermes`. kurama-core runs TWO gateways: the default profile (`hermes-gateway.service`, Telegram live here) and the ops profile (`hermes-gateway-ops.service`, telegram off). A running ops gateway is not evidence the user's channel is alive.

2. **Read the right log.** Main profile: `~/.hermes/logs/gateway.log`. Ops profile: `~/.hermes/profiles/ops/logs/gateway.log`. Crash history: `gateway-exit-diag.log`. First pass:
   ```bash
   grep -iE "flood|error|Sending response|inbound message|connected" ~/.hermes/logs/gateway.log | tail -30
   ```
   The log records inbound messages, sends, and every refused send — this alone usually classifies the failure.

3. **Classify:**
   - `flood control ... Retry in NNN seconds` → Telegram-side mute, see `references/telegram-flood-control.md`. NOT a local fault.
   - Repeated disconnect/connect cycles or `SystemExit` in gateway-exit-diag.log → crash/restart loop, check exit codes and restart notifications before touching the service.
   - `409 Conflict` / polling terminated → second consumer on the same bot token (duplicate gateway, another host, webhook mode).
   - No sends attempted at all → gateway never saw inbound; check service status and pairing/allowlist warnings.

4. **Probe the platform directly before concluding anything.** Local logs show what the bot TRIED; only a direct API call shows whether the channel accepts it now:
   ```bash
   TOKEN=$(grep -oP "^TELEGRAM_BOT_TOKEN=\K.*" ~/.hermes/.env | tr -d "\"'")
   curl -s "https://api.telegram.org/bot${TOKEN}/sendMessage" -d "chat_id=<chat_id>" -d "text=channel probe $(date +%H:%M:%S)"
   ```
   Keep the token in a shell variable — never echo it. A `"ok":true` reply means the channel is open (mute lifted); retrying the identical text once also rules out duplicate-content refusal.

5. **Clean stuck redelivery rows.** Failed sends live in the `delivery_obligations` table in `~/.hermes/state.db`; rows in `failed` state are re-claimed and re-sent on every gateway restart (cap 3 attempts). Stale rows with `flood_control:*` in `last_error` must be marked `abandoned` before any restart, or old status pings fire at the user hours later.

6. **Verify the round trip, then report.** After recovery, confirm in gateway.log: an `inbound message` line, a `response ready` line, a `Sending response` line, and NO new flood/refusal lines after it. Report to the user in plain language: what was muted, that it self-healed, what the recurring cause was, and offer to slow the cause (see reference).

## Pitfalls

- Never restart the gateway repeatedly while a flood mute is active — every restart re-claims failed delivery rows and re-pokes the platform API, which extends the mute instead of waiting it out. Clean the rows first (step 5).
- The `sqlite3` CLI is not installed on kurama-core. Use `python3` with the stdlib `sqlite3` module for all state.db work.
- Low send volume does not rule out flood control. Background progress pings with near-identical text every few minutes for hours trip Telegram's limiter even at ~25–60 sends/day. Judge the PATTERN (repetitive text, sustained cadence), not the daily count.
- `getChat` succeeding proves nothing about send permission — it is a read. Only a real `sendMessage` probes the mute.
- Web-UI chat variant: a turn that 'disappears' while the gateway is healthy usually means a tool call sat on an approval-consent prompt until timeout — the transcript carries `BLOCKED ... The user has NOT consented` results and the visible reply is lost. The consent popup is not reliably delivered to the web-UI client, so the turn stalls invisibly. Surface the pending action (or have the user flip /yolo), and never requeue the blocked call — consent blocks forbid retrying the same command.
