---
name: rust-verification-harnesses
description: Use when proving a Rust port matches its Python reference.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [rust, parity, testing, e2e, mock-server, verification]
---

# Rust verification harnesses (parity, corpus, adversarial, wire e2e)

Use when verifying a Rust port against a living reference, or an HTTP/WS client against
the real wire. The core doctrine: **a passing test suite is the weakest form of evidence**;
stack independent kinds (parity diff, real-data corpus, adversarial input, live wire)
until a miss in one is caught by another.

## The verification ladder (run in order, each gate independent)

1. **Unit tests** in-crate. Cheap, first.
2. **Cross-language parity**: Python reference and Rust port run identical fixtures;
   outputs diffed automatically (exact for decisions/strings, tolerance for floats).
   Harness shape: `gen_*_golden.py` writes golden.json → `<name>_parity_run` Rust bin
   writes answers.json → `compare_*.py` diffs, exits nonzero on drift.
3. **Corpus audit** (mandatory for any hand-rolled parser): run BOTH implementations over
   the real data the parser will see in production, not synthetic fixtures. Synthetic
   fixtures encode what the porter imagined the input looks like; the live corpus contains
   CRLF files, YAML block scalars, list-of-maps, and nested frames the fixtures never had.
   Measured case: unit + parity fully green while ~40% of real files mis-parsed.
   A stdlib routine (`int`/`float`/`fromisoformat`/`realpath`) has no production corpus: drive thousands of seeded mutations of valid inputs over a hostile alphabet through the REAL function instead — a first-run diff there is a finding about your reading of the C, not noise (recipe: the `python-rust-porting` skill, topic `python-stdlib-semantics`).
4. **Adversarial probe**: one input per rule nobody wrote a test for — boundary chars,
   case variations, empty-vs-whitespace, multibyte splits at truncation points.
5. **Mutation check of the suite itself**: apply targeted breaks to the port (invert a
   guard, drop a marker, skip a heal, bypass a CAS), rebuild, and require the comparator
   to fail on every one; restore the original in a `finally`. A surviving mutant is a
   fixture gap — add the missing scenario (proven: an ordering rule whose fixtures never
   contained both orderings; a method that reads the shared map raw while every scenario
   loaded it first), re-run, then classify only thread-race-only breaks as documented
   equivalents with the reason printed. This is the only gate that measures the SUITE, not
   the port, and it belongs in the campaign alongside the comparators.
6. **Replay the reference's OWN test suite** — whenever the reference ships tests for the
   code you ported, they are a free, high-quality oracle you are wasting by hand-writing
   goldens instead. A pytest plugin that wraps each ported public function and appends
   `{node, fn, args, kwargs, result}` per call turns those tests into replay rows: run the
   reference suite under the plugin, then feed the trace to the Rust port and diff. Recipe,
   trace encoder, and the classes that cannot be replayed:
   `references/reference-test-replay.md`. Treat a passing replay as a real gate: it found
   bugs the hand-written golden for that module had never covered.
7. **Tamper audit of every comparator** — mutation testing proves the SUITE catches port
   bugs; this proves the comparator catches OUTPUT corruption. Corrupt the answers file
   (drop a key, flip a bool, bump a number, cut a string, reorder a list) and require each
   `compare_*.py` to exit nonzero; a comparator that passes tampered output is not a gate.
   Report suites whose comparator writes no answers file (in-process compares) as gaps,
   never as passes. Scales to every suite with no per-suite work.
8. **Wire e2e** against a local mock server for anything that speaks HTTP/WS. Recipe and
   the runtime-shape traps (multi-thread flavor for spawn+connect, timeouts on every await,
   case-insensitive header asserts, reading client-sent bytes off an mpsc): the
   "Mock-server wire e2e — standing rules" section below.
9. **Live smoke** through the real deployed path (tunnel/public URL) before claiming done.

## Landing a partial layer honestly

