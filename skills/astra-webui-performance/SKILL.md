---
name: astra-webui-performance
description: "Astra web UI chat performance fixes."
version: "1.0.0"
author: Hermes Agent (session 2026-10-03)
license: MIT
metadata:
  hermes:
    tags: [astra-webui, chat-performance, layout-blocking, memoization, reveal-timer, diagnostics, conflict-resolution, native-ticker, open-install]
    related_skills: [hermes-web-ui-qa, neutrinos-web, agentive-pipeline]
---

# Astra Web UI Chat Performance Fixes

Always-on rules for astra.jitinnair.com chat (shared repo, concurrent sessions, native APK builds, diagnostics plugin required).

## always-on rules

### 1. Check merge conflicts before editing chat-landing
Run `git status --short src/components/chat-landing.tsx`. If `UU` or `<<<<<<< Updated upstream` markers exist, resolve first (take upstream version, re-apply fix) or fix safe files (`chat-timeline.tsx`, `native/shell-theme.ts`, `styles.xml`). Never patch conflicted files.

### 2. Defer blocking `fitComposer` via async rAF
`fitComposer` (`chat-landing.tsx` ~line 1370) reads `scrollHeight` synchronously. A synchronous layout read on a 7K-node DOM blocks typing ("whole sentences before a letter").
- Fix: wrap the height measurement in `requestAnimationFrame()` inside `fitComposer`. Apply `style.height` in the rAF callback.

### 3. Memoize parent message mapping (`useMemo`) — CRITICAL, deepest fix
The parent `ChatLanding` creates new JSX via `messages.map()` on every state change, defeating child (`TurnTimeline`) memo. Every keystroke in the draft input re-runs the entire `.map()` and recreates JSX for every message in history (200+ messages = 200+ object allocations per keystroke).
- Fix: wrap `.map()` with `useMemo(() => messages.map(...), [messages])` (line 1824). This is the single highest-impact fix; memo on TurnTimeline alone is insufficient.
- Verified: Session 20261003_085657_3abcb3 applied this as the final fix after async fitComposer, timeline memo, timer reductions proved insufficient. Reduced per-keystroke JSX allocation from 100% to ~3% of profile time.

### 4. Memoize `TurnTimeline` component
`chat-timeline.tsx`: export `const TurnTimeline = memo(TurnTimelineImpl);` so the internal `canvasPlan` `useMemo` isn't triggered by prop-reference changes.

### 5. Slow reveal timer (16ms -> 100ms)
`useReveal` (`chat-timeline.tsx` ~line 385): `setTimeout(tick, 16)` creates ~60 state updates/second. Change initial and recursive intervals to `100`.

### 6. Reduce native ticker overhead
`native/shell-theme.ts`: `setInterval(updateColors, 1200)` -> `5000`. Bar contrast update doesn't need sub-second frequency.

### 7. Theme bars transparent (`AppTheme` in `styles.xml`)
`AppTheme` parent must be `Theme.AppCompat.DayNight.NoActionBar`. Add transparent `statusBarColor`, `navigationBarColor`, `windowTranslucentStatus`, `windowBackground` so `.app-shell` (`bg-void`) extends continuously under bars.

### 8. Confirm APK rebuilt and delivered
Build command that works on this host (both parts are required, bare `./gradlew` fails twice otherwise):

```bash
cd android && npx cap sync android            # from repo root first
export $(grep KEYSTORE_PASSWORD ~/Work/services/astra-android/astra.keystore.env)
JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew assembleRelease
```

- Run the build with `JAVA_HOME=/usr/lib/jvm/java-21-openjdk` — the host default is JDK 25 and Gradle fails in semantic analysis with `Unsupported class file major version 69`.
- Export KEYSTORE_PASSWORD from `~/Work/services/astra-android/astra.keystore.env`; release signing shares the debug keystore, and a missing storePassword fails `:app:packageRelease` after codegen already succeeded.

