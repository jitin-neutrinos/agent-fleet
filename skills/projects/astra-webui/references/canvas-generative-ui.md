# Generative-UI canvas (Astra chat + gates)

The chat renders fenced ```astra-canvas blocks as composed surfaces instead of
prose walls: KPI rows, charts, comparison tables, flow/relationship diagrams,
checklists, steps, callouts. The same block vocabulary backs review gates,
report gates, fix gates and clarify cards, so every "structured" surface in the
app shares one design language.

## Files

| path | role |
|---|---|
| `src/lib/canvas-schema.ts` | block types + `splitCanvasBlocks(text, streaming)` parser. No React. |
| `src/lib/canvas-schema.check.ts` | parser suite |
| `src/lib/canvas-gates.ts` | pure gate-body → block mappers |
| `src/lib/canvas-gates.check.ts` | mapper suite |
| `src/lib/canvas-markdown.ts` | spec → markdown (the copy-as-markdown button) |
| `src/components/canvas/canvas-blocks.tsx` | dependency-free renderers (KPI/table/diagram/checklist/steps/callout) + grouping |
| `src/components/canvas/canvas-chart.tsx` | the ONLY recharts consumer |
| `src/components/canvas/canvas-view.tsx` | canvas shell (header + copy button) |
| `src/components/ui/chart.tsx` | vendored shadcn chart wrapper (byte-for-byte) |
| `docs/canvas-directive.md` | the SOUL.md section that makes the agent emit canvases |

## Block types (closed set)

v1: `kpi`{label,value,delta?,trend?} · `chart`{chart:line|area|bar|radial|pie,title?,labels?,series:[{name,points}]} · `table`{columns,rows} · `diagram`{layout:flow|relationship,direction?,nodes,edges} · `checklist`{items:[{text,status}]} · `steps`{items:[{title,detail?,status}]} · `callout`{tone:info|warn|success|danger,title?,body}

v2 added the shapes v1 could not express — reach for one when the answer is a status/coverage read, a chronology, an option comparison, a hierarchy, a snippet, or a citation list: `progress`{label,value,max?,unit?,status?,detail?} · `timeline`{items:[{title,detail?,time?,status}]} · `compare`{items:[{name,caption?,badge?,points:[{text,tone:pro|con|neutral}]}]} · `tree`{nodes:[{id,label,detail?,children?}]} · `code`{language?,filename?,code} · `references`{items:[{title,href?,note?}]}

v3 (2026-10-03) added five types + two chart kinds + kpi `spark` + streaming lenient repair: `quote`{text,attribution?,role?,context?} (author/source alias to attribution/context) · `keyvalue`{title?,items:[{key,value,mono?}]} · `diff`{language?,filename?,hunks:[{header?,lines:[{op:add|del|ctx,text}]}]} — also accepts RAW unified-diff `lines:["+ added","- removed"," kept"]` with `@@` hunk headers · `heatmap`{title?,rows,cols,values} (rect grid enforced, cell intensity via `color-mix(cyanx)`; >10 cols hide cell numbers) · `tabs`{items:[{label,blocks:[…]}]} (each tab validated per-block, empty tab = invalid block) · chart kinds `donut` (single-series composition, total readout in the hole) and `stack` (stacked bars, `stacked`/`stacked-bar` alias) · `kpi.spark:number[3..24]` inline SVG sparkline (bad spark silently dropped, tile kept) · `parseStreamingBlocks` runs the lenient repair (comments/trailing commas/bare keys) per element MID-STREAM, not only on the closed fence.

KPI and progress blocks group into responsive rows (`Blocks`'s `ROWY` set); everything else stands alone. Add a type to that set only if it genuinely reads as a row.

## Adding a block type

1. Extend the union in `canvas-schema.ts` and add a case to `validateBlock`.
   Validate the SHAPE strictly (a field of the wrong type is a real defect and
   should drop that block), but never let one bad block sink the canvas — see the
   per-block tolerance rule under Parser contract. Alias near-miss type names
   instead of dropping them.
2. Add a renderer in `canvas-blocks.tsx`, then wire it into `Blocks` — one branch
   in the `inner` ternary. No registry/lookup abstraction for seven types.
3. Case in `blockToMd` (`canvas-markdown.ts`) so copy-as-markdown stays lossless.
4. Case in the parser suite: valid shape, invalid shape, and default-value tests.

## Editable + downloadable blocks (spreadsheet, slides, document, text) — SHIPPED 2026-10-03

Read this section before designing any block that writes a file or opens an overlay.
**These four are live**, not a plan: `spreadsheet`/`slides`/`document`/`text` render
embedded, expand to fullscreen, and download as real `.xlsx`/`.pptx`/`.docx`/`.md`.
Implementation is `src/lib/canvas-download.ts` + `src/components/canvas/canvas-fullscreen.tsx`
+ `src/components/canvas/canvas-docs.tsx`; commit `764f1de`.

### Generated files CANNOT download on the Android app

Anything a browser GENERATES in memory (`.xlsx`, `.docx`, `.pptx` — all built by zipping parts in JS) reaches the download as a `blob:` or `data:` URL. The Android WebView refuses both outright:

```kotlin
// android/app/src/main/java/com/jitinnair/astra/MainActivity.kt
wv.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
    if (url.startsWith("blob:") || url.startsWith("data:")) {
        toast("Can't download this item"); return@setDownloadListener
    }
    ...
}
```

So "generate then anchor-click" works on web and fails with a toast on the APK — the surface a download feature matters most on. **Fix: write the bytes server-side first, then download by path.**

1. `POST /api/files/upload` with `{ path, data_url, overwrite }` (upstream `hermes_cli/web_routers/files.py`). It decodes the data URL and resolves the target through `_resolve_managed_path`, which rejects `..`, enforces the managed root, refuses to clobber a directory, and 409s when the file exists without `overwrite`.
2. Call the existing client helper `downloadFile(path, name)` from `src/lib/download.ts`. It builds `/api/hx/files/download?path=…` — an ordinary HTTP URL, so Android `DownloadManager` treats it like any other file and forwards the `astra_session` cookie.

Verified live end to end: POST returns `{"ok":true,"path":"/home/notjitin/Downloads/…"}` and the
download URL serves byte-identical content. `saveCanvasFile` tries `~/Downloads` then `~`, and
stamps a collision suffix rather than silently exporting yesterday's file.

Web and APK then share one code path. Never branch on `Capacitor.isNativePlatform()` for downloads — that manufactures two behaviours and one of them is broken.

### Licence before weight, and reuse before dependency

Decision order for a new interactive dependency: (1) is an engine for this already installed, (2) is the licence usable commercially, (3) how many bytes. Neutrinos is a company, so a non-commercial licence disqualifies — **Handsontable**, the reflexive data-grid pick, is non-commercial AND the heaviest option. Grid cells that only need typing are a controlled `<input>`, not a data grid.

| package | role | raw | gzip | licence |
|---|---|---|---|---|
| `xlsx@0.18.5` | spreadsheet read + write | 412 kB | 140 kB | Apache-2.0 |
| `docx@9.8.1` | write .docx | 438 kB | 125 kB | MIT |
| `pptxgenjs@4.0.1` | write .pptx | 369 kB | 123 kB | MIT |
| `docx-preview@0.4.1` | render .docx | 172 kB | 49 kB | MIT |
| `pptx-preview@1.0.7` | render .pptx | 1.26 MB | 392 kB | MIT |
| `handsontable@16.1.0` | data grid | 1.11 MB | 280 kB | **non-commercial** |

A rich-text editor is usually not needed — a `contenteditable` surface is ~0 kB and enough for "basic editing, nothing more". Size figures come from `bundlephobia.com/api/size?package=<name>@<ver>` (JSON; it rate-limits and intermittently fails — retry, or read `node_modules`).

`pptxgenjs@4.x` changed its write API: `outputType` is a JSZip enum, **not** `"array"` — use `"uint8array"`, which returns exactly what the download helper wants. And `Packer.toBlob(doc)` returns a `Promise<Blob>`, so `await` it before `.arrayBuffer()`.

`pptxgenjs@4.0.1` pulls `image-size@1.2.1`, which carries two HIGH DoS advisories (JXL/HEIF and ICNS infinite loops, GHSA-5p2g-fcmc-qvqq / GHSA-w3rx-r6r6-pgpr) with **no fixed 4.0.x**. Pinned via `overrides: { "image-size": "^2.0.4" }` in package.json. The pre-existing `xlsx@0.18.5` advisories (prototype pollution, ReDoS) have no npm-published fix and are NOT reachable from this feature's input — we build our own workbook, we do not parse an untrusted upload.

### Fullscreen expansion is ONE shared host

Every block must be expandable, and embedded vs fullscreen must be the SAME live node — two renderers drift, and a second render loses edit state. Copy the contract proven in `src/components/media-viewer.tsx`:

**The scratch harness will NOT catch a broken overlay — it mounts at the document root, where `position: fixed` trivially works.** Only the real chat reproduces it. Two defects shipped that way and were invisible to `scratch/canvas-v3/`:

- **An overlay rendered inside `.chat-scroll` is invisible.** That container SCROLLS, and a `position: fixed` child anchors to the nearest scrolling ancestor's box, not the viewport. Measured live: `top -4604px`, 2314px tall — the card looked like it did nothing when maximized. **Portal the overlay to `document.body`**, and pin `height: 100dvh` or the pane grows with its content instead of filling the screen.
- **Mount the provider ONCE, at the app root (`src/main.tsx`) — never per card.** Per-card meant N overlays and N scroll-locks for one open card: overlay count 4, and `body { overflow: hidden }` left behind after close, leaving the chat unscrollable with nothing on screen. A "first provider claims the host" guard is a trap: the claimer is often an earlier card whose provider unmounts, leaving *no* overlay at all.

Debug it by MEASURING, not by clicking: overlay count, `getBoundingClientRect().top/height`, `parentElement`, and `document.body.style.overflow` before and after each close path.

- **One owned history entry.** `history.pushState({ ...prev, astraViewer: 1 }, "")` on open; close via `history.back()` when that state is present, else the `onClose` prop. Never call `history.back()` in unmount cleanup — `popstate` already handled the pop and doing both double-pops.
- **Android back asks the page first.** Register `window.__astraBack = () => { requestClose(); return true; }`, delete it on cleanup. `MainActivity`'s back handler evaluates it and only falls through to app-exit when absent or false. Without it, back exits the app instead of closing the overlay.

**The store is a MODULE SINGLETON, not component state** — the reason the provider must be mounted once. `useSyncExternalStore` bridges it into React.

**The expanded surface is the SAME DOM node, moved by `createPortal` into the shell's slot** — not a second render of the block. That is why an edit made fullscreen is still there on collapse. The old spot renders an explicit "Showing fullscreen" note rather than an unexplained gap. The overlay mounts in the same commit that flips the open id, so the slot needs one `requestAnimationFrame` before it exists.

**Slot ids must be unique page-wide.** The fullscreen key is a singleton, so a collision expands the wrong card. Namespace with React `useId()` (per `RichText` and per `TextRow`) — never a bare array index, and never the block index alone: `bi` restarts per group, so every standalone block would collide on `...-0`.

Radix dialog is a dependency but UNUSED here — build on the media-viewer pattern, the one already proven against the native shell.

### Gotcha: a NUL byte makes grep silently skip a file

`chat-timeline.tsx` joins memoized markdown blocks with a literal `"\0"`, so every content search
over it returns **zero matches** while a directory listing still shows it — "0 matches" reads
exactly like "the code isn't there". Any targeted search returning nothing for a symbol you have
personally seen in that file: confirm with `grep -c $'\0' <file>`, then re-run with `grep -a` /
`search_files` with text mode. Never conclude a call site is absent from a search that skipped the file.

### Gotcha: `renderOne` needs the id, so `Blocks` must thread it

When a block needs a stable identity, `renderOne(b)` has to become `renderOne(b, canvasId, bi)`
and `Blocks` gains a `canvasId` prop. Two call sites in `chat-timeline.tsx` (`RichText`'s canvas
parts and `TextRow`'s anchored/live canvases) then must pass an id or `tsc -b` fails — note
`tsc --noEmit -p tsconfig.json` is **looser** than the `tsc -b` that `npm run build` runs, so
always run the real build before declaring done.

### Build order that keeps verification cheap

Ship the zero-dependency path first, so the whole pipeline is proven before any weight is added:

1. Fullscreen host + expand affordance (proves the overlay contract against the shell).
2. The POST-to-disk download helper — kills the blob trap once, for every block.
3. Spreadsheet + text blocks, reusing installed engines, zero new bytes.
4. Document, then slides, each writer added lazily.
5. Extend `docs/canvas-directive.md` and the schema suite; keep every existing check green.

Emit new blocks lazy-loaded (`lazy(() => import(...))` + `Suspense`) like `canvas-chart.tsx`, so an ordinary chat never pays for them. Record the baseline BEFORE the first edit — `npx tsc --noEmit` then `npx tsx --test src/lib/canvas-schema.check.ts` — because a research/design turn must leave the tree exactly as found and the pass count is the receipt.

**Ship order that kept this cheap (and what actually happened):** fullscreen host + download helper first (zero new bytes, kills the Android trap once), then `spreadsheet` + `text` on already-installed engines, then `document` and `slides` with their writers added lazily. Each stage was independently verifiable, and the whole pipeline was proven before a single kilobyte of dependency was added.

**Show the new tests going RED before believing them.** Reverting just the new `validateBlock`
cases and re-running took the suite 81 → 75 pass / 6 fail; restoring the file returned 81/0.
A new green test proves nothing until it has been shown failing against the pre-fix code.

### Verifying a new block renders (deterministic, no live model)

`scratch/canvas-v3/` mounts the REAL `Blocks` renderers through the REAL `src/index.css`, so it
needs no auth and no WS. Two gotchas, both hit here:

1. **vite emits JS+CSS but no `index.html`** for this multi-config root — copy
   `scratch/canvas-v3/index.html` into `dist` and rewrite the script/link tags to the HASHED asset
   names after every rebuild, using `basename` (a path-with-`assets/` prefix double-prefixes).
2. **The `Suspense` fallback is not a failure.** A probe taken immediately after load sees
   `.ast-cv-doc-skeleton` placeholders and zero inner surfaces; the lazy chunk resolves a second
   later. Poll for the real surface (`document.querySelectorAll('.ast-cv-sheet, …').length >= 4`)
   before concluding anything is broken. Screenshotting at that moment shows a blank card.

Then assert behaviour, not just presence: edit a cell and re-read its value, click Next on the
deck and read the new heading, click the maximize button and read `__astraBack` /
`history.state.astraCanvasFull` / overlay count / `body.style.overflow`, then close via
`window.__astraBack()` and confirm the edit survived the portal move.

**But finish the check in the REAL app before calling fullscreen done.** The harness cannot see
the scrolling-ancestor or multi-provider failures above. Drive the live chat (sidebar -> Chats ->
the conversation), click maximize, and read the same numbers there. `npm run build` also runs
`tsc -b`, which is STRICTER than `tsc --noEmit -p tsconfig.json` — a prop added to a component
whose call sites were missed passes the loose check and fails the build.

## The lazy-chunk rule (bundle budget)

`lazy()` only helps if NOTHING on the eager path reaches the heavy module.
A static import of `canvas-blocks` from any always-loaded component drags the
whole subtree into the main bundle — which is exactly what a synchronous consumer
(gates must not flash a lazy fallback while the user waits on a decision) seems
to require.

Working split: keep the eager module dependency-free and push the heavy consumer
one level deeper, then lazy-load THAT.

    chart-timeline.tsx ──lazy──> canvas-view ──> canvas-blocks ──lazy──> canvas-chart (recharts)
    gate-card.tsx ──────────────> canvas-blocks   (sync, zero deps)

**Verify the split in the built output, not in the source.** Counting the heavy
library's signature strings per chunk catches the regression the source lies
about:

    for f in dist/assets/*.js; do
      printf "%s %s recharts-hits=%s\n" "$f" "$(stat -c%s $f)" \
        "$(grep -o 'recharts\|PolarAngleAxis' "$f" | wc -l)"
    done

Non-zero hits in `index-*.js` means the boundary leaked. Chunk size alone proves
nothing — a lazy chunk can be 2 kB because the engine never left main.

## Fence length is part of the contract (2026-10-03)

A `code` block whose content contains ``` **cannot live in a 3-backtick fence.**
The regex closed on the first run inside the JSON, truncating the spec, and the
whole card degraded to raw text. Reproduced on a real emitted card.

