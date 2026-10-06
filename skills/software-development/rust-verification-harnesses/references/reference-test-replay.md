# Replaying the reference's own test suite

When the reference implementation ships tests for the code you are porting, they are the
strongest oracle available: real bugs, real edge cases, already written and passing.
Hand-writing a golden for the same module re-invents a weaker version of that suite.

The technique: a pytest plugin that wraps each ported public function and logs every call
while the reference's tests run. The log is a list of `{node, fn, args, kwargs, result}`
rows. A Rust runner replays the rows through the port and diffs.

## Why it finds bugs the golden cannot

A golden is what YOU think the module's inputs are. The reference's tests are what the
module actually gets fed. Replaying them surfaced, in one pass, a mis-transcribed constant,
a message-extraction branch that fired only when a dict had no nested key, a helper that
understood one of four message grammars, a header read as the wrong unit, a defaulted
status code, and an entire classification stage that was never ported. None were reachable
from the hand-written fixtures.

## Procedure

1. **Write the plugin into the reference's test tree** (e.g. `tests/ref_trace_plugin.py`)
   so pytest can load it with `-p`. Wrap the module-level functions you ported; for
   classmethods wrap the underlying function. Skip functions whose args cannot be
   reconstructed — record them as skipped instead of faking them.
2. **Deep-JSON encode every arg and result.** A shallow `try json.dumps` returns `str(v)`
   for anything non-serializable, and the trace silently fills with `"True"` or a repr
   string. Handle separately: dataclasses → dict, enums → `{"__enum__": name}`, exceptions →
   `{"__exc__": class, "str": …, "attrs": {…}, "cause": …}`, objects with `__dict__` →
   `{"__obj__": Class, **vars}`. Record `__cause__` — reference helpers walk the exception
   chain for status/body/headers, so without it those rows are unreplayable.
3. **Run the reference tests under it**, then keep the pass/fail outcome per row. A test
   whose recorded result came from a FAILING assertion is not an oracle; filter on outcome.
4. **Record the module attribute the reference's own tests pin** (e.g. a classifier patched
   to a fixed table) and give the Rust port the same injection seam — otherwise every row
   exercising the pinned path diverges.
5. **Replay and diff field-wise.** Compare only the fields the reference materializes as
   concrete values. Two classes of field need special handling:
   - **Defaults.** A dataclass with `retryable: bool = True` writes `True` where a port
     keeps `None`. Normalize per-field defaults, and do NOT guess one default for all:
     `retryable` defaults true while `should_compress` / `should_rotate_credential` /
     `should_fallback` default false.
   - **Wall-clock values.** `reset_at`-style timestamps differ per run. Compare the
     PRESENCE of the key (as a set), never the value.
   Compare `error_context`-style key lists as SETS — ordering is a rendering choice, and a
   field-wise comparator that iterates our insertion order turns key order into a false
   mismatch.
6. **Triage each survivor against the reference source, not against intuition.** Rows
   needing a subsystem you deliberately do not port (a vendor model catalogue) are
   recorded as known-gaps in the runner, never counted as parity rows.

## Pitfalls that cost a session each

- **The trace plugin must live on the test tree and be importable.** `-p ref_trace_plugin`
  fails with "No module named" unless the tests dir is on `PYTHONPATH` (set it) or the
  plugin sits in the rootdir conftest path.
- **Async tests need `pytest-asyncio` installed in the venv you invoke.** Without it they
  fail with "async def functions are not natively supported" — a harness gap that reads
  like a real failure. Install it; do not record those tests as failing.
- **Join `--json-report --json-report-file=X` as ONE argv token and pytest reads it as a
  PATH**, yielding "file or directory not found". They are two separate arguments.
- **Coverage/naming aside: a `--json-report` file that silently isn't written means an empty
  manifest**, not an empty suite. Check `rep.exists()` before concluding "0 tests".
- **Self-referential borrows:** the liveness/state data both a db handle and a closure need
  must live in an `Arc` shared by both; a closure capturing a `&struct` that is then moved
  into `Box<dyn Trait>` fails E0597.
- **Enum comparison:** a reference enum serializes as `{"__enum__": "FailoverReason.auth"}`
  while the port yields `"auth"`. Normalize by stripping the class prefix and the repr tail
  rather than matching raw values.

## What to do with the result

Run it as a campaign gate next to the comparators (`REF_TRACE REPLAY OK <n> rows matched,
0 mismatched`). Report non-replayable rows as a count in the same line — a replay that
quietly replays 40 of 233 tests looks like coverage and is not.