---
name: frontend-layout-measurement
description: Use when content bleeds, clips or sits off-centre in layout.
---

# Frontend layout defects: measure, then fix

Class-level skill for CSS/layout bugs reported as a vague visual symptom
("content bleeds off the edge", "clipped on the left", "offset to the left",
"too cramped", "cards touching"). Applies to any app, not one repo.

## The rule that matters: never diagnose layout from source

Those symptoms look identical while having unrelated causes. Consecutive
fix-by-inspection attempts on one symptom made it strictly worse each time. What
settled every case was reading real numbers from a browser.

Procedure, in order:

1. **Reproduce the DOM shape outside the app.** Write a standalone HTML file that
   emits the same structure and CSS as the component, parameterised
   (`?mode=broken|fixed&w=380`). Serve it (`python3 -m http.server`) and drive it
   with the browser tool. This isolates one variable per run.
2. **Read actual geometry**, not intentions: `getBoundingClientRect()` on the
   page, the scroll container and the parent, compared against `clientWidth`,
   `offsetWidth`, `scrollWidth`. Compute the bleed explicitly (parent.left minus
   child.left) rather than eyeballing it.
3. **Change one variable, re-measure.** Keep the change only if the number moves.
4. **Then** write the real fix and re-verify against the same harness.

Two measured pitfalls that make source-reading actively misleading:

- **Minified CSS merges selectors onto one line.** `grep -c 'sel{…}'` returning 0
  does NOT mean the rule is absent. Grep the bare class name and read the merged
  rule before concluding anything about the stylesheet.
- **A selector targeting a wrapper the renderer never emits matches nothing**,
  with no error anywhere — cards render flush together and the CSS looks
  correct. Read the renderer's actual return shape (`grep` the component for
  `className=`) before writing layout rules, and assert the selector resolves.

## `transform: scale()` does not change layout size

The paint shrinks; the layout box keeps its full dimensions. Two failures follow,
both reported as "offset to the left" or "huge empty gap":

- `margin-inline: auto` on a scaled element has nothing to centre inside.
- A scaled element keeps its UNSCALED layout height.

Fix: real size on an OUTER wrapper in px (`page * scale`) — that is what centres;
`transform` on an INNER box — that is what shrinks. When rasterising, reset the
inner transform, capture, then restore, or the export is scaled and blurry.

When a container holds a fixed-width child and must centre it, the parent needs
the child's TRUE layout width. A child that inherits an already-shrunk parent
width is centred in the wrong box and overflows BOTH sides; with
`overflow-x:hidden` that overflow is unreachable, so it reads as "clipped on the
left with no way to scroll to it".

## Hidden content must stay laid out to be captured

Export/screenshot passes rasterise through computed styles. Pages that are
`display:none` or detached capture as blank rectangles. Hide with
`visibility:hidden` and stack siblings in one grid cell (`grid-area: 1 / 1`) so
container height does not change as you page through.

## Wide content: containment, not more padding

A fixed-width box with `overflow:hidden` slices off any intrinsically wide
content (many-column table, long code line, `min-width` diagram, heatmap).
Fix with containment on the block and its scroll wrapper — `max-width:100%` plus
`min-width:0` — and `overflow-wrap:anywhere` for unbreakable tokens, exempting
`pre`/`code` (they scroll rather than fragmenting a command). Grid/flex children
default to `min-width:auto`, which is what pushes a container wider than its
declared width; neutralise it on children.

Keep geometry constants in ONE module shared by the layout code and the CSS
(custom properties). If they disagree, the page paints at one size while the code
measures another, and pagination silently drifts.

## Verify what is SERVED

A green build does not mean the user sees the change.

```bash
systemctl --user restart <service>     # or whatever serves the app
curl -s <url>/api/health
curl -s <url>/ | grep -o 'assets/index-[A-Za-z0-9]*\.\(js\|css\)'
# then grep a distinctive string in that exact hashed asset
```

Hashed assets typically carry `max-age=31536000, immutable`, so a tab open across
a deploy keeps the old bundle until reload. **Rule out stale cache before
treating a "not working" report as a code defect** — it is the cheapest
explanation and it looks exactly like a failed fix.

If a native app wraps the site, confirm whether it loads a live URL or a bundled
snapshot before blaming the network; a stale bundled copy will mask every web
deploy.

## Reporting honestly

State what you measured and what you changed. If a symptom is not reproduced
locally (no login, no device), say so plainly instead of claiming a fix is
verified. A green test suite is not proof a visual defect is fixed — the suite
says nothing about the pixels.

## Overflow reports: real vs by-design
An element whose bounding rect extends past the viewport is NOT automatically a
defect: marquee/vortex/particle containers are overflow-hidden viewports that
deliberately hold a much wider flex row, and absolutely-positioned animation
layers do the same. Diagnose real user-scrollable overflow with
`document.documentElement.scrollWidth - document.documentElement.clientWidth`
(== 0 means none), NOT by enumerating out-of-viewport rects. Enumerate rects
only to answer "what is inside the visual overscroll region", and skip
`position: fixed/absolute` layers plus any ancestor that clips.