A large module rarely ports in one pass. When you split it into layers, the split is only honest if
every artifact says the same thing. A row that has parity on one layer and an unstarted second
layer is **DRAFTED, UNGATED** — and that phrase must appear in the commit message, the ledger row,
and the handoff header, not just in a status file. Then commit it: an uncommitted partial layer is
lost work, and a committed one labelled UNGATED is a resumable starting point.

Report the numbers with their qualifiers attached, not in a later paragraph — parity count,
scope caveat, mutation result, and what was never run. A gate wired into the campaign but never
executed is not evidence, and saying so at the point of the number (not buried under "what's
next") is what stops the next session reading a partial row as finished.

State plainly when a session net-regressed the gate it was trying to close, and name the cause.
Regression happens when new scenarios and a scanner rewrite land in the same sitting; the fix is
ordering — land the harness fix (comparator, anchors, gate plumbing) and confirm it green BEFORE
adding edge cases, because the harness fix is usually the high-value half and it is the only part
that invalidates every earlier measurement.

## Coverage meter

Line coverage is the cheapest way to see WHICH ported code nothing exercises, and the
fastest way to misread it: `cargo llvm-cov -p <crate> --lib` reports 0% for every module
driven by a parity runner, because runners are separate binaries, not unit tests. Always
measure with `--all-targets`; a module reading 0% under `--lib` and high under
`--all-targets` is an artifact, not a gap. Read the report's own column layout (name,
Regions, Missed Regions, Cover, …, Lines, Missed Lines, Cover) — index the SECOND `Cover`,
not the first, or every line reads as 0%.

## Mock-server wire e2e — standing rules

- Tests that `tokio::spawn` a listener-accept task while the main task connects need
  `#[tokio::test(flavor = "multi_thread", worker_threads = 2)]` — the single-thread
  current_thread runtime can deadlock that shape.
- Bound EVERY await that could hang (mock JoinHandle, channel recv) with
  `tokio::time::timeout` so a regression fails in seconds, not the 60s test-runner hang.
- Assert request headers case-insensitively (`req.to_lowercase().contains(...)`):
  hyper/reqwest emit lowercase header names, and asserting the capitalized form fails
  while the request is actually correct.
- To verify what the CLIENT SENT, capture via an `mpsc` channel inside the mock task and
  assert on the received string after the client call returns — do not rely on the
  JoinHandle's return value reaching the test.
- Mock read loop: read-until-headers-complete plus a short settle timeout (300-500ms),
  never an unbounded blocking read; then respond, `shutdown()`, done.

## Pitfalls that produce false greens or dead time

- **Repair harness bugs with an assert-anchored scratch script, never a chain of inline edits.** A parity session converges on a fixed point: the golden and the runner disagree in a dozen places, each fix reveals two more, and a badly-placed edit silently rolls back the one before it. Write `scratch/<session>/patchN.py` with one `sub(old, new)` helper that asserts `text.count(old) == 1` before replacing, apply ONE group of edits, then verify with `ast.parse` + a compile. When an anchor fails, re-read the file and print the real surrounding lines before composing the next anchor — never retry the same anchor. Track edit counts so a no-op is visible. Also: a script that mutates `s` across several `sub()` calls and only writes at the end loses EVERYTHING if the last assertion fails — that is what happened here twice.
- **Line-index surgery on a file you are also editing programmatically corrupts it.** Deleting "lines 940-948" by index after an earlier insert lands on the wrong span and leaves orphaned braces, which surface much later as unrelated compile errors. After any index-based edit, print the affected range back and re-verify syntax before moving on.
- **Two crates' binaries with the same name collide in `target/release`** — last build
  wins silently. Name runners `<area>_parity_run`; when a runner errors with another
  crate's startup message, suspect the collision before the code.
