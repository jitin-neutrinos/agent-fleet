# Subagent report retrieval

A finished subagent's full report is **not** on disk where you would look, and the
obvious source gives you a fraction of it.

## The trap

- The live transcript `~/.hermes/cache/delegation/live/<deleg_id>/task-N.log` stores
  each assistant message **truncated**, with a literal `…(+N chars)` marker in place of
  the rest. A 9,000-character technical brief reads back as ~1,400 characters.
- No result file is written under `~/.hermes/cache/delegation/`. Do not search there.
- The delegation's `status: running` does **not** mean no report is available. See below.

## Read the real thing from `state.db`

`async_delegations.result_json` holds every completed child's summary, verbatim:

```bash
node --input-type=module -e "
import { DatabaseSync } from 'node:sqlite';
const db = new DatabaseSync('file:' + process.env.HOME + '/.hermes/state.db?mode=ro', { readOnly: true });
const row = db.prepare('SELECT result_json FROM async_delegations WHERE delegation_id=?')
             .get('deleg_XXXXXX');
for (const r of JSON.parse(row.result_json).results) {
  console.log(r.task_index, r.status, (r.summary||'').length, 'chars');
}"
```

Write each `summary` to a scratch file and read it with `read_file`. Useful columns:
`state`, `completed_at`, `delivery_state`, `delivered_at`, `task_json`.

- **`result_json` accumulates as children finish.** A delegation reported as `running`
  can already contain two of three reports. Poll the DB instead of waiting for the whole
  batch — and when asked "are they done?", answer per-child from this table rather than
  from the log, which shows tool calls but not results.
- **A long single-line JSON payload defeats line-oriented reads.** Open it with plain
  Python `open(path).read()` + `json.loads` and iterate by index; retrying the read tool
  at different offsets cannot recover the middle of a one-line file.

## A child's report is a self-report, and it corrects the parent

Re-verify every load-bearing number against the real files before repeating it to the
owner. Children doing empirical work are especially likely to contradict a parent that
estimated from memory: one reported a hardcoded-value count ~2.4x lower than the
parent's estimate, which is what prompted a hunt that turned up a real production bug
the parent had not suspected.

A child that reports being blocked, or that finishes without a working method, is not a
validated workflow — do not write its dead ends up as guidance.

## Correcting a child is routine; so is crediting it

Two of three children on a fan-out returned a load-bearing claim that a five-line probe
disproved. Neither was careless: both were **over-generalised from a partial probe whose
confounder went unreported** — a documented API rule stated as a rejection behaviour when
the real trigger was something else in the test string, and a "never emitted" claim that
was simply false in the built output.

- **Re-test with the cheapest probe that matches the claim's type.** An HTTP behaviour
  needs a status-code matrix across the valid AND invalid case (one success proves
  nothing). What a build emits is answered by grepping the built bundle, not the source.
  A library claim is answered by running it.
- **When a child's claim contradicts your own earlier reading, re-run the CHILD's probe
  first.** The likeliest explanation is a confounder in whichever reading came first — in
  the observed case the child's own negative test contained the extra axis that caused the
  400 it attributed to ordering.
- **A child that contradicts a number you already showed the owner is your cue to re-audit
  your own figure.** Do not defend a count you have not re-measured.
- **Report the corrections in the deliverable, attributed.** Naming which claims survived
  verification, which did not, and which child caught your error is what makes the rest of
  the report trustworthy. Quietly folding a correction in hides that your earlier number
  was an estimate.
- **Re-run the artefact the child left behind.** A throwaway parser or probe script is a
  claim you can execute rather than believe; running it over the repo's own files is the
  cheapest possible audit (one session parsed 12/12 real font files clean with a child's
  zero-dependency parser, which turned an unproven suggestion into a usable component).

## Diagnosing "it did not render" as a funnel, not a guess

When a UI artefact "does not load", walk the layers with one measurement each instead of
theorising — the delivered artifact, the parser, the sanitiser, the render boundary. For a
generated card that meant pulling the ACTUAL delivered text out of the session store rather
than re-drafting it, running the real parser over it, counting what each layer rejected,
and only then reasoning about the render. That converts "the payload is bad" versus "the
render threw" from a guess into a measurement, and the report can then say precisely which
layers were ruled out and which one is still open.

Watch for the two-functions trap: a per-segment splitter and a turn-level planner both
sound like "the canvas parser", and feeding the planner a single whole-message string can
legitimately return zero canvases with the fence still in the markdown. Test the function
the call site actually uses, and read the call site before blaming the parser.

Also read what a validator RETURNS before using it as a predicate — a function named like a
`validate*` may be a coercer returning a normalised value or null, in which case a naive
`!result` reads every healthy block as invalid.
