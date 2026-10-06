---
name: mutation-check-audit
purpose: reference file for the verification/audit discipline used in parity-gated Rust ports (Taal). Load before trusting any mutation-check result.
used_by: python-rust-porting, rust-verification-harnesses
---

# Mutation-check audit reference

Apply before calling any mutation result "done". A mutation check measures the SUITE's coverage, not the port's correctness; the two can diverge.

## Audit steps (do these in order, always)

1. **Read the mutation-check source file.** Confirm it applies the mutant to the real port file (not a copy/stub), then rebuilds the runner against the mutated port.
2. **Confirm the comparator compares FULL diffs, not truncated/sliced.** Any `head -N`, `sorted(...)[0:N]`, or index-based truncation before comparison is a silent failure — it lets mutants that add/move/remove items past the slice pass. The comparator's `compare_*.py` should use structural equality (`json.loads` + recursive dict comparison) on the full `answers_*.json`, not a substring or first-N check.
3. **Confirm the golden is not the same wrong reading as the port.** If the golden was written from the worker's draft (not the reference interpreter's real function), the mutation check has no teeth — every mutant that breaks the reference but matches the wrong reading passes. Verify by replaying a long-English-like corpus (>=200 chars with frequent-letter pairs) through the REAL Python function (e.g. `python3 -c 'import difflib; ...'` on the actual `SequenceMatcher` behavior). The divergence in block sizes (e.g. 41 vs 43, 68 vs 66) is the signal that the golden and port disagree on the reference semantics.
4. **Confirm the runner calls the port's REAL public function.** A runner that re-implements `ratio_str` locally (instead of calling `crates/taal-loop/src/py_difflib.rs::ratio_str`) hides every mutant inside that function from observation. The runner should import the port module and delegate; any private re-derivation must be flagged as a gap.
5. **Before blaming the suite, blame the PORT for inventing a guard.** When a survivor points at a
   guard you wrote that the reference appears not to have, the correct fix is usually to DELETE the
   guard from the port, not to add a fixture that kills it. Three measured instances of this class,
   each of which would have shipped a silent behaviour difference:
   - An upstream check that can never fire (`only` holds enum MEMBERS while the membership test
     compares against NAMES, so the restricted branch is unreachable for every input). The port had
     "repaired" it, which restricted settings the original accepts everywhere. Prove inertness by
     probing the real reference with an input that should trip the guard and confirming the code
     past it never runs; then reproduce the inertness and put the reason in the doc comment.
   - A helper's second element read as an environment NAME where the reference passes a VALUE, so
     every call site produced an empty result and the setting silently vanished.
   - `getenv(name, default)` modelled as "empty means default". The default applies only to an
     UNSET variable; set-but-empty returns "". Collapsing the two gives an explicitly blank field a
     value the user chose to clear.
   A port that "improves" on the reference is a port bug. Inert upstream code is a fact to record,
   not an oversight to repair.
6. **If no scenario disagrees across a guard, the row is not isolating it.** Design the isolating
   input by making the two branches produce different answers: seed a key the cleanup path does NOT
   touch, feed two valid values the default would collapse, use a value that is falsy AND survives
   the reference's coercion (the CPython string `"0"`, not the int `0`), or make a malformed
   container a STRING CONTAINING the key — Python's `key in "a string"` is a substring test, so
   that is the only shape exposing a dropped isinstance guard.
7. **Classify survivors, not dismiss them by argument.** For each survivor:
   - If the branch is reachable in the reference fixtures (real `tests/gateway/test_*.py` fixtures, not synthetic): add a scenario that reaches it to the golden, regenerate, and re-run. The survivor is a fixture gap (`"golden is missing this scenario"`).
   - If the branch is NOT reachable with any fixture shape (e.g. a no-sigma string never hits the fast path because no U+03A3 exists in that input): measure equivalence by replaying the mutant over the full golden or >=300,000 random seeded inputs; record `"0 differences"`; document the equivalence with the reason (e.g. "no U+03A3 in input space, slow path takes same `c != GREEK_CAPITAL_SIGMA` arm for every char"). Only then call it `EQUIVALENT`.
   - Never classify a survivor as equivalent without measurement.
8. **Record everything in the mutation-check log file.** Each line: `KILLED [N/M] <description> :: <fixture>` or `EQUIVALENT <name> :: <reason> :: measured: <method> (0 differences)`. The log file (`scratch/s9/mut_*.log`) must exist and contain both categories before any "done" claim.