Then verify APK timestamp updates (`stat -c '%y'`), and deliver via Telegram bot `8631271551:AAHKXrC1SeBqkOyGFp2FW1PMJYY_QyUiEVE` (chat `8881524728`). Confirm user installed before claiming fix verified.

PITFALL (phone staleness masquerading as a live bug): the APK's WebView loads the REMOTE site (`server.url` in capacitor.config.json), but a phone running an old build predates web-fixes users expect everywhere. When the owner reports a known-fixed bug 'still broken' on the phone, check `stat android/app/build/outputs/apk/release/app-release.apk` against the dist bundle date BEFORE re-debugging — rebuild + redeliver is often the whole fix.

### 9. Collect real device data (`Diagnostics` plugin)
Always call `stats()` (cookie health, log age, log bytes) and `dumpLogs()` (last 256KB of `filesDir/astra-perf.log`) when investigating mobile lag. Never claim "faster" without on-device measurement. Pull log via `adb pull .../astra-perf.log` when USB connected.

### 10. Composer split into separate input + buttons cards (2026-10-04)
When restructuring the composer layout (input field and buttons bar into two separate rounded rectangles):
- **SVG trace parent binding:** ComposerTrace uses `svg.parentElement` to bind the SVG to its container's border. Move the SVG inside the input card container; the trace will follow that container's border, not the outer shell.
- **CSS class layout:** Use a shell wrapper (no border/bg/radius) containing flex-column children: `.composer-field` (input card with border, bg, rounded corners, class `chat-composer`) and `.chat-composer-bar` (buttons card with own border, bg, rounded corners, padding). This separates concerns and lets drag-over / focus-within states target each independently.
- **Drag-over and focus states:** Update selectors to scope hover/drag/focus effects: `.composer-field:drag-over`, `.composer-field:focus-within` for the input card behavior; `.chat-composer-bar` for button card styling. The shell wrapper has no visual state.
- **Padding re-allocation:** The old outer card had padding covering both fields. Redistribute: input card keeps text-field-appropriate padding; buttons bar gets its own (e.g., `6px 10px` with `align-items: center`). Remove margin offsets between the cards by using flex `gap` on the shell.
- **Test signal:** Verify by running the app and confirming the running trace SVG only animates around the input field, not the buttons bar. Ensure drag-and-drop highlighting targets only the input field.

### 11. Slow-chat / slow-open RCA procedure (always, not just on Android)

Full walkthrough with commands: `references/chat-open-rca.md`. The rule that
governs the whole class:

**Measure before touching anything, and cost your own recent work against its
budget first.** A slow-chat report right after you shipped something is an
accusation until you have disproved it. Microbench your own per-frame work on
realistic input and express it as a fraction of the budget it shares (streaming
is ~30 frames/sec, so a 33 ms window); anything under ~1% is not the cause.
Report the number, not a claim — "my change costs 0.10 ms of a 33 ms frame"
closes the question, "my change is unrelated" does not.

Minimum evidence set before you name a cause:

1. Baseline `/api/health`, then each route the client calls, locally and
   authenticated, median of 4+ samples. Single-digit ms means the server is not
   the cause — say so before going client-side.
2. The same route through the Cloudflare tunnel. This gap is commonly 100–300 ms per
   request and multiplies by request count; it is usually the biggest number
   in the report and it changes which fix matters most. ALSO check staleness,
   not just latency: the zone's Browser-Cache-TTL filters can override origin
   `no-store` and serve a cf-cache-status:HIT that is HOURS old — new chats
   and unread pills then never appear until restart. Fix class: a minute-
   epoch cache-buster (`_r=`) on the wire URL (must not change the cache KEY,
   see `src/lib/sessions-cache.ts`), plus origin `cache-control: no-store`.
3. `window.fetch` hooked in-page, logging URL + duration + body size. Duplicate
   fetches from independent call sites are invisible to per-route timing.
