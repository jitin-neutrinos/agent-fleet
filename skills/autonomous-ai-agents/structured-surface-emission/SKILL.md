---
name: structured-surface-emission
kind: skill
description: Emit data surfaces that render instead of degrading to text.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [canvas, emission, validation, generative-ui, json-fence]
    related_skills: [astra-canvas]
---

# Structured surface emission — make it render, prove it renders

Class-level skill for any answer whose DATA lives inside a machine-parsed envelope
(the Astra `astra-canvas` fence today; the same discipline applies to any fenced-JSON
surface a renderer consumes).

A parser that tolerates malformed input fails SILENTLY, in two ways. A bad envelope
falls back to plain text: the user sees raw JSON, concludes the feature is broken, and
the agent goes hunting in the renderer. A bad BLOCK inside a good envelope is dropped on
its own: the card renders without it, with no error and no raw JSON, and the user
reports a "blank" or "missing" chart. **Validate the payload with the consumer's own
parser BEFORE emitting.** One command replaces the round-trip.

## When to Use

- Emitting numbers, a comparison, a sequence, a hierarchy, status or citations into a
  structured surface (canvas card, fenced-JSON block, any renderer-consumed envelope).
- The owner says a surface "rendered as text", "is broken", "showed raw JSON".
- Any emission whose malformed form fails SILENTLY rather than loudly.

## Procedure

1. **Compose the payload as data, not as prose.** Build the JSON in a scratch file
   (or an `execute_code` cell), never by hand-typing a fence into the reply —
   hand-typed fences pick up smart quotes, truncated tails, and stray prose after
   the closer, all of which parse as garbage.