## Tools / commands that must be used

- `python3 parity/gen_*_golden.py` — generates the golden using the REAL reference import (`sys.path.insert(0, 'hermes-ref')`).
- `python3 parity/mutation_check_*.py --check-anchors` — validates anchor uniqueness (each mutant is unique, no duplicate anchors).
- `python3 -u parity/mutation_check_*.py > scratch/s9/mut_*.log 2>&1` — runs the mutation check with full output.
- `grep -E 'KILLED|SURVIVED|EQUIVALENT|DOES NOT COMPILE' scratch/s9/mut_*.log` — reads results (never just the exit code).
- `python3 -c 'import difflib; ...'` (with the real `SequenceMatcher` from the pinned `difflib` module) — verifies divergence on long inputs.

## Pitfalls that produced false greens in this project

- A comparator slicing to the first 12 diff entries before comparing (row 66 audit fix).
- A golden encoding the same wrong reading as a broken worker draft (py_difflib, 7,395-pair golden with zero teeth until the 12,895-pair extended corpus exposed divergence).
- A mutation-check script that rewrites the golden in place (not a clean copy per mutation) — a failed mutation corrupts the base file for the next mutant, producing phantom survivors.
- Not verifying the workspace gate result by reading the non-zero test counts (the `0 passed; 0 failed` artifact from an empty binary).
- A mutant whose two forms are literally the same function (`source.and_then(as_object)` vs an
  explicit `Some(Object(o))` match). It survives, proves nothing, and must be REMOVED from the list —
  reporting it as a survivor trains you to ignore the list. Same for a mutant typed so it cannot
  compile: that is a broken mutant, reported separately and failing the gate loudly, never folded
  into the survivor count.
- Classify EQUIVALENT mutants AT SURVIVE TIME, inside the check loop — not in a post-hoc pass over
  the summary list. Session 11's run_topics checker first printed the summary, then tried to
  reclassify from the printed survivor list, and the gate kept failing on two proven equivalents
  until the classification moved into the moment a mutant survives (row-70a's checker inherited the
  same shape). Post-hoc summary classification also runs before `finally` cleanup of later mutants.
- A survivor caused by the golden passing a reference ARGUMENT in the wrong place — a nested config
  block passed inside the main mapping where the reference takes it as a separate parameter, or a
  whole section passed where it wants the inner map. Every row below it then exercises the empty
  path and the mutants below it all survive together, which reads like a broken port.
- **A mutant whose two forms LOOK different but are the same computation is broken, not equivalent.**
  Rewriting a dispatch arm as `"x" => {}` beside an unrelated arm still MATCHES `x` and still does
  what the original did, so it survives while testing nothing — and it reads as a genuine
  equivalent. The tell is that the two forms cannot be distinguished by ANY input, which you prove by
  measuring the reference on the branch's inputs and seeing the arms agree (an `aborted` outcome emits
  no records; the `failed` arm emits a WARNING plus a retryable error — clearly distinguishable, so a
  survivor there is a broken mutant, not an equivalent). Write the mutant to REMOVE or REROUTE the
  arm, never to blank it: `arm => {}` is a skip, and renaming the pattern so nothing matches it
  (`"x_disabled" => ...`) is the form that actually fails. Before accepting a survivor as equivalent,
  ask whether the two forms differ for ANY input; if not, the mutant cannot fail and must be fixed.
- **A stale runner binary makes a mutant look like it did nothing.** The checker restores each source
  file from a snapshot, so a rebuild that races the restore can leave the binary holding a DIFFERENT
  mutant than the comparator replays — the diff then matches the golden and the survivor is fake. When
  a mutant survives a branch you have just measured as distinguishable, `stat -c %y` the source and
  the runner binary; when the source is newer, `touch` the source, rebuild, and re-run that one mutant
  by hand before believing the gate's count.
- **One mutant can need to span TWO call sites when the replacement changes a value's TYPE.** Making a
  binding `Option<Value>` instead of `Option<&Value>` breaks its consumer's call site, so the
  single-site replacement fails to compile and is reported BROKEN — not evidence. Either keep the type
  identical and change only the VALUE the fallback produces, or extend the anchor to cover both the
  binding and its use. Count BROKEN mutants as non-evidence in the denominator either way.
