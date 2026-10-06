# Shape / scale architectures

Verified against **published package artifacts**, not documentation prose. Where a
widely-repeated claim is false, it says so.

## The one to copy: a single multiplier plus a separate "full" token

The only mature system whose shape control is a single runtime-swappable multiplier,
and the shape a runtime engine should take:

```css
[data-radius] {
  --radius-1: calc(3px  * var(--scaling) * var(--radius-factor));
  --radius-2: calc(4px  * var(--scaling) * var(--radius-factor));
  --radius-3: calc(6px  * var(--scaling) * var(--radius-factor));
  --radius-4: calc(8px  * var(--scaling) * var(--radius-factor));
  --radius-5: calc(12px * var(--scaling) * var(--radius-factor));
  --radius-6: calc(16px * var(--scaling) * var(--radius-factor));
}
[data-radius='none']   { --radius-factor: 0;    --radius-full: 0px; }
[data-radius='small']  { --radius-factor: 0.75; --radius-full: 0px; }
[data-radius='medium'] { --radius-factor: 1;    --radius-full: 0px; }
[data-radius='large']  { --radius-factor: 1.5;  --radius-full: 0px; }
[data-radius='full']   { --radius-factor: 1.5;  --radius-full: 9999px; }
```

Three ideas carry the design:

1. **`--radius-factor` is the mode switch.** One number moves the whole scale.
   Sharp is `0`, so sharp mode needs **zero rewrites** — existing tokens can stay as
   aliases.
2. **Pill mode flips a SEPARATE token, not the factor.** `--radius-full` is `0px` in
   every mode but pill. A pill is not "scale × huge"; conflating them is why naive pill
   modes break the surfaces that must never pill.
3. **`max(var(--radius-N), var(--radius-full))` is the pill idiom.** Every sized
   component composes it, so one declaration yields rounded-rect or pill based only on a
   token value. Anything that must never pill (code blocks, images, caret-aligned
   inputs) references `--radius-N` directly and is immune.

Components compose through per-component **aliases**, not raw scale references, so
re-pointing a component later is a one-line change.

## Naming: roundedness, not container size

Steps named for corner softness read consistently across a 24px chip and a 600px dialog;
steps named for container size do not. A widely-used design system's scale is:
`none 0 · xs 4 · s 8 · m 12 · l 16 · l-inc 20 · xl 28 · xl-inc 32 · xxl 48 · full`.
Its shipped web tokens are a narrower fixed subset — the `*-increased` /
`*-extra-large` steps are Sass-only composites with **no custom property**, so do not
plan around them.

**Asymmetric inner corners for grouped items** (menus, split buttons) are always composed
from symmetric steps, never given new values. The optical rule is
`outer radius − padding = inner radius`.

## A semantic `default` alias pays for itself

A `--shape-default: var(--shape-3)` lets every existing declaration reference *intent*
and re-point later without touching them. This is what makes a codemod's output
survivable — especially when the declarations being migrated number in the hundreds.

## Alias into the size scale, don't invent values

One mature shop keeps every radius step an alias into a shared 4px `size` scale, so
radii never drift off the grid; its type definitions even split "pick a scale step" from
"pick pill" at the compiler level. Mirror that discipline.

## The counter-example worth knowing

A large enterprise design system has **zero** radius tokens — verified zero occurrences
of the word "radius" in its theme package — with radius values sitting as literals in
component stylesheets, and its house style is square. It stays square precisely because
nobody introduced an escape hatch. That is what a hardcoded stylesheet becomes: not a
codebase with rounded corners, but one that can never change them. It is the argument
for doing the codemod rather than adding another override.

## Do not confuse this with a *component-size* scale

If the goal is only to round things slightly more, a `corner-size` extra property may
ship with no prefix at all (unlike `corner-large` → `--md-sys-corner-large`). Check the
shipped reference before assuming a prefix convention.

## Migration shape

1. Histogram the literals; the bucket structure is the lookup table.
2. Keep already-token-driven declarations untouched — they are the destination.
3. Map the odd shapes explicitly: `50%` is a circle, `9999px` is a deliberate pill,
   4-value shorthands are asymmetric composites.
4. Re-point the framework's own default tokens as aliases of the new scale, or half the
   app will not move.
5. Prove completion by asserting the literal count reached zero, not by eye.
