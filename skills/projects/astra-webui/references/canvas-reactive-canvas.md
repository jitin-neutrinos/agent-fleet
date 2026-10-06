# Reactive canvas + controls (canvas v5, SHIPPED)

The canvas is no longer read-only: a spec with a `state` key becomes an
**interactive card** — controls write per-canvas state locally, reader blocks
resolve bindings against it, and the whole card recomputes with no network.
Implementation: `src/lib/canvas-expr.ts` (expression language),
`canvas-bind.ts` (bindings), `src/components/canvas/canvas-state.tsx` (store),
`canvas-reactive.tsx` (control + media renderers, lazy chunk). Directive
sections: `docs/canvas-directive.md` §Reactive blocks + §Media blocks.

## Design verdicts (researched across A2UI / json-render / OpenUI, verified live)

- **One state object per card; two-way binding is local-first.** Controls write
  state synchronously in the client (A2UI law); NO network and NO server roundtrip.
- **Expressions use a NAMED-FUNCTION/CLOSED-LANGUAGE registry, never eval.**
  Every reference system hit the same answer; expr-eval (CVE-2025-12735 CVSS 9.8,
  unmaintained since 2019) and json-logic-js (CVE-2021-4329 + prototype pollution)
  are the cautionary tales. Astra's answer: a hand-rolled tokenizer + precedence
  parser in `canvas-expr.ts` with a banned-name set (`__proto__`, `constructor`,
  `globalThis`…), own-property-only reads, and hard caps on source length,
  depth, steps, array and string size.
- **React holds the store, not window globals.** Per-canvas module map +
  `useSyncExternalStore` (same pattern as the fullscreen singleton).
- **No canvas card ever fetches the network.** Live-data blocks were evaluated
  and rejected for v5: an agent-authored URL fetched with the user's session
  cookie is agent-controlled exfil + SSRF surface. If ever built: leading-slash
  same-origin only + server-enforced allowlist + `credentials:omit` + size cap.

## Adding a control block (the complete checklist)

1. **Schema** (`canvas-schema.ts`): interface + union + `BLOCK_TYPES` + case in
   `validateBlock` (alias near-miss type names; coerce bounds — swap min>max,
   snap step to a decimal grid; NEVER silent-zero an invalid value).
2. **Renderer** in `canvas-reactive.tsx` + hub case. All controls follow the
   same shape: `label + input pair`, 44px touch target, `:focus-visible` ring,
   reduced-motion tier. Use NATIVE inputs styled with theme tokens (`::-webkit-
   slider-thumb`, `appearance: base-select`); no Radix slider/select/cmdk —
   zero new deps held, and `base-select` progressively enhances Chrome ≥135 with
   native a11y intact.
3. **Writes are rAF-batched** (`commit()` pattern): a slider drag notifies the
   store at most once per frame — a per-keystore setState loop is the
   typing-lag audit's exact failure mode at scale.
4. **Markdown** (`canvas-markdown.ts`): every new type needs a `blockToMd` case
   or `tsc -b` fails with "function lacks ending return statement".
5. **Media URL mapping**: host paths → `downloadUrl()`/`streamUrl()`/
   `transcodeUrl()` from `src/lib/media-paths.ts` — reuse the skill's own
   `linkHref()` logic (`canvas-blocks.tsx`) instead of reimplementing.
6. **`compileData`/`collectData`:** a `data` block is a CARRIER (columns, rows,
   header?); `width` padding is derivation from row 0 unless `columns` given.
   Empty name or unknown-type rows reject the block; pad-with-null is allowed,
   ragged rows survive.
7. **State must survive re-parse**: reset only when the AUTHORED initial state
   actually changed (compare JSON signatures), never on every render — user
   edits otherwise vanish on every history reconciliation.

## The expression language (canvas-expr.ts) — hard rules

- **No eval / new Function / with / dynamic require.** Hand-written tokenizer +
  precedence parser + whitelisted interpreter.
- **No member access at all** — `a.b` and `a[b]` throw, so there is no path to
  any prototype chain. Identifiers resolve ONLY from the state scope or the
  frozen function whitelist; word operators (`and`/`or`/`not`) map to
  `&&`/`||`/`!`.
