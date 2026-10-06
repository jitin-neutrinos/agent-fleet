# Neutral skeletons: theme-derived greys (owner 2026-10-03, commit a1ece86)

The report: "skeletal loading screens must be dark/light contrast adjusted grey —
some are orange, some are blue." Both halves were real, and the cause was a single
class of mistake repeated across four surfaces.

## The root cause: an ANNOTATED channel var carrying an ACCENT role

`tokenize.mjs` emits an `--r-c-N: <role>` annotation beside every channel var. The
skeleton rules used channel vars that resolve to **accent roles**:

| surface | var | annotation | role value | result |
|---|---|---|---|---|
| `.ast-sk::after` (shimmer sweep) | `--c-69` | `cyanx` | `#ff5c1f` Fire / `#22d3ee` Astra / `#38bdf8` Water | orange, cyan, blue |
| `.ast-cv-doc-skeleton` | `--c-89` | `redx` | red family | RED under Fire |
| `[data-theme="light"] .ast-sk::after` | `--light-c-45` | `cyanx` | `#0369a1` | blue on paper |
| `config-page.tsx` loading | hardcoded `bg-white/5` | — | literal white | invisible on light paper |

The fills were already neutral — only the **sweep** carried hue, which is why the
report read as "some are coloured" rather than "all are coloured".

**Rule this establishes:** a NEUTRAL surface (skeleton, hairline, placeholder,
divider) must never be built from a channel var whose `--r-c-N` annotation is an
accent (`cyanx` / `violetx` / `amber` / `redx` / `emerald`). Check the annotation,
not the hex — the hex looks neutral in the default palette and only reveals itself
under another one. This is the inverse of the frozen-accent audit elsewhere in this
skill: that pass finds *unannotated* saturated vars, this one finds *annotated* vars
whose role is wrong for the surface.

## `color-mix` is NOT enough to make a neutral

The obvious fix — `color-mix(in oklab, var(--color-void), var(--color-brandtext) N%)`
— still carries each palette's own cast, because the palette's ink is not a neutral:

| palette | sat of the 22% mix (dark) |
|---|---|
| astra-ui | 0.083 |
| fire | 0.126 |
| water | **0.288** |
| earth | 0.083 |
| wind | 0.103 |

Water at 0.288 is plainly blue — it would reproduce the original bug at lower
amplitude.

**The working form** (shipped as `neutralGrey()` in `src/lib/theme-store.ts`):

1. Compute the oklab **cone lightness** `L` of both endpoints (cbrt of the linear-RGB
   · LMS matrix dot product).
2. Interpolate only that scalar: `L = L_ground + (L_ink - L_ground) * pct`.
3. Rebuild as an **achromatic** colour: for a grey all three cone responses are
   equal, so feed `L³` back through the matrix on every channel.

Saturation comes out exactly `0`, and the value still sits at the right contrast
against that palette's own ground. Percentages (`SKEL_PCT`):
`dark {fill 0.22, sweep 0.34}`, `light {fill 0.10, sweep 0.26}`.

Do NOT memorize the oklab inverse matrices from memory — they get transposed and
the round-trip check fails silently (every channel clamps to `#ff0000`). Compute
the inverse with Gauss-Jordan and assert a round-trip on known colours first.

## Wiring: the runtime owns per-palette, the stylesheet owns the baseline

- `--ast-sk-fill` / `--ast-sk-sweep` are written by `syncThemeColorMeta()` in
  `theme-store.ts`, beside the existing slate ramp. That function already runs on
  palette change, mode flip, remote sync and boot, so skeletons follow all of them
  with no new call sites. Verified by reading computed styles under each palette.
- The stylesheet keeps the Astra UI literals in the `@theme` block (dark) and
  `[data-theme="light"]`. Note they live in **`@theme`, not `:root`** — that is where
  every `--color-*` default lives.

## The lightningcss trap on relative colour

`oklch(from … l 0 h)` DOES survive minification (it emits a literal fallback plus an
`@supports (color:color-mix(in lab, red, red))` twin), but the **static fallback is
computed against the wrong scope**. Declaring the relative form in both the
`@theme` block and `[data-theme="light"]` produced a DARK grey fallback in light mode
(oklch L 25.4% instead of ~88%) because the minifier resolved it against the root
tokens and ignored the light-scope overrides. Any browser without relative-colour
support would have shown a dark slab on light paper.

Fix: write the fallback hex **literally per mode** and let the runtime own the
per-palette value. Always inspect the SERVED `dist/assets/index-*.css` — the source
looks correct and only the built artifact shows the bad fallback.

## Measured result (all 5 palettes x both modes, live engine)

Fill contrast against the page ground: 1.61–1.66:1 dark, 1.23–1.26:1 light.
Sweep over fill: 1.45–1.52:1. All 40 computed colours have `r == g == b`.

## The gate

`src/lib/skeleton-grey.check.ts` (manifest row RG-059) pins this:
- no skeleton paint rule may reference `--c-69`, `--light-c-45` or `--c-89`
- the sweep must read `--ast-sk-sweep`, the fill `--ast-sk-fill`
- both tokens defined for both modes
- the shipped maths re-derived in the check must equal the stylesheet literals
- every palette's derived grey must have `sat == 0` and sit in the contrast bands
- no component reintroduces a hand-rolled `bg-white/5` placeholder

Adding it turned `npm run check` red until the manifest row existed **in the same
change** — the gate refuses unpinned checks by design. It caught two real defects
on first run: hand-written literals off by 1–2 units from the shipped maths, and a
light sweep at 1.25:1 under the 1.3 floor (fixed by moving light sweep 0.20 → 0.26).

## Verifying it yourself

```bash
node --import ./scripts/ts-resolve.mjs src/lib/skeleton-grey.check.ts
npm run check && npm run build
```
Then drive the live engine and read computed styles under each palette — a build
being green proves nothing about what a surface actually paints:

```js
localStorage.setItem('astra-palette', 'fire');   // then reload
// read getComputedStyle(el).backgroundColor and the ::after backgroundImage,
// assert r === g === b on every value
```