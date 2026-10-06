---
name: astra-webui-regression-fixes
description: "Use when a fixed astra bug recurs or a deploy looks stale."
---

# Deploy + verification lessons (2026-10-02 regression spree)

## 1. "Fixed and verified" but keeps coming back = check the DEPLOY, not the code

The `stroke-linecap: butt` comet fix was committed (0a428f6), pixel-verified, and then
reported by the owner TWO more times. Root cause of the recurrences:

- A concurrent session kept reverting `src/index.css` round↔butt (its edits won the
  last-writer race), AND
- `npm run build` was FAILING on that session's in-flight TS6133 (`doEndSession`
  declared but unused after it deleted the End-session button), so the fix never
  reached `dist/`. The served hashed CSS still said `round` while src said `butt`.

Procedure when a verified fix recurs:
1. `curl the served index-*.css | grep <property>` and compare against `src/`. A
   mismatch means the build/deploy is broken — stop editing the fix.
2. Identify what breaks the build: `npm run build` and read the FIRST error. Do not
   fix another session's half-finished edit; flag it to the owner as the blocker.
3. To ship your own change regardless: `git worktree add <dir> HEAD --detach`,
   `ln -sfn <repo>/node_modules <dir>/node_modules`, apply ONLY your changes there
   with an IDEMPOTENT assert-anchored script (a worktree at HEAD may already carry
   your committed fix — the assert "expected 1 match, found 0" firing is the
   idempotency check doing its job), `npm run build` in the worktree, verify.
4. Grep the file again IMMEDIATELY before building (concurrent sessions revert
   working-tree lines between your edit and your build), and re-verify the served
   bundle right after.
5. Multiple sessions on one repo is the norm here: treat every `git status` dirty
   file you did not touch as another session's work in progress. Never `checkout --`
   a dirty file wholesale — you may erase their in-flight header fix along with your
   one-line revert.

## 2. `<video>` "playing" is not `<video>` decoding

Three fixture traps, each faking success differently:

| Trap | Symptom | Truth |
|---|---|---|
| video-only mp4 (no audio track) | `DEMUXER_ERROR_NO_SUPPORTED_STREAMS`, error 4 | rejected outright |
| MPEG-4 Part 2 encode | `playing:true, readyState:4, currentTime advancing` AND `videoWidth:0` + black canvas | FALSE GREEN — audio clock runs, no video frames decode |
| `canPlayType('video/mp4')` = "probably" | reads as codec support | proves nothing about the actual stream |

Honest green = `videoWidth > 0` PLUS a canvas `drawImage` luma sample (mean/max /
non-black %). Build fixtures with `-c:v libx264 -profile:v baseline -c:a aac` —
ffmpeg defaults (mpeg4 part 2, or video-only) hit the traps above.

Server was never the problem: `/api/hx/files/stream` served `200`, `video/mp4`,
`206 Partial Content` on Range, valid `ftyp isom` bytes — verify the SERVER with
curl, verify the CLIENT with decoded frames; neither substitutes for the other.

## 3. The "sidebar vanished under the video backdrop" bug had TWO stacking traps

- A `z-index` on a STATIC element does nothing — the guard must set
  `position: relative` AND `z-index`.
