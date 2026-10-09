# Building a rich canvas card — the verified pipeline

Class of task: the owner asks for ONE card demonstrating the canvas's full range
("show me every block type", "rich capability showcase") — many block types,
interactive controls, layout composition, embedded media, and real data in one
emission. The failure mode this recipe replaces: hand-typing a giant fence,
shipping invalid blocks, or improvising block shapes from prose docs.

The measured shape of a good run: 76 blocks / 48 distinct top-level types (49
counting `badges` nested inside a `layout`) / ~20 KB compact spec / validator
0 invalid / exactly one card. A 20 KB card is safe to emit; the ~13.5 KB figure
an earlier run recorded is not a cap.

## Steps

1. **Collect real host data in ONE batch before drafting.** `uptime`, `free -h`,
   per-service port probes (`curl -s -o /dev/null -w '%{http_code}' --max-time 2`
   in a shell loop), git log + parent map + merge commits, DB row groups via
   sqlite3, real hexes from the theme file. Probe at least one failing endpoint
   too — a status row mixing success and failure reads as evidence; all-green
   reads as decoration.
2. **Audit coverage of the CLOSED SET before drafting, by reading `BLOCK_TYPES`
   from `src/lib/canvas-schema.ts` (line ~650) — do not trust this recipe's type
   list as current.** Emit a census at the end of the build cell comparing the
   types you emitted against that set: a type named in prose docs but absent from
   the schema nulls its block, and a type you skipped silently fails the
   "one of each" ask. Read every per-block `case` body in the same pass — those
   bodies, not the prose or the aliases table, are the shape rules.
3. **Assemble the spec programmatically in ONE build cell, as a JSON structure.**
   `spec = {"v": 1, "title": …, "state": {...}, "blocks": []}` and
   `spec["blocks"].append({...})` per block; dump with `json.dump(spec, indent=1)`
   to a scratch path. NEVER hand-type a 20 KB fence and NEVER split the assembly
   across multiple cells — each cell re-declares the array and silently drops the
   other cell's blocks.
4. **Fix from the validator output, from no other source.** Run the validator,
   read each `BLOCK n INVALID: <type>` line, correct the named block by reading
   that shape's raw case body in `src/lib/canvas-schema.ts` (its `case "diagram":`
   is the authoritative rule, not prose docs), then re-run. Two rounds converged a
   45-block draft to 0 invalid. When the validator reports 0 invalid but the
   build-cell census still shows a gap, the block was never emitted — fix the
   draft, not the validator.
5. **Cite from the code, not a paragraph.** The validator re-exports `validateBlock`
   from the schema — read `canvas-schema.ts` and the renderer component yourself,
   and cite LINE NUMBERS in the build cell. A claim about internals without a
   line number is decoration.
6. **Set a top-level `state` seed matching every control's default** (slider value,
   select/segmented defaults, toggle default, `"q": ""`). Control defaults do seed
   themselves even with no authored state, but the seed makes the first paint
   deterministic — a toggle-gated block's `$expr` must be TRUE at first paint or it
   renders absent.
7. **Unreferenced state keys still power bindings.** The binding reader falls back
   when a key is absent from state, so a bare `$expr` like `sum(threads)` computes
   even without `threads` in `state` — but keep `$expr` readers simple (arithmetic
   + helpers over one or two state keys). State values must stay SCALARS; objects
   in `state` are unsupported.
8. **Sequence blocks as a narrative, not data-type order.** Status badges → KPI
   evidence → data visuals → explanatory sections → interactive reveal → closing
   success callout LAST. Nothing trails the closing callout. Consecutive `kpi`
   blocks (≤4) group into one row; `progress` groups the same way. `spark` accepts
   3–24 points; outside the range the spark silently drops while the tile still
   renders.
9. **Dump the compact JSON in numbered slices** and print each in its own output
   block, then hand-reassemble into one `astra-canvas` fence in the chat reply.
   A 20 KB one-line compact JSON exceeds a single echo cell's comfortable output
   and risks silent truncation; three slices of ~6-7 KB each printed cleanly.
   Keep every slice an exact character-range slice of the compact form — the
   reassembled fence must equal the validated file byte-for-byte.

10. **Re-validate from disk after the state-seed, media-path and ordering edits,
    then emit.** Post-edit the file, re-run the validator (expect 0 invalid and
    card count 1); only then emit the fence. Re-derive the byte size AFTER the
    last edit and re-slice — an edit that grows the spec past a slice boundary
    silently truncates the emission if the slices were computed before it.

- `BLOCK_TYPES` is a closed set of 49 emittable types (incl. `layout`, `math`,
  `gitgraph`, `theorem`, `algorithm`, `palette`, `scorecard`, `compliance`,
  `clause`, `obligations`, `schema`, `sequence`, media, controls) — read the live
  set at `src/lib/canvas-schema.ts` ~line 650 rather than trusting any prose list.
  The schema file also tracks SIX phantoms that the validator REJECTS: never emit
  `metadata`, `entitycard`, `keyfinder`, `cluster`, `mapfield`, `footnote`,
  `canvasref` — those are reader-assembly names, not block types.