- **Every numeric gate allows boolean/null/numeric-string coercion** (`'1,234'*
  2` = 2468, `'12%'` = 12, `$off` = 0). Junk is NaN, never a crash.
- **Resource caps**: src ≤600, depth ≤40, steps ≤20k, array ≤1000, string ≤4k.
  Cache compiled ASTs per source (bounded LRU-like clear at 500).
- **Templates** (`interpolate`): `{expr}` slots; a slot that fails stays VERBATIM
  so prose braces never mangle.
- **Verify the sandbox with live execution, not reading**: run tsx on the
  extracted evaluator, execute the attack tests (`__proto__`, `constructor.name`,
  `globalThis`, heavy exponents, deep parens, `'a'+1`, `"1000"+1 == 10001`), and
  FIX what they catch (two real bugs were caught this way: a `FUNCS` object
  literal whose `hasOwnProperty` key shadowed the prototype method, and a
  left-assoc `^` letting `4^30` slip the operand cap).

## Controls table (built, zero deps)

| control | build | ARIA | notes |
|---|---|---|---|
| slider | native `<input type=range>` styled via `::-webkit-slider-thumb` | slider | `touch-action:none` scoped to it mitigates Chromium's range-touch bug (40843079) |
| select | native `<select>` + `appearance: base-select` progressive | select-only combobox | keep native popup on Android; no dropdown lib |
| multiselect | chips: `role=group` of `role=checkbox` buttons | listbox/checkbox | 2-col wrap ≤sm, `flex-wrap` |
| segmented | `role=radiogroup` + `role=radio` buttons, roving tabIndex | radio | arrow keys move selection; 2–5 options only |
| toggle | `role=switch` button + pill/knob divs | switch | label NEVER changes with state (APG rule) |
| search | `type=search`, `enterKeyHint="search"` | searchbox | rAF debounced; drives `$from` filters |
| number/daterange | NOT built — reach for native `<input type=date>` pair if asked | spinbutton/group | spinbutton (APG) is the pattern if needed later |

Per-canvas a11y: tab order = JSON array order; controls are NOT a `<form>`
(avoid Enter-submit semantics colliding with the composer); every control block
emits `role=group` + `aria-label`; the copy-as-markdown path EXCLUDES controls.

## Binding reader fields (what an LLM authors)

- `$key` or `{$key}` or `{"$state":"/key"}` or `{"path":"/key"}` — read state.
- `{"$expr":"price * qty"}` or `{"expr":"…"}` — evaluate.
- `table`/`chart` take `bind:{"$from":"name","filter":[{col,op,value}],
  "sort":{by,dir},"top":N}`; op set `== != < <= > >= in`; ANY block takes
  `visible:{"$expr":…}`; unset binding ⇒ visible (show by default).
- Chart series: `points:{"$expr":…}` (a number array) + `visible:{"$expr":…}`.
- Alias near-miss control type names (`dropdown`→select, `range-slider`→slider,
  `switch`→toggle, `chips`→multiselect, `dataset`→data, …) in TYPE_ALIASES —
  watch object-literal DUPLICATE-KEY collisions in that table (TS1117): later
  entries win, so a duplicate is a silent re-point, not an error at the site you
  were editing.

## React/TS wiring pitfalls

- **A control rendered without a state provider must not crash.** CanvasView
  wraps the body in `CanvasStateProvider` ONLY when `spec.state` has keys; the
  hook side falls back to a module-level inert store so a stray control block
  still renders and writes nowhere rather than throwing.
- **A control rendered without state in the enum of BLOCK_TYPES / the hub's
  switch never mounts — check both the schema union AND the renderer hub when
  adding a case.**
- **Streaming control blocks must NOT mutate state mid-stream**: the streaming
  card renders the block but only paints inputs on `seg.status === "done"` (the
  same law as gates; a mid-stream mutation races the parser).
- **`data` blocks never render or title the card** — filter them out of
  `deriveTitle` (pick the first non-`data` block) and return null in `renderOne`. 
- **Slider value display**: `format` picks `plain|money|compact|pct`; render
  through the expression language helpers (`money()` etc.) so formats match the
  KPI value formatting EXACTLY.
