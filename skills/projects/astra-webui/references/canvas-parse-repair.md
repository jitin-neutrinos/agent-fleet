# Canvas fence repair ladder + "unreadable payload" diagnosis (astra-webui)

Scope: the JSON repair tiers in `src/lib/canvas-schema.ts` (`lenientJson` + the async twin) and the
workflow for an owner report of a canvas card dying with "could not be read — unreadable payload".
Emitter-side shape errors (wrong envelope, novel block types) are the sibling reference
`canvas-payload-shape.md` — start there unless the payload is a valid envelope that still fails.

## Diagnosis first: recurring = stored data, not a live bug

"Keeps failing since yesterday / every time I open it" means old STORED payloads re-failing on
every chat reopen — the served bundle is fine and a rebuild changes nothing. The full wire
history is on disk; use it instead of guessing:

1. Rebuild each session's text from `data/stream-log.db` (`stream_events`: sid, seq, type,
   payload, ts_ms): concatenate `message.delta` payload `.text` in `seq` order.
   `message.complete` carries the final text AGAIN — dedupe before counting (rebuild under both
   keys and compare, or you double-count every fence).
2. Scan for fences: opener ```astra-canvas + next ``` as closer; record closed vs unclosed.
3. Replay every body through the REAL exported parser: `node --experimental-strip-types`
   importing `src/lib/canvas-schema.ts` from a probe OUTSIDE the repo (an ESM import resolves
   relative to the importing file, not cwd). Keep probes pure JS (.mjs): strip-types only
   processes `.ts` modules, so TS annotations pasted into a .mjs probe are syntax errors.
4. Classify each dead fence:
   - `valid-JSON-but-spec-rejected` → per-block validation/alias gap (fix: alias the model's
     variant field name; `body` wins).
   - `json-error @position` → syntax; read the context bytes around the position BEFORE writing
     any repair — the defect is never the one the error message names.
   - `truncated-never-closed` → turn died mid-stream; no card ever existed. It renders as an
     honest placeholder/markdown — do NOT "fix" this class.
5. After any fix, re-run ALL historical fences through BOTH `parseCanvasSpec` and
   `parseCanvasSpecAsync` — async must stay a strict superset and never answer differently.

## The ladder (order matters; each tier tries then falls through)

raw → comments/trailing-commas → quoteBareKeys → fixUnescapedNewlines → fixMissingCommas →
**1.65 fixKeyValueInArray** → **1.7 fixTruncatedString** → **1.75 healMisnestedClosers** (on
truncated text, then again on un-completed text) → balanceBrackets. Async adds
extractOutermostJson + jsonrepair.

- **1.65 pair-in-array**: the model writes a `"k":"v"` pair inside a string array
  (`["cell","cell","tone":"neutral"]`) — JSON.parse dies at the stray colon. Drop the stray
  pair cleanly so rows keep their real cells. jsonrepair instead splits it into junk elements
  (`"tone",":","neutral"`) — the sync tier is strictly better; async must agree.
- **1.75 misnested closers**: a closer doesn't match the innermost open container (model closes
  the blocks array while a row object is still open, then keeps writing). The implied closers
  CANCEL in any brace count, so depth-count EOF completion appends nothing. The healer keeps a
  real stack: a closer first closes everything above its match; stray closers dropped; EOF
  completes innermost-first.
- callout accepts `detail` as a body alias (`body` wins) — the model mixes vocabulary from
  steps/algorithm blocks and valid JSON otherwise dies in per-block validation.

## Pitfalls (each cost a debugging round)

- Tiers must CHAIN: each fix consumes the PREVIOUS fix's output. Feeding an older text forward
  silently discards an earlier repair — real bodies carry multiple defects at once.
- fixTruncatedString's phantom completion corrupts misnestable bodies (it closes brackets
  around a broken structure, making the healer's job impossible) — run the healer on the
  UN-completed text too and let whichever parse succeeds win.
- A repair tier must PEEK the value before touching its output: `{`/`[` after `"key":` inside an
  array is a legit object key seen through misnesting, not a pair-in-array defect. Emitting
  anything on that site (comma strip, stray quote) actively corrupts every misnested body that
  reaches the tier.
- Depth counts cannot see cancelling defects; keep a real stack when structure matters.
- Probe with REAL block types: parseCanvasSpec validates the spec, so toy shapes (`{"a":"b"}`)
  correctly return null and make a working tier look broken.
- A "sync must refuse" pinned test flips when a new tier starts repairing its shape: update the
  sync test AND the async-agreement test to the new contract, and keep one genuinely-unfixable
  shape (a bare unquoted value) pinned as degraded — the no-fabrication rule still holds.
- Build new check cases from the REAL failing bodies, not invented minimal shapes, and give
  every guard its REGRESSIONS row in `scripts/regression-gate.check.mjs`.

Guards live in `src/lib/canvas-schema.check.ts`.
