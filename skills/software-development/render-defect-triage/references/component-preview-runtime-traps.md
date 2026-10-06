# Component-preview runtime traps (compiled-in sandbox)

For any UI that renders a COMPONENT's own source at runtime: a shadcn-style
registry, a component gallery, a live-canvas catalogue. The pattern is the same
everywhere — server-side bundle with esbuild, serve one self-contained file,
mount it in a sandboxed iframe, and let the component report its own verdict via
`postMessage`.

Every trap here was measured on ui.jitinnair.com (185 components, builder v12 →
v13). Mechanisms, not symptoms.

## The three silent classes

A preview that reports its own verdict has a specific failure shape: **the
verdict lies**. There is no exception, so every one of these hides.

### 1. `export default X;` is invisible to naive export regexes

A picker that matches `export function`, `export const` and `export { … }` finds
nothing in:

```tsx
const AnimatedBackground: React.FC<P> = ({ className = '' }) => { … };
export default AnimatedBackground;        // ← invisible
```

Measured: 10 of 185 components reported "no renderable export" for files whose
entire purpose was that one default component.

Return the string `"default"` as the mount target — not the identifier.
`mod["default"]` is what the author designated. Returning the identifier is
wrong for wrappers: `export default memo(TradingViewChart)` resolved to `memo`,
which is React's wrapper API, not a component, and mounting it paints nothing.
ENTRY should already fall back to "any function export" when a named lookup
misses, so `"default"` is both correct and safe.

Also cover `export default function`, `export default async function`,
`export default class`, `export default function () {}` (anonymous),
`export default dynamic(() => import(…))`, `export let/var`.

### 2. React discards a non-renderable element WITHOUT throwing

A stub package proxy answers `createElement(type, …)` with `null` when `type` is
not a string. React then drops the whole subtree silently: no throw, no
`window.onerror`, no React error boundary trip. The preview posts
`jitinnair-preview-ready` over an empty `#root` and the host shows a green badge.

```js
flushSync(() => root.render(tree));
report("ready", name);      // ← claims success over nothing
```

**Fix: verify the paint, never trust the absence of a throw.**

```js
const settled = () =>
  new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
settled().then(() => {
  if (!root.childNodes.length) return paint("empty", `${name} rendered nothing`);
  report("ready", name);
});
```

**Two animation frames, not a microtask.** A component that renders null until
an effect fires (`if (!mounted) return null`, with `useEffect` setting `mounted`)
is still empty when a microtask runs — React has not flushed the effect's state
update. A microtask check reported 2 healthy components as empty, which is the
same class of lie pointing the other way. Two rAF is the earliest point at which
effects and their resulting re-render have both committed.

Corollary: a module that genuinely returns null (a `<meta>` injector, a theme
provider, an effect-only component) is CORRECT to report "empty". The canvas
should say so; it is not a bug to fix.

### 3. Observer-gated content is transparent forever

`whileInView={{ opacity: 1 }}` + `viewport={{ once: true }}` never fires in a
preview frame — there is no scroll. The node mounts correctly-sized at
`opacity: 0`. Measured: 20 of 185 components.

**`el.style.setProperty("opacity", "1", "important")` does not work here.**
framer-motion keeps its animation loop running and re-writes the inline style
every tick; a direct property assignment REPLACES the declaration, clearing the
`!important` flag, so Motion wins on the next frame. This looks like the fix
working in one measurement and doing nothing in the next.

**What works: a stylesheet rule tagged !important**, which outranks an inline
normal declaration in the cascade and cannot be overwritten from script. Tag the
node, re-apply for ~12 frames to catch late mounts:

```js
sheet.textContent =
  '[data-jitinnair-revealed]{opacity:1 !important}' +
  '[data-jitinnair-untransformed]{transform:none !important}';
// …tag only nodes whose COMPUTED opacity is <= 0.02, so a deliberate fade is not fought
```

**But lifting opacity is not enough.** A wrapper whose `children` is missing
measures 0×0: visible, and still empty. Measure `getBoundingClientRect()` area
AND computed opacity in the gate — `nodes > 0` proves nothing.

### 4. `children` cannot be filled with a deep proxy

Demo-props generators substitute a catch-all proxy for unknown props. For
`children` that yields a wrapper with nothing inside: measured `primitives` at
**107×24 with text** vs **0×0** once `children: "Demo content"` was passed. Text
is the right fill — it is what a real consumer passes, it needs no package, and
it cannot itself throw. Override it by prop NAME, after generation, so array
names (`items`, `sections`) still win.