- **`spec.state` keys live in ONE scope, controls write into it by `bind` key.**
  An authored `state` object with an object/`null` value in it is a VALIDATION
  ERROR, not a renderer concern — block it at `parseCanvasSpec` time, not at
  render time.
- **Never echo `spec.state` straight into `Object.freeze`**: the store needs its
  own immutable copy per write (spread-on-write) — `Object.freeze(initial)`
  wedges the first `set`.

## Media blocks (built)

- `image`{src,alt?,caption?} · `gallery`{items[{src,alt?,caption?}],layout?
  :"2col"\|"3col", max 24} · `video`{src,poster?,captions?,caption?} — native
  `<video controls playsInline preload="metadata">` + `<track kind="subtitles">`.
- `srcUrl(src, image)` maps host paths → `downloadUrl`/`streamUrl`/
  `transcodeUrl`; `/api/…` and `https://` URLs pass through; `onError` → a clean
  "unavailable" slot, never a broken-image icon. Gallery tap-to-zoom uses a
  native `<dialog>` with `::backdrop` — no dependency.
- The existing media-viewer host stays the ONLY fullscreen owner (one history
  entry + `__astraBack`); a canvas gallery must never spawn a second overlay.

## Adding a CONTROL block vs a DATA block — the alias table bites data types

`validateBlock` resolves `TYPE_ALIASES` BEFORE `BLOCK_TYPES`. A leftover
near-miss entry therefore silently hijacks a brand-new real type: the v1 entry
`graph: "chart"` rerouted every `graph` block into the chart validator, so each
card degraded while the type existed, the parser accepted it, and the alias
looked obviously correct. **When adding any type whose name was ever a near-miss
(`graph`, `list`, `note`, `chip`, `meter`, `range`, `filter`, `rows`, `grid`),
delete its alias entry and add a test asserting the REAL type reaches its own
validator.** In JS object literals the LATER duplicate wins (TS only errors on
literal duplicates) — so a re-point is silent, not a compile failure.

## The accent is a ROLE (`--color-accent`), never a hue name

The theme engine's storage slot is `--color-cyanx` (palettes.json + tokenize.mjs
own that name), but **every painted value reads `var(--color-accent)`**. A
palette whose accent is orange must not paint a cyan button; addressing the hue
slot directly is the bug. Rules that keep it true:

- The storage slot stays OUT of `@theme`, on a plain `:root` rule. A `@theme`
  token makes Tailwind emit `*-cyanx` utilities, which is a second, invisible
  way to paint by hue name — verified absent from the built CSS.
- `theme-store.applyPalette` writes `--color-accent` on every palette switch (and
  `:root`/`[data-theme="light"]` each declare a real literal, never a
  self-reference: `var(--color-cyanx)` inside the light scope resolved to
  nothing and wiped the accent in light mode).
- Channel-var role annotations read `accent`, and the role→slot map resolves
  `accent` to the palette's own `--color-cyanx`.
- `--color-accent` must be IN `@theme` or no `text-accent`/`bg-accent` utility
  exists.
- Pin it by extracting PAINTED VALUES (the right side of a colour property), not
  by matching the var anywhere — the role's own definition legitimately reads the
  slot, so a file-wide match passes while a component still bypasses. Prove the
  assertion RED on an injected bypass before trusting it green.
- `theme-panel.tsx` may name `--color-cyanx`: that panel's job is editing the
  palette slots by name.

## Text must never split a word mid-word

`overflow-wrap: anywhere` and `word-break: break-word` break a word IN HALF on a
tight line ("deploy|ment") — the owner reads this as broken typography. The
correct combination, applied as ONE global baseline so new components inherit it
(re-adding `anywhere` per rule is exactly the regression):

```css
overflow-wrap: break-word;  /* break a token only when it cannot fit a line alone */
word-break: normal;         /* keep Latin/CJK word boundaries */
hyphens: none;              /* no invented hyphenation artefacts */
```

Hashes, URLs and paths still wrap because they are unbreakable tokens. The one
sanctioned `break-all` is `.gate-finding-file` — a raw path in monospace is not
prose and a re-wrapped hash is a wrong hash. Pinned by `src/lib/text-wrap.check.ts`;
when writing such a check, strip CSS comments before matching selectors (a comment
that NAMES the token otherwise trips the assertion) and join multi-line selectors
(only the last line is not the whole selector).