## Touch-target audit (mobile overhaul work)
Audit tap targets with a scripted sweep across 4 viewport classes (360/390/412/768
+ optionally tablet) × every route: `getBoundingClientRect()` on
`a,button,[role=button],input,select,summary`, flag min(w,h) < 24. Fix rule:
enlarge the HIT AREA, not the visual — a transparent pad wrapper or padding
around the same glyph keeps the design unchanged while meeting Apple 44pt /
Google 48dp / WCAG 2.2 24px. For canvas/staged animation sequences keyed on a
dimensional class, keep the classlist intersecting: `md:` responsive prefixes
rate-limit density changes. Drop 9-10px arbitrary text sizes to ≥11px on
mobile — below that is illegible: the probe only fires on touchable elements,
tiny non-interactive text must be swept separately with a
`text-\[9px\]|text-\[10px\]` grep, and desktop-only density labels stay as-is.
Contrast sweep belongs in the same pass: slate-500/600/700-class body text on
a near-black background fails 4.5:1 (subset of ~2.9:1) — bump text colors to
slate-400 minimum, pin `::placeholder` color explicitly because the browser
auto-grey is ~3.5:1.

## Content buried under a sibling layer (the invisible-element failure)
When a ported/cloned component's content is present but "nothing shows", suspect
a STACKING regression before a styling one: absolutely-positioned siblings
(z-0 image/overlay backgrounds) paint over static-positioned text inside the
same stacking context. Diagnose in two probes, both scripted:
1. `document.elementFromPoint()` at the missing element's ink position —
   returning a different element PROVES burial and identifies the coverer's
   full ancestor chain (walk parents, log position/zIndex/pointerEvents).
2. COUNT LIT PIXELS in the region from screenshots (Pillow: pixels with
   max(r,g,b) > 120) — compare against a working reference render; two orders
   of magnitude less content (178 vs 11k) means burial, not subtle styling.
Fix by restoring the explicit stacking on the TEXT side (`relative z-10`), not
by demoting the background — background layers legitimately need absolute + z-0.
When porting a component between codebases, re-verify its z-stack alongside
markup parity: copy-paste ports drop ancestor classes that carried stacking.
If true vision comparison is unavailable (rate limits), pixel instrumentation
fully substitutes; do not stall a diagnosis waiting on vision quota.

## Porting a live design to a sibling codebase: measure the reference first
Visual parity means matching MEASURED geometry, not reading similar source.
Capture the live site's rects under identical conditions (headless playwright,
same viewport classes, same wait-for-settle) and assert the port matches:
grid placement (whether a wrapper is `relative` changes which ancestor an
`absolute inset-0` child resolves against — this flips a boxed avatar into a
full-bleed background), element rects, and whole-frame ink counts (a cheap
parity metric; <1-2% delta passes). Re-run the same probe on the port and diff.

## Stacked-slide decks: kill ghost-neighbor flashes by construction
In a slide-stack landing (absolute full-viewport slides, lazy GSAP re-stacking),
two classes of stray content appear that markup review passes:
- The LAST slide flashes on first paint: all slides render stacked before the
  lazy animation layer pushes slides 2..n offscreen. Fix: park deeper slides
  `visibility: hidden` until the animation layer claims the stack, and SSR an
  opaque veil div over the first frame that CSS-fades out on mount (opacity
  only; unmount by timer; reduced-motion gets a ~150ms fade, not the full one
  and not an instant flash).
- A NEIGHBOR slide ghosts through mid-transition ('slide 3 sliver while moving
  1↔2'): yPercent offscreen parking is insufficient — sub-pixel rounding and
  compositor rounding can let an edge bleed. Set `visibility: hidden` on every
  card NOT involved in the current transition, in-flight AND at rest; only the
  two cards in the swap are ever visible. Invariant to verify with probes:
  exactly 1 visible card at every rest point and only 2 in flight, across
  desktop wheel, mobile touch, and swipe.
For the wheel gesture: accumulate deltas only within a single gesture
(reset when the previous wheel event is >200ms old) or slow trackpad rubbing
banks credit and fires a slide change after the user stopped; and crossfade
the OUTGOING slide (opacity→0) alongside its translate or the handoff reads
as a hard cut. Probe scrolls with dispatched WheelEvents (single ticks +
timed bursts) — Playwright's `mouse.wheel` synthesizes momentum-tail events
unrepresentative of a real swipe.

## References

- `references/measure-dont-guess.md` — worked example: one symptom, four distinct
  causes, and the harness that separated them.
- `scripts/mobile-touch-audit.mjs` — parameterized mobile audit probe
  (viewports × routes: real h-overflow, sub-24px tap targets, console errors);
  cwd-only playwright import, set PLAYWRIGHT_PATH to a repo that has it.
- `scripts/stack-probes.cjs` — stacked-slide-deck probe kit (veil fade
  timeline, visible-card ghost lifecycle, gesture-scoped scroll feel),
  `PLAYWRIGHT_PATH=<repo-with-playwright> node stack-probes.cjs <veil|ghost|scrollfeel> [baseURL]`.