- `diagram` rejects in TWO ways: a missing `from`/`to` in any edge, AND a node id
  that appears in NO edge (dangling nodes). Either case nulls the WHOLE diagram
  block with no helpful error. Cross-check edges against the node id set before
  emitting.
- `layout` wraps nested blocks under `blocks: [...]`; `tabs`/`accordion` also
  recurse. Keep nesting two levels maximum — deeper composites risk inner-frame
  drops and grow unbounded on a phone.
- Chart kinds: `donut` (aggregates), `area` (a time series with multiple points),
  `radar` (a profile), `funnel` (a sequential flow), `histogram` (a distribution).
  `donut` shows the total in the hole; `stack` splits one bar into segments.
- **A block whose own `type` discriminator is also a field name loses to the field.**
  `palette` accepts `type` (`brand`/`ui`/`data`) but every other block uses `type`
  to say which block it is — so `{"type":"palette","type":"brand"}` is JSON where the
  LAST duplicate key wins. In JS `JSON.parse` the block becomes `type:"brand"`;
  in Python the build cell silently keeps the first, so the type census names a
  block that does not exist. Treat a census that reports an unknown type as a
  duplicate-`type` collision, not a new block: pass the family through a field
  that is not the discriminator (e.g. `space:"hex"` on palette, not `type`).
- **An "unexpected type" in your own census is a draft bug, not a schema change.**
  The validator only knows `BLOCK_TYPES` plus `TYPE_ALIASES`; a name that reaches
  neither is a name you invented. Fix the emitted block.
- Use the editable `slides` block for a deck preview; use the editable blocks
  (`spreadsheet`/`slides`/`document`/`text`) whenever the owner may take the
  file away. Nothing invalid degrades the whole card: invalid blocks are dropped one-by-one,
  so a missed `state` seed takes the WHOLE gated reveal with it while the rest of
  the card still renders — a blank reveal is the validator's usual verdict, not a
  renderer bug. Read canvas-schema's per-block `case` body for the exact rule.

## Media-path rules (verified near-miss)

- Verify every path EMBEDDED in image/gallery/video blocks against the deployed
  web root, never the repo checkout. `/assets/logo.png`-style repo paths can point
  OUTSIDE the shipped root and render the slot as "unavailable" — a validator
  clears the spec but does not chase file hits. Files under the web root that
  the bundler serves (e.g. `public/astra-logo.png`) are provably reachable in
  production; a repo asset folder that nothing imports or serves is NOT bundled
  and its paths render dead.
- **Resolve `image`/`gallery` `src` through the host files API, not the public path.**
  `srcUrl()` (src/components/canvas/canvas-reactive.tsx ~216) rewrites a non-URL,
  non-`/api/` src: an image becomes `/api/hx/files/download?path=<encoded>` and
  a video becomes `/api/hx/files/stream?path=…` (or `/api/media/transcode` when
  it needs transcoding). So `src:"~/Work/projects/astra-webui/public/foo.png"`
  is CORRECT for an image/gallery block — the server expands the `~/` — while the
  bare web path `/foo.png` is only right if the file genuinely lives under the
  served root. When in doubt, point `src` at the real host file path and let the
  server rewrite it; that path always resolves.
- A host path outside the web root (e.g. a generated splash video under
  `~/Work/local-av-gen/scripts/comfy_out/`) is fine for `video` — it exists on
  disk and the renderer shows it as a native `<video>` slot with controls.
  Annotate `caption` with the generator so the owner knows the provenance.
- **A `content_type` of `text/html` on a 200 means you probed the SPA fallback, not
  the asset.** `curl -s -o /dev/null -w '%{http_code}'` on an unrouted path returns
  200 from index.html. Check the content type (and the byte size) before claiming
  an image path is reachable.
- Deck previews use the editable `slides` block; don't hand-stack `image`
  blocks to fake one.

## Craft principles

- The `visible` binding (`{"$expr": …}`) gates EVERY block — use it for
  toggle-driven reveals, not a fake code marker.
- Write `backdrop-filter` (standard) in any embedded CSS, never only
  `-webkit-backdrop-filter` — lightningcss drops the unprefixed variant, so the
  glass effect silently vanishes in production.
- Do NOT trust the heuristic summary table for things the owner will MEASURE
  against. Re-derive each figure from log lines, DB rows, or API responses in the
  build cell; an unverified number on a polished card gets quoted as fact
  downstream.
- Keep chart kinds varied across a normal report: one aggregate (donut), one
  time-series (area), one profile (radar), one flow (funnel), one distribution
  (histogram) — not seven donuts. A "one of each type" showcase is the deliberate
  exception: there every CHART_KIND gets its own block, and the kind must match
  the data shape it is given — a `candlestick` gets `series[].ohlc:[[o,h,l,c]]`,
  an `errorbar` gets `series[].error`, a `scatter` gets `[x,y]` pairs. Feed a
  chart the wrong payload and it renders empty while the card still looks complete.