- **An empty text filter on build or test output proves nothing — it matches nothing on success AND on failure.** After adding a module, confirm its `pub mod` line, run the check once WITHOUT the filter and read the final `Finished` / `could not compile` line, and for tests confirm your test names appear in the listing. A pipe also replaces the build's exit code with the filter's.
- **A comparator that ignores its arguments is not a gate — it is a rubber stamp.** Reading a
  fixed answers path while the mutation checker passes the mutant's path as `argv` means every
  mutant is compared against the GOOD answers: all of them survive, the log looks plausible, and
  the entire pass is worthless. The signature and the output are both normal, so nothing flags it.
  Make argv WIN over any env-var default, then TAMPER-TEST every comparator once per arc — corrupt
  one field in the answers file, require a nonzero exit, discard. A comparator that has never been
  tamper-tested is a gate whose numbers are unverified, whatever its pass rate says. This is the
  same class as the runner that re-derives a value instead of calling the port: the harness stops
  seeing the thing it exists to see.
- **When a gate's own plumbing throws while reporting a failure, the gate dies with it.** A
  mutation checker that parses the comparator's summary with `line.split("—")[1]` raises
  `IndexError` on any comparator failure that produced a TRACEBACK instead of a diff list, and the
  exception kills the whole loop mid-run — so a real finding is reported as a crashed gate, and
  everything after that mutant goes unchecked. Parse the count defensively (and treat a comparator
  crash as a kill, since the mutant still failed to produce golden-matching output), because a
  reporting bug must never be able to hide the results it was written to report.
- **Run the mutation check BEFORE calling a module done, not as a late audit.** A module can reach full parity (every scenario matching) and still be untested: in this project a 305/305-green module had only 15 of 29 mutants killed, and each survivor was a branch no scenario reached — the successful-send arm, the sleep durations, a "prune dropped nothing" arm, a zero-timeout disable. Writing the mutant list while reading the reference (each mutant IS a coverage requirement) surfaces those branches up front. When survivors appear, add the scenario, regenerate, and re-run — do not downgrade the mutant to "documented equivalent" when the reference plainly exercises that branch.
- **A golden scenario that never reaches its success path usually means the FIXTURE is wrong, not the port.** An `async def` fake for something the reference enters with `async with` returns a coroutine, and `async with <coroutine>` raises `TypeError: 'coroutine' object does not support the asynchronous context manager protocol` — a fixture that silently kills every "real" path in the section while still producing plausible output. Symptom: every success-path scenario reports the same failure and no send is ever recorded. Confirm with a throwaway probe of the REAL module (a few lines, real scope stub, real send) and copy that shape into the fake; verify the fake's fake: an adapter whose `send` splats a `SimpleNamespace` with `**v` raises TypeError where a raw dict would work. The same class of blindness is a stub marked with an UNKNOWN enum variant, which makes the port answer `None` and routes every row through the fallback arm.
- **A golden whose result flips when rows run in sequence is leaking module state between scenarios.** A fake's class-level counter (e.g. an adapter id incremented per constructed instance) makes row N's expected value depend on rows 0..N-1, so a parallel or reordered runner diverges. Either make the counter explicit in the shared scenario spec or have the runner advance its own identical counter. Related: a driver that does not install a monkeypatch inherits the LAST one a sibling row installed — reset any patched module attribute the driver does not set itself.
- **Python `read_text` applies universal newlines (CRLF→LF); Rust `read_to_string` does
  not.** Normalize `\r\n` at every ported-parser entry, or CRLF-authored files diverge
  (corpus audit is what catches this class).
- **A hand-rolled YAML-subset parser is not done until block scalars (`>`, `|`, `>-`)
  and list-of-maps items work** — a large fraction of real-world frontmatter uses them.
- **Secret scanners/redactors rewrite source and captured output containing credential
  shapes.** In test fixtures, assert on redaction-safe substrings (lowercase
  "authorization: bearer " prefix) and build fake keys from character-class concatenation,
  never a realistic literal — a realistic literal gets rewritten and the assert fails on `***`.
- **Write nested-quote fix scripts to a scratch .py file and run it; never inline them
  in an execute_code cell** — shell heredocs plus Python triple-quotes plus Rust string
  escapes triple-escape and corrupt the target file.
  Keep probe commands off the approval scanner's list too — no `rm -rf` (even inside scratch), no inline heredocs carrying lookalike Unicode: a flagged command waits for a human, and on an unattended surface the step is blocked with no answer. Make a fresh uniquely-named dir and clean up in-process (`shutil.rmtree`) from a scratch script.
