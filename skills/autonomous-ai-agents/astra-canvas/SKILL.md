---
name: astra-canvas
kind: skill
description: >
  Render generative-UI surfaces (KPI rows, charts, tables, diagrams, checklists,
  steps, callouts) inside Astra chat messages via `astra-canvas` fence blocks.
  Always read `docs/canvas-directive.md` and `src/lib/canvas-schema.ts` first.
---

# Astra Canvas — generative UI surfaces in Astra chat

Class-level skill for any work that produces or tests the composed `astra-canvas` blocks rendered in Astra web + Android chat.

## The default is canvas

**Reach for a canvas FIRST on this surface.** It is the default output format, not
a garnish for data-heavy answers. If the answer contains numbers, a comparison, a
sequence, a hierarchy, a status, a snippet or a citation list, that content goes
in a block and the prose goes to interpretation and caveats.

Use it **aggressively**. 2–4 cards in one answer is normal and good — a KPI row
plus a findings table plus a risk callout is a well-shaped answer. The
anti-slop rule means *don't fragment ONE idea across five blocks*; it does NOT
mean *use at most one card*. When the owner asks to "see the other cards", emit
the remaining block types as real cards, never a description of them.

Surfaces that are NOT Astra (plain Telegram/CLI) render the fence as literal
text — answer in prose or a compact markdown table there instead.

## Always-on rules

- **37 block types, closed set (schema `BLOCK_TYPES`, canvas-schema.ts
  ~:414, measured 2026-10-04):** `kpi`, `chart`, `table`, `diagram`,
  `checklist`, `steps`, `callout`, `progress`, `timeline`, `compare`, `tree`,
  `code`, `references`, `quote`, `keyvalue`, `diff`, `heatmap`, `tabs`,
  `accordion`, `terminal`, `badges`, `divider`, plus the four EDITABLE ones —
  `spreadsheet`, `slides`, `document`, `text` — plus the v5 reactive controls
  `slider`, `select`, `multiselect`, `segmented`, `toggle`, `search`, `data`,
  and media `graph`, `image`, `gallery`, `video`.
  `kpi` (with optional `spark:number[3..24]` inline sparkline) and `progress`
  group into responsive rows; everything else stands alone. Chart kinds (12, `CHART_KINDS` in the same file): `line`/`area`/`bar`/`radial`/`pie`/`donut`/`stack`/`sankey`/`treemap`/`funnel`/`radar`/`scatter`
  (`donut` shows the total in
  its hole; radial gauges carry a fixed 0-100 domain — without it recharts
  auto-scales to the data max and 71% renders as a full ring).
  `diff` accepts structured `hunks` OR raw unified-diff
  `lines:["+ added","- removed"," kept"]`. `accordion` nests blocks and
  opens its first item; `terminal` accepts object/plain-string/bare-string
  `lines`.
- **Reach for an EDITABLE block when the user may want to CHANGE the value or
  take it away as a file.** `spreadsheet` (→ `.xlsx`), `slides` (→ `.pptx`),
  `document` (→ `.docx`), `text` (→ `.md`/`.txt`). Each renders embedded,
  expands to fullscreen via a maximize button, and downloads for real — on web
  AND the Android app. Pick on the artifact, not the size: a 3-row budget they
  will adjust is a `spreadsheet`, not a `table`; a talk you are delivering is
  `slides`, not a `steps` walkthrough. Do NOT use them for read-only reference —
  `table`/`keyvalue` render lighter and copy cleaner. Emit plain JSON (cells are
  scalars), never an engine object.
- **A `code` block containing ``` breaks a 3-backtick fence.** Emit it inside a
  4-backtick fence. The parser tolerates mismatched openers and trailing prose
  after a closer, but the longer fence is still correct.
- Emit structured data as a canvas block, never as a prose wall. Prose carries
  the argument; the canvas carries the evidence.
- **Colour codes render as swatches — so emit them as DATA.** A colour code
  (`#020C1B`, `rgb(…)`, `oklch(…)`) as a WHOLE `table` cell or `keyvalue` value
  paints as a swatch of that colour plus the code. Palette/design-token reports
  are plain tables of code values: one code per cell, the name in its own column
  (mixed text suppresses the paint — whole-string match only). Never fake
  swatches with emoji or colored text; never bury colour codes in prose when a
  cell or key/value value can carry them. 4-digit hex is not recognised
  (ticket-collision class); see docs/canvas-directive.md "Colour values render
  as swatches".
