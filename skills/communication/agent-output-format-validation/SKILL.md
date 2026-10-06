---
name: agent-output-format-validation
description: Validate an agent payload that rendered as raw text.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [canvas, generative-ui, structured-output, validation, emit, fail-soft]
    related_skills: [python-rust-porting, astra-canvas]
---

# Agent output format: validate the payload, not the client

Class-level skill for any case where the agent EMITS a structured payload into a client
that renders it as a composed surface — a generative-UI card, a fenced JSON spec, a
gates/status report — and the user reports it arrived as raw text or lost a section.

## The core diagnostic rule

**When the client is fail-soft, a malformed payload looks exactly like a broken client.**
Most rich-payload clients degrade silently by design: on bad JSON, an unknown enum, one
invalid block, or a dangling cross-reference they emit the source text as a plain markdown
block and drop nothing. So the FIRST question is never "is the renderer broken?" — it is
"is my payload valid?", because that failure is invisible until the owner says so.

Work in this order, cheapest first, and stop as soon as one step explains the symptom:

1. **Run the client's own parser checks.** Green means the client is healthy — stop suspecting it.
2. **Validate the exact payload with the client's own validator.** Per-block validation, then
   the client's fence splitter on the exact bytes you shipped. Compare the card count to what
   you expected; one expected and zero found means it will degrade.
3. **Only if both are green does the bug live in the client** (component, chunk load, theme).

## Validate before emitting, not after the complaint

A large hand-built payload has one independent chance to invalidate the whole surface per
block. For an N-block report that is N chances to lose everything, and the feedback loop is a
round-trip to a human. So: build the payload as JSON, run it through the client's validator,
confirm the card count, then emit. The cost is one local command; the saving is a
re-emission cycle every time.

Prefer generating the payload with a script (build the structure in code, serialize, validate,
then paste the validated text) over hand-writing braces. Hand-written payloads fail silently;
generated ones fail loudly.

## Emission traps that invalidate a whole surface

- **Fence length is part of the contract.** Payload content containing the fence marker (e.g. a
  `code` block whose content has ``` ) truncates a 3-backtick fence. Emit the outer fence one
  level longer. Always check whether the payload contains the marker before choosing the fence.
- **Cross-references must resolve.** An edge/node/child naming an id not present in the same
  block is usually a hard rejection, not a warning.
- **Enums are closed sets.** An invented severity or direction string rejects the block; the
  client will not guess a value for you. Near-miss synonyms are often mapped by the client, but
  an entirely unknown word is not.
- **Numbers that should be numbers.** Numeric fields sent as strings fail type checks; counts
  and scores sent as numbers are fine even where display expects a string.
- **Required per-item keys.** Item lists whose entries each need a key (`title`, `text`) reject
  the whole block when one entry omits it.
- **Wrapper shape.** A payload that is a bare block, a list where an object is expected, NDJSON,
  or unquoted keys may be coerced — but a payload with no type marker anywhere is not.
- **Never emit the payload as a tool-call-shaped blob.** Emitting the structure through an
  intermediate tool/function call shape instead of the literal fence is a common cause of "it
  rendered as text": the client receives something that is not the agreed wire format. If the
  surface expects a literal fenced block, emit a literal fenced block.

## Shared near-miss tolerance (what clients usually DO accept)

Clients built for real model traffic coerce common sloppy shapes rather than dropping content:
alias/synonym type names, an alternate key for the same field, singular/plural collection
names, wrapper-shape variants. Do not hand-normalize these — but do not assume a fully novel
shape is covered either. The validator tells you which, in one command.

## Worked reference (Astra canvas)

The concrete instance this was learned from, with the exact commands and the trap list:

1. `npx tsx --test src/lib/canvas-schema.check.ts` — the client's parser checks. Green (48/48)
   means the renderer and parser are healthy.
2. Validate the spec with the repo's own `validateBlock()` per block plus `splitCanvasBlocks()`
   on the exact fence; expect exactly 1 canvas card. Script it and run it on the JSON file
   rather than trusting the fence by eye.
3. Only if both are green look at `CanvasView` / `Blocks` / the lazy chart chunk.

Astra-specific traps: a `code` block containing ``` inside a 3-backtick fence (use 4);
a `diagram` edge naming a node absent from `nodes`; unknown `trend`/`tone` enums; `progress`
`value` sent as a string; `steps`/`checklist` items missing `title`/`text`. Coerced (do not
hand-fix): bare block, `blocks` used as the item list, NDJSON, a misnested ```kpi fence,
unquoted keys.

Note the schema tests need `npx tsx --test`, not bare `node --test` (ESM `.ts` resolution) —
that is the runner, not the import spec.

## Verification discipline

- Report the client's health-check output (the real command and its real count) before
  concluding anything about the payload. "The parser tests pass, so this is my payload" is a
  finding; "the canvas is broken" without that evidence is a guess.
- Name the specific invalid element when validation fails — the client usually reports which
  block or field, and that maps to one edit, not a rewrite.
- When asked why it rendered as text, answer with the measured cause and the fix. Do not
  speculate about client internals you have not read.
- Never claim a rich surface renders correctly when you cannot see a render. Say you validated
  the payload and the parser checks pass; that is the honest boundary.
