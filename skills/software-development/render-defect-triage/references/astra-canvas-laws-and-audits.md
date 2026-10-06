# Astra canvas: standing laws, audits, replaying the owner's card

Scope: the Astra web UI canvas (`astra-canvas` fences, repo `~/Work/projects/astra-webui`). The triage order is in SKILL.md; this file holds what is specific to that surface.

## Standing laws (every card, every width, both themes)

- Nothing overlaps and everything fits inside its own container. Chrome (legends, diagram controls, tooltips) sits outside the drawing, in normal flow, below it.
- Every chart has axes, a title and a legend, the legend at the BOTTOM, and none renders blank.
- Text wraps only between words: no mid-word break, no ellipsis, no silent clip, no one-word last line. Only raw paths and hashes (`mono: true` values, `.gate-finding-file`) break like code.
- The accent is the active theme's token, never a colour name or hard-coded hue in UI code.
- Every surface is a rounded rectangle.
- Check the phone first (390, with 320 as the floor), then 768 and 1280.

## Pins to extend, never duplicate

- `src/lib/etiquette.check.ts`: source-level text and chart-structure rules.
- `text-wrap.check.ts`, `canvas-text-integrity.check.ts`, `canvas-chart-render.check.ts`, `rounding.check.ts` in `src/lib/`.
- A new `*.check.*` file fails `scripts/regression-gate.check.mjs` until it has an `RG-nnn` row (symptom + guard path): add the row in the same commit.

## Browser harnesses (untracked, in the repo's `scratch/canvas-v6/`)

They build the bundle from current source, then drive real Chromium with the real parser and the brand fonts. If you drive one by hand, clear `node_modules/.vite` and the harness dist first.

| Script | Proves |
|---|---|
| `etiquette-e2e.mjs` | at 320/390/768/1280: split words, widows, ellipsis, silent clip, spill, KPI chip squeeze, chart-text contrast, blank charts, legend below the plot. `SPEC=<name>` loads `scratch/canvas-v6/<name>.json`; `REPORT=1` lists failures instead of exiting 1; `WIDTHS=390,1280` narrows |
| `diagram-e2e.mjs` | diagram overlaps, labels inside boxes, controls below the stage, late-font re-measure, both themes |
| `media-e2e.mjs` | images and videos really decode; needs the real login: `set -a; . ~/.config/astra-webui/env; set +a` |
| `reactive-e2e.mjs` | sliders, selects, bound tables, `$expr` KPIs |
| `crash-repro.mjs` | a poisoned card is contained by the per-card error boundary |

## Replay the owner's exact card

1. Read the assistant message from `~/.hermes/state.db` read-only (`role='assistant' and content like '%<card title>%'`).
2. Parse it with the APP's parser: a `.mts` script run as `node --import ./scripts/ts-resolve.mjs x.mts` that calls `splitCanvasBlocks(text, false)`; write the `canvas` part's `spec` to `scratch/canvas-v6/<name>.json`. Python's `json.loads` rejects cards the app's lenient parser repairs (trailing commas, mis-nested arrays), so it proves nothing about what the app renders.
3. `SPEC=<name> node scratch/canvas-v6/etiquette-e2e.mjs`.

`planTurnCanvases` is the wrong entry point for this: it plans only fences that span message segments, so a card contained in one message comes back as zero canvases.

## Where the pieces live

- `src/lib/canvas-schema.ts` `validateBlock`: the whitelist and the normalisers. A new authoring shape needs a normaliser and a case in `canvas-schema.check.ts`.
- `src/components/canvas/canvas-chart.tsx`: recharts kinds, the shared `ChartLegend` row after the plot, the early branch for self-sizing kinds. `canvas-native-charts.tsx`: nivo sankey/treemap/funnel, and `useResolvedColor`, which hands nivo concrete theme colours.
- `src/index.css`: the blanket svg rule is scoped `.ast-cv-chart-native:not(.ast-cv-sankey) svg`.
