# Canvas surface traps

Concrete mechanisms behind the triage steps. Each entry: symptom → mechanism → fix shape.

## Chart libraries position chrome absolutely inside the plot

**Symptom:** a legend renders above the plot, or overlapping the axis tick labels, or
floating at an odd offset that changes with viewport.

**Mechanism:** recharts 2.x (and most charting libs) render the legend wrapper as
`position: absolute` and derive its offsets from the chart `margin` via an internal
default-position helper. A chart authored with a near-zero margin
(`margin={{ top: 6, right: 6, bottom: 0, left: 0 }}`) gives the legend nowhere to sit but
over the plot. `verticalAlign="bottom"` alone does not move it out of the plotting box.

Confirm by reading the vendored source — `node_modules/recharts/lib/component/Legend.js`
— look for `position: 'absolute'` and the default-position helper. Do not infer from props
documentation.

**Fix shape:** render the legend as ordinary DOM *outside* the chart container, below it,
in normal document flow. Reuse the design system's legend classes and the exported series
colour array. Self-sizing chart kinds that already draw their own legend in normal flow
should be left alone — check before you change every chart.

**Also:** legends and tooltips count as chrome. Content may never be covered by them.

## `text-overflow: ellipsis` is a no-op on a flex box

**Symptom:** a value is cut mid-glyph with no ellipsis — `+38ms` renders as `+38m`, a path
renders as a truncated fragment.

**Mechanism:** `text-overflow` only takes effect on a *block* container that has
`overflow: hidden`. On an `inline-flex` chip (a common KPI delta/badge pattern) the
property is inert and the text is simply clipped at the box edge. Adding `max-width` makes
the clip happen silently instead of at the container edge, which is what makes it look
like a rendering bug rather than a config one.

**Fix shape:** pick one —

- wrap by word: `white-space: normal` + `overflow-wrap: break-word` on the flex chip, plus
  `min-width: 0` so the shrink chain reaches it; or
- keep one line and make the ellipsis real: put the ellipsis on a block child of the chip
  (`display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap`).

Never `white-space: nowrap` + `overflow: hidden` on the flex chip itself.

## Duplicate selector declarations

**Symptom:** a style fix "doesn't take", or two rules for the same class disagree and the
wrong one wins.

**Mechanism:** the same selector declared twice in one stylesheet with contradictory
values. Which one the cascade picks is not reliably the later one once media queries,
specificity and layers are involved — and the built asset may not match `src` at all if the
build is stale or another session reverted the line.

**Fix shape:** count hits (`grep -n "<selector>" file.css`); two non-media-query rules is
the defect. Delete the stale one. Then grep the **built** artifact for the property to
confirm the winner. Never assume source order decided it.

## Normalizer branch order

**Symptom:** a block that is valid per the spec renders as an empty state.

**Mechanism:** the normalizer collects generic array fields (`items`, `nodes`) before the
kind-specific branch runs. The generic collector consumes the very field the specific
branch needed, so the specific branch produces nothing and the block is rejected downstream
as empty.

**Fix shape:** order kind-specific branches FIRST, with a comment saying they must run
first and why. When a spec sanctions two authoring shapes for one kind, give each its own
branch and a check per shape.

## A self-sizing chart collapses to a 0×0 svg

**Symptom:** the card shows its title and legend but the plot area is empty, although the
data parsed fine. `svg.getBoundingClientRect()` is 0×0, or the plot wrapper has height 0.

**Mechanism (two causes were found together; check both):**
1. The chart draws itself from its own measured width/height (nivo sankey/treemap/funnel,
   a hand-rolled SVG) but was mounted inside the frame built for the other chart family: a
   fixed-height `ResponsiveContainer`. It then has no definite box of its own (a percentage
   height inside an auto-height parent resolves to 0), so the library can measure 0.
2. A blanket rule such as `.chart svg { max-width: 100%; height: auto }`, written for the
   recharts family, overrides an svg that is sized ONLY by its `width`/`height` attributes;
   `height: auto` on such an svg is 0.

