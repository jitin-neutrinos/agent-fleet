# Icon & art-asset sourcing

Applies whenever a task needs a NEW icon, illustration, or animated asset. The owner's standing rule: **search existing packs/registries/MCPs first — do not hand-draw decorative assets.** Hand-drawn stand-ins are a stopgap to be named as such, not a deliverable.

## Where to search, in order

1. **Component registries** (for whole components): `mcp__magicui__searchRegistryItems`, `mcp__aceternity__search_components`, `mcp__shadcn__*`, `mcp__21st_magic__*`.
2. **Icon sets — a DIFFERENT surface.** Component registries rarely carry illustrated icon art. Use `mcp__iconify__search_icons`, which indexes hundreds of sets (including filled/illustrated families) and returns real SVG paths you can drop in directly.
3. **Animated icon packs on npm.** `@sudoh/animated-icons` (MIT, has a purpose-built sun↔moon toggle, spring physics), `@animateicons/react` (MIT, 500+ path-level animated, tree-shakeable, reduced-motion aware), `cssvg-icons` (MIT, zero-dep SMIL).
   **These are all MINIMAL LINE-ART.** If the ask says "illustrated", they do not satisfy it — that mismatch is a finding to report, not a reason to silently substitute.
4. **LottieFiles** — the main source of genuinely ILLUSTRATED animated art (e.g. the "Day And Night Toggle" pack). Free under the Lottie Simple License (commercial OK).

## Gated sources: the drop-zone pattern

Some sources cannot be fetched by an agent and must be downloaded by the owner:
- LottieFiles' `assets-v2.lottiefiles.com` returns **403 for hotlinks**, and the pages sit behind **Cloudflare**, so `browser_exec`/curl both fail — and a remote `<Lottie src>` would 403 for real users too.
- Some vendor registries are API-key-gated on the owner's key, not publicly fetchable.

When a source is gated, do NOT hand-roll the asset and present it as done. Wire the integration so it works the moment the file lands, and hand back a named drop-zone:

```
public/<feature>/<name>.json     # or .png / .lottie
```
plus a README in that folder with: the exact filenames, where to get them, the licence, and why it is self-hosted. **Self-host rather than hotlink the CDN** — same bytes, no third-party runtime dependency, and it sidesteps the 403.

The consumer should HEAD-probe each asset once per session and fall back when missing, so the feature is never blank and needs no rebuild to adopt the file:

```ts
const probed = new Map<string, boolean>();
async function assetExists(url: string) {
  const hit = probed.get(url);
  if (hit !== undefined) return hit;
  try {
    const res = await fetch(url, { method: "HEAD", cache: "no-cache" });
    const ok = res.ok && (res.headers.get("content-type") || "").includes("json");
    probed.set(url, ok);
    return ok;
  } catch { probed.set(url, false); return false; }
}
```

A player dependency (`lottie-react`) is a real cost — `lottie-web` is ~250KB min for ONE 22px icon. Say the size out loud when proposing it and offer the dependency-free alternative as a named option.

## Icon-legibility rules that survive the theme swap

- **The icon semantic is a decision, not a detail.** "Shows the CURRENT theme" and "shows the theme you'd switch TO" are both defensible and the owner has changed his mind between them. Ask once, in one line, before building.
- **Light mode has NO glows** (standing law), so a pale icon on cream cannot be fixed with brightness. Give it a **silhouette**: a dark outline stroke on the shape. This is what actually keeps a silver moon / amber sun legible on paper, in both themes.
- **Contrast must be judged on the theme the icon actually renders on** — measure, don't assume from the other theme's screenshot.

## Swapping one icon for another (the animation trap) — RESOLVED

Two implementations were tried for crossfading sun↔moon; both failed, in ways that recur:

- **`AnimatePresence` left the EXITING child mounted.** Verified: two `.theme-glyph-slot` nodes still present seconds after the toggle, so both icons rendered at once. If you use it, assert node COUNT after the transition, not just that the new icon appeared.
- **Per-icon motion `animate` restarted on every theme-driven re-render** — both slots were caught mid-flight (opacity ~0.8) long after the 260ms transition should have finished, because a theme change re-renders the tree and re-triggers the animation.
- Driving visibility from a stylesheet avoids the unmount lifecycle, but confirm the rule actually WINS: check `element.matches(selector)` AND the computed value. A rule that matches yet computes to the wrong value means something later in the cascade overrides it, and a selector-matching check alone will not catch it.