4. Per-key byte totals per response, grepped against what the client reads.
5. DOM node count across the open window plus a `longtask` observer, to split
   network from render.

Two pitfalls that cost real time here:

- **Synthetic clicks usually do not reach React.** `el.click()` and dispatched
  `MouseEvent`s are unreliable; use the real coordinate click on a freshly-read
  `getBoundingClientRect()`, and confirm with `document.elementFromPoint` what
  you are about to click. Stale coordinates land on the search box and produce
  the same empty waterfall as a genuinely broken handler.
- **A `requestAnimationFrame` probe that "times out" is usually the CDP
  transport blocking on a promise, not a blocked main thread.** Confirm with a
  bounded busy-loop probe; if it returns in ~its own budget the thread was free.
  Never report "the renderer is saturated" from a timeout alone.

PITFALL (measurement): the sessions list row key is `id`, not `session_id`. A
KeyError here reads as a broken endpoint. A `Secure` session cookie also will not
travel over plain HTTP, so script-driven calls to the public hostname 403 even
with a valid token — measure public latency from inside the browser.

## pitfalls

- **Concurrent session reversion:** Claims that "fix X is applied" may not be true. In shared repos with parallel work, a claimed fix can be reverted by another session without updating this skill. Always verify via grep/git log before trusting a claimed fix — the verification checklist items (section below) are not optional guardrails, they are the proof. Session 2026-10-03 found that TurnTimeline memo (item 4 below) was claimed applied but `grep memo(TurnTimeline` returned 0 hits.
- Editing conflicted `chat-landing` corrupts concurrent session's work. Check markers first.
- Only applying timeline memo without parent memo — typing still recreates full message JSX.
- Not deferring `fitComposer` — blocking layout read causes severe typing delay.
- Not collecting `stats()` / `dumpLogs()` — performance claims are unverified.
- The `*.check.*` suite covers only the pure modules. To prove a React-side fix
  in astra-webui (canvas card rendering, state seeding) without a browser, use
  the `react-headless-render-probe` skill: `npx tsx` + `react-dom/server`, run
  from the repo root.

## Audit procedure (owner asks "check all chat bugs are fixed")

Don't trust claimed fixes — verify in BOTH source and the served/phone bundle, then probe the server live:

1. **Source grep pass:** each known fix has a grep signature (verification checklist below). One bad call site (`cd ~/Work/projects/stra-webui` typo) silently probes nothing — read the cwd in the output, not just the exit code.
2. **Bundle pass:** grep the same signature in `dist/assets/index-*.js` (minified names differ — grep stable string literals like class names, not function names) AND `android/app/src/main/assets/public/assets/index-*.js`. A fix present in source but absent from the phone's bundle means the APK predates it.
3. **Server-truth pass:** login to `127.0.0.1:3011/api/login` (password in `~/.config/astra-webui/env`), GET `/api/hx/sessions?...&sources=webui,telegram,cli,tui,android`, and verify the reported chat/row actually exists server-side. This distinguishes "list is stale on the client" from "row never got created/tagged".
   - When the complaint is about row CONTENT (empty, first-message, wrong last), dump `last_reply` vs `preview` for every row and classify: which rows are empty server-side vs which are populated server-side but rendered empty client-side. Server-populated + client-empty points at a render-path filter (greet/canvas blanking, fallback ordering); server-empty points at the enrichment stage. Do not debug the client renderer for rows the server never enriched.
4. **Live-try on the public path through the tunnel** (relogin via the curl tunnel to get the valid cookie there): verify `cf-cache-status` is MISS/BYPASS on session GETs, not HIT.
5. **Headroom the audit surface:** run `node scripts/run-checks.mjs` (regression gates + suites). Red gates = real repo findings, report them.