**Fix shape:** give self-sizing kinds their own render branch outside the fixed-height
container, with an explicit pixel `height` on the plot element; scope the blanket svg rule
away from them (`:not(.that-chart)`). Confirm by walking `document.styleSheets` for every
rule that matches the plot element rather than trusting source order.

## `var(--x)` colours inside chart libraries

**Symptom:** chart text or marks render black on a dark card (measured about 1.1:1), in one
library's charts only.

**Mechanism:** SVG presentation attributes and many library theme objects do not resolve CSS
custom properties. Worse, a library that DERIVES a colour (nivo's default label colour is "a
darker shade of the node colour") runs the value through d3-color, which cannot parse
`var(--x)` and returns `rgb(0, 0, 0)`.

**Fix shape:** resolve the variable to a concrete colour at render time
(`getComputedStyle(document.documentElement).getPropertyValue("--x")`), re-read when the
theme attribute changes (a MutationObserver on `data-theme`), and pass concrete colours to
the library's theme AND its colour props (for example `labelTextColor`). Audit by computing
each `<text>`'s resolved `fill` against the card background (WCAG ratio >= 3:1), not by eye.

## A block that parses to `null` vanishes without a trace

**Symptom:** the card is fine but one chart or table is simply absent ("blank", "missing").

**Mechanism:** parsing is tolerant PER BLOCK: every block that validates is kept, invalid
ones are dropped silently, and only a card with no valid block degrades to raw text. A
whitelist stricter than the shapes authors naturally write (point pairs for a scatter,
`{x, y}` objects) therefore deletes the block with no error anywhere.

**Fix shape:** run that block alone through the real parser (`null` = dropped); normalise the
natural shapes inside the parser; add one check per accepted shape plus one proving the shape
stays rejected where it does not belong (pairs must not leak into a bar chart).

## Measuring text integrity in a real browser

Define each defect so a script can count it, then run it at 320, 390, 768 and 1280 px:
- **Split word** — a word's `Range.getClientRects()` land on different line tops (skip
  hyphen/slash-joined tokens).
- **Widow** — the last line of a multi-line paragraph is one short word (about 7 characters
  or fewer). Exempt columns narrower than ~9em (a prose cell in a 3-column table at 320 px):
  wrapping alone cannot fix them and a sideways-scrolling table is worse, so report them
  separately instead of failing.
- **Ellipsis / silent clip** — a computed `text-overflow: ellipsis` on prose, or a box whose
  `overflow` is not visible and whose `scrollWidth` exceeds its `clientWidth`.
- **Spill** — an element's right edge past its card's.
- **Squeezed chip** — a value chip wrapped onto several lines while narrower than ~120 px.

Fix the CLASS with one authoritative block of family rules (`white-space: normal;
overflow-wrap: break-word; word-break: normal; hyphens: none`, `text-wrap: pretty` on prose,
`balance` on labels), exactly one declaration per selector, and a non-breaking space joining
a trailing figure or unit to its title so it cannot orphan on its own line. Grid tracks that
hold labels should be `minmax(min-content, 1fr)` so a label is never squeezed below its
longest word.

## Reading a saved page capture

A Safari `.webarchive` is a **binary plist, not a zip** — `unzip` fails with
"End-of-central-directory signature not found". The payload is still readable and is
genuinely useful evidence of the symptom:

```bash
strings -n 6 capture.webarchive   # archived HTML, every computed style inline
```

That inline style dump is the fastest way to see a clipping `max-width`, a `nowrap` with
no ellipsis, or a missing `min-width: 0`. Still compare its capture time against the
deploy before treating it as current behaviour.

For structure rather than a style dump, load the plist with `plistlib` and take the
`WebMainResource` entry's `WebResourceData`: that is the page HTML as bytes. Write it to
scratch and parse it to get the visible text and the inline styles of the exact elements
the user saw.
