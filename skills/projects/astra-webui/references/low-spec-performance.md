# Low-spec device performance (android WebView, weak phones)

Symptom class: typing feels laggy in the composer, and continuous decorative
animation stutters — while the same build is fine on desktop. Desktop profiling
hides all of this, so optimise against the device class, not the dev machine.

## 1. A decorative animation must NOT sit in the React render path of a container that resizes

The composer grows with its content, so its ResizeObserver fires on **every line
typed**. Anything that re-renders on that callback costs a keystroke.

Symptom: per-keystroke lag that scales with how much is mounted inside the
resizing container, not with text length.

Fix: render the decoration ONCE and write its geometry imperatively to refs.

```tsx
const rectsRef = useRef<(SVGGeometryElement & SVGGraphicsElement)[]>([]);
useEffect(() => {
  const svg = svgRef.current, host = svg?.parentElement;
  const paint = () => {
    const r = parseFloat(getComputedStyle(host).borderTopLeftRadius) || 12;
    const w = host.offsetWidth, h = host.offsetHeight;
    svg.style.display = w > 40 && h > 20 ? "" : "none";
    if (w <= 40 || h <= 20) return;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    for (const el of rectsRef.current) {
      if (!el) continue;
      el.setAttribute("x", String(STROKE / 2));
      el.setAttribute("width", String(w - STROKE));
      el.setAttribute("rx", String(Math.max(0, r - STROKE / 2)));
    }
  };
  paint();
  const ro = new ResizeObserver(paint);
  ro.observe(host);
  return () => ro.disconnect();
}, []);   // <- empty deps: React renders the nodes once, then never reconciles
```

Verify the re-render is actually gone rather than assuming: tag a node, cause a
resize, and check **node identity** survived.

```js
window.__probe = document.querySelector('.composer-trace-step');
window.__probe.__tagged = 'yes';      // type into the composer
// then: document.querySelector('.composer-trace-step') === window.__probe
```

Identity surviving = React did not reconcile. A replaced node = it still did.

## 2. Cost ranks: node count x filter x animation property

- **SVG `filter: drop-shadow()` is a separate GPU render pass.** It is the single
  most expensive thing in a small decoration, and worst in a mobile WebView.
  Prefer stacking a wider, low-opacity stroke behind the shape over a filter;
  if a filter is required, drop it on low-spec via a class, not by removing it
  everywhere.
- **N animated nodes each cost per frame.** 28 bands at 60fps is fine on desktop
  and visibly steppy on a budget GPU. Scale the count to the device (28 → ~10).
- Animating `stroke-dashoffset` is cheap (no layout, no paint-area change);
  animating layout properties or re-creating DOM nodes is not.

## 3. Device-class detection must have a fallback

`navigator.deviceMemory` is Chromium-only and frequently missing in WebViews;
`hardwareConcurrency` is broader but can report a generous core count on a phone
that is thermally throttled. So:

```ts
export function isLowSpec(): boolean {
  if (typeof navigator === "undefined") return false;
  const mem = (navigator as any).deviceMemory;
  if (typeof mem === "number" && mem <= 4) return true;      // absent != low
  if (typeof cores === "number" && cores <= 4) return true;
  // reliable phone signal for WebViews that report neither:
  return matchMedia("(pointer: coarse)").matches && window.innerWidth <= 820;
}
```

Treat a MISSING hint as "unknown", not "low" — otherwise desktop Firefox and
Safari silently get the reduced path. Gate a CSS class on the shell root so
stylesheets can respond without re-rendering:

```
.astra-lowspec .composer-trace-head { filter: none; }
```

**Emulation does not prove the media query.** CDP
`Emulation.setDeviceMetricsOverride` sets the viewport but does NOT flip
`pointer: coarse` (verified: `matchMedia('(pointer: coarse)')` stayed `false`).
A JS probe keyed on a CSS-only media query is untestable headlessly — put the
device decision in JS so it is assertable, and keep CSS as the styling layer.

## 4. Forced-reflow autosize is a per-keystroke cost

The composer autosize idiom (`height:auto` → read `scrollHeight` → write
`height`) is two forced synchronous layouts on every value change. Skip the
measure when the box already fits — the common case while typing inside a box
that has already grown:

```ts
if (LOW_SPEC && ta.clientHeight >= ta.scrollHeight - 1) return;
```

Reading `clientHeight`/`scrollHeight` is itself a layout read, so this only pays
off because it avoids the *write*-then-read-then-write cycle; measure the real
device before assuming a win elsewhere.

## 5. Headless cannot verify View Transitions

`document.startViewTransition` exists in headless Chromium, but `vt.ready` never
resolves without compositor frames, so the `vt.ready.then(...)` animation never
runs and nothing is observable — no animation in `getAnimations()`, and
`getAnimations()` on the root does not surface pseudo-element animations
reliably either. Do not conclude the feature is broken.

Extract the geometry into a pure module and pin it with a test instead:

```
src/lib/theme-wipe.ts   -> wipeClipFromRect(rect, w, h) + radiusPct(...)
src/lib/theme-wipe.check.ts
```

The test is what catches a regression to `document.activeElement`; the visual
check still belongs on a real browser.

## 6. A lazy() entry point only helps if NO eager path reaches the dependency

Bundle budget is a **graph** property, not a file property. Lazy-loading a
component does not keep its dependency out of the main chunk when anything in
the eager graph imports it, directly or transitively — one “obviously safe”
static import is enough to pull the whole library back in. (Seen for real: a
chart surface was lazy at the chat entry point, but the approval-gate path
imported the same renderer statically, and the chart engine landed in the main
bundle anyway.)

Rule: **the module that imports the heavy dependency must be reachable only
through a dynamic import.** Keep its presentational siblings dependency-free so
paths that must render synchronously (approval gates, print/export, surfaces
that cannot afford a Suspense fallback) can still import them statically. When
the eager path needs both, split the heavy consumer into its own file and
`lazy()` *that* file — not the composite wrapper.

Verify on the BUILT output by signature-grepping every chunk; source reading and
a green `npm run build` prove nothing here:

```bash
for f in dist/assets/index-*.js dist/assets/<heavy>-*.js; do
  printf "%-34s %9s  dep-hits=%s\n" "$(basename "$f")" "$(stat -c%s "$f")" \
    "$(grep -o 'recharts\|PolarAngleAxis' "$f" | wc -l)"
done
```

The main chunk must report `dep-hits=0`; the library belongs to exactly one lazy
chunk. Then assert the **served** bundle after restart — pull the hashed
filenames out of the served HTML and `curl` each for a 200, because a stale SPA
cache otherwise makes a correct build look like a broken feature.

## Ordering

Fix in this order — each step's measurement is only trustworthy after the
previous one:

1. Get the decoration out of the React render path (node identity check).
2. Drop the filter on low-spec; reduce node count.
3. Make the autosize conditional.
4. Re-profile on the real device — desktop numbers do not predict phone numbers.