PITFALL (red gate ≠ your regression): the regression gate fails wholesale when
ids are DUPLICATED — two sessions pinned different bugs under the same RG id.
Before adding a new pin, grep `id: "RG-` in `scripts/regression-gate.check.mjs`
for the id you intend to use; renumber the colliding set, never reuse. And every
new `*.check.*` file MUST be pinned to a manifest row or the gate fails with
'is not in the regression manifest'. A check file that passes standalone but
FAILs under the parallel runner is usually runner-timing, not a real bug —
re-run it alone before debugging.

PITFALL (stale html parses as 'fix didn't work'): if the fix is in dist but the
user still sees old behaviour, the CF edge may be serving the PINNED old
index.html (zone catch-all cache, html rewritten to a 1y TTL at the edge).
Diff the served asset hash against `ls dist/assets/index-*.js` first; purge
procedure + build-check mechanics: `references/deploy-staleness.md`.

## Sidebar rows (last-reply preview) — the enrichment chain

The row sub-line is a THREE-stage chain; "wrong/first message showing" can fail at any stage — probe each:

1. **Server enrichment** (`server/last-reply.mjs`): derives the LATEST response per row via one `/api/sessions/<id>/messages?order=latest` fetch, cached per session and invalidated by activity stamp. `enrichLastReplies(rows, {max})` covers only the first N rows of a page — keep `max` ≥ the panel's page size (`limit = 15`), or tail rows silently fall back to the gateway's `preview`, which is the chat's FIRST user message (reads as "shows the first message, not the last").
   - The scan accepts USER rows too, newest first (owner spec: "the last message from Astra or me"). Assistant-only scans blank out tool-heavy windows and interrupted turns, and every one of those chats falls through to the greet preview → EMPTY row.
   - Skip `[tool_call]/[tool_result]`-shaped, `[Surface…]`-scaffolded, and greet rows; accept `role: user` and `role: assistant`. Keep `server/last-reply.check.mjs` pinned to this contract — its old rows pinned the opposite (user messages rejected); update the test when the contract changes, never weaken the code to satisfy a stale test.
2. **Greet filter**: the auto-greet kickoff ("New chat just started…") is a UI convention, not a message — filter it in BOTH the server's `lastResponseFrom`/`responseText` and the client detectors (mirror `GREET_RE` from `src/lib/notify.ts` in one place per side). It can ride BOTH `last_reply` and `preview`, and the kickoff turn DOES complete on the wire — the live preview patch handler must refuse greet text or it re-plants the greet over a good value.
3. **Client render** (`src/lib/row-inline.ts` + `RowSub` in `chats-panel.tsx`): the sub-line is INLINE markdown only (bold/italic/code; links reduce to text — a 10.5px row is not a tap target), never raw paint, never full markdown. Escape FIRST (model output is untrusted), then collapse fences to `…`, then drop pair-less emphasis markers (the server's 220-char cut can strip a closer — a row must never end in a stray `**`).

Live-turn status per row (animated Thinking…/Working… on any chat, open or not): ws-engine drops foreign-session frames at the live-session guard — emit a synthetic `chat.turn {sid, stored, running, thinking, text}` BEFORE the return for `message.start`/`message.complete`/`message.error` on other sessions, and have the panel maintain a `Map<sid, turnState>` from `astra-ws-event`. A canvas-card last reply renders as "Open to read canvas card →" (detect `astra-canvas` in `last_reply`).

Live-status sid rules — this is where a silent no-show comes from:

- **Events carry the LIVE session id (rotates on compression/reconnect); rows key on the STORED id.** A naive sid match registers the animation against a key no row holds — nothing shows, with zero errors. Stamp BOTH ids on the event (`stored` from `payload?.stored_session_id || notify.storedKeyFor(liveSid)`) and register the row state under both keys.
- **`message.start` frames carry NO payload object on the wire**, so `payload.stored_session_id` is unavailable there. The proxy (`server/hermes-proxy.mjs` `broadcastFrame`) must MINT a payload object and stamp `stored_session_id` on start frames too — the client-side mapping alone covers only chats this tab resumed this boot.
- The live row text replaces the sub-line IN PLACE at the sub-line's own geometry (10.5px, no wrapper padding). The generic `AITextLoading` component carries `px-4 py-2 text-sm` + centering — wrapping it inside a 10.5px row inflates the card. When embedding a shared loader in a compact row, write the inline shape (CSS shimmer with `background-clip: text`) at the host geometry instead.
- **Shimmer/gradient-text ink must be visible WITHOUT the clip.** Set a solid `color` first and put `color: transparent` + `background-clip: text` inside `@supports` — an unconditional `color: transparent` paints NOTHING on any renderer where the clip is dropped (minifiers already dropped unprefixed `backdrop-filter` here once; same trap class). Blank text reads as 'shows nothing', not 'shows grey'.

PITFALL: any new CSS in `index.css` with `border-radius: 0–3px` fails `src/lib/rounding.check.ts` (sharp-rectangle ban) — use `var(--shape-1)` (the smallest scale step), never a raw pixel radius or an invented token name (`var(--radius-sharp)` does not exist).

PITFALL (unread-pill flicker): `notify.seedFromServer` must not delete a local live bump whose `t` is newer than the row's `last_read_at` watermark — the server snapshot and a live bump can arrive out of order, and delete-then-re-bump reads as flicker. Decide stale-snapshot vs real-read by comparing the watermark against the bump timestamp, not by trusting `unread: false` blindly.

PITFALL (light-mode accent on muted surfaces): shared dark-mode accent ink (e.g. a label designed for dark) needs an explicit `[data-theme="light"]` override to a mid-tone token (`var(--color-muted)`, `--light-c-33`) — dark-mode accent tokens on a light background read as white-on-white invisible.

## Deploy pipeline — use `tools/deploy.sh`, never a hand-typed sequence

One command per deploy: `tools/deploy.sh web|android|all`. It builds, restarts
the service (only when `server/` changed), purges the CF edge, and rebuilds+
delivers the APK. Grep the script before extending it; its decisions are load-
bearing:

- **The APK bundles NO web assets** (R6 in `android/app/build.gradle`):
  `server.url` points the WebView at the live site, so web-only fixes need no
  APK rebuild — the phone picks them up through the tunnel. Only NATIVE changes
  (Kotlin, manifest, capacitor config, plugin) require gradle+Telegram. The
  script skips the whole APK loop otherwise; an "APK is stale" conclusion for a
  web-only bug is always wrong.
- Assets are `immutable` 1y keyed by hash; HTML revalidates at 60s (zone rule);
  open tabs self-heal via the build-id poll. After any JS change the ONLY
  mandatory edge action is the purge (and it is only needed because the catch-
  all rule can pin newer paths too).

## Verification checklist

1. `git status --short src/components/chat-landing.tsx` — clean (no `UU`).
2. `grep -n 'useMemo.*messages\.map' src/components/chat-landing.tsx` — **CRITICAL**: parent memo present at line ~1824, wrapping entire `.map()` with `useMemo(() => messages.map(...), [messages])`.
3. `grep -n 'requestAnimationFrame' src/components/chat-landing.tsx` — async fix present (fitComposer deferred).
4. `grep -n 'TurnTimeline = memo' src/components/chat-timeline.tsx` — component memo present.
5. `grep -n 'setInterval(updateColors, 5000)' src/native/shell-theme.ts` — ticker slowed.
6. `grep -n 'setTimeout(tick, 100)' src/components/chat-timeline.tsx` — reveal timer slowed.
7. `grep -n 'AppTheme' android/app/src/main/res/values/styles.xml` — transparent bars present.
8. `./gradlew assembleRelease` -> `BUILD SUCCESSFUL`.
9. APK timestamp new (`stat -c '%y'`).
10. Telegram delivery: `{"ok":true}` with `message_id`.
11. User confirms: installed new APK, faster on long chats (test on 200+ message chat if possible).
12. (USB): `adb pull .../astra-perf.log` — no errors; `stats()` shows `cookieAlive` = true, log age reasonable.