- Invalid specs degrade gracefully to a plain fenced markdown block (`kind: "md"`) — never silently drop data.
- Prefer 1–3 canvases per *idea*; multiple canvases are fine when sections are genuinely distinct.

## Procedure (test / build / emit)

1. **Confirm feature exists.** `src/components/canvas/canvas-view.tsx` + `canvas-blocks.tsx` + `canvas-chart.tsx`; `src/lib/canvas-schema.ts`; directive at `docs/canvas-directive.md`.
2. **Run the schema/test checks.** `.ts` ESM files require `tsx`, not bare `node --test`:
   ```bash
   npx tsx --test src/lib/canvas-schema.check.ts
   ```
   Expected: 81 pass, 0 fail (split, parse, degrade, diagram edges, streaming fence, mount gate, enum normalization, the five real emission shapes recovered from the Hermes DB, the v3 block-type suite — quote/keyvalue/diff/heatmap/tabs, kpi spark, donut/stack, streaming lenient repair — and the v4 editable-surface suite for spreadsheet/slides/document/text). See agentive-pipeline `references/esm-ts-testing.md`.
3. **Emit from agent:** wrap JSON in a fenced `astra-canvas` block inside your prose message. Example (from directive):
   ````
   ```astra-canvas
   { "v": 1, "title": "Usage", "blocks": [
     { "type": "kpi", "label": "Tokens", "value": 1234, "delta": "+12%", "trend": "up" },
     { "type": "table", "columns": ["x", "y"], "rows": [["1", "2"]] }
   ] }
   ```
   ````
4. **Copy feature:** `CanvasView` renders a header with `Copy` / `Copied` toggle (`lucide-react` icons) that writes markdown via `canvasToMarkdown` from `src/lib/canvas-markdown.ts`. Test the copy action manually if the feature was just rebuilt — do not assume it survived a bundle change.
5. **No `canvas_exec` tool exists.** There is no CLI that renders canvas blocks independently. Rendering is done by `CanvasView` inside the chat message pipeline (`src/components/chat-timeline.tsx` or equivalent). If a test asks "test the chat canvas feature," run the `.check.ts` tests, verify the component files exist, and confirm the fence format matches the directive — that is the actual work.

## Pitfalls

- **Never hand a generated file to an anchor as a `blob:` URL.** The Android
  WebView refuses `blob:`/`data:` outright (`MainActivity.setDownloadListener`
  → toast "Can't download this item"), so generate-then-anchor works on web and
  silently fails on the APK. Write the bytes server-side first (POST
  `/api/hx/files/upload` with a data URL, `overwrite:true`), then download by the
  returned path through the existing `downloadFile(path, name)`. Shared helper:
  `src/lib/canvas-download.ts`. Never branch on `Capacitor.isNativePlatform()`
  for downloads — that manufactures two behaviours and one is broken.
- **`note` aliases to `callout`, NOT to `text`.** Do not "fix" the alias table
  by claiming it for the text editor — that silently re-renders existing callout
  cards as editable boxes. Pinned by a test in `canvas-schema.check.ts`.
- **Fullscreen is a MODULE SINGLETON with a portal-moved node.** `Blocks`
  renders in several hosts at once (each card, each gate body), so per-component
  state would allow two overlays each owning a history entry and Android back
  would close the wrong one. The expanded surface is the SAME live DOM node
  moved by portal (one render → edits survive expand), and its id must be unique
  page-wide — namespace it with `useId()`, never a bare index.
