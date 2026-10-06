# Telegram flood control — mechanism and recovery

## What a flood mute is

Telegram answers sends over its rate budget with HTTP 429 (`Retry after NNN seconds`). Hermes' adapter fails closed for penalties over its inline cap (~60s): it logs `flood_control:<wait>` and returns a typed failure so the delivery ledger owns the retry. Penalties typically run 300–600s.

## Amplification loop (why mutes stretch for hours)

1. A send is refused → row lands in `delivery_obligations` with `state='failed'`, `last_error='flood_control:NNN'`.
2. Gateway restart (or reconnect recovery) re-claims failed rows and re-sends them.
3. Every send attempt during a mute pokes Telegram, and Telegram extends/refreshes the penalty.
4. Meanwhile new background completions queue fresh sends.

Result: the mute never gets quiet time to expire. Breaking the loop = stop new sends (pause the pinging background job if possible) + mark stale failed rows `abandoned` + WAIT, rather than restart.

## Common causes on this host

- **Watch-pattern notifications**: background job completions inject synthetic turns into the Telegram session; each injected turn produces a reply in the user's DM. A job that pings progress every few minutes generates a sustained stream.
- **Near-identical repeated text** (`147/195 batches… next ping in ~9 min` style) — Telegram's spam heuristics weigh duplicate content, not just volume.
- **Startup budget burn**: `set_my_commands` registration (60 commands) plus restart notifications all fire at connect time; a restart during a mute burns budget immediately.
- **Streaming text-batch flushes**: streamed replies flush in small batches; each flush is an API call against the same budget.

## Cleanup SQL (python3, no sqlite3 CLI)

```python
import sqlite3, time
db = sqlite3.connect('/home/notjitin/.hermes/state.db')
cur = db.execute("""
  update delivery_obligations
  set state='abandoned', updated_at=?,
      last_error = last_error || ' | manually abandoned: stale after flood recovery'
  where platform='telegram' and state='failed'
""", (time.time(),))
db.commit()
print('abandoned:', cur.rowcount)
```

Ledger states: `pending` (never sent), `attempting` (in flight), `failed` (rejected; retry boundary), `delivered` (pruned), `abandoned` (exhausted/stale). `attempts` caps at 3; rows older than the staleness cutoff become `abandoned` automatically on the next claim — manual abandonment just does it now instead of after the next restart.

## Recovery expectations

- The mute self-heals once the send storm stops; do not restart to 'fix' it.
- Direct-probe sequence: `getMe` (token valid) → `sendMessage` probe (mute status) → identical resend (duplicate-content refusal). All `"ok":true` = channel open; then verify the gateway's own next send lands (no new flood lines in gateway.log).
- If the cause is a background job's ping cadence, the durable fix is slowing/batching that job's notifications — otherwise the mute recurs on the same pattern.