`scanFences()` now tries each candidate closer and takes **the first whose body
parses**. One rule covers every case: the canonical close, trailing prose after
the closer (` ``` outro`), a ``` run living inside the JSON, two canvases in one
message, and a mismatched opener (replaying history found a SEVEN-backtick
opener closed by three). `hasCanvas` and `planTurnCanvases` share the scanner, so
the mount gate and the renderer cannot disagree.

Getting there took three attempts and the replay guard caught every wrong one:

| attempt | looked right | actually did |
|---|---|---|
| strict line anchoring | correct per markdown | broke 5 real cards (mid-line closers) |
| prefer a line-alone closer | sensible | a LATER lone run swallowed the next canvas |
| first closer whose body parses | — | correct |

**Lesson: a "more correct" fence rule is not automatically better.** Every
change here must keep `canvas-replay.check.ts` green over the real corpus — it is
the only thing standing between a plausible regex and five silently broken
cards. Anchors are a trap: an anchored `OPEN_FENCE_RE` once failed to strip a
mid-message open fence, streaming raw JSON to the user.

## The emission shape is the real failure mode — coerce it, don't just document it

**Replay the corpus before touching the renderer.** `sqlite3` is NOT installed on
this host — read `~/.hermes/state.db` with python's `sqlite3` module (`file:…?mode=ro`,
`uri=True`) instead. Then run every `astra-canvas` message through the REAL entry
points and bucket by outcome. On 2026-10-03: **120 fences / 84 messages → 106
rendered, 14 not** — and the 14 were NOT all bugs:

| bucket | count | is it a bug? |
|---|---|---|
| prose that merely mentions ```astra-canvas``` | ~12 | **no** — a correct non-card |
| surplus trailing bracket (depth -1) | 2 | **yes** — repaired by `lenientJson` |
| a `kpi` item missing its `{` | 1 | **no** — genuinely malformed, must stay degraded |

So the true defect rate was 2/120, not 14/120. Always split the bucket before
reporting a number; "14 cards are broken" sends the fix at the wrong layer.

That surplus-bracket class is now repaired (`lenientJson` → `balanceBrackets`):
walk with a stack of open brackets, step over string contents so a brace inside a
value is never structural, drop a stray closer matching nothing, re-close with the
exact mirror. It never invents content, so a payload it "repairs" is the payload
the model meant. Pinned by tests that also assert an unrepairable payload STILL
degrades — a repair that fabricates a block is worse than the raw JSON.

**Evaluate a JSON-repair library by RUNNING it on your real payloads, not by
reading its README.** `jsonrepair` (2.5 kB gzip, zero deps) beat the hand-rolled
`balanceBrackets` on missing commas, single quotes and truncation — but fed
prose-wrapped JSON (`Here is the card:\n{...}\nHope that helps.`) it returns an
ARRAY of three elements, prose and object as siblings, silently destroying a card
that was otherwise valid. A repair library that mangles a parseable payload is
worse than one that refuses. So: extract the outermost object FIRST with a
string-aware scanner, hand only pure JSON to the repairer, and validate that
`blocks` exists before trusting the result. Judge any candidate against a table of
synthesized shapes — surplus closer, missing comma, single quotes, trailing comma,
truncated, prose-wrapped, genuinely-broken — plus the real corpus.