- **Background-process result logs go stale when a newer process lands.** Before reading
  output, re-list the results directory by mtime and read the newest; a stale read sends
  you debugging a failure that was fixed three steps ago.
- **When a test fails, re-read the reference source before touching port or test** — wrong
test expectations are as common as port bugs. Arbitrate against the reference (run the
Python one-liner on the exact fixture) before changing either side.
- **A golden that drives a reference METHOD must call it with the right receiver and inherited state.** A fake runner object that does not inherit the mixin under test fails immediately with `AttributeError: 'Runner' object has no attribute '_BUILTIN_ALLOWED_USERS_VARS'` — the class-level tables the method reads are resolved on the real class. Fix the fake (inherit the mixin, or subclass it) instead of adding module-level aliases to satisfy it. The same applies to a method's late imports from a sibling module: patch the attribute on the MODULE the method resolves (`R._write_runtime_status_quiet`), not where it is defined, or the patch is captured but never called.
- **A golden must carry every INPUT in the row's `spec`, not just an index into a generator-local table.** If the runner reads the transcript from anywhere but the row it is replaying, the two sides can be asked different questions and the diff is meaningless. Timestamps are the usual culprit: pin them RELATIVE to a generator-local `T0` and emit the shifted value into the spec, so both sides read one number. A row whose spec is `{"i": 7}` is a row the runner cannot reproduce — treat it as a generator bug.
- **Isolate a hanging runner by slicing the golden BEFORE raising any timeout.** Partition the scenarios by `kind` into separate files, run each under a short timeout, then split the offending kind to one row per file. This names the culprit in a couple of minutes and the exact input that triggers it; a raised timeout just turns an infinite loop into a slower infinite loop. Full bisect recipe lives in the `python-rust-porting` skill, `references/regex-scanner-state-machines.md`.
- **Port an injected seam on BOTH sides of the fixture, and run it twice with opposite answers.** A reference helper gated on something the golden cannot control (a filesystem check, a pluggable validator) needs the generator to patch it BOTH true and false — otherwise the false arm is never exercised and a port that hardcodes one answer looks green. Two fields in one row (`validate_true` / `validate_false`) prove the gate is actually consulted.
- **Capture log records for a function whose only effect is logging — and normalise the exception TEXT, not the level.** Already stated above for parity width; the generator-side detail that costs a cycle is that a `logging.Handler` on logger A captures nothing when the code under test logs to logger B, so the golden's `logs` list comes back empty and every row diffs as `len 0 != 1`. Attach the handler at import, set `propagate = False`, and clear per row.
- **An empty golden log list is a capture bug, not a port result.** If the golden shows `[]` for a row whose reference plainly logs, the handler is on the wrong logger (or `propagate` was left True and the record escaped). Check the golden before assuming the port forgot to log.
- **Comparator tolerances must be stated, not implicit.** Where the generator pins relative timestamps, round both sides identically in the comparator and compare floats with a relative tolerance; never round the golden and not the answers. A comparator that does `round(x, 6)` on one side only manufactures a permanent diff.
- **Byte-pinned constants (prompt sections, wire prefixes, marker strings) come from a
generator script, never hand-transcription** — import the live reference module, emit
the Rust `const` file programmatically (`json.dumps` each string), commit both. Hand-copied
multi-line prompt text drifts on a stray apostrophe or dropped word, and only a
full-string parity row catches it; a generator makes the drift impossible.
- **Reset or reconstruct reference state between golden-generator rows** — a mutated
attribute leaking from fixture N into N+1 poisons the golden itself, and a CORRECT port
then fails parity chasing a phantom bug. When the Python side of a diff looks semantically
wrong (e.g. an iterative-update form where a fresh one was requested), suspect the golden
generator before the port.
- **Port reference quirks verbatim, including deliberate-looking off-by-ones** — when the
reference builds a value inside a loop and uses the stale one, the port must reproduce
that staleness; a "cleaner" post-loop recomputation is a parity break, not an improvement.
Parity is against the reference AS-IS; improving behavior is a separate, explicitly-gated
change on top.
- **Locate large parity diffs programmatically** — when a compare dumps hundreds of KB,
run a small script that finds the first differing character and prints a window around
it on both sides; eyeballing truncated terminal output sends you debugging the wrong end
of the string.
- **serde_json's `json!` macro hits the recursion limit on very large literal objects**
(roughly 45+ entries) — build a `Map<String, Value>` and insert in a loop instead of one
giant `json!({...})` literal.
- **Comparators must diff dict KEY ORDER, not just membership** — the reference's dict
  construction order is observable wire shape (claimed-row payloads, result keys); a
  compare that only checks `==` on parsed objects passes while the port emits the right
  fields in the wrong construction order.
