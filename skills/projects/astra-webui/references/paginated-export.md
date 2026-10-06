# Paginated canvas export — A4 report / 16:9 slides

Contract for turning a long canvas into a real multi-page document with a
download. Every rule here was paid for with a wrong build; the WHY is kept so a
future session does not re-reason it.

## Geometry (96dpi)

| format | px | usable height (after PAD_Y x2) |
|---|---|---|
| A4 portrait | 794 x 1123 | 1035 |
| 16:9 slide | 1280 x 720 | 632 |

PAD_X 48, PAD_Y 44, GAP 18 — defined in `src/lib/canvas-pagination.ts` and fed
to CSS as `--pad-x` / `--pad-y` / `--x-gap`. The paginator subtracts the SAME
constants. If CSS and the packer drift apart, every report mis-paginates
silently. One source of truth, always.

## Architecture that works

- `src/lib/canvas-pagination.ts` — pure packing: `toUnits`, `packSections`,
  `toBlockRanges`, `pageOverflows`. No DOM, unit-tested.
- `src/lib/canvas-pagination.check.ts` — pins it.
- `src/components/canvas/canvas-export.tsx` — measures off-screen, calls the
  packer, renders ALL pages, captures them.

**Every page is in the DOM at once**, stacked via `grid-area: 1 / 1` on a
single-cell grid. Only the current page is visible. The export walks the SAME
nodes, so what you download is exactly what you saw — one render, no drift.

Non-current pages use `visibility: hidden`, NEVER `display: none` and never
detached: html-to-image renders through computed styles, so a display:none or
unmounted node rasterises as a blank rectangle.

## Section-aware packing (not height-only)

Height-only pagination buries headings mid-page with their bodies overleaf —
the "not section aware" complaint. Rules, in strength order:

1. **Atomic blocks never split.** chart/table/heatmap/diagram/graph/image/
   gallery/video/code/terminal/diff/spreadsheet/tree/keyvalue/compare. Half a
   table is not a page of a report. Adjacent atomic blocks with no section
   break between them merge into one unit — but NEVER past a page boundary, or
   a run of oversized tables chains into a single page.
2. **Section opener** = a `divider`, or a `callout`/`quote` carrying a label.
   Starts a fresh page when at least half the page is still free
   (`used * 2 <= avail`) — reads as a deliberate break. Flows on when there is
   only a sliver, so short sections don't each waste a page.
3. **Never orphan** a heading at the page foot: it moves down with its body.
4. **Never strand** a heading alone on a page: it moves down too.

## Traps that cost real debugging time

- **A `ready` flag gating measurement deadlocks.** `useEffect(() =>
  setReady(false), [blocks, mode])` plus a measuring effect depending on
  `ready` reset each other every render. `meta` never settles to match
  `blocks`, so the fallback `[[0, blocks.length]]` wins — one endless page,
  no page 2. Measure on `[blocks, mode]` alone. This presented as "pagination
  doesn't work" when the packer was perfect.
- **`transform: scale()` does not change layout size.** A scaled stage keeps
  its full 794px box, so `margin-inline: auto` has nothing to centre inside
  and the page sits hard against the left edge. Put the scaled SIZE on an outer
  wrapper in real px and the TRANSFORM on an inner box. Capture must reset the
  transform before rasterising or the file is a blurry screenshot.
- **A child without `min-width: 0` pushes its parent wider.** Grid/flex children
  default to `min-width: auto`, so one wide table stretches the page box past
  `--pg-w`; centring then overflows BOTH edges and `overflow-x: hidden` makes
  the left overflow unreachable (looks like left-edge clipping with no way to
  scroll to it). Cap with `min-width: 0; max-width: 100%`.
- **Long unbroken tokens (URLs, paths, hashes) have no wrap opportunity** and
  run past the content box where the page clips them. Use `overflow-wrap:
  anywhere` (not `break-word` — that needs an existing break opportunity).
  Exempt `pre`/`code`/`kbd`: they scroll in place rather than fragmenting a
  command into unreadable pieces.
- **Spacing rules must target the DOM that actually exists.** `Blocks()`
  returns a bare fragment whose children are `.ast-cv-group` siblings — there
  is no `.ast-cv-body` wrapper. Rules targeting a non-existent wrapper match
  nothing and cards sit flush with zero separation while the CSS "looks right".
  Grep the component for real class names before writing selectors.
- **The off-screen measuring rig must be out of flow** (`position: absolute`)
  as well as `visibility: hidden`, or its full height inflates the card into
  one endless scroll. Measure at the SAME width and padding the real page
  paints — measuring at a different width silently mis-paginates.

## Capturing

```ts
const prev = stage.style.transform;
stage.style.transform = "none";     // files stay full-res, not scaled
try { /* toPng each [data-cv-page] in order */ }
finally { stage.style.transform = prev; }
```

Hide screen-only affordances during capture (the page folio) so the file
matches the printed page. PDF: jsPDF with the matching format (`a4` portrait,
or `[279.4, 157.5]` landscape) and fit-inside-centre math. PPTX: pptxgenjs
`LAYOUT_16x9`, one full-bleed image per slide — text is rasterised, so it is
not selectable or editable. Say so rather than implying native text.

## Drafting a test report

Use only real block types from `BLOCK_TYPES`. `paragraph` is NOT one of them —
it is dropped, so the card renders silently shorter than intended while still
looking plausible, which then reads as "the feature is broken". For prose use
`callout` (tone + body), `quote`, or `document`. Mark sections with `divider` +
`label`; that is what makes pagination section-aware.

## Verify before claiming it works

`npx tsx --test src/lib/canvas-pagination.check.ts src/lib/canvas-schema.check.ts`
(the `.ts` ESM files need `tsx`, not bare `node --test`). Then rebuild and
confirm the SERVED bundle carries the change:

```bash
npm run build && systemctl --user restart astra-webui.service
IDX=$(curl -s http://127.0.0.1:3011/ | grep -o 'assets/index-[A-Za-z0-9_-]*\.js' | head -1)
CH=$(curl -s "http://127.0.0.1:3011/$IDX" | grep -o 'canvas-view-[A-Za-z0-9_-]*\.js' | head -1)
curl -s "http://127.0.0.1:3011/assets/$CH" | grep -c '<marker>'
```

For geometry claims ("fits the viewport", "nothing clipped", "centred"), build
a small standalone HTML harness that reproduces the same DOM + CSS, serve it on
a local port, and read `getBoundingClientRect()` in a real browser at phone
widths (360/380/430). Reasoning about transforms and grid areas from source is
how three consecutive "fixes" failed here; one measurement settled it.