**The owner's browser is the ground truth, and it can disagree with yours.** The
same chat rendered 5 cards with zero raw JSON on both `127.0.0.1:3011` and
`astra.jitinnair.com` while they reported raw JSON. Before changing code: confirm
they are on the deployed build (`curl -s <url> | grep -o 'assets/index-[^\"]*\.\(css\|js\)'`
and compare with `ls dist/assets/`), then ask for a hard reload. Two false
theories got measured and discarded before the real one surfaced — say that
plainly instead of shipping the first plausible fix.

**When you cannot reproduce the owner's report, never quietly turn it into your
own bug report.** State what you measured and on which origin, say you could not
reproduce, name the theories you discarded, then point at the specific message
they should look at. Here the honest "renders correctly here; 2 of 120 fences
genuinely broken" was more useful than a fix aimed at a stale cache, because the
bucket split is what revealed the real defect rate.

Replaying every `astra-canvas` fence in `~/.hermes/state.db` (30 occurrences,
23 messages) showed **only 6 rendered as cards**. The parser was correct the
whole time; the model's OUTPUT was not, and the directive alone did not fix it
(29 of 30 postdate it going live). Do not assume "the agent was told" means
"the agent complied" — measure the DB.

Five shapes that all used to degrade to a raw-JSON code block, now coerced in
`canvas-schema.ts`:

| shape | example | handled by |
|---|---|---|
| bare block, no envelope | `{"type":"kpi","label":…}` | `coerceToBlocks` wraps it |
| `blocks` as the ITEM list | `{"type":"kpi","blocks":[{label,value}]}` | inner objects have no `type` → they are items |
| NDJSON, no envelope | one `{…}` per line | `parseNdjson`, per line |
| misnested fence | ```` ```astra-canvas ```` then ```` ```kpi ```` | `healMisnestedFence` + type hint |
| unquoted keys | `{label:"x",value:1}` | `quoteBareKeys`, string-aware |

The misnested one is the nastiest: the outer fence closes on the **empty first
line**, so the payload lands outside the fence and the body handed to the parser
is `""`. Nothing downstream can recover it — the heal has to run on the whole
message text in `splitCanvasBlocks` / `planTurnCanvases` / `hasCanvas`, and the
inner fence's language tag must be carried through as a type hint or the
typeless payload objects can't validate.

## Tiered JSON repair (live 2026-10-03, commit 8a9f675)

`lenientJson` runs three tiers, then hands off to a lazily-imported library:

| tier | what it fixes | where it runs |
|---|---|---|
| comments / trailing commas / bare keys | sloppy JSON | sync |
| 2 `balanceBrackets` | surplus trailing closer | sync |
| 1 `extractOutermostJson` | prose wrapped around the payload | **async only** |
| 3 `jsonrepair@3.12.0` | missing commas, single quotes | **async only**, own 6.4 kB chunk |

**Three constraints that are not obvious and cost real debugging time:**

- **A repair tier on the SYNC path pre-empts the NDJSON fallback.** `parseCanvasSpec` only tries `parseNdjson` when `lenientJson` THROWS. Any tier that returns a successful parse therefore wins — and an NDJSON body has no envelope, so "isolate the outermost value" keeps the FIRST object and silently drops the rest. Measured: it broke the NDJSON, bare-block and misnested-fence tests. **Any new repair tier must either throw on partial input or live on the async path.**
- **Never hand raw fence content to a repair library.** `jsonrepair("Here is the card:\n{…}\nHope that helps.")` returns `["Here is the card:", {…}, "Hope that helps."]` — an array of fragments that reads as a valid payload and destroys the card. Isolate the outermost value FIRST (that is the Polaris technique), and require the result to yield a real `blocks` array or treat it as unrecoverable.
- **`repairIsolated` must build a full `CanvasSpec` itself, not return the block list.** It initially returned `coerceToBlocks(...)` (a bare array) where every caller expected a spec with `.blocks`, so `.blocks[0]` was undefined and every rescued card was silently discarded — tier 3 was a no-op that still "passed" because nothing asserted `spec.blocks.length > 0`. If a helper changes its return SHAPE, dump it in a scratch script (`repairIsolated(body, repair)?.blocks.length`) before wiring callers; a return-shape mismatch is invisible to `tsc` when the type is inferred as `any`.
- **The fence scanner only reports fences whose body PARSES** ("first closer that wins"). So it reports none of the malformed payloads tier 3 exists to rescue — gating an async retry on `scanFences` makes the whole repair path unreachable. Count openers with a plain `/`{3,}astra-canvas/g` match instead, and assert the async path never returns FEWER cards than the sync one.
- **Under the rider: a LAZY cross-fence regex renders FEWER than sync — walk fence by fence instead.** Wiring the rebuild as one regex (`/(`{3,})astra-canvas[^\n]*\n([\s\S]*?).../`) spanned a fence boundary when a body closed late: corpus message i=33 rendered 6 cards sync, only 5 async. Final shape: opener count for the gate, then walk opener → candidate closers in OCCURRENCE order, cutting the body at the FIRST closer whose body parses; only when NO closer parses does the tail go to `repairIsolated`. Re-run the 120-fence replay after every wiring change; `async >= sync` with no new leak rows is the pass bar (final: 110/110, leaks only the genuinely-broken i=65).
- **Trigger the async retry by counting openers vs rendered cards — never `hasCanvas`.** `hasCanvas` is the lazy-chunk mount gate and false for exactly the rescueable cards, but ALSO false for prose that merely MENTIONS the fence, so as a retry trigger it loads the repair library for chats that never need it. In `chat-timeline.tsx`: sync paint first (tiers 1-2), then after the text settles only when `text.match(/`{3,}astra-canvas/g).length > sync canvas parts` does `splitCanvasBlocksAsync` run — and `setParts` fires only when the rescue renders MORE canvas parts than sync. That keeps the 6.4 kB chunk out of every clean chat.

**Polaris comparison (read before porting more of it):** `frontend/src/lib/integrations/claude/validation.ts` (415 lines) is a good EXTRACTOR — fence stripping, preamble removal, string-aware brace counting — and that half is worth reusing. It is not a repair library: it parses or throws. It would not have fixed either card that actually broke. Its `validateBlueprintStructure` / `normalizeBlueprintStructure` (inferring a missing `displayType` from content shape) is the other portable idea if a display hint is ever needed. **Polaris has NO graphify graph** — the owner asked to "use graphify to understand smartslate", but `~/Work/projects/Smartslate/smartslate-polaris-v4/` carries no `graphify-out/`; grep the frontend directly (`grep -rln "JSON.parse|extractJson|repairJson" frontend/src`) instead of trying to query a graph that does not exist.

**Assert the repair boundary, not just success.** Pinned tests must cover BOTH directions: a missing comma / single quotes render after tier 3, AND a payload missing an actual `{` still degrades. A repair that fabricates a block is worse than raw JSON shown honestly — it displays invented data as fact.

- **Quote bare keys string-aware.** A regex also rewrites text INSIDE string
  values (`"see { a: 1 }"`), silently corrupting displayed data. Track
  string/escape state.
- **One alias table, shared** by `validateBlock` and the coercer, so "is this a
  block type" cannot drift from "what does it normalize to".
- **Apply every new tolerance to `hasCanvas` too.** It is the lazy chunk's mount
  gate; parser and gate disagreeing means the card never loads. Assert
  `hasCanvas(t) === splitCanvasBlocks(t).some(canvas)` over the corpus.
- **A payload with no `type` anywhere still degrades — that is correct.** With
  nothing to validate a block from, fabricating one is worse than showing code.
- **Write the test from the DB payload, not an idealized version.** The first
  draft of the misnested test used quoted keys and passed green while the live
  case still failed. When a new assertion passes, confirm it fails against the
  pre-fix code.
- Prose that merely *mentions* the fence (`` ```astra-canvas fence `` mid
  sentence) must stay a code block. Expect ~10% of occurrences to be this; they
  are correct non-cards, not misses.

