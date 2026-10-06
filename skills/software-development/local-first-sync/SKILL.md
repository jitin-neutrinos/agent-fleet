---
name: local-first-sync
description: "Use when durably logging streams or syncing clients."
version: "1.0.0"
license: MIT
metadata:
  hermes:
    tags: [durable-log, event-sourcing, idempotency, outbox, offline-first, sqlite, wal, replay-cursor, retention, ordering]
    related_skills: [rest-api-design, system-design, test-driven-development, verification-before-completion]
---

# Durable event logs & offline-first sync

The class of work: making a stream or message survive **disconnect, crash, retry
and multiple devices**, without the server or the client lying about what was
saved. Applies to chat transcripts, live token streams, sync engines, background
job logs, anything with a "did my message actually send?" failure mode.

Covers: append-only event logs, server-side idempotency, replay cursors,
truncation signalling, retention gating, and the offline-first client store.

## Procedure

### 1. Establish what is actually durable today — measure, don't assume
Before designing anything, probe the live system: the DB row counts, the
runtime's real library versions, which processes hold the file open, and which
existing tables carry a watermark column. Most "we already persist this" claims
are about the *final* record while the intermediate stream is discarded.

```
lsof <db>                                  # who holds it, from how many processes
<runtime> -e 'print(db.prepare("select sqlite_version() v").get())'
grep -rn "DELETE FROM" <pipeline dir>       # does anything ever purge?
grep -rn "wal_checkpoint" <dir>            # independent checkpointer = different risk class
```

### 2. Write the durability decision down as a named decision
Every one of these is a fork the user should own: retention window, body-vs-
reference split, durability pragma, dependency count. Record the choice, the
measured reason, and what would reopen it. A decision justified by a number that
later fails to reproduce is worse than no number.

### 3. Server: append-only event log, written BEFORE the side effect
- Write to the log **before** pushing to clients / calling upstream. If the
  socket write fails, the log still has the event — that is the whole point.
- Order rows by a sequence number, never a timestamp — but **check whether the
  upstream counter is per-process**. A counter living in the upstream's memory
  resets to 1 on restart, which makes `(id, seq)` collide and `INSERT OR IGNORE`
  silently drop every post-restart chunk. When it resets, put a per-process
  **epoch** in the primary key and keep your own monotonic counter as the replay
  cursor. Refuse to log a frame lacking one: an unorderable row is worse than none.
- Batch writes behind a short coalesce timer (~33ms) and flush at the natural
  boundary (turn/response completion) and on clean process exit.
- Split large vs small payloads: store prose in full, store bulky machine output
  as a **reference** to wherever it is already durable plus a one-line headline.
  Measure which payloads dominate before deciding.
- Each concern gets its **own database file**. Independent lifecycle, independent
  connection, independent purge.

### 4. Server: idempotency before the outbox can become durable
An at-least-once client needs a server-side dedupe store, and it must land
**before** the client's flush is durable. Order inside the write path:

```
claim(key)  ->  side effect  ->  return
```

- `claim` is **one statement** (an INSERT that can hit a UNIQUE constraint). A
  read-then-write check lets two concurrent callers both win.
- On duplicate: acknowledge locally so the client can clear its pending state,
  and **return** — never fall through to the side effect.
- **Any dedupe-store error forwards the message anyway.** Losing idempotency
  costs a rare duplicate; losing the user's message is not recoverable.
- Resolve whatever identifier the client can't know yet (a durable/archive id vs
  a live id) *before* claiming, and backfill it later if learned afterwards.

### 5. Read paths: ordering, resume, and truncation
- Replay is `WHERE seq > :cursor`, ascending. Expose the cursor.
- **A truncation flag is mandatory.** After retention purges rows, the client
  cannot distinguish "never had events" from "your events were deleted" — both
  look like an empty log. Keep a purge watermark so the two are separable.
- **Sparsity is not loss.** An upstream counter counts frames you deliberately do
  not store, so the oldest kept row usually sits far above cursor 0. Testing
  "cursor < min(seq)" reports *every* session as truncated, and a client obeying it
  refetches full history on every load. Only actual deletion sets the flag.
- Reads must **degrade, never throw**: a corrupt row returns a parseable marker
  the client can refetch, not a 500.

### 6. Retention
Gate on an ingestion watermark, not age alone: purge only what downstream
consumers have already taken. Capture the purge boundary **before** the delete.
`auto_vacuum` must be set at CREATE time (it cannot be changed once tables exist)
or purge frees pages into a freelist the file never returns.

**The scheduled sweeper runs dry-run by default and is gated behind an explicit
enable.** Deletion is irreversible; an unattended timer that starts purging on its
own is how data disappears without anyone choosing it. The timer reports what it
would remove and removes nothing until the enable is deliberately flipped. Enable
`secure_delete` (or VACUUM) so freed pages are overwritten, not left readable.
Delete child rows with the parent, and prove no orphans remain.

### 7. Client: local store is a cache and an outbox, never the archive
Write user messages locally first, flush on reconnect, and treat the server as
the source of truth. Use IndexedDB for anything large (localStorage is
synchronous, string-only, ~5 MiB, and unavailable to workers). Multi-tab sync via
BroadcastChannel. **Do not build on Service Worker Background Sync** — verify
current support for your actual mobile target first; it is Chromium-desktop only
in practice.