- `.chat-backdrop ~ *` is a SIBLING selector; the backdrop is mounted inside
  `<main>`, so it can never reach the shell-level sidebar (an ancestor's sibling).
- The prior guard `.app-shell > aside#astra-sidebar` matched ZERO elements (the
  aside is nested one level deeper, inside `div.flex.min-h-0.flex-1`). A guard that
  matches nothing reads as insurance while insuring nothing.

Fix: `aside#astra-sidebar { position: relative; z-index: 2; }` and ASSERT
`document.querySelectorAll(selector).length === 1` for every stacking guard written.

## 4. Upload route returns a host path, not a URL

`ThemePanel.upload` stored `src: path` (`/home/notjitin/chat-bgs/x.mp4`) verbatim;
the browser resolved it against the origin → SPA fallback → index.html →
`MEDIA_ERR_SRC_NOT_SUPPORTED (code 4)`, black backdrop. Fix in the backdrop
component (`bgSrc()`): absolute host paths →
`/api/hx/files/stream?path=<encodeURIComponent(src)>` (Range-capable, which
`<video>` needs for seeking); pass through `https?:`, `blob:`, `data:`, `/api/`.
Regression check: `npx tsx src/components/chat-backdrop.src.check.ts` (7 cases).
Restore the owner's real theme-state (`data/theme-state.json`, `PUT /api/theme/state`)
after backdrop experiments — tests overwrite it via the server sync.

## 5. Two slash popups → one surface, two groups (owner 2026-10-02)

`CommandPalette` (live registry) and the hardcoded `TUI_COMMANDS` `slashOpen` menu
both opened on `/` and fought over the same keystrokes. Merged into ONE palette
grouped by where the command RUNS, split from the registry's own data
(`cli_only`/`gateway_only` on `/api/hx/commands` — 102 commands live), never a local
list:
- Web UI group: browser-local `/bg` `/steer` — adopt into the composer via the
  existing cmdPrefix slash-stripping (do not re-enter the send path).
- TUI group: `slash.exec` on pick; reply painted into the chat feed as a normal
  assistant message; call `finalizeActive()` BEFORE appending the user row so the
  reply paints BELOW the command, not into the bubble above it.

Kill a duplicated popup in ONE scripted pass (state + keyboard branch + JSX + dead
handlers) — patch-by-patch left orphaned `setSlashOpen` calls in the send path that
only surfaced at `tsc`. Narrowing a ChatMsg union inside a map callback needs an
explicit role check (`if (x.id !== id || x.role !== "assistant") return x`) —
spreading with `as ChatMsg` does not un-narrow `x.segments`.

## 6. Concurrent-session patterns seen live (all in one session)

- Its commit can land your same fix mid-flight (`0ce485d` carried the actions-row
  work) — re-verify before redoing.
- It can revert your committed line in the working tree twice in an hour.
- Its half-finished edit blocks the shared build for you (TS6133).
- It can delete a JSX element but leave its handler orphaned — build fails on their
  side, your deploy silently stops.
- Its header/sidebar glass fix (align `.mobile-accent-header` to `.sidebar-glass`,
  both `color-mix(in oklab, var(--color-midnight) 45%, transparent)` +
  `blur(29px) saturate(1.25)`) was correct and landed in the working tree — verify
  with computed styles on BOTH elements (byte-identical `backgroundColor` and
  `backdropFilter`) before touching it yourself.

## 7. Blob backdrops + stale clients (2026-10-04, commits ba05da5 / 6f4c67c)

Owner bug: a background set on the phone was invisible on the iPad. The stored src
was a `blob:` URL — a handle into ONE browser tab's memory. Root cause: no
`onUpload` was ever handed to ThemePanel, so the local object-URL fallback fired and
the session-local URL was then pushed to `/api/theme/state` as if durable.

- **A client-side check cannot protect shared state from a client that predates the
  check.** Fix in three layers: upload() POSTs to `/api/theme/bg` and keeps the
  returned real URL; `isDurableBgSrc()` in theme-store.ts gates the sync push; the
  SERVER (theme-sync.mjs) rejects `blob:`/`data:` bg srcs and keeps the previous
  value. The server backstop is the one that actually works — an app left open in
  the background across a deploy still runs the old JS and pushes whatever it has.
- **Diagnose from the three live facts, not the symptom report:** `data/theme-bg/`
  empty (no upload ever reached the server) + a NEW blob rev in theme-state.json +
  the guard present in the served bundle ⇒ stale client-side code, not a broken fix.
  Also prove the upload route after editing it: the server was NOT restarted after
  the first edit, so the raw-body path answered "multipart boundary missing" until
  `systemctl --user restart astra-webui.service`.
- **Upload route accepts RAW body (`content-type` + `x-file-name` header) alongside
  multipart** — FormData is ~30% overhead on a 95MB video and forced a hand-rolled
  parser. Verify with a real PNG: raw upload → durable URL, authed GET 200
  image/png with the right byte count, unauth 401, multipart still works, bad type
  rejected. Failed-adduploads keep the local blob BUT the panel warns
  ("device only — re-upload"); a blob never silently persists again.

## 8. A `*.check.ts` can block the APP build — TS2591 → the fix never deploys (2026-09-26)

`npm run build` is `tsc -b && vite build`, and `tsc -b` type-checks every file under
`src/` INCLUDING the `*.check.ts` files. A check using node-only APIs (`process.exit`)
fails the whole build with TS2591 ("Cannot find name 'process'. Do you need to install
type definitions for node?") because the app tsconfig sets only `types: ["vite/client"]`
— so nothing reaches `dist/`, the served bundle keeps the pre-fix hash, and the feature
reads as broken for the entire time the build is red (the approvals-ownership fix wedged
exactly this way through one review-only cycle).

- Repo check pattern: assert-and-throw (mirrors `streaming-resilience.check.ts` /
  `tab-isolation.check.ts`), never `console.error("FAIL:", …); process.exit(1)`.
- Recurrence-scan shape: fix "deployed" + owner still sees the bug + `served:
  assets/index-*.js` hash unchanged since before the fix → read the FIRST `npm run
  build` error before touching the fix again; here it pointed straight at the check file.

## 9. Green gates over a red tree (2026-10-05 fix-run)

A fix-run found SIX checks passing standalone while asserting a dead design or a wrong premise: a check sliced `@theme` by first textual occurrence and matched prose inside a COMMENT (vacuous assertion); `perf-chat.css` was imported by NO file (ships nothing) while its check asserted only source presence; `sysinfo.audit` pinned one-shot probes inside 24h-auto-pruned scratch (built-to-fail premise); `css-chat-surface` asserted the superseded tinted-scrollbar design days after the owner made rails invisible; a committed check imported `./canvas-code-hl` from the wrong directory (fresh-clone breaker); `training.mjs`'s CREATE TABLE never emitted `ingested_at` while ingest/retention/backfill all SELECT it.
Rule: after any owner-steered design change or a concurrent-session restructure, re-run the FULL suite, not just the touched layer. A failing check is either repaired to current intent or explicitly demoted — never left red, never silently green. Verify each repair individually (run the single check), then the gate, then the build.
Also: a sibling commit can absorb your uncommitted shared-tree work (`62d6f1b` swept a session's renderer fixes in under "the commit that got lost"). Before redoing an edit, `git log -S '<marker>'` — the tree may already carry the fix under someone else's commit. Runtime data files (`.cache/command-registry.json`, `data/read-state.json`, `data/theme-state.json`, `data/test-ledger.jsonl`) stay uncommitted by design.

## 11. CF cache rules: the LAST matching rule wins (2026-10-06)

Zone `http_request_cache_settings` rulesets are sequential, last-match-wins — NOT
first-match like most firewalls. The ruleset shipped with `[/api/ bypass] →
[HTML 60s] → [catch-all 1y]`; the catch-all sat LAST and silently re-cached
everything, so measured: `/api/build-id` served `cf-cache-status:HIT, age:538,
max-age=31536000` DESPITE a bypass rule matching it. Every symptom of "the
android app drifted from the web implementation" traced here: the WebView's
HTML+bundle were year-pinned at the edge, AND the 08586af build-check
could never fire because its own poll endpoint was edge-cached (stale stamp
compared against stale stamp). Worse: `/api/me` 200s were edge-cacheable keyed
by URL with no cookie in the cache key — one device's authenticated response
could be served to another client. The `b3deeb8` minute-busters and `08586af`
build-check were all defeated by this one ordering bug.

- Correct order: **catch-all (1y assets) FIRST, narrowers AFTER, `/api/` bypass
  LAST**. Verify with a fresh-URL double hit: MISS→HIT (or DYNAMIC) per route.
- Verify after ANY cache-rule edit: `curl -sI <url>` on `/`, `/api/build-id`,
  `/api/health`, one hashed asset — expect DYNAMIC on /api, 60s on HTML,
  immutable on assets; then purge_everything.
- The WebView disk cache ALSO honored the 1y max-age on the top document: after
  fixing the edge, a phone may still hold the old HTML in its own HTTP cache and
  self-heal only if its bundle carries build-check (poll → DYNAMIC stamp →
  reload). Older cached bundles need one manual force-stop / clear.
- Authenticated GETs (`/api/me`, `/api/ntfy-config`) must NEVER be edge-cacheable:
  the CF cache key has no cookies, so a 200 leaks across sessions/devices.

## 12. Live-status / transient-frame bugs: the state must live on the SERVER (2026-10-06)

Owner: "I don't see the thinking/working text on the sidebar chats section on
phone." Three stacked defects, and the shape recurs:

- **A frame that carries no payload cannot be stamped inside a payload guard.**
  `message.start` is declared `event("message.start", None)` in
  `tui_gateway/contracts/events.py` — no payload at all. The proxy's stored-id
  stamping sat inside `if (stored && p.payload && typeof p.payload === "object")`,
  so a start frame was NEVER stamped, and the client-side "mint the payload"
  fallback a commit message claimed to add was unreachable dead code. Fix:
  mint the payload (`if (!p.payload) p.payload = {}`) instead of guarding on it.
- **A per-connection gate is the wrong gate for per-message work.** The whole
  turn block lived inside `if ((anyTagged || anyCompleteFilter) && opcode===0x1)`
  — it only ran while some OTHER client held a sid-tagged socket. With a quiet
  socket list the frames were never parsed: measured `payload: null` on 2 of 4
  runs, and after a restart the feature was dead until a chat was opened. Gate
  on the FRAME (opcode + a cheap `includes` pre-test), never on who else is
  connected. Verify with a restart loop: 5/5, not 1/1.
- **A feature fed by transient frames needs server-side state for the mount
  path.** A drawer opened mid-turn has already missed `message.start` — the
  phone hits this constantly because its drawer is shut most of the time. Track
  running turns proxy-side, stamp `turn_running` on the session-list rows, and
  seed the client from that. TTL the entries (15m): an interrupted turn emits no
  completion, and a permanent "Thinking…" on an idle row is worse than a
  missing one.

## 13. Undeclared on-disk deps: `npm install <x>` prunes them and breaks the build

`canvas-export.tsx` imported `html-to-image` and `jspdf`, neither of which was in
`package.json` — they existed only in `node_modules`. Adding `ws` with
`npm install --save` pruned both and the build died on TS2307. An undeclared dep
is a fresh-clone break waiting to happen; declare what you import. Prove it with
`npm ci` in a throwaway dir and `ls -d node_modules/<pkg>` — the build passing on
your machine proves nothing, because your machine already had the tree.

## 14. Prove a new check has TEETH: negative-control it against the old shape

A check written after a fix can pass for the wrong reason. Re-introduce the bug
(here: re-wrap the turn block in the old tagged-socket gate), confirm the check
FAILS, restore, confirm it passes. `server/turn-status.check.mjs` §5 is the
worked example — it exercises `broadcastFrame` through a capture socket, so it
pins the RELAY path, not a pure function that merely resembles it. A source-shape
assertion (grep the file for the new string) would have passed on both shapes.

Also: `server/ws-codec.mjs` killed the connection on ANY fragmented frame
("fragmentation unsupported"). It now reassembles RFC 6455 fragments, delivers
interleaved control frames immediately, and caps a message at 16 MiB. Pin a codec
against the REFERENCE implementation, not against itself — feed your hand-built
fragment stream to a real `ws` server (RG-144).

## 10. Synthetic wire-frame QA through the page's real WebSocket handler (2026-09-26)

Reusable verification pattern proven across four features this session (approval
scoping, harness-CLI panel, reply-dedup, and the gateway's `already_streamed` interim):

1. Arm a socket capture BEFORE the app boots: CDP `Page.addScriptToEvaluateOnNewDocument`
   wrapping `window.WebSocket` (instances land in `window.__sockets`). Hooks armed
   mid-life miss the socket — `dispatchEvent(new MessageEvent('message'))` does NOT fire
   the property handler (`s.onmessage = …`), so call `sock.onmessage(ev)` directly.
2. Find the LIVE ui_session sid from `hermes logs` (`tui prompt accepted:
   ui_session=<hex> session_key=…`) — construct one from the URL's stored key and the
   strict `session_id !== liveIdRef` filter silently drops the frame; positives look
   like failures (and the reverse makes negative probes look like over-blocking).
3. Fire the exact wire shape passthrough (`{method:"event", params:{type,
   session_id, payload}}`), then assert on the DOM (rendered text count, panel bar,
   aria-hidden) — and dismiss with the app's own controls; a synthetic Deny replies to
   a nonexistent srq id, which is harmless by design.
4. Clean up: reload or close the test tab; a `window.__sockets` capture arm survives
   until nav and pollutes later probes with stale entries.
