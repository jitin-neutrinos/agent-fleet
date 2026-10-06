# Performance Audit Reference (mobile-app-optimization)

## Browser measurement commands

Playwright probe (mobile viewport, touch enabled):
```typescript
await p.goto(BASE + "/", { waitUntil: "domcontentloaded" });
await p.waitForSelector("textarea", { timeout: 25000 });
const t = []; for (let i = 0; i < 10; i++) { const a = Date.now(); await ta.press("a", { timeout: 4000 }); t.push(Date.now() - a); }
console.log(`avg=${t.reduce((x,y)=>x+y,0)/t.length}ms worst=${Math.max(...t)}ms`);
```

Measure scaling with chat size: open busiest session, measure `dom` nodes and `messages` count, then type.

## Blocking layout fix (`fitComposer`)

Symptom: "type whole sentences before a letter appears" = synchronous `scrollHeight` read blocking the event loop.

Fix: wrap measurement in `requestAnimationFrame` (applied in `chat-landing.tsx`):
```typescript
requestAnimationFrame(() => {
  if (!taRef.current) return;
  const current = taRef.current;
  current.style.height = "auto";
  const h = Math.max(current.scrollHeight, 44);
  current.style.height = `${Math.min(h, 200)}px`;
});
```

Also reduce `LOW_SPEC` guard to avoid premature skips that leave tall composers.

## Timeline memo (`TurnTimeline`)

The timeline component (`chat-timeline.tsx`) should be exported via `memo`:
```typescript
const TurnTimelineImpl = function({...}) { ... };
export const TurnTimeline = memo(TurnTimelineImpl);
```
This prevents full history re-render on each keystroke when the parent (`ChatLanding`) re-renders.

Note: memoization alone does NOT fix blocking layout — it only reduces render cost. The real blocker is the synchronous layout read.

## APK verification

After build (`./gradlew assembleRelease` with env):
```bash
aapt2 dump xmltree app/build/outputs/apk/release/app-release.apk AndroidManifest.xml | grep -E 'AppTheme|NoActionBarLaunch'
aapt2 dump resources app-release.apk | grep -A4 'resource 0x7f120009' | head -5
unzip -p app-release.apk classes.dex | strings | grep -i 'DiagnosticsPlugin'  # verify plugin class present
```

## Conflict resolution

When `git status --short` shows `UU` (unmerged):
```bash
git status --short src/components/chat-landing.tsx
grep -nE '<<<<<<<|=======' src/components/chat-landing.tsx
```
Resolve before applying edits. If the fix belongs in a clean file (`chat-timeline.tsx`), apply there instead to avoid corrupting the concurrent session's work.

## Ticker overhead (`shell-theme.ts`)

Reduce from 1200ms to 5000ms:
```typescript
// Before: setInterval(updateColors, 1200);
// After: setInterval(updateColors, 5000);  // removes competing timer from typing event loop
```

## Build environment

Always source the keystore env before building:
```bash
source ~/Work/services/astra-android/astra.keystore.env
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk
export ANDROID_HOME=$HOME/Work/android-sdk
export KEYSTORE_PASSWORD
```
Build command: `./gradlew assembleRelease --no-daemon`

## Reveal timer (`useReveal` in chat-timeline)

The continuous reveal timer (`setTimeout(tick, done ? 48 : 16)`) updates state every 16ms during live streaming — that competes with the typing event loop. Reduce to `100` ms for streaming segments so the event loop has room to process keystrokes:
```typescript
// Before: window.setTimeout(tick, done ? 48 : 16);
// After (both initial + loop): window.setTimeout(tick, done ? 48 : 100);
```
Note: memoization + async `fitComposer` alone did NOT eliminate lag (verified on real device — user reported "still very laggy" after both fixes). The reveal timer frequency is the remaining dominant blocker.

## User-confirmed measurement (2026-10-03, real device)

Real device confirmed by user's message: timeline memo + async `fitComposer` produced "no noticable difference". Reveal timer reduced from 16ms → 100ms; rebuilt APK delivered via Telegram bot (`8631271551:AAHKXrC1SeBqkOyGFp2FW1PMJYY_QyUiEVE`, chat `8881524728`). Always measure with `scratch/scale-probe.mjs` or the `Diagnostics` plugin (`stats()`, `dumpLogs()`) — never infer from component source alone.