**The resolution — when ONE asset carries BOTH states, render ONE child and drop the exit animation entirely.** Most "animated toggle" art is not two icons: it is a single timeline whose `t=0` is the light state and some later `t` is the dark state. Crossfading two mount points is then pure liability — `AnimatePresence` stacks the stale state on top (light mode showed a night pill while the label read "Light mode"), and the keyed remount resets the playhead so the flip restarts from the wrong end. Working shape:

```tsx
<span className="theme-glyph" data-mode={dark ? "dark" : "light"}>
  <span className="theme-glyph-slot">
    <ThemeArtwork dark={dark} />   {/* one child; tweens internally on `dark` */}
  </span>
</span>
```

Assert `document.querySelectorAll('.theme-art').length === 1` after a toggle — that count is the regression test for this whole family of bugs.

## Owning a self-animating SVG (SMIL)

**An animated SVG placed in an `<img>` plays FOREVER on its own.** SMIL runs in the image's own document with no host handle, so an asset exported with `repeatCount="indefinite"` presents as "the icon flips by itself" — a bug that looks like state thrash in your component and sends you hunting in React. Recognise it by measuring the state the icon supposedly churns: if it does not change, the motion is inside the asset, not your code.

To drive it, **inline the SVG** (Vite `?raw` import + `dangerouslySetInnerHTML`, so it stays one source file) for a ref to the `<svg>`, then take the playhead:

```tsx
svg.pauseAnimations();                                     // kill the self-playing loop
const from = Number(svg.dataset.t ?? LIGHT_T);             // persist last frame yourself
svg.setCurrentTime(from + (to - from) * easeFlip(p));
```

Read the timeline facts out of the file first — `dur` is the loop length, and per-element `begin` offsets mean interesting frames are NOT evenly spread:

```bash
python3 -c "
import re; s=open('public/icons/theme.svg').read()
print('loop:', sorted({float(m) for m in re.findall(r'\bdur=\"([0-9.]+)s\"', s)})[-1])
print('SMIL:', {t: len(re.findall(r'<'+t+r'\b', s)) for t in ['animate','animateTransform','set']})"
```

**Find the frames by looking, not guessing** — build a throwaway harness page that inlines the SVG, calls `pauseAnimations()` + `setCurrentTime(t)`, screenshots several `t`, and identify each with vision. Frame identity is not inferable from SVG source. Keep the chosen constants named (`LIGHT_T`, `DARK_T`) with a comment recording what each frame looks like.

**One asset usually means no second file is needed** — check the timeline before asking the owner for a light/dark pair; a day↔night piece already contains both.

## Cropping art exported from a design tool

Design exports arrive on a full-screen canvas: a small pill centred in `viewBox="0 0 1920 1080"`. In a 22px slot it renders tiny with huge dead margins, because the slot letterboxes the whole canvas.

**`getBBox()` is not the crop box** — it includes filter/gradient/glow overflow and can return a rect larger than and offset from the viewBox. Scan RENDERED PIXELS for the true visible bounds instead: `Emulation.setDeviceMetricsOverride` to the SVG's EXACT native size (a letterboxed render scales x and y differently, so px→viewBox mapping is wrong), screenshot, then scan for `alpha > 12` pixels that are not near-white. Those coords become the new `viewBox`.

## Easing that reads premium

A quadratic ease-in-out reads **violent** on a state change: it peaks exactly at the midpoint, which is where the artwork changes most. Use `cubic-bezier(0.4, 0, 0.2, 1)` over ~1000–1200ms, solved by bisection on x (monotonic for this curve, so bisection is correct and cheaper than Newton).

**That curve is deliberately ASYMMETRIC — `f(0.5) ≈ 0.7756`, not 0.5.** It commits early and settles late. A test asserting symmetry or a 0.5 midpoint is asserting a curve you did not write; pin reference values instead. Same "check the assertion, not the code" trap as the rest of this skill.

## Verify with eyes

Asset work is appearance work. Grepping the bundle proves code shipped, not that the icon reads. Close-up-capture the icon (crop to the element's own `getBoundingClientRect`, `scale: 8–12`) and look at it. Watch for capturing mid-animation — that produced a false "it washes out" reading here, where the element was simply still fading in.