## Fence discovery — never regex-close on backticks, probe candidates instead

A `code` block whose content contains ``` (a markdown example, a template
literal, a regex — the canonical demo for this feature is literally a fence
regex) truncated its own fence. The body handed to the parser was cut mid-JSON,
so the entire card degraded to raw text.

`scanFences(text)` replaces the regex. Candidate closers are every run of >= 3
backticks after the body; **the winner is the first whose BODY PARSES**
(`parseCanvasSpec(body)` non-null). One rule covers every observed case:

| case | why it works |
|---|---|
| canonical `\n```\n` | closes immediately |
| trailing prose after the closer (`\n``` outro`) | that run still parses the body |
| a ```` ```` ```` run INSIDE the JSON | body cut there does not parse, so the scan continues |
| two canvases in one message | each closes at its own run |
| mismatched opener (history has a SEVEN-backtick opener closed by three) | the closer is NOT gated on the opener's length |

`hasCanvas` and `planTurnCanvases` must call the same scanner, or the lazy mount
gate and the renderer disagree about whether a fence is closed.

Three wrong rules, each caught by the corpus replay guard — do not re-derive them:

- **Strict line anchoring looks correct and is not.** Requiring the closer to sit
  alone on its line (`^[ \t]*`{3,}[ \t]*(?=\r?$)`) breaks every mid-line closer the
  pre-existing tests depend on. Five real cards stopped rendering.
- **"Prefer a line-alone closer over any run" is worse.** It scans PAST an earlier
  legitimate closer to a later lone one, so the cut runs past the fence and swallows
  the NEXT canvas. The corpus guard flagged two-canvas messages for exactly this.
