# Chat input / timeline performance audit (class-level)

Target: any chat UI with a chronological turn timeline where typing feels slow.
Always measure before fixing — the symptom is "lag", the root cause varies.

## Procedure (measurement-first)

1. Build a Playwright probe (`scratch/scale-probe.mjs` pattern) that logs in,
   opens the busiest session, then measures per-keystroke cost over 10 presses (`ta.press`)
   and records: message count (`[data-msg-id]`), DOM node count, avg keystroke ms, worst ms.
2. Repeat with an EMPTY chat (0 messages). If the empty case is fast (<5ms) but loaded chats
   scale with message count / DOM size, the timeline re-render is dominant.
3. If keystroke cost stays high regardless of message count, check the native ticker
   (`updateColors` interval) and the forced-layout autosize (`fitComposer` / `scrollHeight` read).
4. If the timeline component (`TurnTimeline`) is NOT memoized, wrap it: rename the
   component to `TurnTimelineImpl`, wrap the export with `memo`. This stops the parent
   (`ChatLanding`) from forcing a full history re-render on every keystroke.
5. Confirm the fix: rebuild the web bundle (or APK if native), re-run the probe, report
   before/after numbers — never "it feels faster" alone.

## The measurement trap

Never infer from the component source. A comment above a timer (`"measured as the typing
lag on android"`) is a hint, not proof — read the timer BODY; a guard missing from the
body means the timer fires unconditionally. A `useEffect` with a dep array that includes
the state its own callback writes (e.g. `bgItems`) creates a self-re-arming interval; that
looks like "network is busy" when it is just a timer that never settles. Check `setInterval`
frequency — 1200ms is fine for updates, but 5000ms is safer when typing is the dominant load.

## Shared-repo guard

Before editing any file:
- `git status --short` — a `UU` file (unmerged conflict) must NOT be edited blindly.
- `git cat-file -t HEAD:src/components/chat-landing.tsx` — confirm HEAD has the file
  (a concurrent session's untracked file may share a name but is not in HEAD).
- Apply changes to files that are clean (`??` untracked or tracked-but-not-conflicted)
  first; for conflicted files, resolve the conflict before applying any fix, never merge
  a fix into a conflict body.
- Commit only your paths (`git commit -- <path>`). A `git add -A` sweeps another
  session's untracked suite (e.g. `run-checks.mjs`, `ts-resolve.mjs`) into your commit
  and breaks fresh clones (untracked dependencies become tracked without their siblings).

## Native ticker (shell-theme)

`initShellTheme()` runs `updateColors()` via `setInterval`. Reducing the interval
from 1200ms to 5000ms removes a competing timer from the main thread during typing
bursts — a secondary win, not the primary root cause.

The design contract (never violated): the native bars are transparent (`Theme.AppCompat.DayNight.NoActionBar`
with `statusBarColor` and `navigationBarColor` transparent); the `.app-shell` CSS (`bg-void`
+ `padding-top`/`padding-bottom` = `env(safe-area-inset-top/bottom)`) paints the theme
under both bars. Do NOT call `StatusBar.setBackgroundColor()` — at targetSdk 36 it is
ignored for the status bar and cannot reach the navigation bar; it is a silent no-op.

## Reveal timer (`useReveal` — remaining dominant blocker after memo + async `fitComposer`)

After `TurnTimeline` memoization and the async `fitComposer` fix were applied together, the user confirmed (real device): "no noticable difference"; "installed and still very laggy"; "type whole sentences before a single letter appears". The remaining blocker is the continuous reveal timer (`useReveal`) updating state every 16ms (`window.setTimeout(tick, done ? 48 : 16)`), which competes with the typing event loop. Reduce both the initial and loop intervals to `100` ms for streaming segments:
```typescript
id = window.setTimeout(tick, done ? 48 : 100);
if (nRef.current < text.length) id = window.setTimeout(tick, done ? 48 : 100);
```
This is a secondary fix — apply it together with the memo and async layout fixes, verify with measurement (`scratch/scale-probe.mjs`), and confirm on the real device. Never rely on inference alone; measure before and after.

## User-confirmed measurement (2026-10-03, real device — Android app, rebuilt APK installed)

- Per-keystroke cost scales linearly with DOM size (3.3ms empty → 20.5ms at 7,366 nodes; Playwright `ta.press` over 10 presses).
- Timeline memo (`TurnTimeline` via `memo`) did not resolve the lag alone.
- Async `fitComposer` (synchronous `scrollHeight` → `requestAnimationFrame`) did not resolve the lag alone.
- Reveal timer frequency reduction (16ms → 100ms) is the remaining dominant blocker; rebuilt APK delivered via Telegram bot (`8631271551:AAHKXrC1SeBqkOyGFp2FW1PMJYY_QyUiEVE`, chat `8881524728`, message 133, file `app-release.apk`, 6.67MB, rebuilt 13:10 IST).
- Always measure with the `Diagnostics` plugin (`stats()` / `dumpLogs()`) after connecting the phone via USB; never infer from component source.

## Reference commands

- Playwright measurement: `timeout 280 node scratch/scale-probe.mjs`
- Verify memoization: `grep -c 'export const TurnTimeline = memo' src/components/chat-timeline.tsx`
- Verify async `fitComposer`: `grep -n 'requestAnimationFrame' src/components/chat-landing.tsx`
- Verify reveal timer: `grep 'window.setTimeout(tick' src/components/chat-timeline.tsx`
- Native ticker: `grep 'setInterval(updateColors' src/native/shell-theme.ts`
- APK theme verification: `aapt2 dump resources <apk> | grep -A3 'style/AppTheme'`
- Diagnostics plugin: `unzip -p <apk> classes.dex | strings | grep -i 'DiagnosticsPlugin'`
