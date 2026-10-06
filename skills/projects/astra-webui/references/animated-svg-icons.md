# An owner-supplied animated SVG as an icon

Applies when the owner hands you an illustrated asset (theme toggle, status glyph, brand mark) that is an **animated SVG**, and you need it to behave like an icon that changes with app state.

## The trap: `<img>` makes an animated SVG self-play forever

A SMIL-animated SVG dropped in `<img src=…>` runs its timeline unattended. Export tools bake in `repeatCount="indefinite"`, so it loops for the life of the page. The owner sees an icon that flips forever and reports "it's in a loop" — which reads as an app bug, not an asset bug.

Triage it by counting the animation elements before theorising:

```bash
python3 -c "
import re; s=open('asset.svg').read()
for t in ('animate','animateTransform','animateMotion','set'):
    n=len(re.findall(r'<'+t+r'\b',s))
    if n: print(f'<{t}>:', n)
print('repeatCounts:', sorted(set(re.findall(r'repeatCount=\"([^\"]+)\"',s)))[:5])"
```

Any of those counts being non-zero, or `repeatCount="indefinite"`, means the asset will animate itself. The `<img>` is the bug.

## Read the asset's timeline BEFORE wiring it

`dur` and the frame contents tell you what the asset actually is. A theme toggle exported at `dur=8.017s` with `repeatCount=indefinite` is usually a **day↔night cycle** — one file carrying BOTH states, not one state.

Pause the timeline and capture frames at chosen times to find each state:

```js
// harness page: inline the svg, then drive its SMIL clock
s.pauseAnimations(); window.__seek = t => s.setCurrentTime(t);
```

`vision_analyze` each captured frame to name it (`t=0` day / `t=4.0` night here). This single probe usually replaces a whole round of "please send the light-mode version" — **one asset often covers both states**, and asking for a second file is an unnecessary ask.

## The working implementation

Inline the SVG (not `<img>`), take ownership of the clock, and tween it only on state change:

- `svg.pauseAnimations()` on mount — kills the self-play permanently.
- Store the playhead in a DOM property (`svg.dataset.t`) so it survives re-renders.
- On state change, run a `requestAnimationFrame` loop writing `svg.setCurrentTime(t)` between the two state times.
- Put the easing in a **separate pure module** (`src/lib/<x>-ease.ts`), not the component — a check file importing a component that pulls a Vite `?raw` asset dies with a module-not-found that looks like a code bug.

**Animate the playhead, not a crossfade.** One element moving through its own timeline cannot desync; two elements fading over each other can.

## Do NOT use a keyed swap for this

`AnimatePresence` with `key={isDark ? "moon" : "sun"}` is the obvious shape and it is wrong here, three ways that all present as the same symptom ("both icons showing"):

1. **The exit slot never unmounts** — the outgoing icon stays in the DOM at opacity 1 and stacks on top of the incoming one.
2. **The remount resets the clock** — a fresh `<svg>` has no `dataset.t`, so the playhead restarts from the wrong end.
3. **Motion restarts animations on every parent re-render**, so a theme change elsewhere can restart the transition mid-flight.

If the child can render both states itself (an animated asset, or any state it can derive), the keyed swap is **pure liability**: render ONE child and let it react to the state prop. Reach for `AnimatePresence` only when the swap is genuinely between two different elements.

Corollary for the no-animation case (two plain SVGs): drop it too and let a CSS rule keyed on the parent's `data-mode` control opacity — CSS reads the parent, so it holds even when a child lingers in the DOM.

## Crop to the content box before shipping

Design-tool exports are full-canvas: the artwork sat centred in a `viewBox="0 0 1920 1080"` with hundreds of pixels of dead margin. In a 22–44px slot that renders as a tiny speck with vast empty space — it looks like a CSS bug and sends you debugging the wrong layer.

Compute the real bounds by rendering at NATIVE size and scanning pixels, then rewrite the viewBox:

```bash
# render the SVG at exactly its viewBox size (a scaled viewport letterboxes
# and gives non-uniform x/y factors, so the mapping back is wrong)
# then, in python over the capture:
#   keep pixels where alpha > 12 AND NOT (r,g,b all > 245)   # drop white page bg
#   content box -> write as the new viewBox
```

Filter on alpha **and** near-white: a transparent-background render on a white page produces both, and a white page alone marks the whole canvas as content.

Keep `preserveAspectRatio` on the element so the asset's own aspect holds at any slot size, and give a wide pill a wider slot than a square glyph rather than forcing it into one.

## Verify

- `animationsPaused()` returns true on the live SVG.
- Sample the playhead several times over a few seconds **with no interaction** — it must not drift. That single probe separates "self-playing asset" from "React re-render loop" in one shot.
- Toggle once and confirm the playhead lands on the target state and stops.
- Then look at it: a frame proves the mechanism, only a capture proves the composition.