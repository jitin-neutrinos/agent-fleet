---
name: astra-webui-architecture
description: "Use when changing astra-webui streaming, storage, ordering."
version: "1.0.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [astra-webui, architecture, streaming, persistence, sqlite, ordering, sync, storage]
    related_skills: [astra-webui-performance, astra-webui-regression-fixes, grounded-citations]
---

# Astra WebUI — server/client architecture

Class-level rules for the parts of `~/Work/projects/astra-webui` that own DATA:
the streaming relay, the server databases, client persistence, and message
ordering. Perf/layout work is `astra-webui-performance`; deploy and bug
recurrence is `astra-webui-regression-fixes`.

Connection-layer depth (log signatures, the four-layer attribution table, interval
arithmetic, deployment gaps) is in `references/connection-churn.md`; the raw
client-vs-server isolation probe is `scripts/ws-liveness-probe.mjs`. The five-layer
cross-chat isolation audit (per-tab identity, wire ownership, event filter,
stale-reply guard, queue flush) lives in the pitfalls section.

## The shape, in one paragraph

`hermes-proxy.mjs` is a RELAY, not a store. It receives frames from the Hermes
gateway and writes them to browser sockets. Everything the gateway owns lives in
`~/.hermes/state.db`. Everything Astra owns lives in `server/*.mjs` modules over
`data/astra-training.db`. If a frame is not appended by Astra before the socket
write, it does not exist on this side.

## always-on rules

### 1. Measure the database; never assert its contents
There may be no `sqlite3` CLI on the host. Node's built-in `node:sqlite` is the
reliable probe — it is stdlib, so it works inside a zero-dependency server too:

```bash
node --input-type=module -e "
import { DatabaseSync } from 'node:sqlite';
const db = new DatabaseSync('file:/abs/path.db?mode=ro', { readOnly: true });
console.log(db.prepare('SELECT count(*) c FROM messages').get().c);
console.log(db.prepare('PRAGMA journal_mode').get());
"
```

Use the `file:…?mode=ro` URI form for a database owned by another service. Probe
row counts, per-role byte averages and top-N by size — averages decide whether a
storage proposal is affordable, and they routinely invert the naive intuition
(tool rows dominate assistant rows in both count and bytes).

### 2. Persist inside `broadcastFrame`, BEFORE the socket write
`server/hermes-proxy.mjs` `broadcastFrame()` is the single funnel for every
upstream frame. Anything durable must be appended there before `s.write(frame)`.
Writing after the socket write loses frames to any error in between; writing from
a different module means a second copy of the parse.