- **A `^` anchor on the streaming tail regex leaks raw JSON.** `OPEN_FENCE_RE`
  anchored with `^` only matches when the open fence starts the string, but it is
  normally mid-message (`done. ```astra-canvas`). It must stay unanchored, or
  unterminated JSON streams to the user while the turn is still open.

When a closer-count or boundary assertion fails, suspect the RULE before the
implementation: read the failing input byte-for-byte (`JSON.stringify(text.slice(i,
i + 200))`) rather than reasoning about the regex. Every one of these three was a
different bug that presented as "the scanner is broken".

## Chart visual language — AXES + LEGEND ON EVERY CHART (standing owner law)

Owner directive: every chart carries real x AND y axes with tick values, plus a
legend naming every series. This SUPERSEDES the earlier "no grid, no axes, the
data carries it" law — if you find a note anywhere claiming axes should be
`hide`d, it is stale. Draw them as hairlines in the theme's muted ink so they
read as chrome, not as data: no gridlines, no per-series hue.

- Legend ALWAYS renders (even for one series) so a single series is still named;
  left-aligned, **below** the plot.
- **The legend cannot live inside the chart.** recharts 2.15.4 hardcodes
  `position:absolute` into its legend wrapper's `outerStyle`
  (`Legend.js:171`), so `verticalAlign="bottom"` positions it relative to the
  plot box — with a small chart `margin` it lands ON the x-axis tick labels, and
  on some viewports reads as if it were at the TOP. Render it as ordinary
  sibling DOM AFTER `</ResponsiveContainer>` instead, reusing
  `.ast-cv-chart-legend-block` / `.ast-cv-legend-item` / `.ast-cv-dot`. Exclude
  the kinds that already carry their own legend block (donut, treemap, funnel,
  sankey) or the legend appears twice. Verify by comparing
  `getBoundingClientRect().top` of legend vs plot, not by eye.
- Axis titles come from the DATA. Hardcoding `request (index)` / `p95 (ms)`
  on every scatter mislabels every other scatter.
- Compact values in the tooltip (`1.2k`, `3.4M`, `1.28B`) — long raw numbers wrap
  the tooltip and shift every other row.
- Round line caps, `barCategoryGap` around 22%, radial/pie get a taller frame.
- `isAnimationActive={false}` on every series: a chart that grows while streaming
  reads as broken, and the lazy chunk may mount mid-stream.
- Colours stay theme tokens (`var(--color-cyanx)` / `rgb(var(--c-N) / a)`) and the
  brand is gradientless — depth comes from the surface and a hairline outline.

**`grep -c CartesianGrid` on the BUILT chart chunk always returns ≥ 1.** That is
recharts' internal component registry, not a rendered grid. Grep the hit in
context (`grep -o '.\{40\}CartesianGrid.\{40\}'`) before concluding a grid is on
screen; the real assertion is that your own source imports none.

## A passing shape validator proves nothing about whether the card RENDERS

Before emitting any canvas, run the spec through the REAL entry points, not a
standalone validator:

```bash
cat > gtest.ts <<'EOF'
import { readFileSync } from "node:fs";
import { splitCanvasBlocks, hasCanvas } from "./src/lib/canvas-schema";
const raw = readFileSync(process.argv[2], "utf8");
console.log("hasCanvas:", hasCanvas(raw));
for (const p of splitCanvasBlocks(raw))
  if (p.kind === "canvas") console.log((p.spec as any).blocks?.map((b: any) => b.type));
EOF
npx tsx gtest.ts <scratch>/my-spec.json
```

Two traps this replaces:

- **The driver must live INSIDE the repo** — a scratch path cannot resolve `./src/...`, and the module
  error reads like a broken spec rather than a bad import.
- **`splitCanvasBlocks` returns parsed OBJECTS, not strings.** `JSON.parse` on its output yields
  `"[object Object]" is not valid JSON`, which looks exactly like a corrupt payload and sends you hunting
  the parser for a fence bug. Branch on `p.kind === "canvas"` and read `p.spec` directly.

**A validator only checks SHAPE. A card can pass it and still be broken**, because the renderer is a
separate contract the validator never touches. Observed: a 31-node `graph` passed the shape validator,
parsed cleanly and laid out correctly — and rendered blank, because the graph panel read `ele.data("detail")`
while the cytoscape adapter only ever wrote `description`, so 0 of 31 nodes carried any text. The failure
looked like a rendering fault, not missing data.

**Prove the data reaches the RENDERER, not just the parser.** For any lazily-loaded block, call the adapter
the renderer actually consumes and assert the field survived:

```bash
# graph: toElements() is the adapter; assert the panel's field is populated
els.nodes.filter(n => n.data.detail != null).length   // was 0/31 — the whole bug
```

The general rule: **when a card renders but looks empty, diff the field names across the pipeline** —
schema → parser → adapter → component read. A rename on one side is invisible to every shape check and
fails silently. Pin the agreement structurally: assert every key the component reads via `.data("…")` is a
key the adapter writes, so a future rename cannot split them again.

## Delegating canvas fixes in this repo

The owner prefers Astra work done directly, but a multi-defect batch delegates well when each defect ships
with: exact root cause + file:line, the measurement to re-take, and an instruction to prove its guard goes
RED on pre-fix code.

**Steer a running delegate when a mid-flight state looks like a regression.** `npm run check` will show
`FAIL: <new>.check.ts is not in the regression manifest` while the delegate is still writing — that is
bookkeeping in flight, not a broken build. Message it to add the rows, re-run to green, and report real
measured numbers; do not "fix" the manifest underneath it.

**Report what a delegate got WRONG.** One ran `git checkout --` on a shared tree to compare pre-fix
behaviour and wiped its own fix mid-run (restored from a backup, but on a repo with three live sessions
that was luck). `git checkout <path>` discards uncommitted work — to compare against pre-fix code use the
materialize-old-file dance in `references/concurrent-sessions.md` (`cp` to scratch, `git show HEAD~1:<f> > <f>`,
re-run, restore, `diff -q`). Never let a delegate run destructive git on a shared tree, and verify its
claim that a file was "another session's" by mtime before accepting it.

The repo gate fails with `not in the regression manifest — add a row or it is
unpinned` for any discovered check file the manifest does not name. Adding a
guard file is therefore a TWO-part change: write the check, then add its row
(unique `RG-NNN` id, `found`, `symptom`, `guard`) to `REGRESSIONS` in
`scripts/regression-gate.check.mjs`. The gate also re-runs every pinned guard, so
an unpinned check is both a failure and an escape hatch.

**Take the next free `RG-NNN`, and expect ids to be claimed under you.** Two sessions added rows
concurrently and the second silently reused an in-flight number — re-read the manifest immediately before
patching, then verify no duplicates landed:

```bash
grep -o 'id: "RG-[0-9]*"' scripts/regression-gate.check.mjs | sort | uniq -d   # must be empty
```

**A manifest row whose `guard:` file is still untracked will break a fresh checkout** — the gate fails on
`git show`/`HEAD` for a path that was never committed. So when the staged manifest diff contains rows you
did not write, do NOT commit the manifest: those rows belong to the session that wrote them. Commit your
source + check only, and report the manifest as a shared file needing reconciliation:

```bash
git restore --staged scripts/regression-gate.check.mjs
git add src/lib/<yours>.ts src/lib/<yours>.check.ts
```

When cards are "not showing", the instinct is to read the parser for bugs. That
is the wrong layer: **replay what the model actually emitted first.** Extract the
real occurrences out of `~/.hermes/state.db`, run them through the live entry
points, then bucket the misses by SHAPE.

```bash
sqlite3 ~/.hermes/state.db "select id, content from messages
  where role='assistant' and content like '%astra-canvas%'"   # dump to JSON in scratch
# then, per message: count fence openers vs. canvases the renderer returns
```

Two facts this buys you, and both change the plan:

1. **Rendered-vs-total says whether the parser is at fault at all.** A high render
   rate means a different bug entirely (bundle, mount gate, directive not loaded);
   a low one means emission shape.
2. **Timestamp the misses against when the directive went live.** Most were written
   AFTER it, which rules out "the agent was never told" and closes that branch.

Bucket by top-level JSON shape before diagnosing — a bare `parseCanvasSpec(m[1])`
check conflates two different defects: a fence whose body is genuinely bad, and a
misnested fence whose body is empty because the payload was never inside it.
Measure through the **real entry points** (`splitCanvasBlocks` /
`planTurnCanvases`), never a raw regex capture, or you under-report exactly the
cases the heal fixes.

Generalisable shape worth keeping: **when output from another system is
malformed, corpus-replay it and cluster the shapes before reading the code.** It
is the cheapest way to turn "renders sometimes" into a numbered list.

## Verify a new guard can actually go red

A guard added alongside a fix proves nothing until it is shown failing on the
pre-fix code. `git stash push -- <path>` does NOT do this on already-committed
work (see `references/concurrent-sessions.md`) — it stashes nothing, and the
re-run then measures unchanged code.

```bash
cp src/lib/canvas-schema.ts <scratch>/fixed.bak
git show HEAD~1:src/lib/canvas-schema.ts > src/lib/canvas-schema.ts   # pre-fix
npx tsx src/lib/canvas-schema.check.ts                               # MUST fail
git checkout HEAD -- src/lib/canvas-schema.ts
diff -q src/lib/canvas-schema.ts <scratch>/fixed.bak && npx tsx src/lib/canvas-schema.check.ts
```

Report both counts (red before, green after) rather than only the passing run. A
check reading external state (a transcript corpus, a live endpoint) must `skip`
when that state is absent rather than fail, so a clean clone stays green.

## Canvas visual language — no coloured edge rails (standing owner law)

The owner has asked for this removal more than once, and for the sidebar as well
as the canvas: **coloured lines down the left edge of a container read as stray
stripes, not as accents.** No canvas block may carry one.

- Every block wears the same rounded 1px outline. Tone is carried by a small
  leading dot plus the title colour, never by an edge stripe.
- The dot is not decoration: when the rail was the ONLY tone signal, removing it
  without a replacement flattened info/warn/danger into identical grey boxes.
  Check what the affordance was actually encoding before deleting it.
- Grey connector rules that belong to a specific diagram (the timeline rail
  between chronology dots) are exempt — they are structure, not an edge accent.

When removing one, grep the CSS for every selector that carries it, not just the
one you spotted:

```bash
grep -an "border-left" src/index.css | grep -i "ast-cv"
```

Then **delete the overrides that the removal orphans.** A `[data-theme="light"]`
rule setting the border colour on a border that no longer exists is dead code
that reads as intent and will reassert the rail the moment someone re-adds the
property. Grep after the edit to confirm zero hits.

**Verify in the SERVED stylesheet, not `src/`** — the CSS only reaches the site
when `npm run build` succeeds, and another session's failing build silently
leaves the old rule live:

```bash
CSS=$(curl -s http://127.0.0.1:3011/ | grep -o 'assets/index-[^"]*\.css' | head -1)
curl -s http://127.0.0.1:3011/$CSS | grep -o '\.ast-cv-callout{[^}]*}'
```

Tell the owner to hard-reload; browsers cache the old CSS and the hash only
changes on rebuild.

## Parser contract worth preserving

- **Parse at TURN level, never per segment — this is the rule that keeps getting broken.** The segment engine opens a NEW text segment whenever the previous one is not a running text segment: a `tool.start` barrier, a message boundary, or a `text-final` that does not extend the live text each split ONE assistant message into several. A fence crossing that boundary is unparseable in BOTH halves, so it degrades to a code block and the owner reports "canvas missing from mid responses". `planTurnCanvases(segTexts, streaming)` in `canvas-schema.ts` stitches the turn's text segments and parses the whole. Because the planner lives in `TurnTimeline`, live streaming AND history reload are fixed by the same change.
- **Then classify every fence — CONTAINED stays inline, only SPANNING is extracted.** Getting this wrong the other way is its own bug: extract EVERY canvas and re-render it after the segment, and a card with prose after it jumps to the bottom of the message ("the card came at the very end, not below the text").
  - CONTAINED (opens and closes inside one segment — the common case): leave it in the markdown. `RichText` already splits and renders it inline, so following prose stays below it.
  - SPANNING (opens in one segment, closes in another): unparseable from either half, so cut it out and anchor it to the segment where it CLOSES. `TurnTimeline` passes each text segment its fence-stripped markdown plus its anchored canvases; `TextRow` renders the stripped markdown so canvas JSON is never swept in character by character.
- Collect fence removals per segment and apply them RIGHT-TO-LEFT. Splicing left-to-right shifts the offsets of later cuts in the same segment and silently corrupts them.
- **A DONE segment always renders its full text — never gate completion on an animation finishing.** `seg.status === "done" && n >= text.length ? text : shown` looks harmless and is a live corruption bug: the reveal sweep is timer-driven, so a backgrounded WebView (Android), a Stop, or a dropped socket kills it mid-run, `n` never reaches the end, and the message stays permanently TRUNCATED. Truncated markdown never closes its `**`, so marked emits literal asterisks and the owner reports "text after the card isn't formatted". Sweeping is a live-only nicety; correctness wins. If you see literal `**` or an unterminated list in a FINISHED message, suspect truncation before suspecting the parser — confirm by running the markdown pipeline on the complete text and counting `<strong>`/`<li>`.
- **Fail-soft must be PER BLOCK, not per canvas.** Validating the whole spec and bailing on the first bad block means one unexpected block shape turns a whole card into a wall of raw JSON — the owner sees "markdown text instead of generative UI" and no error. Keep every block that validates; degrade to markdown only when NONE do. Verify this stays backward compatible: a suite whose failing cases each use a single invalid block still expects `null` and still passes.
- **Repair sloppy JSON before parsing.** Models emit trailing commas and `//` or `/* */` comments; strip them and retry before giving up.
- **Accept near-miss block-type names as aliases** rather than dropping them: `metric`/`stat`→kpi, `graph`/`plot`→chart, `flowchart`/`flow`/`map`→diagram, `list`/`todo`→checklist, `ordered-list`/`process`→steps, `note`/`warning`/`insight`→callout, `meter`/`bar`/`gauge`→progress, `sources`/`citations`/`links`→references, `snippet`→code; `donut`/`doughnut`→pie, `columns`→bar, `gauge`→radial; a flowchart with no `layout` defaults to `flow`.
- A degrade that the user cannot see costs a full debugging round every time — log it (`console.warn` guarded by `import.meta.env?.DEV`) with the first ~160 chars of the fence, so the next failure is self-diagnosing.
- While streaming, a trailing unterminated canvas fence is HIDDEN (raw JSON mid-stream is noise); once finalized, an unterminated fence is PRESERVED as markdown. Reversing either half loses content on reload.
- Diagram edges referencing an unknown node id invalidate the whole diagram — a dangling arrow is worse than no arrow. Same for a tree node whose `children` names a missing id.

## Diagramming without a graph library

Layer nodes by repeated relaxation over the edge list (a back edge just lands one
layer late), render nodes as CSS-grid cards, and draw edges as an SVG overlay
measured from live `getBoundingClientRect()` under a `ResizeObserver`. No
react-flow, no d3. Connect the nearest facing edges and give the control points a
minimum offset so short hops still curve.

## Wiring the agent to emit canvases

The UI cannot make the agent use the canvas; the system prompt does. Directive
lives in `docs/canvas-directive.md` and is mirrored into `~/.hermes/SOUL.md`
(take a timestamped backup first — SOUL.md is agent-critical and there is no
undo). Because SOUL.md is read at session start, verify a new directive on a
FRESH session; the current one keeps its already-loaded copy.

State the non-web-surface caveat IN the directive: a CLI or Telegram surface
renders the fence as literal text, so the agent must answer in prose there
instead of emitting a raw JSON block at someone reading it in a terminal.

## Gates

`gate-card.tsx` keeps its JSON-RPC answer contract untouched — only the BODY
rendering moved. Review → severity KPI row + findings table; report → verdict
callout + stats + phase steps + radial gauges; fix → checklist; plan → prose
(already markdown) with edit mode intact. Any change here must keep
`onRespond(reqId, reply)` payloads byte-identical or the gateway contract breaks.

## What the owner expects from it (product behaviour, not just rendering)

- A canvas card stays in the chat. **Only gates notify the phone.** Never promise a push notification for a canvas — conflating the two misleads him about what he will actually get.
- The renderer being live does not mean a card appears: the agent must CHOOSE to emit one, and the SOUL.md directive is what makes that consistent — no code change can force it. So when he says "it doesn't look wired", check whether a card was ever emitted before assuming the renderer is at fault.
- `~/.hermes/SOUL.md` carries two sections: the generative-UI mandate, and a progress-report mandate (a progress report is a card — KPI row + steps/timeline + progress bars + checklist + a callout naming what needs attention; state failures and deferrals in the SAME card as successes, never an all-green card while something is broken). A new-chat opening follows the same shape: the handoff is
ONE compact card (open threads + the decision to make), never recon churn
attached to a greeting and never a prose survey.
- **Resume after a mid-turn interrupt (operator abort, model/provider switch or
  history truncation mid-load) is a RESUME, not a restart.** Continue from the last
  completed tool result already in history — never re-run finished recon, re-ask, or
  re-load a skill whose content is already in context. If the active model/provider
  changed under you, answer for the CURRENT one.
- He verifies the visual result himself and asks to SEE a sample card as the test. Emit a real one rather than describing it, and say plainly when you could not see a render yourself — never open a report with "verified" for a change whose whole claim is appearance.
- Standing owner steer for Astra work: do it directly rather than through the delegated agentive pipeline.
- The Android app is a Capacitor WebView loading the live site, so Android CHAT renders canvases with zero extra work. The native gate popup (`GateActivity.kt`) is a separate Kotlin surface and does NOT get canvas rendering — do not promise it does.

## Layout hardening (owner steer 2026-10-03: no awkwardly cut-off or hanging words/numbers, world-class desktop AND mobile)

The KPI-row rule that cost a debugging round: a `nowrap` label inside a grid whose flex/grid chain does not carry `min-width: 0` at EVERY level (motion `ast-cv-item` div → tile) forces the grid column to its intrinsic width (489px) and the WHOLE DOCUMENT scrolls sideways at 390px. Ellipsis cannot engage without the shrinkable chain. Also: KPI rows are 4-up desktop / 2-up ≤480px / 1-up ≤400px (selector is `.ast-cv-group.rows` — `rows`, NOT `kpis`).

**Never clip a value surface with `nowrap` + `overflow:hidden` + `text-overflow:ellipsis`.** Ellipsis is
INERT on an inline-flex box (the KPI delta chip), so that trio can only ever cut a word in half with no
indicator — the owner saw `+38m` where the value was `+38ms` and read it as a rendering fault. The correct
combination is `overflow-wrap: break-word` + `word-break: normal` + `hyphens: none`, which breaks an
unbreakable token ONLY when it cannot fit alone on a line.

**One stylesheet must not declare the same value surface twice.** A stale `nowrap` copy of
`.ast-cv-kpi-delta` sat alongside a newer wrapping one and the loser was decided by cascade order nobody
intended — while the source "looked correct" on both. After any edit, assert the WINNER rather than the
author's intent:

```bash
python3 - <<'EOF'
import re
src = re.sub(r'/\*.*?\*/', '', open('src/index.css').read(), flags=re.S)
for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', src):
    if 'ast-cv-kpi-delta' in sel and 'white-space:nowrap' in body.replace(' ', ''):
        print('CLIPPING RULE STILL PRESENT:', sel.strip()[:60])
EOF
```

Run it against the SERVED stylesheet (`curl` the hashed `assets/index-*.css` from `127.0.0.1:3011`) —
`src/` is not what ships, and another session's failing build silently leaves the old rule live.

**Measure overflow numerically, not visually.** A clipped value reports `clientWidth` < `scrollWidth`; the
number is the evidence. Sweep every canvas leaf text node at 360 / 768 / 1280 and assert zero elements with
`scrollWidth > clientWidth + 1` on a non-scroller — that single sweep is what proves "no broken words on any
device" instead of asserting it.

Playwright layout-QA harness (deterministic, no auth/WS): `scratch/canvas-v3/` — `harness-entry.tsx` mounts the REAL `Blocks` renderers
 with the REAL `src/index.css` through a scratch vite config; `layout-qa.mjs` builds + serves it statically (port 4180) and asserts, at 1280×900 and 390×844 in dark+light: zero document hscroll, zero elements clipped past the viewport (intentional horizontal scrollers — diff body, heatmap, tablist, table wrap — excluded), tabs switch panels, sparkline/donut/heatmap render, zero console/page errors. Run: `npx vite build --config scratch/canvas-v3/vite.config.mjs && node -e "/* wire dist/index.html asset hashes */" && node scratch/canvas-v3/layout-qa.mjs`. HARNESS GOTCHA: vite emits JS+CSS but not index.html (multi-config root), so copy `scratch/canvas-v3/index.html` into dist and rewrite the script/link tags to the hashed asset names after each rebuild. Also: driving the LIVE site needs WS auth — the harness route exists precisely to avoid that.

## Verified render/test rules (durable)

- Verify the canvas render path with the parser suite (`npx tsx src/lib/canvas-schema.check.ts` → 66/66 pass post-v3, including the split-across-segments regressions, per-block tolerance, alias and lenient-JSON cases, the five real emission shapes above, the backtick-in-code fence regressions, and the v3 type tests), then run the corpus guard (`npx tsx src/lib/canvas-replay.check.ts`) — it SKIPs when no corpus is present. Then confirm `npm run build` produces a chunk named `canvas-chart-*.js` containing recharts hits (count `grep -o 'recharts\|PolarAngleAxis'` per chunk); zero hits in `index-*.js` confirms the lazy boundary holds. A passing test + clean build is proof — a screenshot is not.
- When a NEW assertion fails, check the assertion before the code: a whitespace expectation once failed against a correct planner ("a " + " b" is "a  b", no leading space).
- `CartesianGrid` must be absent from the SOURCE — delete the import and the line, not mute its opacity. Note the built chunk still contains the string `CartesianGrid` (recharts' internal registry), so grep the match in context rather than counting it as a rendered grid.
- Never show a skeleton/building phase for the lazy chart chunk (`ast-cv-chart-skeleton`). Replace the `Suspense` fallback with a clean empty container (`style={{ height: 190 }}`) — the user sees nothing instead of a loading artifact.
- Chart ticks, tooltip labels, diagram edges, and all canvas components must reference theme variables (`var(--color-muted)`, `var(--c-89)`) so both `:root` and `[data-theme="light"]` colors apply; never hardcode a hex or a frozen `rgb()` value that ignores the active theme.