## The `graph` block — deterministic force layout, zero dependencies

`canvas-graph.ts` (pure maths) + `canvas-graph-view.tsx` (SVG renderer). Ported
from the comindash dashboard's cytoscape + d3-force implementation with the
dependency dropped: d3-force is ~90 lines of the same springs, and the payload is
small enough that hand-rolled pan/zoom beats a 137 kB canvas engine.

**Physics that actually settles** — each of these was a real failure:

- Repulsion must fall off as `1/d` (d3's many-body), not `1/d²`. Inverse-square
  decays so fast that the springs cannot pull nodes apart at all and the whole
  graph collapses to one point; equilibrium is set by force BALANCE, so no amount
  of charge tuning fixes it.
- Separation is a POSITIONAL CONSTRAINT applied after each integration step,
  over ALL PAIRS, twice per tick (d3's `forceCollide` trick). As a force — or
  limited to linked neighbours — unlinked nodes pile up and their labels stack.
- Velocity decay (~0.62/tick) is what makes a simulation settle; without it the
  nodes ring around the fixed point forever and the spread stays tiny.
- No centring force when springs define the layout — centring fights them and
  everything ends up at the middle.
- Golden-angle seeding, synchronous settle, same graph → same picture, so people
  build a mental model of where things live. Filters must NOT re-run layout.
- Verify shape by ANGULAR spread around the centroid and MIN PAIRWISE DISTANCE
  (≥ sum of radii + label room), never absolute span: the normaliser rescales to
  the frame by construction, so span proves nothing.

Graph laws: kind reads as circle/square/diamond at three opacity tiers (never
hue); dangling edges are dropped, not fatal; focus dims but never removes; a
text list twin carries keyboard/AT access; component counting must take the
NODES too — an adjacency built from edges alone reports zero clusters for a lone
node.

## Extra chart kinds ride the engine you already ship

`sankey`, `treemap`, `funnel`, `scatter`, `radar` come free from the installed
recharts — zero new bytes, four more things the owner can ask for. Each accepts
its NATURAL vocabulary (`nodes`+`links`, `items`, `stages`, `labels`+`series`)
and the validator normalizes to the canonical `{labels, series[]}` shape, so a
near-miss emission renders instead of degrading. Never force these onto the flat
`series` shape at authoring time — models write the natural one. Cell/node
renderers hand-roll the label paint (`paint-order: stroke`) so text stays legible
over any fill.

## Motion: transform/opacity only, and never gates content

- Progress fill animates `transform: scaleX(var(--cv-pct)/100)` over a full-width
  element — never `width`, which forces layout on every change.
- Block arrival is ONE CSS keyframe staggered by a `--i` index set per item, so
  no JS timer is scheduled per block.
- Every animation is gated on `prefers-reduced-motion`, and none of them gate
  CONTENT: a card must paint its final state even if the animation never ran (a
  backgrounded Android WebView kills timers).
- `:focus-visible` must exist on every interactive canvas surface — a canvas with
  focus rings only on its editable fields is unusable by keyboard.

```bash
npx tsx --test src/lib/canvas-schema.check.ts src/lib/canvas-bind.check.ts \
          src/lib/canvas-expr.check.ts src/lib/canvas-theme.check.ts \
          src/lib/canvas-gates.check.ts src/lib/canvas-replay.check.ts
npx tsc -p tsconfig.app.json --noEmit     # project-strict; solo configs are looser
npm run build                              # tsc -b (strictest) + vite
# then confirm the SERVED bundle carries the feature (build == deploy):
JS=$(curl -s http://127.0.0.1:3011/ | grep -o 'assets/index-[^"]*\.js' | head -1)
curl -s "http://127.0.0.1:3011/$JS" | grep -c ReactiveHub
CSS=$(curl -s http://127.0.0.1:3011/ | grep -o 'assets/index-[^"]*\.css' | head -1)
curl -s "http://127.0.0.1:3011/$CSS" | grep -c 'ast-cv-ctl'
```

A passing test + clean build is proof; the owner is the visual QA — emit a real
reactive card and ask him to drag the slider.
