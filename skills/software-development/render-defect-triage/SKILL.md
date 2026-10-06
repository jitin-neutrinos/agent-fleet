---
name: render-defect-triage
description: "Use when UI renders wrong: blank, overlapping, clipped."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Debugging, CSS, Charts, Frontend, Rendering, Canvas]
    category: software-development
    related_skills: [dogfood, web-design-guidelines, systematic-debugging]
---

# Render-defect triage

## When to Use

- A user reports a surface renders wrong: blank, missing, overlapping, clipped mid-word,
  chrome in the wrong place, or text that breaks badly on a phone.
- An attached screenshot or saved page evidences a visual defect you have not yet reproduced.
- A fix "didn't take" and you suspect the built artifact differs from source.

Skip it for purely behavioural bugs with no visual symptom (a wrong API response, a state
machine taking a wrong branch) — use `systematic-debugging` instead.

A user reports that something *looks wrong*. The report is a symptom in their words, not a
diagnosis. This skill is the order of work that turns "the flow chart is blank" and "the
legend is at the top" into one confirmed root cause with a check that fails before the fix
and passes after.

Applies to any declarative/generative UI: canvas card renderers, chart libraries, CSS
layers, component libraries, and PRINT/HTML-to-PDF output.

**Print/PDF has its own measured trap set** — `attr()` crashing WeasyPrint page
margin boxes, `body { string-set }` pinning one running header to every page,
flexbox cross-axis stretch silently overriding an image's width so it renders
~4x too tall, and how to prove an image is undistorted by comparing drawn aspect
ratios against the source. Read `references/print-and-pdf-render-traps.md`
before building or fixing a paginated document.

On the Astra web UI canvas, the owner's standing laws (nothing overlaps, legends at the
bottom, text wraps only between words, theme accent only, rounded rectangles) bind every
fix: read `references/astra-canvas-laws-and-audits.md` before changing anything.

For a REGISTRY or GALLERY that renders a component's own source at runtime
(shadcn-style store, component catalogue, live canvas): the failure mode is
"renders nothing and the page says it worked". Read
`references/component-preview-runtime-traps.md` before touching the bundler —
it covers `export default` detection, React discarding non-renderable trees
without throwing, observer-gated opacity-0 content, the rewriter-before-resolver
ordering trap, and the two-gate split.

## Order of work

Cheap discriminators first. Each step names the report wording, because that wording is
usually the only clue to which layer broke.

### 1. Establish whether the evidence is current

Before reading a single line of source, compare the evidence's capture time against the
deployed build. A screenshot or saved page hours older than the last deploy can show a bug
that is already fixed — chasing it wastes a cycle or reintroduces a solved problem.

- Served/deployed state: the service's active-enter timestamp, the build artifact mtime,
  or whatever the platform exposes.
- Static captures (saved pages, `.webarchive`, screenshots): useful as evidence of the
  SYMPTOM — they carry computed styles inline, so a clipped value or a missing ellipsis is
  visible immediately — but never as proof of current behaviour.

Confirm against the LIVE build in a browser before fixing anything, and say plainly in the
report which evidence was stale and which was measured.

### 2. Data layer — "the card is blank", "no data", "nothing shows"

A block rendering an empty state usually means its input never reached the renderer, not
that the renderer is broken.

- If the component spec documents **more than one authoring form** for the same widget,
  trace EVERY form through the parse/normalize step to the renderer. A form with no
  normalize branch falls through to the empty state and reads as a valid spec that cannot
  render — invisible until someone uses the second form.
- Watch branch ORDER in the normalizer: a generic collector (`items` / `nodes`) placed
  before the kind-specific branch consumes the field the specific branch needed.
- Guard on the shape you actually read. A field legitimately either an array or a binding
  expression must be narrowed before any `.map`/`.length`, or one malformed block throws
  inside render and takes the whole card down.