## Resolver ordering: a shim the rewriter never sees is dead code

The trap that makes shims silently fail, and it looks like a resolver bug:

- `rewriteImports` (a source-to-source pass) runs FIRST and rewrites any import
  whose specifier is not in `VENDORED` into `import { stub as s0 } from "jitinnair:empty"`.
- Only THEN does esbuild's `onResolve` plugin see the specifier.

So adding an `onResolve` rule for `@mui/material` changed nothing — the rewriter
had already replaced the specifier, and the bundle still carried the stub. Proof
marker: grep the built bundle for a string only the shim emits
(`b.js.includes("jitinnair-mui")` → `false`).

**Rule: a shimmed package must be in BOTH the VENDORED set (so the rewriter
leaves it) and the resolver (so it never reaches a real install).** Keep one
`SHIMMED` set and spread it into `VENDORED` so the two cannot drift.

## Every virtual module needs an explicit `resolveDir`

esbuild defaults an unset `resolveDir` to the **process CWD**. Under Docker
Compose that is `/`, so `import React from "react"` inside a shim failed with
`Could not resolve "react"` while `STUB` and `CN` (which import nothing) kept
working. That split is why the failure looked random — it hit exactly the shims
with imports. Set `resolveDir: path.join(import.meta.dirname, "..")` on EVERY
`onLoad` return, including the empty-CSS module.

## Template-literal shims hide syntax errors from `node --check`

A shim written as a backtick template is a STRING to `node --check` — a typo
inside it cannot fail the source file. It surfaces only as an esbuild error
inside a 250 kB generated bundle, pointing at a line of generated code.

Fix: export the resolved strings and parse each one directly in a gate
(`export const SHIM_SOURCES = { mui: MUI_SHIM, … }`). The failure then names the
shim and the real line. This found a misplaced paren
(`createElement(…})), children)` — the call closed before its argument).

**Also: a backtick inside a comment in a template literal terminates it.** Write
"setting el.style.opacity to 1" rather than quoting the code with backticks.

## Stub proxies must be callable AS the thing they replace

The inert stub is a callable Proxy, so `dynamic(() => import("./x"))` type-checks
and then React throws "not a function" while evaluating the module — before any
error handler is installed, so the frame is silently blank with no readable
message. For `next/dynamic`, return a component that calls the loader
synchronously and renders `mod.default`.

Note the tension with the existing stub comment: returning `null` from the proxy
keeps render rate up but makes a stub used as a DATA factory return null; returning
the proxy gives React error #130 on components that render a stub AS AN ELEMENT.
Both losses are real; pick deliberately and measure.

## Library shims that actually earn their keep

MUI was 27 of 92 failures. Its value is `styled()` and the theme object, not its
DOM, so a shim reproduces: `styled(X)({…})` returning a component that renders X
with a generated class, `sx` applied, `createTheme`/`useTheme` answering so
`theme.palette.*` and `theme.breakpoints.down('md')` resolve, and style objects
compiled into a real `<style>` tag so flex/spacing/grid geometry is VISIBLE.
Inject rules per-class rather than one accumulating string, or the sheet grows
without bound across re-renders.

## The two-gate split, and where each must run

**Compile in the container, paint on the host.** esbuild lives in the app image;
chromium lives on the host.

- Container gate: shim syntax, shim reachability, export-form coverage,
  demo-props validity, real components build. `docker exec ui-api node …`.
- Host gate: bundle via `docker exec`, then evaluate in headless chromium and
  assert on the painted DOM. Cross-process file paths DO NOT work — the
  container cannot write to a host scratch dir, so every build "succeeded" and
  the host then ENOENT'd on all 28 reads. Write to `/tmp` INSIDE the container
  and read back with `docker exec cat`.

## A "fixed" build that never reached the users: three cache layers

The most expensive lesson here is not a rendering bug at all. Fixes were shipped,
gates passed, the audit still showed the old numbers — and the reason was caching
at three independent layers. When a measurement does not move after a fix that
should have moved it, check these BEFORE re-diagnosing the code.

**1. In-memory cache keyed on source hash only.** `previewCache.set(slug + ":" +
content_hash)` returns a bundle compiled by the PREVIOUS builder for the whole
process lifetime. Add the builder version to the key: `slug:hash:b13`.

