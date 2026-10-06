# Theme engine, backdrop media, and header/sidebar glass

Verified findings from the theme + media pass (moved out of SKILL.md to keep it under the size cap). Read the theme rows here before touching `dashboard-themes/`, backdrop media, or `.sidebar-glass`.

## Theme engine (design verified + prototyped; full build interrupted)
- Native CSS custom props (`:root` + `[data-theme="light"]`) with `color-mix()` / OKLCH derivation.
- DTCG-inspired flat `.astra-theme.json` (dot notation); import shadcn `cssVars` / tweakcn.
- base16 / Base24 YAML (tinted-theming/schemes) as a theme-source format; Style Dictionary optional export.
- **Glows dark-only** (`--glow-on`: 0 light, 1 dark).
- A theme = colors + optional background. Shapes, typography and motion stay fixed across themes.
- Theme store = `ThemeStore` card grid with scoped var previews + editor; filter All / Dark / Light.

## Lightningcss gotcha (hit 3x — VERIFIED)
`-webkit-` twin drops the standard `backdrop-filter` property; write the STANDARD property only in source. Confirm via grep of the SERVED css, never `src/`.

## Backdrop media (deployed + Playwright Pixel 7 + live-site `elementFromPoint`)
- `position: fixed; inset: 0`.
- Without a backdrop the theme void (`--color-void`) fills naturally.
- Dim / scrim: `color-mix` over `--bg`.
- YouTube plays through a bare `youtube-nocookie.com` iframe with `autoplay=1&mute=1&controls=0&loop=1&playlist=<id>`. **`loop=1` + `playlist=<same id>` is YouTube's OWN seamless loop** — `loop=1` alone is ignored on a single-video embed, the `playlist` is what makes it repeat. Do NOT load the ~500KB IFrame API just to seek on `ENDED`. Load it lazily, ONLY when a saved position >1s must be restored; with no saved position (a freshly picked wallpaper, the common case) ship the bare iframe and no JS. Also `iv_load_policy=3` keeps YouTube's chrome out of the frame.
- `localStorage` resume, 3s throttle, `seekTo(saved, true)` — position key is per-source (`astra-bg-video-pos:<src>` / `…:yt:<id>`), so switching wallpapers keeps each one's position.
- Blur: apply `filter: blur(Npx)` on the CONTAINER, not the media, so the blur samples the composited frame once and the dim scrim stays sharp above it. Pair it with `transform: scale(1 + N/90)` — without the scale the blurred element's transparent 1px rim shows as a dark halo at the viewport edge. Emit the style only when `N > 0` so the default path carries no filter cost.
- Stacking: `aside#astra-sidebar { position: relative; z-index: 2; }` — deployed and verified in the served bundle.

## Header / sidebar glass (VERIFIED)
- `.mobile-accent-header` and `.sidebar-glass` = `blur(29px) saturate(1.25)` over `color-mix(in oklab, var(--color-midnight) 45%, transparent)`.
- Mobile drawer uses `.sidebar-glass`; verified PASS on Pixel 7 emulation (drawer opens at x=0, glass matches bubble intensity `blur(29px) saturate(1.25)`, closes at -288, zero page errors; session `20261002_170946`). Header/logo content-fit (`h-16` = 64px; chat header `lg:min-h-0` + `lg:py-2.5`).
- `.composer-trace-step { stroke-linecap: butt }` is load-bearing: `round` paints a bright dot at path position 0.

## Build / check discipline for this area
`npm run build` (look for `built`) -> restart -> `scripts/selfcheck.sh` (`ALL PASS`) -> verify the SERVED hashed css (`grep -o '.sidebar-glass{…}'`), never `src/`.

## Cross-session coordination
A concurrent session edited the same files; fixes merged cleanly on top. `git stash` unrelated work; verify SERVED `.css` rather than `src/`.

## Generating a palette from two accents (OKLab) — the theme builder's engine

Pure, tested module `src/lib/color-engine.ts` with its own `color-engine.check.ts` (pinned in the
regression manifest). Keep colour maths OUT of the React component: the builder's verdict decides
whether a theme is readable, and a theme syncs to every device, so the maths must be assertable.

**Derive in OKLab, never sRGB.** sRGB is perceptually uneven — a fixed lightness delta looks like a
much bigger step in yellow than in blue, so stepping in sRGB produces ramps whose perceived contrast
drifts by hue. Mix and step in OKLab and equal steps look equal at every hue.

Three bugs the check file caught that eyeballing would not have:

1. **The OKLab forward matrix's `a` and `b` rows are easy to get wrong** and the failure is loud but
   localised to the transform — every generated colour came out magenta while the code still type-checked
   and still produced plausible hex strings. Correct rows: `a = 1.9779984951·l − 2.4285922050·m + 0.4505937099·s`,
   `b = 0.0259040371·l + 0.7827717662·m − 0.8086757660·s`. ALWAYS assert a hex → OKLab → hex round-trip
   within 1/255; that single assertion catches a bad matrix immediately.
2. **Ground ramps must carry the accent's HUE at LOW chroma, not full accent chroma.** Mixing the accent
   toward neutral 96% still leaves each palette's cast, and a saturated dark ground reads as
   brown/espresso rather than as a theme. Scale the chroma down explicitly (≈0.02 dark / 0.026 light)
   while keeping the hue direction — a chroma of exactly 0 makes every theme the same neutral grey app,
   so assert a floor as well as a ceiling.
3. **Verify your own expectations, not just the code.** Two assertions in the first run were wrong, not
   the implementation: `#999999` on white is 2.85:1 (fails even the 3:1 large-text bar), and OKLab's
   black↔white midpoint is sRGB byte **99**, not 128 — that darkness IS the point of the space. A test
   asserting a wrong belief is worse than no test, so when a check fails, first ask whether the code or
   the expectation is wrong.

Report measured ratios, never assumed ones: the builder recomputes `contrastRatio(role, card)` live and
shows the number, so a bad edit cannot quietly produce an unreadable role. Text roles owe 4.5:1 against
the CARD surface (`--color-midnight`) — the worst case, not the page ground; accents used for borders and
icons owe the 3:1 non-text minimum. A generator that cannot hit those must report failures rather than
throw, and the check asserts zero failures across a spread of accent pairs in BOTH modes.

## Making a user-built theme available everywhere

A theme the user creates must sync to every device and app, which constrains storage:

- **Never write user themes into `src/theme-engine/palettes.json`.** It is generated by
  `scripts/theme/build-palette.mjs` and regenerated on every palette build, so a hand-edit there is erased.
  Store user themes separately (own `localStorage` key) and merge them at the SINGLE lookup seam
  (`allPalettes()`), so the picker, `applyPalette`, `mergeCustom`, `currentPaletteId` and the sync layer
  all see both without being individually rewritten. Audit with `grep -c 'palettes.find'` — every
  remaining bare call site is a lookup that will silently miss user themes.
- Sync the whole list last-write-wins, never per-id merge, so a DELETE on one device propagates instead of
  being resurrected by a merge on another.
- A user theme must define BOTH modes — make it structural, not a UI convention: the generator only ever
  produces both, and a stored theme missing a variant is rejected on READ (client) and on WRITE (server).
  A dark-only theme is not a valid stored state.
- Server-side shape-validation on the sync route matters more than usual: that file is the one place a
  malformed theme can reach every client at once. Round-trip it live with a minted cookie
  (`PUT` then `GET` `/api/theme/state`) and DELETE the probe you pushed — test data on a live state file
  outlives the session.

## Command popups / docked panels must share the CHAT COLUMN width

The chat column is `max-w-[52rem]` (832px) — the feed and the composer both use it. Every popup, dock or panel rendered in that column must carry the SAME constraint or it visibly juts out past the bubbles:

- `/compact`-style `CommandSurface` had NO width constraint (full-bleed to the container).
- `.suba-wrap` (sub-agent panel) and `.bgd-wrap` (background tasks dock) used `max-w-3xl` = 768px — 64px narrower than the column, the opposite error.

Fix: wrap the surface in `mx-auto w-full max-w-[52rem]`, and give docked panels `w-full max-w-[52rem]`. Grep for `max-w-3xl` and bare panel mounts before adding any new popup. Assert it by measuring `getBoundingClientRect().width` of the popup against `.chat-composer` and requiring a delta <= 2px.

## Parked / unverified — do not claim these
- Unified slash popup (build-green, never verified in a browser).
- Video resume live reload (tracker wired for uploads + YouTube — `YT global: true`, `seekTo(saved,true)`, throttle fixed at 3s; session `20261002_170946` applied owner steer `continue playing / maintain global tracker`; cross-reload resume verified in build but not yet observed live across reload).
- End-session sidebar row-menu live click test (header button removed; `chats-panel.tsx` `ast-row-menu` item wired with `LogOut` import, `App.tsx` passes `onEndSession` callback POSTing `/api/training/end-session`; build passes; session `20261002_170946` — live click not run).

Verified since this note was written: `/api/theme/state` cross-device sync (two-device push/adopt observed), the sidebar `z-index: 2` stacking guard, and the theme/backdrop/glass rules above.