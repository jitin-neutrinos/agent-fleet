# One symptom, four causes

A worked example of why layout bugs get measured instead of guessed. All four
below were reported to the owner as some form of "content bleeds off the edge" /
"it looks cut off". Four different mechanisms, four different fixes.

## The harness

Standalone HTML emitting the component's real DOM shape and CSS, with one
query parameter per variable under test:

```
case.html?mode=broken|fixed&w=380
```

It computes and parks the numbers on `window.__RESULT__`, so one browser call
returns the whole comparison:

```js
const r = (el) => { const b = el.getBoundingClientRect();
  return { left: +b.left.toFixed(1), right: +b.right.toFixed(1), width: +b.width.toFixed(1) }; };
// parent vs page vs scroll, plus:
// stageLayoutWidth: stage.offsetWidth,
// bleedLeft:  parent.left  - page.left,
// bleedRight: page.right   - parent.right
```

Reading `offsetWidth` (layout) alongside `getBoundingClientRect().width` (paint)
is what separates cause 2 from the others — they disagree exactly when a
transform is involved.

## Cause 1 — page wider than the viewport

A fixed-width page (A4 ≈ 794px) inside a 380px phone column. The stage overflowed
and its edges, padding included, were cut at the screen edge.

Fix: scale the stage to the available width. Capture resets the transform first,
so exported files stay full-size.

## Cause 2 — transform has no layout size (the deceptive one)

After cause 1 was fixed, the page sat hard against the left edge with dead space
on the right. `transform: scale()` shrinks the PAINT but leaves the layout box at
full width, so `margin-inline:auto` had nothing to centre inside, and the scaled
box kept its unscaled height — leaving a tall empty gap.

Fix: real size on an outer wrapper (`page * scale`), transform on an inner box.
The wrapper centres; the inner box shrinks.

## Cause 3 — child centred in the wrong box (the "clipped on the left" one)

Cause 2's fix still clipped on the left. Measured: stage layout width 318px
while its child page was forced to 794px. The stage had no width of its own, so
it inherited the ALREADY-SCALED width of its wrapper, then
`justify-content:center` pushed a 794px page ~62px past the card's LEFT edge and
equally off the right. `overflow-x:hidden` made the left overflow unreachable —
which is exactly why it presented as "clipped on the left and I cannot scroll to
it".

Measured before/after at three phone widths:

| card width | stage layout before | clipped left | after |
|---|---|---|---|
| 380px | 318px | 62px | 0px |
| 360px | 298px | 60px | 0px |
| 430px | 368px | 66px | 0px |

Fix: give the centring container the child's TRUE layout width.

## Cause 4 — a selector that matches nothing

Cards rendered flush together, no error anywhere. The spacing CSS targeted a
wrapper class the renderer never emits — `Blocks()` returns a bare fragment of
sibling group divs. Every rule matched zero elements.

Fix: read the renderer's actual return shape before writing layout rules; target
what it emits; assert the selector resolves.

## What this cost, and the rule

Three of these four were "fixed" by reasoning from the source first. Two of those
attempts made the defect worse. The harness — roughly forty lines of HTML — paid
for itself on the first run and turned every subsequent fix into a one-line
change with a number attached.

**Build the harness before the second attempt, not after the third.**