**Re-run the pre-existing per-tab/multi-surface checks after making storage
durable.** IndexedDB is shared by every tab on the origin, so a change that looks
like a pure durability win can silently reintroduce whatever cross-tab bug an
earlier per-tab design was avoiding. Stamp a per-tab owner id, filter on it, and
keep **unowned rows adoptable** so a crash between write and ownership-stamp never
orphans a pending message. Write ownership once — never let a second tab steal it.

### 8. Verify at three levels, and prove each
1. **Unit** — the store's semantics, including a concurrency race.
2. **Wiring** — the interception *decision* as a pure function over real frame
   shapes, plus non-intercepted frame types, malformed input, and a throwing
   dependency.
3. **Live E2E** — real auth, real socket, real traffic, then read the store back
   independently and compare byte-for-byte.

## Pitfalls

- **Truncating stored JSON at a byte offset produces unparseable data**, which
  then crashes the READ path — a degradation that becomes an outage. Shrink
  fields and always emit valid JSON; never slice mid-token.
- **`PRAGMA synchronous` is per-connection.** Setting it on a second connection
  changes nothing about the writer, so a benchmark reports "no difference"
  because both runs were identical. Apply it on the writing connection and read
  it back.
- **A throughput figure from research rarely transfers.** A per-row-autocommit
  number does not predict a batched writer. Re-measure against the real writer;
  if the claim does not reproduce, report the honest number and say why it differs.
- **`WITHOUT ROWID` tables have no `rowid`.** A `WHERE rowid IN (...)` purge
  subquery silently matches nothing — retention becomes a no-op that still
  reports success.
- **A version number is not a safety level.** Newer runtime can bundle an older
  library. Assert the library version, not the runtime version.
- **An E2E "PASS" that asserted nothing.** If the fixture was unauthenticated or
  returned no frames, absence-of-failure reads as success. Always assert the
  fixture was *live* (frames returned, status 101) alongside the behaviour under
  test.
- **When a check fails, decide whether the CODE or the TEST is wrong** — and fix
  the code when the failure exposes real dead code. Loosening the assertion to
  green hides the finding. Equally, a correct guard firing (a throttle skipping a
  call) means the *test* needs an explicit seam, not a weakened guard.
  - **Verify which side is wrong before changing either.** A test that builds an
    impossible fixture (a fixed past-epoch timestamp that a retention window
    correctly hides; two rows sharing a value the engine guarantees is unique;
    a miscounted turn) reports a fabricated product bug. Reproduce the
    implementation's real output first — if it is right, the fixture is wrong.
    Count how often you assumed the code was broken before checking; in one build
    pass this happened roughly eight times and only the fixtures were at fault.
  - **Assert the CONTRACT, not an arbitrary outcome of your fixture.** When a
    tie or coincidence decides the result, assert order-independence and a stable
    position rather than hard-coding whichever row won alphabetically.
  - **Prefer computing an expected value over hand-counting one.** A hard-coded
    byte count becomes a wrong assertion the moment the envelope changes.
- **Never ship an unused export.** Grep for a new helper's call sites; dead
  exports with correct-looking doc comments are a trap for the next reader.
- **A partial-write helper may CREATE the row it updates.** Upsert-shaped APIs
  ("set partial fields on row X") silently insert when X does not exist, so
  tagging ownership on an id you do not own conjures a phantom pending message.
  Assert existence before the write, and assert the row is absent afterwards.
- **Literal route paths before parameterized ones.** `/stream/stats` matched
  `/stream/<sid>` and answered a session read to a stats request. Order
  registrations most-specific-first, and reject reserved segments as ids.
- **A late-arriving row splits the turn of the OTHER kind, not its own.** When
  locating where an out-of-order row belongs, check whether it falls inside ANY
  existing span before looking for same-kind neighbours: a user message arriving
  late lands inside the assistant turn it interrupts, so a same-kind-only scan
  reports "no split" for precisely the case that needs one.
- **Boundary insertion must take the LAST neighbour it sorts after, not the
  first.** Returning on the first match places a trailing row mid-transcript.
- **A rendered-UUID string slices at its dashes.** Hex fields live at `[0:8]`,
  `[9:13]`, `[14:18]`; slicing `[8:12]` yields `"-4a4"`, and `parseInt` on that
  returns a negative number that reads exactly like an encoder bug. Assert the
  timestamp round-trips rather than trusting a field-position regex.
- **Shared repos:** check `git status` for files other sessions are mid-edit and
  build in new files plus surgical edits to files that are clean. Confirm again
  immediately before editing — a clean file can become dirty mid-session.
- **Pinning a regression guard means re-checking its numbering.** Sibling sessions
  claim ids concurrently; read the manifest before adding a row and place yours
  after theirs rather than overwriting.

## References

- `references/sqlite-durability.md` — WAL-reset bug exposure test, pragma
  trade-offs measured on real hardware, `auto_vacuum`/`WITHOUT ROWID` mechanics.
- `references/ordering-and-idempotency.md` — choosing a total order, why client
  wall-clock is unusable, replay/truncation protocol shapes, outbox patterns.