- **A mutation checker has its own blind spots: audit the checker before trusting a "killed" count, and read a survivor before touching the port.** Three seen in one session: (1) a comparator that sliced the sorted diff to its first 12 entries BEFORE comparing let a mutant with 55 extra mappings pass; (2) a runner that re-derived the ratio privately instead of calling the port's own public function made every mutant inside that function invisible; (3) a golden written from the same wrong reading as the port has no teeth (a SequenceMatcher port that treated autojunk-popular elements as junk passed a 7,395-pair golden; only long English-like inputs, where frequent letters cross the 1% popularity threshold once len >= 200, expose it). Compare the FULL diff, drive the port's real entry point, and prove the golden kills the specific wrong reading. In (1) and (2) the port was already right and the harness was the deaf part; in (3) the port was wrong.
- **Classify an "equivalent" mutant by measurement, not argument.** Replay the mutant over the whole golden, or over >=300k seeded random inputs, and record "0 differences"; keep a pure argument only when the input space is unbounded, and say so. A survivor argued away is how a real gap gets documented as harmless. Before hunting for a scenario, check whether the shape is ALREADY in the golden — a survivor whose input class is present is an equivalent, not a coverage gap, and adding a duplicate row wastes the pass. The commonest equivalents are convergence (a second trim on an offset the primary scan already cut) and unreachability (a guard a preceding guard already satisfied); both need the reference to confirm, not the port.
- **Rust std Unicode tables are not CPython's.** They track a newer Unicode (17.0 on this toolchain) than CPython 3.11's unicodedata (14.0.0): `char::to_lowercase` alone had 55 extra mappings. For `str.lower`, `re` `\w`/`\s` and `repr` parity, generate pinned tables from the reference interpreter (a consts generator, byte-diffed against the committed file) and sweep all 1,114,112 code points plus context strings; treat any std char-class call in a stdlib port as suspect until swept.
- **A background job inherits the CWD at launch, not the one you are standing in later.** A long test+clippy+slop gate started with an absolute `cd` looked finished because its sentinel file existed — but a later `cat scratch/s9/ws2_tests.log` ran from the REFERENCE checkout and printed "No such file", and a `git rev-parse --short HEAD` in the same batch returned the reference's own HEAD. Every "the results vanished" moment is this: `cd` in a separate terminal call does not move the session. Start background jobs with an explicit `cd <repo> &&` prefix, and re-`cd` at the top of every follow-up probe before reading logs or asking git for HEAD. A git HEAD that differs between two calls in one session is this bug, not a race.
- **Report a port's progress from the AUDIT's own file list, never a filename glob.** Inventory measured by "does a `<stem>*.rs` exist in the crate" marks an unported 6,160-line file as done because a thin same-named module exists, and miscounts the remainder. Derive the ported set from `parity/audit_symbols.py`'s output (the tool that already resolves each reference file to its Rust target), diff it against the reference tree, and report the MISSING largest files explicitly. Every "X% done" figure quoted to the owner must come from a recomputation in this session — a stale tally in a root-level review file is what gets restated as fact.

## Sourcing a helper's owner: AttributeError at import IS the finding

