# Compose the astra-canvas report surface correctly (owner-visible surfaces)

The canvas renderer on astra.jitinnair.com parses JSON blocks only in this envelope:

```
```astra-canvas
{"v":1,"blocks":[ … ]}
```
```

Anything else — named sections (kpi/table/checklist objects as top-level keys), a bare {"callout":…}, prose around the JSON name — degrades to a fenced code block showing raw JSON. The fail-soft parser is BY DESIGN; the fix for "the card renders as json" is the envelope, never the renderer.

## Content rules

- `kpi` values are strings/numbers, NOT nested objects — `{"value":{"value":"175px","delta":"…"}}` is invalid and drops the block to a markdown fallback.
- Block types the renderer accepts: kpi, chart, table, diagram, checklist, steps, callout, progress, timeline, compare, tree, code, references (plus later reactive/media types — check `src/lib/canvas-schema.ts`, the closed set, BEFORE emitting a novel shape).
- A `code` block inside JSON needs a 4-backtick outer fence (the 3-backtick fence cannot survive the inner ```).
- On reports with several distinct messages use multiple cards, but keep one idea per card — do not fragment or merge.

## When the owner complains "it rendered as JSON"

1. Re-emit with the correct envelope (do NOT debug the renderer; the fail-soft path worked as designed).
2. Own the mistake in one line — a session that told the owner it was a renderer bug and tried to patch the pipeline was actually shipping malformed payloads.
3. Only if the renderer genuinely degrades a VALID `{"v":1,"blocks":[…]}` payload should you investigate `src/lib/canvas-schema.ts` / `chat-timeline.tsx` parsing — extend the existing check suite (`scripts/regression-gate.check.mjs` pins the canvas checks), never replace it.

## Related

- Card fails with "unreadable payload" instead of rendering as JSON: the parser-side repair
  ladder and the stream-log replay workflow live in `references/canvas-parse-repair.md`.