- A block that VANISHES (no empty state, the rest of the card renders fine) was dropped by
  validation, not rendered empty. Feed that one block to the real parser first (`null` =
  dropped). The usual cause is a natural data shape the whitelist rejects (a scatter's
  `[[x, y]]` pairs); normalise it in the parser and pin it there, rather than teaching
  authors a stricter shape.

### 3. Renderer layer — "at the top", "covering the axis", "floating oddly"

For chrome that belongs outside the drawing, suspect the LIBRARY's positioning, not the
props you passed.

- Read the vendored source (`node_modules/<lib>/...`) rather than trusting prop docs. Chart
  libraries commonly position legends/tooltips `position: absolute` INSIDE the plot and
  derive offsets from the chart `margin`; a near-zero margin gives them nowhere to sit but
  on top of the plot.
- Fix shape: render that chrome as ordinary DOM BELOW/OUTSIDE the plotting container, in
  normal document flow, reusing the design system's existing legend/badge/label classes
  rather than fighting the library.
- A single-series chart still gets a legend — an explicit name beats an ambiguous chart.
- Content is never covered by chrome. This is a design law, not a preference.

### 3b. Layout layer — "blank" although the data arrived

Measure the drawing before reading chart code: the `<svg>`'s `getBoundingClientRect()` and
its `width`/`height` attributes. A 0×0 svg, or a plot wrapper of height 0, means the plot
never got a box, whatever the props say.

- A SELF-SIZING chart (draws itself from its own measured box) nested in a frame whose
  height was set for a different chart kind has no definite box of its own and can measure
  0 (a percentage height inside an auto-height parent resolves to 0). Give self-sizing
  kinds their own branch OUTSIDE the fixed-height container and an explicit pixel height
  on their plot element.
- Then list every rule that matches the plot element (walk `document.styleSheets`, test
  `el.matches(rule.selectorText)`). A blanket `svg { height: auto }` written for another
  chart family zeroes an svg sized only by its attributes; scope it out with `:not(...)`
  instead of overriding it.
- Unreadable chart text (black on a dark card) is measured, not eyeballed: compute each
  `<text>`'s resolved `fill` and its contrast against the card (>= 3:1). SVG attributes and
  library colour derivations do not resolve `var(--x)`; hand the library a concrete colour
  resolved at render time (mechanism in `references/canvas-surface-traps.md`).

### 4. Style layer — "text is cut off", "broken words"

Two distinct silent mechanisms. Check both.

1. **Contradictory duplicate declarations** for one selector in one stylesheet. Count hits
   for the selector; two non-media-query rules is the bug. Delete the stale one, then verify
   which won **in the built/served artifact** — source order is not what the cascade served,
   and `src` may not reflect what ships.
2. **Truncation on the wrong box type.** `text-overflow: ellipsis` requires a BLOCK
   container with `overflow: hidden`. On an `inline-flex` chip it is a no-op and the text is
   guillotined mid-glyph with no ellipsis at all. Fix by wrapping by word, or by moving the
   ellipsis onto a real block child. Never leave `white-space: nowrap` + `overflow: hidden`
   on the flex chip itself.

### 5. Text integrity sweep

When the user asks for "no broken words or sentences anywhere", you are asking for a
property, not a spot fix. Find the existing text-integrity check in the repo and EXTEND it —
hand-editing CSS without extending the pin guarantees the regression returns.

Rules for the sweep: break an unbreakable token ONLY when it cannot fit alone on a line;
never hyphenate; never clip silently (an ellipsis must be visible); keep label:value pairs
together; monospace/code values break as code, prose values break by word.

Surfaces checks usually miss: chart axis tick labels (long category names on a phone),
legend items, table headers and cells, timeline/compare titles, link/URL notes,
label:value rows, file-tab and fullscreen-header titles, heatmap row/column headers.
Measure it per width; the definitions and thresholds are in
`references/canvas-surface-traps.md` under "Measuring text integrity in a real browser".

## Measurement rules

- **Assert geometry, not class names.** Compare `getBoundingClientRect()` of the chrome
  against the element it must not cover.