### 3. Order by id, never by timestamp
Upstream orders messages by `messages.id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
and says why in its own docstring: clocks regress. `timestamp` is display
metadata only. Every messaging platform that survives multi-device clients
assigns order server-side; client wall-clock is never the key, because a phone
whose clock drifts places messages wrongly. Sort committed rows by `(seq, id)`,
optimistic local rows by `(client_uuid, id)`, and rank committed ahead of
optimistic — never by a client-provided time value.

### 4. Treat client storage as a CACHE and an OUTBOX, never the archive
The Android shell loads the LIVE origin (`capacitor.config.ts` `server.url`), so
phone and desktop share one quota — and each WebView is still its own storage
partition, so N devices are N independent caches, never one shared store.
`navigator.storage.persist()` cannot be relied on in a WebView shell (the
underlying heuristic needs a bookmarkable origin a WebView does not have); treat
it as a hint and record `persisted()` for diagnostics only. Server stays
authoritative; local loss must degrade to a slow first paint, never data loss.

### 4.1 A queued prompt records its target session; the flush matches that target, never the connector

The offline queue is the one send path that crosses a chat switch: a prompt queued
while chat A was open survives a switch to chat B, and the flush fires whenever any
session's create/resume reply lands. A flush filter shaped "everything not
explicitly targeting a DIFFERENT session" sends chat A's queued text into B's
freshly minted session — typed in A, answered in B (the Android shape: offline →
queue → chat switch → reconnect).

- A resume-mode row carries `sessionId` = the stored sid CAPTURED AT ENQUEUE TIME;
  it flushes only on a reply whose sid equals it. A missing sessionId on a resume
  row is an enqueue bug — fix the capture, never widen the flush into a wildcard.
- Fresh-mode rows have no target yet: flushing them on the create reply that mints
  their session is the one legitimate cross-reply flush.
- Filter shape: `p.mode === "fresh" ? true : p.sessionId === sid`. A mis-targeted
  row stays queued for its own chat's next resume; the 24h staleness cap is the
  backstop.

### 5. Before trusting a component's own doc comment, read its code
A header comment claiming a guarantee the code no longer provides is worse than
no comment — the next reader trusts it. The outgoing-queue module claimed survival
of an app kill while persisting to `sessionStorage`, which dies with the tab. The
cause was two correct fixes colliding: a per-tab fix (stop tab A's queue leaking
into tab B) and a durability fix (stop losing queued sends) both wanted the same
storage. Grep for the primitive the comment names; if the code disagrees, the
comment is the bug.

### 6. Zero importers means unimplemented
Correct-shaped, fully-commented helper modules with no call sites are traps: they
read as implemented. Before planning work that assumes a module exists, grep its
importers. Either wire it or delete it — never leave a third copy to be written.

### 7. Storage hazard: the SQLite WAL-reset bug (check before touching DBs)
A data race between a checkpoint and a WAL-resetting commit silently drops an
acknowledged committed transaction. Affected: SQLite 3.7.0 through 3.51.2;
fixed in 3.51.3 and its backports. Measure what the RUNTIME actually loads — the
bundled copy is frequently behind the system package:

```bash
node -e "const{DatabaseSync}=require('node:sqlite');console.log(new DatabaseSync(':memory:').prepare('select sqlite_version() v').get().v)"
```

All three preconditions must hold: WAL mode, two or more connections in different
threads/processes, and a write colliding with a checkpoint. Two of three is common
and survivable. The change that pushes a database INTO the blast radius is adding
a background `wal_checkpoint` thread or process — never do that to an Astra
database. Give a new high-write log its OWN file so its blast radius stays
single-connection, create it with `auto_vacuum=INCREMENTAL` (that pragma cannot be
changed once tables exist, and purge otherwise only feeds a freelist), and gate on
`sqlite_version()` being at or above the fixed release so a future runtime bump
cannot silently reintroduce the risk.

### 8. A durable outbox requires server-side idempotency — build that first
A retrying, at-least-once flush on top of no dedupe turns every crash into a
duplicate user message. Ship the idempotency key and its server-side dedupe table
BEFORE making the queue durable; that ordering is not negotiable. Do not assume
the upstream can carry a client-supplied id — verify a write path actually sets it
(grep the ingest module, not just the schema).

### 9. Do not depend on Service Worker Background Sync
Absent in Android WebView (the primary mobile target for a Capacitor shell), in
Safari and in Firefox. Feature-test and register opportunistically; drive flushes
from signals the app already has (connection-state events, `visibilitychange`,
`pagehide`).

### 10. Retention is an architecture decision, not a config value
Before proposing "keep N months", check what the upstream engine already retains.
If a longer horizon forces the app to own an independent copy of data the engine
already holds, say so — it converts a one-line config into a second archive tier.
Aligning with the engine's own horizon deletes the conflict outright. The purge
gate stays two-part: a retention watermark AND proof the pipeline consumed the
data, so an un-ingested transcript is never deleted.

### 11. The per-user sync state has a hard body cap, so user assets are URLs
`PUT /api/theme/state` destroys the request past 64 KB, and it shape-validates
each field it stores. This one fact decides the architecture of every
user-uploadable asset: a font, a logo, an avatar or a wallpaper cannot be carried
in the state object as base64, because the sync layer is for SETTINGS, not
payloads.

The pattern is already proven — mirror `server/theme-assets.mjs`: raw body with an
`x-file-name` header, an extension allow-list, `basename()` plus a non-word strip
for the stored name, a timestamp prefix, a per-kind directory under `data/`, and
a returning URL. The state object then holds only that URL. Two rules make it
safe across devices:

- **A URL another device cannot fetch is a dead value pushed as if it were real.**
  `blob:` and `data:` are handles into one tab's memory. The client must refuse to
  broadcast one, and the SERVER must reject one independently, so a stale client
  left open across a deploy cannot poison shared state for everyone.
- **A durable URL is a decision, not a fact.** "Off" is a global decision and
  syncs; a per-tab local file is a decision for this device only and must stay
  on it. The UI should say which it is rather than looking identical in both
  cases.

Read the cap before designing any feature that lets the user attach something.

### 12. Connection churn is diagnosed from logs, not from symptoms

"It keeps disconnecting" spans four layers (page client, native Android legs, the
proxy, the CF edge). Attribute the churn from the server logs before touching any
client code:

- `handleWsUpgrade` logs `filter=`, `device=`, `since=` and the request UA; the
  shared ping loop logs `ws-reap` with `lq=` (that socket's last pong), `dev`, `f`.
  Together they name the offender by leg and user agent.
- Count `ws-upgrade` per minute: tens per minute is a reconnect loop; one or two is
  normal app lifecycle (WebView handoff on background/foreground).
- A reap whose `lq` equals that socket's OPEN time means the leg never ponged once —
  dead transport (Doze/NAT) and expected. A leg that ponged and then stopped is the
  bug. `peers=` climbing monotonically with no matching closes is a leak, not a loop.
- Group by `filter`/UA: `filter=1` + `ua=okhttp` isolates the native background leg,
  `filter=0` + browser UA is the page leg.

**Isolate client vs server with a raw probe before fixing anything.** Connect a
hand-rolled RFC 6455 client to BOTH `127.0.0.1:3011` and the public tunnel host,
answer server pings, and hold for 100s+. If both survive and every ping is answered,
the proxy/relay/edge path is healthy and the churn is entirely client-side — stop
editing server code. `scripts/ws-liveness-probe.mjs` is that probe.

**Close-before-overwrite introduces a loop unless the callbacks are guarded.**
Adding a defensive `close()` to a socket-replacing connect function fires the OLD
socket's own `onClosed`/`onFailure`, which schedules a redial, which closes the next
socket — self-sustaining at the backoff floor. Measured: ~44 reconnects/min on one
filter. Guard every close/failure callback with a superseded-socket check
(`if (ws !== currentSocket) return`) so only the live socket drives reconnects.

**Backoff must not reset on instant death.** `onOpen` unconditionally resetting the
attempt counter pins the redial at the base delay forever when a socket opens then
dies instantly. Reset only when the previous socket lived past a floor (~5s), so a
broken path escalates instead of hammering.

**Keep the intervals ordered.** The server reap threshold needs at least one full
round of grace beyond the client ping, and the client ping must be shorter than the
server ping round. Measured zero-grace bug: ping 30s / reap 30s reaped healthy
sockets whose single pong was seconds late, and OkHttp `pingInterval(60)` straddled
two 30s rounds. Working shape: client ping 20s, server ping round 30s, reap 65s.

**Native edits ship only through their own deploy plus an on-device restart.**
Kotlin/Java/manifest changes go out via `tools/deploy.sh android` AND an install; a
web deploy never carries them, and an APK install alone leaves the old process
running with the old behaviour. Force-stop the app, then re-measure. The script's
"no native changes" skip keys on COMMITTED diffs — commit before deploying or the
rebuild is silently skipped. Confirm the device took the new build by comparing the
served `/api/build-id` against the commit you shipped.

**Run the repo check suite with the SERVICE's interpreter:**
`ASTRA_WEBUI_PASSWORD=… ~/.local/node-22.23.3/bin/node scripts/run-checks.mjs`. The
shell's `node` is a different build whose bundled SQLite sits below the pinned-safe
version, so `scripts/sqlite-runtime.check.mjs` fails and `regression-gate` reports a
regression that does not exist. Compare `sqlite_version()` under both interpreters
before believing a red gate.

## Theme engine: the subsystems and their traps

A theming request is rarely one subsystem. Colour is usually already built; fonts,
shape and branding are usually three hardcoded literals plus a few hundred
hand-written values. Establish which before planning — the built half should be
left alone, and the missing half is most of the work.

- **backdrop-filter: the alias line is poison, and the drop is silent per-rule.** (2026-10-08, composer shell) Adding `-webkit-backdrop-filter` alongside the standard prop in the SAME rule makes lightningcss emit ONLY the -webkit- form for that rule; Chromium ignores it alone → computed `backdrop-filter: none`, no frost, no warning. Source must carry the STANDARD prop only (let the builder prefix), and every backdrop-filter change is verified with `getComputedStyle(el).backdropFilter` in a real browser — dist-grep alone lies.
- **A `var()` with no definition is not "no radius", it is an INVALID declaration.**
  An unresolved custom property makes the whole declaration invalid at computed
  value time, so it falls back to the property's initial value — `border-radius`
  becomes `0px`, and `calc(var(--missing) - 4px)` becomes `0px` too, not `NaN` and
  not an error. So a token used in many rules and defined in none renders those
  surfaces perfectly square with no signal anywhere. Check it in a real browser,
  not by reading: `getComputedStyle(el).borderRadius` on a probe element with and
  without the definition, comparing the two. A source grep that finds uses but no
  declaration is the fastest way in; the browser probe is what proves the
  consequence.
- **A palette switch can erase inline custom properties written by other
  subsystems.** When resetting to the default theme, code that iterates
  `root.style` and removes every property starting with `--` is correct for the
  colour tokens it owns and destructive to anything else a new subsystem persists
  the same way. The fix is a namespace preserve-list, and it needs a regression
  check: assert a palette round-trip leaves an unrelated namespace intact. Check
  for an existing guard before assuming one is there.
- **A shape scale needs a mode switch AND a separate pill token.** The proven
  architecture (Radix Themes, read from published CSS) is one multiplier driving
  `calc()` across the scale, plus a distinct full/pill token that is `0` in every
  mode except pill. Pill is a toggle of that one token, never a huge multiplier —
  which also means components that must never pill (code blocks, images,
  caret-aligned inputs) reference the scale directly and need no opt-out. Give the
  default-pill token a `0` value rather than a huge one, or every one of those
  components needs a manual exception. Sharp mode should use small non-zero
  values: a bare `0` on an 18px control reads as broken rather than deliberate.
- **Retiring hand-written literals is a codemod, and the value histogram IS the
  mapping table.** A histogram of the distinct values clusters into a handful of
  buckets, so the rewrite is mechanical and reviewable. Mirror the existing
  tokenizer's shape exactly: idempotent (detect your own output and no-op), with
  reset from git rather than from a stale backup snapshot, which is a one-run
  snapshot that silently reverts a concurrent session's work. Handle the odd
  forms separately: `50%` stays a circle, multi-corner shorthands become
  composite tokens rather than new values, and a token already inside a
  `calc()` needs the expression preserved.
- **A font picker cannot enumerate families from Google's own metadata endpoint
  in a browser** — no CORS header, so the fetch fails outright. A font CDN's
  registry API is the working source: one request, no key, CORS-open, and it
  carries per-family variable/weight/subset detail. Search must then be
  client-side, since the query parameter form is not supported.
- **Serving user fonts from your own origin means the upload response can stay
  cookie-gated.** A font subresource request does send the session cookie, so an
  authenticated asset route works with no CORS header; a cross-origin font
  source requires an explicit allow-origin header or the face silently fails to
  load and the fallback stays. If a font is ever served from another origin, add
  the header — and prove it by measuring, because the failure is a silent
  fallback rather than an error.
- **A cookie-gated favicon/manifest is a 401 waiting to happen.** Browsers
  request a web app manifest WITHOUT credentials by default, so gating it
  returns 401 and no icon is ever requested. Serving a single-tenant app's name
  and logo ungated is simpler and removes the need for a credentials-mode
  attribute. Two rules that are easy to miss: the manifest href must be
  cache-busted with a version query or the old icon is never re-requested, and
  manifest `src` paths must be root-relative, since relative ones resolve against
  the manifest's own directory.
- **Sanitise an uploaded SVG, and a regex is not enough.** An inline SVG shares
  the app's origin and its session. A heuristic pattern test lets entity
  declarations, external `<use>`, CSS `@import`, and event-handler elements
  through, and cannot see nesting. Use a strict allowlist. Two implementation
  traps that break LEGITIMATE logos rather than malicious ones, so a
  payload-only test suite never surfaces them: lowercasing attribute names before
  the allowlist lookup destroys camelCase attributes like `viewBox`, and a
  control-character strip built on `\s` eats the spaces inside path data.
  Rendering the asset through an image element is a stronger guarantee than any
  sanitizer, since an image-referenced SVG cannot execute script.
- **Raising a fill token's colour quotient flips every text rule painted into
  that surface.** A translucent accent-derived fill (20-25% mix) can carry
  accent-coloured body text; raise the mix (34%+ reads as a coloured bubble,
  not tinted glass) and the same text rule becomes accent-on-accent —
  invisible text with no error anywhere. When a mix percentage changes,
  re-audit every text rule targeting that surface in the same change: body
  text wants the neutral bright token, accent reserved for links/emphasis.

## Per-surface awareness: notes, stamps, presence vs status

Multi-device awareness (which surface sent a message; routing output format
per surface) rides three mechanisms that already exist — never build a fourth.

- **The per-turn note channel is the only cache-safe home for surface/format
  directives.** `tui_gateway/session_notifications.py::_hud_surface_note` keys
  on `session["client_surface"]` (set per submit from `prompt.submit`'s
  `surface` param against a validated frozenset) and `_prepend_note` puts the
  note on the MODEL INPUT for that turn only. `gateway/run_turn.py`'s
  `turn_sidecar_notes` (staged via `_set_pending_turn_sidecar_notes`) is the
  messaging-platform mirror. Notes must never enter the system prompt or a
  context file — that is the one mutation class that re-keys every cached
  conversation.
- **Stamps join on the RPC id; stamp only what is provable.** The proxy sees
  both directions of every frame. Correlate the submit frame's JSON-RPC `id`
  plus the socket's presence `device` with the result frame's `user_row_id`
  (same id, upstream→client direction). `user_row_id` is absent on
  queued/steered inputs — those rows get NO badge. Persist only socket-proven
  stamps in astra's own db; compute inherited origins (a telegram/cli
  session's rows) at read time from `sessions.source`. A wrong badge is worse
  than a missing one.
- **Result-frame hooks live on the upstream→browser relay path.** Results
  travel gateway→client; a bind hook placed on the browser→proxy leg never
  fires and the feature reads as "intermittent". Forwarded frames stay
  byte-identical; derived events (`message.origin`, `external.status`) are
  proxy-originated and downstream-only.
- **Presence and status are different claims.** Connected web/android sockets
  are real presence. Messaging/terminal surfaces only ever prove
  last-activity — label it "last active", never render it as live presence.

## pitfalls

- **Trusting a router card blindly.** Validate it against the real task. A card
  returning near-zero hits, or matching only stopwords, is a no-signal result:
  route manually (scan the skill list, recon the repo, targeted research
  fan-out) and say so rather than acting on a garbage ranking.
- **Presenting an unverified subagent number as fact.** Subagent reports are
  self-reports. Any load-bearing figure you put in front of the owner gets
  measured yourself first — a version string, a row count, a claim that a bug's
  preconditions are met. Cheap to verify, expensive to be wrong about. Research
  children also get STATED RULES wrong even when every individual probe they ran
  was real: in one batch of three, a claim that a CDN validates axis ordering
  (it only rejects an axis the family lacks) and a claim that a CSS utility was
  never emitted (it was) both survived until re-tested. Re-run the load-bearing
  claims yourself and say which ones you corrected. A batch that dies wholesale
  on provider errors (HTTP 402/billing) will not self-heal on re-dispatch within
  the session — do the scope inline instead of re-buying the same failure, and
  check the first transcript lines to confirm a dispatch is actually working
  before building a plan that depends on its parallel results.
- **Mid-turn send targeting rides the rebind order, not the resume reply.** A chat
  switch nulls `liveSessionId` BEFORE the new resume goes out; a send in the switch
  window therefore targets the new chat's stored sid, never the old one. Preserve
  that ordering in any refactor of `rebindToStored` — inverting it (resume first,
  unbind after) reopens a window where a send fires into the previous chat.
- **Commit-on-shared-repo etiquette for queue/engine fixes:** grep `git status --porcelain`
  first; concurrent sessions routinely land CSS-only commits mid-audit (verify your
  messaging-path fix survived with a line grep before building), and a dirty
  `src/index.css` you did not touch is theirs — never commit or revert it with your fix.
- **Dedupe before sort.** Identity and ordering are separate concerns; a retried
  message that sorts into the wrong place is a duplicate AND a chronology bug.
- **Full re-derivation on every keystroke.** Rebuilding a transcript from all
  rows on each state change is correct on load only; the live path needs a stable
  key so only the affected span is re-partitioned.
- **Verifying a precondition by reading config instead of behaviour.** A comment
  saying two processes share a database is evidence of intent; `lsof` on the
  file, or the presence of a second opener, is evidence of fact.
- **Dual-state desynchronization.** When two pieces of state must stay in sync (e.g. `selectedSessionId` and `activeSessionId` in App.tsx), updating one without the other causes silent UI bugs — the active chat row never highlights, or a stale highlight persists after ending a session. Always audit every setter call site: if state A is set in a callback, state B must be set in the SAME callback. Grep for both names across the file to find all sync points.
- **A cross-chat leak audit walks all FIVE isolation layers — the queue flush is the one that bypasses the other four.** (1) per-tab identity: a tab resumes from its own URL/sessionStorage, never shared localStorage; (2) wire ownership: a tab adopts a session only on a reply to an RPC id it sent; (3) event filter: foreign-session frames drop at the engine; (4) stale-reply guard: a resume reply is discarded when the stored sid changed while it was in flight; (5) queue flush: runs on reconnect, after the user may have switched chats — filter it on the row's recorded target session (rule 4.1). Layers 1-4 passing proves nothing about 5. Two supporting separations keep layers 2-4 honest: the watchdog probe is its OWN RPC id class (handled before the resume branch in the message pump — a probe reply can never be mistaken for a chat resume), and the replay-dedupe of completions keys on turn id with a frame-id fallback (a same-ms replay without either can double-bump a pill by one — cosmetic, self-heals on open, not worth a fix). Verify the suite, don't re-derive: `npx tsx src/lib/tab-isolation.check.ts`, `npx tsx src/lib/concurrent-queue.check.ts`, `node --import ./scripts/ts-resolve.mjs src/lib/ws-durable-queue.check.ts`, `npx tsx src/lib/wake-probe.check.ts`, and `node server/ws-filter.check.mjs` with the service's node.
- **A 503 from a dashboard-proxied gateway endpoint is read, not diagnosed around.** Astra reaches the model catalog through the Hermes dashboard (`/api/hx/*` → `127.0.0.1:9119` → gateway). When the checkout moves under a running dashboard/gateway process, the skew guard refuses the endpoint with a `detail` field naming the two SHAs — provider config is fine, the process is stale. Read the body before touching config; fix is a dashboard service restart (the GATEWAY itself can never be restarted from inside a Hermes chat — every session runs inside it; schedule the restart from outside the process tree and remove the scheduler entry afterwards, or the service bounces on every interval).

## reliability invariants (from the edge-case/race/silent-failure audit)

These are the classes of defect a deep audit of the relay, server and client
engine repeatedly surfaces. Check them as a set when auditing or adding any
request/upgrade path — each one is silent by construction, not by bad luck.

- **`decodeURIComponent` on a client-controlled header is a process killer.**
  `decodeURIComponent(req.headers["x-file-name"] || "")` throws `URIError` on a
  malformed value; inside an async request handler an uncaught throw becomes an
  unhandled rejection that exits the whole server (authed self-DoS — a corrupted
  filename from any logged-in device is enough). Wrap the decode in try → 400,
  and audit every upload route for the wrap — the serve-side call sites get the
  try and the upload-side ones get missed, because they were added later.
- **Zero-dep servers need a process-level net.** With no `process.on`
  (`uncaughtException` / `unhandledRejection`) anywhere, ANY sync throw on a
  request or `server.on("upgrade")` path is a full outage plus restart. Wrap
  the upgrade handler, and wrap the buffered-`head` decoder push in the same
  try/destroy the live `data` path already has — the head bytes arrive before
  the handlers attach, so the guarded path and the head path are two different
  code locations that must BOTH carry the guard.
- **A socket-write path with no backpressure degrades silently under slow
  clients.** Every `try { s.write(frame) } catch {}` site buffers unboundedly in
  Node's internal write queue when the client is slow-but-alive (still ponging);
  a pong-based reap never fires. On `write() === false`, stop writing that
  socket and destroy it past a byte threshold.
- **A capped proxy-side frame buffer silently drops user prompts.** When the
  browser→proxy leg is up but proxy→gateway is down, a client's durable queue is
  bypassed (its own socket is open) and the proxy buffer becomes the only copy
  of the prompt — and a FIFO cap shift()s the oldest out silently. Never drop
  `prompt.submit`-class frames; reject them back to the client instead, so the
  client's own durable queue takes over.
- **A `pendingRpcs` map without a close-time rejection wedges locks forever.**
  RPC promises parked on the socket are resolved on reply but, if never rejected
  on `onclose`, any in-flight RPC (a steer bridge holding a busy lock) hangs and
  every later call hits the lock check with no error emitted. On socket close,
  reject every parked promise and reset any lock the callers hold.
- **An upstream leg that never checks its own pongs looks 'online' while dead.**
  A half-open (NAT-blackholed) upstream keeps `online` status while no frames
  flow, because pongs are explicitly ignored. Mirror the browser reap: track
  `lastUpstreamPong`, destroy and reconnect past a threshold.
- **A liveness cap that only guards reassembly leaves single frames open.**
  Enforce the max-message cap on the DECLARED length before waiting for the
  body, not only when fragments are stitched — otherwise N authed sockets each
  declaring a huge single frame amplify memory freely.
- **A reconnect scheduler fed by multiple failure events stacks redials.** One
  failed connect can fire close, error AND response; if each schedules its own
  timer, two connectUpstream runs race and the loser's late close nulls the
  FRESH socket. Funnel every failure event through ONE in-flight reconnect
  timer (cleared before the next is armed).

## verification

- Probe both databases and print row counts, per-role byte averages and journal
  mode before and after any schema change.
- Prove a new log is replay-complete: rebuild a session's events from the log
  alone and diff against the gateway's final text byte-for-byte.
- For every durability claim in a comment, name the primitive backing it and
  confirm it survives a process restart.
- Audit for the reliability invariants above: grep `decodeURIComponent` and
  `decoder.push` for unguarded sites; grep `pendingRpcs` for a close-time
  rejection; grep write sites for `write() === false` handling; grep for a
  `process.on("uncaughtException"` net.
- Verify a consumer exists for every recovery read path (rule 6 applies to HTTP
  routes too): grep the CLIENT tree for the route path, not just the server tree
  for its handler.

## stream-resume: the consumer-side contract

The durable stream log (`stream-log.mjs` + `GET /api/hx/stream/<sid>?since=`)
has a client half (`src/lib/stream-resume.ts`) wired to the session-resume
reply — the engine emits `stream.resumable` and chat-landing splices. Rules
that keep it correct:

- **Splice REPLACE-based, never append.** The fold returns everything since the
  cursor, so a second resume re-delivers a superset; replacing the streaming
  bubble's segments is idempotent where appending doubles every token.
- **`truncated: true` means splice NOTHING.** It reports a hole between the
  client cursor and the log; signal a full history refetch. Splicing onto a
  gap renders a transcript that looks complete and is missing text.
- **The cursor is the server's `mono` counter, not the gateway's `seq`** — seq
  resets on gateway restart; mono is monotonic for the log's lifetime. Persist
  per stored sid; floor garbage/negative values at 0.
- **Only splice a bubble that `isStreaming`; settled rows come from history**
  and must never be rewritten by the resume path.

## reading the surface before planning on it

A request to "enhance the theme engine" usually spans a built subsystem and two
that do not exist yet. Map the boundary before writing a plan, because the built
half should be left alone and the missing half is most of the work:

- Count what is actually wired. For shape, `grep -o 'border-radius:[^;}]*' src/index.css`
  gives the literal histogram and separates the handful of token-driven values
  from the hand-written ones; for fonts, the `@font-face` block may live in its own
  stylesheet rather than the main one, and the `@theme` literals are only the type
  stack. Then check the utility classes in the tsx sources separately — a
  `rounded-*` class resolves through generated CSS and is steerable by a token,
  while a raw pixel in a class file is not. Both numbers belong in the plan,
  because they decide between a codemod and a runtime override.
- Find the consumers of a name before counting its literals. A token that is
  declared in the palette contract but read by nothing, or a colour literal that
  looks themed but is baked, changes what the work is.
- Verify the upstream schema rather than assuming the page is complete. The
  Appearance page's Hermes keys are discovered by walking the config default
  tree; comparing what the page shows against what the schema exposes is cheap
  and turns a vague "add what's missing" into a named list.
- This repo is shared with other live sessions. A dirty shared file is another
  session's work, not a free hand: build in a detached worktree and hand back a
  reviewed diff.
