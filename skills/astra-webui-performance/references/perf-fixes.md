# Performance Fixes (session 2026-10-03)

## Measurements (Playwright scale-probe.mjs, mobile viewport 390x844)

| Chat size | DOM nodes | Keystroke avg | Before/after |
|---|---|---|---|
| Empty (0 msgs) | 316 | 3.3ms | Fixed by memo |
| 6 messages | 3,259 | 14.9ms | Fixed by memo |
| 7 messages | 7,366 | 20.5ms | Fixed by memo |

Root causes (applied in order):
1. Blocking `fitComposer` (deferred via `requestAnimationFrame` inside `fitComposer`)
2. Parent message memo (`useMemo` on `.map()` in chat-landing)
3. Timeline memo (`TurnTimeline` with `memo`)
4. Reveal timer reduced (16ms -> 100ms)
5. Native ticker reduced (1200ms -> 5000ms)

## Conflict resolution
Always check `git status --short src/components/chat-landing.tsx`. If `UU`, resolve before editing (`git checkout --conflict=merge`). Never patch files with `<<<<<<<` markers.

## Verification
Always collect `stats()` + `dumpLogs()` (diagnostics plugin) before making performance claims. Pull `adb pull .../astra-perf.log` when USB connected. Confirm APK rebuilt (`BUILD SUCCESSFUL`), timestamp new, delivered via Telegram bot (`8631271551:AAHKXrC1SeBqkOyGFp2FW1PMJYY_QyUiEVE`), user installed and reports faster typing.

## Proving a render-layer fix live (in-app fiber probe)
When a claim depends on what a React component ACTUALLY received at runtime (not what the parser/sanitizer hands it on paper), dump it from the DOM instead of reading code:

```js
// from a rendered node: find its fiber, walk f.return until the prop you want
const c = document.querySelector('.recharts-wrapper');
const key = Object.keys(c).find(k=>k.startsWith('__reactFiber'));
let f = c[key], hops=0;
while (f && hops<80) { if (f.memoizedProps?.data) return JSON.stringify(f.memoizedProps.data); f=f.return; hops++; }
```

Caught a chart-data bug this way that every code-path reading missed: a sanitizer mid-wire rewrote the field the renderer reads (`points` → left only `data`), so bars rendered 0-height while all component-level checks passed. For spec-shaped props walk up to a fiber with `memoizedProps.spec && spec.blocks`.

Login-state note: after a server restart mid-debug a probe tab may show the login password form — that is session expiry, re-auth and continue (password in `~/.config/astra-webui/env`), not a regression.