- **Don't describe a card — emit it.** The owner is the visual QA. When he asks to see a block type, produce it; if you could not see a render yourself, say so plainly rather than claiming it looks right.
- **Fence length is part of the contract.** ``` inside a `code` block truncates a 3-backtick fence and the whole card degrades to raw text.
- **ESM `.ts` test resolution:** `node --test src/lib/canvas-schema.check.ts` fails with `ERR_MODULE_NOT_FOUND`. Use `npx tsx --test`. The fix is the runner, not the import spec.
- **Unknown enums kill only their BLOCK, never the whole card — verify at `canvas-schema.ts:1764` (per-block tolerance, 2026-10-04):** blocks validate one by one and `parseCanvasSpec` keeps every block that passes; the fence degrades to markdown only when NONE survive. But inside a block the vocabularies are exact and coerce silently: `checklist` `done|open|fail` (unknown e.g. `"warn"` → `"open"` — line 763, no rejection); `steps`/`timeline` `done|active|fail` + unknown → `"todo"` (774/804); `progress` `warn|fail` + unknown → `"ok"` (792); `callout` tone must be in TONES or the WHOLE callout block returns null (779); `kpi.trend` must be in TRENDS — unknown values try TREND_ALIASES, else the kpi block is DROPPED ("no silent lie", 557-560). Read them from schema before emitting.
- **Lazy-loaded chart chunk:** `ChartBlockView` is a `lazy` import backed by `Suspense`. A first-time render in a new browser tab triggers the chunk load; a second message reuses it. Do not assume `recharts` is in the main bundle — it isn't. If the build breaks on recharts import, verify `node_modules/recharts` exists and the lazy split point (`canvas-chart.tsx`) hasn't been renamed.
- **Copy button state:** `copied` is a `useReducer` ping with a 1600ms reset (`setTimeout`). The `Check` icon shows for ~1.6s, then reverts to `Copy`. Testing copy requires either watching the button or reading the clipboard through the `copyText` helper, not just checking the icon state.
- **Astra Android/web surface interaction:** `clarify` prompts (approval cards, questions) sometimes fail to render on Android/app surfaces. When working through Astra Android, prefer finishing a concrete verification step over leaving an interactive prompt hanging. Confirm results with evidence (test output, file paths, component state) rather than relying on the prompt being visible.
- **Malformed canvas emission, 2026-10-04 AI Hub session (checked against schema, not just remembered):** a `checklist` item drafted with `status:"warn"`; reading `canvas-schema.ts` showed "warn" is not an enum value (it would coerce to `"open"`, silently losing the flagged status) → fixed to `"fail"` before emitting. Corollary: always read the enum values out of `canvas-schema.ts` — `checklist`/`steps`/`timeline`/`progress` each carry different status vocabularies with different silent coercions (see the per-block tolerance pitfall above); and verify every `diagram` `from`/`to` against the nodes' id set before emitting.
- **Citation integrity on cards: quotes live in the citation ledger, never the
  canvas.** Canvas cards cannot carry `verify --evidence`; the measured pattern
  (2026-10-04, 12-source AI Hub chaining report): all `[n]` markers on spoken
  prose and references `note:` fields, verbatim quotes attached per source in
  the `grounded-citations` ledger (scratch evidence file at fetch time, `quote
  <id> --from <file> --text "<exact sentence>"`), ledger `verify --evidence`
  run BEFORE emitting, claims posed to Laya `done_gate(claims, evidence)` with
  the page-fetch outputs as evidence. Measured: verify exited 0 at 71%
  coverage and done_gate returned `supported` — but WITH `fabrication_risk:
  0.93`. The transcript does not prove WHY (the agent's paraphrase-only theory
  was speculation); treat fabrication_risk as a tighten-the-claims prompt, not
  a rejection. Slop-audit the JOINED canvas text (every
  `text/body/detail/title/caption/label/note` field from all cards; this run
  ~98 string fields), never a short prose file — a 278-char prose.txt scored 0
  tokens and proved nothing; the joined measurement (831 tokens) caught the
  one `lifecycle` wordHit.
- **Never invent `canvas_exec`:** There is no such tool in the harness inventory. If a plan mentions it, the plan is wrong; fix the reference to `CanvasView` or `tsx --test`.

## References

- `docs/canvas-directive.md` — full directive (fence format, block shapes, canonical examples).
- `src/lib/canvas-schema.ts` — data contracts (`CanvasSpec`, `CanvasBlock`, `KpiBlock`, `TableBlock`, `SpreadsheetBlock`, etc.).
- `src/lib/canvas-download.ts` — server-side write + download (the blob trap lives here).
- `src/components/canvas/canvas-view.tsx` — render surface (header + copy + `Blocks`, wrapped in the fullscreen provider).
- `src/components/canvas/canvas-fullscreen.tsx` — singleton fullscreen host + `Expandable` wrapper.
- `src/components/canvas/canvas-docs.tsx` — the four editable renderers (lazy; the only module importing the file engines).
- `src/components/canvas/canvas-blocks.tsx` — individual block renderers (`KpiTile`, `TableBlockView`, `DiagramBlockView`, `ChecklistView`, `StepsView`, `CalloutView`) + grouping logic (`Blocks`).
- `agentive-pipeline/references/esm-ts-testing.md` — `.ts` ESM test runner fix.