**2. Warm-directory cache on a persistent volume.** `warm.js` keyed files as
`${content_hash}.js`, and `docker compose up --build` does NOT clear named
volumes — so every bundle built by an older builder survived a rebuild and was
served in preference to a freshly compiled one. Fix: name files
`v${BUILDER_VERSION}-${content_hash}.js` and PRUNE anything without the current
prefix at startup. The prune log is the proof it worked:
`pruned 187 bundles from an older builder`.

**3. The CDN, keyed on URL, with a year-long TTL.** This one is invisible from the
server and it invalidated an entire audit run. The response said
`Cache-Control: public, max-age=31536000, immutable`, and Cloudflare returned
`cf-cache-status: HIT`, `age: 4984` — for a bundle the origin had already
replaced. Measured side by side:

```
origin  http://127.0.0.1:8102/api/preview/primitives.js   → 262333 bytes, "Demo content" present
edge    https://ui.jitinnair.com/api/preview/primitives.js → 262286 bytes, "Demo content" ABSENT
```

Fixes: (a) `max-age=300, must-revalidate` instead of a year; (b) embed the
builder version in the CLIENT URL, since that is the only lever available
without a Cloudflare API token — bumping it changes every URL and forces a
re-fetch; (c) echo `X-Preview-Builder` on every preview response so staleness is
diagnosable from headers alone.

**Detection rule: after a compiler or demo-props change, verify the fix in the
BUNDLE BYTE STREAM served through the public URL**, not just against the source
and not just against the origin:

```bash
curl -s https://host/api/preview/<slug>.js | grep -c "<marker-only-your-fix-emits>"
```

If that is 0 while `grep` on the source finds the marker, you are measuring a
cache, not the code. Compare origin vs edge before touching anything else. Note
that a human-readable marker may be split by the minifier — assert on an
identifier or data-attribute name.

**Corollary: bump the builder version on every deploy that changes bundle
CONTENT**, not only one that changes the compiler's syntax. A demo-props or shim
change alters output for unchanged source, so the content hash never moves and
no other layer notices.

## Gate bugs that produced a green lie

Both of my first gate versions reported PASS while measuring nothing:

- The paint gate printed `every "ready" verdict corresponds to painted DOM
  (0 components)` and exited 0 while all 28 builds had ENOENT'd. **Assert the
  denominator**: `painted >= expected - 2`, with the reason stated.
- The same gate then reported "1 node, 34 chars" for eight components that
  rendered NOTHING — `paint("empty")` writes a placeholder (`#empty-state`,
  `#fallback`) into the same `#root` it is measuring, so the harness graded its
  own output. **Strip the placeholder from every node count, text length and
  visible-area calculation** before asserting anything.
- An earlier check asserted `"lazy chunk unavailable"` was present in a bundle
  — esbuild's minifier splits that string. Assert on a token that survives
  minification (an identifier or data-attribute name), never prose.
- A gate that only knows "painted" and "broken" cannot tell a defect from a
  component that returns null BY DESIGN (a PWA install prompt awaiting an event
  that never fires, a portal host, a `<meta>` injector). Keep an explicit
  `BY_DESIGN_NULL` map with a written reason per slug, and make an unexplained
  empty a FAILURE. Otherwise the gate either cries wolf forever or the team
  learns to ignore it.

Corollary for the host verdict logic: the pre-existing `worst` calculation in a
LiveCanvas marks `null` (pending) until BOTH themes report. An iframe that never
loads leaves the card stuck on "both themes" forever. Treat a settled-but-empty
frame as `empty`, never `ok`, and never leave it pending.

## Measuring the whole population

The audit that found all of this drove real Chromium at all 185 pages, waited
for the canvas verdict to leave its pending state, then measured the frame
directly: `#root` child count, node count, `innerText` length, svg/canvas/img
counts, computed opacity, and `getBoundingClientRect` area. Two passes were
needed — the first classified by DOM size alone and could not tell a
legitimately-textless SVG from a genuinely blank frame.

Classify into: `OK`, `ERROR` (readable message), `BLANK` (0 nodes), `TEXTLESS`
(nodes but no text — probe shape counts before calling it broken),
`EMPTY_NO_EXPORT` (no mountable export), `NO_FRAME`, `HALF_BLANK`. Then group by
FIRST SIGNIFICANT LINE of the error, not by verdict, to see how many failures
share one cause. That grouping is what turned 92 failures into 5 causes.

Screenshot every non-OK page; the images are the evidence a user can check.
