# Visual-parity harness (astra-webui)

Proves "renders identically" with measurements. Built in `~/Work/scratch/astra-theme/wt/scripts/theme/parity/` (run.mjs + fixtures.mjs + capture.mjs + compare.mjs). Copy, don't re-derive.

## Order of operations
1. **Build the harness on the UNCHANGED baseline first; never in parallel with feature work.** A harness written alongside the feature shares its bugs.
2. **Prove determinism**: two captures of the same build must produce zero diffs. Any jitter = unfrozen animation or clock; fix before comparing anything real.
3. **Negative-control it**: mutate the built CSS by ONE alpha step (1/255) in a visible rule and require the compare to FAIL. Compare exit code, not stdout — a mutation run once sailed through because the compare's exit code was eaten by a pipe while the harness "passed" on a tainted dist.
4. Only then run feature-vs-baseline.

## Capture design
- One static server per build (SPA fallback, MIME by `extname`, `cache-control: no-store`).
- Mock `/api/*` + `routeWebSocket` (Playwright) with deterministic fixtures: fixed epoch seconds, fixed message set. Block CDNs (`esm.sh`, `jsdelivr`, `unpkg`, `skypack`) — the login WebGL background pulls from jsdelivr and is non-deterministic.
- Freeze animation in TWO passes: `getAnimations()` → `finish()` finite ones (they land on their final VISIBLE frame), `pause()+currentTime=0` infinite ones. A blanket negative `animation-delay` forces mid-enter frames at opacity 0 and flagged 327k false pixels.
- Per state: DOM tree walk of every element + `::before/::after/::placeholder`, colour-bearing computed props (`color`, `backgroundColor`, `backgroundImage`, borders, `boxShadow`, `textShadow`, filters, `fill/stroke`, `scrollbarColor`, `opacity`, …) joined with a unit separator; skip nodes marked `data-theme-engine-new` (UI the feature adds on purpose).
- Screenshots alongside JSON: computed-style diffs catch invisible changes; the pixel layer catches layout shifts the props miss. Report both a strict and a "significant" pixel count (delta > 2/255) — GPU dither is ±1 and must not gate.
- Click targets: use `:visible` pseudo + `.first()` + `force:true` when overlays intercept (composer trace, drawers with duplicate aria-labels). On failure, dump selector counts + body text — blind timeouts read as "page broken" when the page is fine.
- **Keep every probe runnable in well under the tool's foreground timeout, and pass an explicit `timeout` to the node call.** A multi-scenario matrix that launches a browser per scenario can run for minutes; when it exceeds the limit the tool promotes it to a background process and the foreground call returns nothing useful. Prefer several medium probes over one giant one, give each an explicit `timeout 280`, and when a probe does hang, kill the node PID directly (`kill -9 <pid>`) — `pkill -f` matching a pattern also present in the invoking shell can kill your own wrapper and leave the probe alive.

## Compare design
- **When two states SHOULD be identical, diff them directly — that is the strongest possible assertion.** For "the toggle must produce what a reload produces", the fresh-reload page IS the reference implementation: dump every custom property + the inline `style` override set + a surface computed-style list in both states and require the difference count to be zero. This found a 224-prop divergence that no pixel comparison or spot check would have surfaced. Report the count and track it to zero — a partial fix reads as success until you count.
- **Monkey-patch `CSSStyleDeclaration.prototype.setProperty` to log `[prop, value]` when you need to localize a value diff to a branch.** The value diff shows the symptom; the write log shows which code path wrote it. Note it needs `page.addInitScript` to catch boot-path writes — and a patch that throws before the app boots turns every subsequent selector wait into a timeout that looks like a broken page.
- Chrome serializes `rgb(var(--x)/a)` as `color(srgb r g b / a)` vs literals as `rgba(...)` — numerically identical, different spelling. Normalize `color(srgb ...)` → 255-scale `rgba(...)` before diffing, or a tokenized CSS shows thousands of fake diffs.
- Style diffs surface sub-pixel/1-alpha regressions the eye cannot see (a 1/255 border-alpha mutant showed as 16 computed-style diffs, 0 significant pixels). Trust style diffs over pixels for colour work.
- Compare exit code via `; echo rc=$?` AFTER the pipe — `cmd | tail` reports tail's status, so a genuine FAIL once read as success.

## Real-browser live check (post-deploy, not optional)
1. Mint `astra_session` from `~/.config/astra-webui/env` against `http://127.0.0.1:3011/api/login`, plant on the public domain (`ctx.addCookies`), never type the password.
2. Assert DEFAULTS first (shell renders, default colour tokens, optional layers absent) — "it booted" is not "default is unchanged".
3. Then exercise the feature through its real user path (e.g. set a palette key → reload → assert computed colour changed; 7/7 checks caught a dead engine that greps of the served bundle called "shipped").
4. Re-run `selfcheck.sh` against the public URL (needs `ASTRA_WEBUI_PASSWORD` exported from the env file) plus curl the served hashed bundles and grep engine markers.

## Cross-device / shared-state feature checks
For any feature whose point is "state reaches the other device" (theme sync, read state, presence), a single-browser test proves nothing — drive TWO contexts against one server and assert propagation:
- When comparing against a deployed baseline, build the ACTUAL pre-change HEAD into a throwaway worktree (`git worktree add <dir> <tag> --detach` + symlink node_modules) — a weeks-old snapshot reports every commit since as a regression. Note the sibling chat's boot path fetches history with `order=latest` (newest message LAST): oldest-first fixtures appear to "drop" early turns in the harness — that is the fixture/page interaction, not a regression; probe computed styles on synthetic nodes carrying the real classes when a style assertion does not need live data.
- Device A makes the change; assert the SERVER holds it (the push endpoint's state object), then device B (fresh context) applies it within one poll interval and its COMPUTED styles move.
- Playwright's `page.route("**/*", …)` mock intercepts new `/api/*` endpoints and returns the mock 404 — the real server route never sees the request and the feature "never fires". Re-route the new endpoint to a test-local echo (or unroute) BEFORE concluding the app is broken; this cost a full debug loop once.
- Boot-order dependency: if a boot-time apply BROADCASTS an event that a listener registers later in boot, the broadcast reaches nothing and the push never fires. Register listeners before the boot apply, or make the boot apply push directly.
- Assert persisted values through the browser's real reload path (set localStorage → `page.reload()` → computed style), not through module internals — the engine must re-apply pre-paint on boot for the persistence to be real.