- **Count elements.** `document.querySelectorAll(sel).length === n`. A guard or fix that
  matches nothing reads as insurance while insuring nothing.
- `getBoundingClientRect` is UNCLIPPED — clip boxes to the wrapper before asserting
  no-overlap, and measure the element itself, not its full-width row container.
- Cover at least one narrow phone width, one tablet, one desktop.
- Flex/grid shrink chains need `min-width: 0` at EVERY level, or one `nowrap` label forces
  the column open and the whole document scrolls sideways.
- **Replay the user's exact payload**, not only a synthetic fixture: pull the real
  message/card from the session store and run it through the real parser and renderer. A
  hand-built stress fixture missed the one surface the real card hit.
- **An audit that measured nothing must FAIL.** Assert the audited population is non-empty
  (cards, charts, tiles found > 0); a script that never reached the target page reported
  all-pass over zero elements.
- **Rebuild before every measurement.** A probe that reuses the previous build output
  measures the OLD code after you edit; use a harness that rebuilds and clears the bundler
  cache.

## Leave a check behind

- Every fix gets a runnable assertion, in the repo's existing check style.
- **Show it red before green.** Run it against the pre-fix source (stash or a copy). A check
  never seen failing is not evidence.
- Run the full existing suite before and after; report pre-existing failures separately
  rather than folding them into your result.
- **Mutation-test it.** For every rule the check pins, break that rule in a scratch copy
  (re-add the `nowrap`, move the legend above the plot, drop the explicit height) and
  confirm the check fails; one that stays green is decoration. A source-reading check
  resolves its inputs relative to itself, so copy it into a scratch tree beside the mutated
  inputs instead of mutating the real tree.
- **Beware vacuous loops.** An assertion inside `for (const m of source.matchAll(...))`
  passes when the design it described is gone and the match set is empty. Assert the match
  count, or rewrite the assertion for the design that exists now.

## Pitfalls

- **Patching the symptom.** A one-line CSS tweak that hides the overlap leaves the real
  mechanism in place and the next widget reproduces it.
- **Trusting the report's diagnosis.** "The legend is at the top" names what the user saw;
  it does not name the layer. Re-derive it.
- **Believing `src` describes what ships.** Verify the built artifact, always, and every
  lazy chunk the feature lives in, fetched from the running service (the entry HTML lists
  only the eager ones).
- **Fixing an already-fixed bug.** Re-verify against live first; a stale report wastes the
  cycle and can regress a working fix.
- **Assuming one documented authoring form.** Read the spec for every accepted shape.
- **Hand-fixing instead of pinning.** If no check covers the property, the next edit
  reintroduces it.

## Support files

- `references/print-and-pdf-render-traps.md` — HTML-to-PDF / WeasyPrint traps with
  mechanisms, the CLI commands that measure the built artifact (page box, embedded
  fonts, text layer, per-page image scale), aspect-ratio proof that an image is not
  distorted, the orphan-heading sweep, single-hue palette auditing, and the
  always-read-before-editing anchored-assertion discipline.
- `references/canvas-surface-traps.md` — concrete library/CSS traps with mechanisms
  (absolute-positioned chart legends, ellipsis on flex chips, normalizer branch order, a
  self-sizing chart collapsing to 0×0, `var()` colours in chart libraries, per-block
  validation drops), how to measure text integrity in a real browser, plus how to read a
  binary-plist `.webarchive`.
- `references/astra-canvas-laws-and-audits.md` — the Astra canvas owner's standing laws,
  the pins to extend, the browser audit harnesses, and how to replay the owner's exact
  card from the session store.
- `references/component-preview-runtime-traps.md` — runtime preview/gallery traps where
  the self-reported verdict lies: `export default` invisibility, silent React subtree
  drops, opacity-0 observer gating (and why `!important` inline styles lose to
  framer-motion), `children` needing real text, shim ordering (VENDORED + resolver),
  `resolveDir` on every virtual module, template-literal shims hiding syntax errors,
  and the compile-in-container / paint-on-host gate split.