2. **Run the consumer's real validator over that file.** For Astra, run `scripts/validate-canvas-spec.mjs`
   (in this skill's `scripts/`). It imports the astra-webui checkout and calls its
   `validateBlock` on every block plus `splitCanvasBlocks` on the wrapped fence,
   printing an `INVALID` line per bad block plus the block kinds and the card count.
   The checkout path defaults to `~/Work/projects/astra-webui`; when the repo moves
   or you validate from another workspace, `ASTRA_WEBUI=/path/to/astra-webui node
   scripts/validate-canvas-spec.mjs <spec.json>` — do not conclude the validator is
   broken when only the default checkout path is missing.
3. **Require three things before sending:** every block valid (a single `INVALID` line
   means that block will vanish from the rendered card: fix it, never ship it), exactly
   the expected number of cards, and no ``` inside the payload (needs a longer outer
   fence).
4. **Emit the validated file's contents once**, inside the fence. One canvas per
   idea; 2–4 cards in a reply is normal.
5. **Add no prose restatement of the card's numbers.** One sentence of
   interpretation after the surface, then stop.

## When the card renders NOTHING (blank, no error, no raw JSON)

Distinct from the malformed-emission case: there the user sees text. Here they see an empty space,
which is the *stale-deploy* failure and is invisible from the payload side.

**A rejected dynamic import never reaches a React error boundary.** The rejection is async, so
nothing throws during render, `Suspense` shows its fallback and stays there, and the boundary
never fires — no console error, no fallback UI, just a blank card. A guard placed in a component
boundary therefore cannot see it. Put the handler on the import promise, where the failure is
observable:

```tsx
const View = lazy(() =>
  import("./view").catch((err) => { if (isStaleChunkError(err)) reloadOnce(); throw err; }),
);
```

Diagnose blank-vs-broken in this order, and stop before touching the renderer:

1. **Validate the exact stored payload** through the real parser and renderer (`renderToStaticMarkup`
   on the component). A spec that renders to 15 KB server-side is not an emission bug.
2. **Replay the message that actually failed**, read back out of the store — not a hand-typed
   approximation. Synthetic payloads pass while the live case stays broken.
3. **Walk the chunk graph**: every hashed asset the entry HTML references, then every relative
   import inside the lazy chunk, resolving each over HTTP. A 404 anywhere means a stale tab.
4. **Compare what the SERVED HTML references against the build on disk.** After a rebuild the
   content-hashed filenames rotate; a tab opened before the deploy holds the old names, which no
   longer exist. Hashed assets are correctly served `immutable`, so the stale reference is the
   expected behaviour of a correct cache policy — the remedy is the user's reload.

Corollary for the server: answer a missing hashed asset with 404 (never index.html — that is the
`text/html is not a valid JavaScript MIME type` white screen), and make the boundary's stale-chunk
matcher cover every wording the bundler emits (`Failed to fetch dynamically imported module`,
`Loading chunk N failed`, `error loading … chunk`, `MIME incompatible`, `ChunkLoadError`).
Test the matcher against real messages; a `MIME` phrasing arriving from a 404 is the tell.

## Pitfalls

- **Every number in an emitted card must have a log/file/host-probe behind it, or carry a stated estimate/not-measured label.** A card renders its figures as polished measured evidence — an unverified count, spark/point series, or delta then gets quoted by the reader (and the next debugging session) as fact. Before ANY display card goes out, re-derive each figure from data actually read this session (log lines, DB rows, git log/parent map, `uptime`/`free`, port probes); a figure you cannot trace is dropped or explicitly labeled as demo/not-measured. Showcase cards with synthetic numbers count too — label them, never fake a citation.
- **Media paths must be verified against where the SERVED app reads files, before emission.** A repo-checkout path is not proof of reachability: an asset can sit outside the deployed web root (e.g. Vite `public/`) or in a folder the build never bundles, and the block then renders the clean "unavailable" slot — graceful, but a dead exhibit. Confirm the file exists AND resolves under the served root (or is a real host file the media viewer/video element reads); on a failed check, rewrite the `src`, never drop just that cite-ability claim.
- **"It rendered as text" is a malformed EMISSION until proven otherwise.** Diagnose
  in this order: (1) re-read the bytes you actually sent — a mangled tool-call blob,
  a truncated body, or duplicated fence text all parse as garbage, and the
  fall-back is CORRECT behaviour, not a bug; (2) validate the exact payload; (3) only
  then look at the renderer. Restarting the front end or editing the parser first
  buries a self-inflicted emission bug under a renderer hunt, and re-sending the same
  unvalidated spec reproduces it exactly. Cost here: a full diagnose-and-redo cycle,
  during which the parser's own suite was green (48/48) the whole time.
- **Emit the canonical envelope, never ad-hoc top-level keys.** For Astra the
  wrapper is `{"v":1, "title"?, "blocks":[…]}` with every block inside `blocks`.
  A payload that puts blocks at the ROOT as named keys (`"callout": {…},
  "kpi": {…}`) is valid JSON, passes any syntax check, and still fails the
  envelope shape — so the whole card degrades to a raw code block with no error
  on any surface. The parser coerces a few known shapes, but coercion is a
  compatibility layer, not an API: never lean on it for a new emission. If the
  structure is anything but the canonical wrapper, run the validator before
  sending — and run it for ANY card whose shape you have not emitted before;
  a "simple" status card skipped validation this way and shipped as raw JSON,
  burning a full user round-trip to discover.
- **Repair JSON where it is cheapest, at the string level, in tiers — but never with a
  naive regex.** Real emitted payloads fail in a small set of ways: literal newlines
  inside string values (markdown in a `text`/`document` block), missing commas
  between array elements (table rows), and a string truncated mid-emission when the
  model runs out of tokens. All three are repairable, and the recovery is large — a
  whole long report comes back instead of raw JSON. Every repair pass MUST track
  whether it is inside a string literal; a regex that rewrites `],[` or `}{`
  anywhere will happily corrupt a code block containing those characters, and a
  python `re` will warn "Possible nested set". A repair that makes previously-invalid
  JSON parseable can then change which fence run is read as the closer, so a
  previously-passing suite will catch the collateral damage — run the FULL parser
  suite, not just the new case.
- **A parser-side fix must be verified against REAL failed payloads, not synthetic
  ones.** The failures worth encoding come from replaying actual stored messages; a
  hand-written approximation of "what the model emits" tests the wrong thing and
  passes while the live case stays broken.
- **A card that renders but lacks one block is a validation drop, not a renderer bug.**
  The parser keeps every block that validates and discards the rest; only a card with
  ZERO valid blocks degrades to raw text. Run the one block through the real parser
  (`null` = dropped) before touching the renderer. The usual cause is a natural data
  shape the whitelist does not accept; fix it by normalising in the parser (and pinning
  it in the parser's check), not by teaching every future author a stricter shape.
  **Concrete instance:** `table.columns` must be a plain string array
  (`["A","B"]`), never an array of objects (`[{"key":"a","label":"A"}]`). The
  schema validator checks `isStrArr(b.columns)`; an object array fails and the WHOLE
  table block returns null — the card renders a blank section with no error. Always
  emit column headers as plain strings.
- **A control block nested inside a `steps`/`checklist` item is not a block.** `{"type":"steps","items":[{"title":"…","type":"toggle","label":"…"}]}` is valid JSON and reads as a control in the draft, but the validator rejects the WHOLE `steps` block — one illegal member drops every step, not just that item. Interactive blocks (`slider`, `select`, `multiselect`, `segmented`, `toggle`, `search`) are top-level siblings in `blocks`, never item fields. This is worse than a missing control: the steps it was documenting vanish with it, so the card silently loses a whole section. Compose, validate, then hoist anything the validator names.
- **Test counts written into a skill go stale — re-measure and patch in place.** The
  documented "expected: 43 pass" was 46. Run the suite, then correct the sentence.
- **Pick the chart kind by the DATA shape, not by looks.** A radial/pie is one part
  of a whole (single series, <=6 slices, percentages summing to the total). Feeding it
  absolute counts across three unrelated categories renders a meaningless ring — and
  it silently looks like a working chart. `bar` for magnitudes compared across
  categories, `line`/`area` for a time axis with >=3 points. Two `bar` charts with
  different framings beat one `radial` pretending to be a progress gauge. Non-flat data:
  `scatter` takes `[x, y]` pairs (axis titles from `labels: ["x: …", "y: …"]`), `sankey`
  takes `nodes` + `links: [{source, target, value}]`.
- **A title is a report name, not a label.** The owner asks for a focused dynamic
  heading; the renderer also auto-appends the first KPI value, so a literal "Canvas"
  or "Report" title reads as a bug.
- **A long report still renders as ONE card — that is correct, not a bug.** When
  the user asks for an "A4 report" or "slides", they mean the card must be PAGINATED
  into pages and downloadable, which is a RENDERER feature (a view mode on the card),
  not a different emission shape. Do not invent a `page`/`break` block or split the
  report across several fences to fake pagination — that breaks the copy-as-markdown
  path and the viewer. Emit the one card and add the export affordance in the renderer.
- **Ragged/greedy packing that loses blocks is the export defect to fear.** If a
  paginated view keeps ONE page node and reassigns it as the user pages, the capture
  pass sees a single node and the download silently carries one page while the viewer
  reports nine. Render EVERY page at once and hide inactive ones with
  `visibility: hidden` — never `display: none`, never detached; a rasteriser
  (html-to-image, and the PDF/PPTX writers built on it) renders through computed
  styles, so an undisplayable node captures as a blank rectangle. Stack pages in one
  grid cell so stage height never changes, and make the viewer and the capture walk
  the SAME nodes so the file can never drift from the screen.
- **Extract the page-packing rules into a pure function and unit-test them without a
  DOM.** `packPages(heights, mode) -> [start, end][]` is trivially testable, and the
  invariant worth asserting is a PARTITION: every block on exactly one page, ranges
  abutting, first starting at 0, last ending at n. A viewer-side assertion cannot
  catch a packer that silently drops a block.
- **A fixed-width page box with `overflow: hidden` crops intrinsically wide blocks.**
  Many-column tables, long code lines, diagrams with a `min-width`, and wide heatmaps
  push past the page padding and get sliced at the edge — cropped data, worse than a
  scrollbar. Contain instead of padding: cap blocks to the content width with
  `max-width: 100%` + `min-width: 0`, let wide content scroll in its own frame, and
  neutralise `min-width: auto` on the page's grid/flex children (that default is what
  refuses to shrink and widens the page box past its declared width).
- **Validate through the CONSUMER'S code, never through your own reading of the spec.** Writing a
  probe that imports the component and asserts on its HTML is what turns "the card looks wrong"
  into a named cause. Two mistakes this replaces: asserting on a heuristic you believe is
  equivalent to the renderer's scoring (it is not — the heuristic was invented after one
  misdiagnosis and generalised nothing), and running a probe under a JSX runtime the app does not
  use, which fails with a bogus `React is not defined` on every block. Match the app's own
  `tsconfig` JSX setting.
- **When a probe contradicts a subagent's or a sibling's finding, reproduce the number yourself
  before either claim becomes the premise.** Real corrections this session: a "never fired"
  feature that had 1,363 real outputs; a "timeout too short" diagnosis that was actually a 401; a
  "score is inverted" claim that was a starved data path with correct maths. Each would have been
  written into a plan as fact.
- **A NUL byte in a source file makes every text tool treat it as binary** — `file` reports
  `data`, grep prints "binary file matches", and search/patch fail to match symbols you can
  visibly see. Easy to create via a raw `"\x00"` string literal. Confirm with
  `python3 -c "print(open(p,'rb').read().count(b'\x00'))"`, then rewrite the literal as an escape.
- **Non-structured surfaces show the fence as text** (plain CLI, Telegram). Answer in prose or a
  compact markdown table there instead — there is no error to fix.
- **A very large VALID card can still fail to paint — validate first, then treat size as the
  suspect.** The two failures are indistinguishable to the user: both show a blank or absent
  surface. Discriminate with measurements, not a theory: (1) run the exact stored bytes through
  the real parser and record the block count AND the byte size; (2) if every block validates, the
  payload is NOT the cause and the render path is; (3) a 17-block / 9 KB card is a very different
  render load from a 4-block KPI card, so it is the first suspect, not a proven culprit. State
  that honestly — "the payload is valid, the render is where it fails, size is the leading
  suspect and I have not yet proven the threshold" — and get the size cap in regardless, because
  a card is a visual surface, not a document. `scripts/replay-stored-message.mjs` does step 1 in
  one command.
- **Do not blame the parser, the bundle, or a stale deploy before the payload is measured.** In
  the same session the same valid 17-block spec parsed cleanly through the real parser in both
  streaming modes, the served bundle was byte-identical to the local build, and the card still did
  not appear. Three separate theories were stated as near-causes before any number was taken. The
  cost of that ordering is a report the user reads as a diagnosis when it is a guess.
- **A partially-revealed payload returning `hasCanvas() === false` is the guard WORKING**, not a
  second bug. Confirm it once with a prefix that ends inside the fence, then move on; treating
  correct behaviour as a fault sends the hunt in the wrong direction.

## Shipping a change to the surface

When the task is to CHANGE the renderer (not just emit), the loop is:

1. Edit, then `npm run build`, then `systemctl --user restart <unit>`. Both — a
   restart alone serves stale assets, a build alone is never live.
2. Prove the new code is actually being served BEFORE assuming it is missing:
   grep the BUILT bundle for a distinctive new string
   (`grep -l 'View as A4 report' dist/assets/*.js`), compare the hashed refs in
   `dist/index.html` against what the server serves, and read the asset's
   `cache-control`. Hashed assets are served `immutable, max-age=31536000`, so a
   tab opened before the deploy keeps the old chunk BY DESIGN — the remedy is the
   user's reload, and telling them that is the honest answer, not another rebuild.
3. Report the artefact path and the literal command output. Never a plausible
   summary in place of a real result.

Pitfalls that cost real time in this loop:

- **A literal NUL byte in a source file makes every text tool treat it as binary.**
  `file` reports `data`, grep prints "binary file matches" instead of lines, and
  search/patch fail to match symbols you can visibly see. Easy to create via a raw
  `"\x00"` in a string literal. Symptom: a file you are editing "does not contain"
  a function it plainly contains. Confirm with
  `python3 -c "print(open(p,'rb').read().count(b'\x00'))"`, then rewrite the literal
  as an escape (`"\0"`) or a sentinel char. A build can appear to succeed while
  silently omitting the module entirely — which reads exactly like "my code never
  ran".
- **When a fresh test fails on the run that wrote it, decide whether the TEST or the
  CODE is wrong before editing either.** Asserting a convenient page count instead
  of the real invariant produced two bogus failures against correct greedy packing;
  the fix belonged in the expectation. Re-read what the code does, then assert the
  invariant you care about (a partition, an ordering, a bound).
- **Overwriting a file you have only partially read is refused — read it all, or
  `patch` the region.** The guard is about on-disk content, not your recollection
  from earlier in the session; a full `write_file` over a file last seen via
  `read_file(offset, limit)` is rejected even when you wrote it yourself.
- **Mutating a file through `execute_code` or `terminal` makes the NEXT `write_file`
  a stale write too.** Those paths bypass the read bookkeeping, so the guard sees
  content it has no record of reading and refuses with a "modified since you last
  read" message that is technically true and practically confusing — you are being
  blocked from a file you wrote two calls ago. Round-trip an in-place edit through
  `execute_code`? Re-read the file before rewriting it, or write the next version
  to a NEW path. Editing JSON in place and then rewriting it wholesale is the
  pattern that trips this; `patch` or a fresh filename avoids it.
- **Ship, don't narrate.** Every turn with an unblocked tool call ends with a tool
  call, not a paragraph about what you are about to do. "You've been thinking for a
  while / implement please" means turns went to restating a plan or re-diagnosing
  established state while the artefact stayed put. If a reply's content is an
  intention, delete it and run the tool; the diff has value, the narration does not.

## Ownership note

`astra-canvas` (user-owned) holds the Astra block vocabulary, schema and render
surface — read it first for those. This skill holds the emission/validation discipline
that applies to any fenced-JSON surface, and is where the validate-first rule lives.
To let this curator maintain that skill as well: `hermes curator adopt astra-canvas`.

**Showcase presentations live here too.** A "show me your full canvas"-class giant
card is a presentation task governed by the emission discipline in this skill plus
`references/canvas-showcase-recipe.md`; the block vocabulary itself stays with
`astra-canvas`. Corrections to the VOCABULARY or the render surface (e.g. a block
type's shape) land in that user-owned skill, not here.

## References

- `references/canvas-showcase-recipe.md` — the full build pipeline for ONE rich canvas
  showcase card (many block types + interactive controls + real host data): batch
  data collection, programmatic assembly, validator-driven fix loop, state seeding,
  deterministic first paint, slice-and-stitch emission.
- `scripts/validate-canvas-spec.mjs` — pre-emit validator (Astra): per-block validation +
  card count + fence-safety check. Run on every candidate spec before sending.
- `references/json-repair-tiers.md` — the three malformed-JSON failure modes worth
  repairing, the string-aware rule for each pass, and why a repair forces a full-suite
  re-run.
- `scripts/replay-stored-message.mjs` — pull the message that ACTUALLY failed out of
  `state.db` and run it through the consumer's parser: size, block count, per-block
  validation, both streaming modes, the live-path planner result, and the mid-payload
  reveal-guard check. Run from the repo root so the TS loader resolves.
- `astra-canvas` — the block vocabulary (closed set; `BLOCK_TYPES` in
  `src/lib/canvas-schema.ts` is authoritative), `docs/canvas-directive.md`, and the render path.