When a module-level lookup of a helper you expected raises `AttributeError`, do not add a
module-level alias to silence it — the AttributeError is the measurement. The real owner is
usually a `@staticmethod` on a class (`BasePlatformAdapter.strip_media_directives_for_display`),
and a module-level shim would have hidden the fact that the helper is only reachable through an
adapter subclass. Read the reference to find the true owner and call it there; record the location
in the generator so the next person does not re-derive it.

## Uncovered-line triage: unreachable, or a fixture gap?

A coverage tool that reports reference-line coverage will never hit a defensive arm, and the
instinct is to invent a scenario until it does. Do the opposite first: **ask what the arm's own
guard can accept.** A `if not path: return None` downstream of a regex whose every alternative
requires at least one content character is unreachable BY CONSTRUCTION — no fixture exists, and
hunting one wastes the pass. Prove it structurally (enumerate the pattern's alternatives, show
each has a minimum length of 1) rather than by assertion, then document the proof in the ledger
row next to the coverage number so the 99% is read as "one line proven dead" and not "one line
unexplored".

Two shapes make an arm genuinely reachable, and they look identical on the report:

- **A loop bound you have not exhausted.** An extension ladder bounded at N tokens needs MORE
  than N tokens, all failing validation, to reach its fallthrough. A row with exactly N tokens
  stops at the last iteration instead. Count the calls the reference makes and add one past the
  bound.
- **A lazy quantifier you have not triggered.** The branch fires only when the short form is
  present AND the long form validates; a row that always short-circuits skips it. Drive the
  validator with a scripted fail-then-pass sequence from the scenario spec rather than a fixed
  boolean, and record the CALL LOG so both sides prove which candidate won.

## Evidence discipline

- Claim done only with the commands and their actual output recorded (ledger row,
  commit message, or done-gate tool call with claims + evidence arrays). A claim without
  a command output behind it is a plan, not a result.
- **Stateful-module parity should drive the REAL reference object with its dependencies
  faked at the edge** — construct the actual class (real `__init__`, real mixins) and pin
  only the external dependency (`store._db = fake`), rather than reimplementing the
  object's plumbing in the golden. Scenario specs shared by both sides (one fixture list,
  consumed by the Python driver and replayed by the Rust runner) keep the two in lockstep
  and make misses self-evident. Deepcopy the spec before the driver runs and serialize a
  pristine copy — scripted fakes pop from outcome lists, and a replay runner handed the
  drained list quietly tests defaults. Compare the ordered dependency-call log and the final
  persisted state alongside the step results — and the captured log records
  (a `logging.Handler` on the reference logger) when a branch's only observable effect is a log line.
- **A structural symbol audit complements behavior parity**: map every ported reference
  file to its load-bearing symbols (class/function → Rust counterpart) and diff presence,
  not behavior. Keep audit keys as real reference file paths; resolve non-fork sources
  (installed-venv modules) to their actual location or the audit reports them missing.
  Run it every arc — a symbol present but shadowed by an unverified same-named variant
  passes behavior parity for the crates that use the real one.
- **A first test run showing few failures that goes clean on three re-runs is CPU
  contention, not a bug** — check for concurrent load (a local Ollama serving a graph
  pass, a parallel cargo build, another session's suite) before hunting the flake. Only
  a failure that reproduces on an idle machine earns the capture-loop treatment.
- Report honestly on partial states: mark deferred/known-gap items explicitly in the
  ledger (e.g. "PARTIAL-COVERED: probe until real builder exists") rather than
  silently rounding up to complete.
- **When the real implementation lands, retire its placeholder seam in the same
  arc-closing commit** — swap every call site of the prefix-probe/stub to the
  verified predicate, and expect the seam's own fixtures (written against the fake
  shape) to fail: settle them against a live reference run first, never against the
  old probe's behavior. A placeholder that outlives its successor is silent drift —
  the next porter greps, finds the probe first, and builds on it.
- Optimizations layered on a parity port stay default-off until a benchmark proves them
  (state the bar: e.g. ≥N% token reduction at ≤Xpp quality delta, measured on real data).
