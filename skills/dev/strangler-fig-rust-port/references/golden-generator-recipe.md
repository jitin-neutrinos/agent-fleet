# Golden generators that run the real reference

A parity golden is only as trustworthy as the reference execution behind it. Every value
must come from RUNNING the reference — never from reading its source, a docstring, or a
prior session's notes.

## Pick the fixtures from the reference's own tests, not from the handoff

`grep -rl '<reference_fn_name>' <ref>/tests/` and rank by hit count. The largest hitter is
the module's real fixture set. **Verify the handoff's list before using it**: a handoff can
name test files that never touch the module (a transcript test named for a transcript bug
reads as voice-adjacent and contributes one incidental reference).

Replaying those fixtures beats inventing scenarios because the reference's bug history is
already encoded in them.

## Drive the real object, not a bare namespace

Instantiate the class the method is bound to (`object.__new__(TheClass)`) and call through
the INSTANCE. Calling `Cls.method(obj, a, b)` passes `obj` as `self` and drops a positional
argument. Set each attribute the method reads, one named assignment per line — a dict
literal or `MagicMock(**{...})` auto-creates children, so a typo silently takes the
fallback arm instead of failing.

## Pin every ambient dependency

| Ambient | Pin it with |
|---|---|
| clock / `time.monotonic()` | a fake object on the module, carrying cumulative state |
| filesystem / temp paths | a `TemporaryDirectory`, plus an adversarial row that cannot write |
| logger | a callable that records; assert the ORDERED warnings, not just a count |

A clock pinned per-case but consumed cumulatively is the common slip: the reference driver
holds one clock across every case, so the runner must too or every case after the first
stamps a different time.

**A shared clock across cases makes timestamps part of the golden.** Verify the runner's
clock starts and advances identically; a drift shows up as a diff in one unrelated column
and reads like a port bug.

## Measure the reference's own execution

`python3 parity/refcov.py <gen.py> <ref.py>[:func1,func2]` traces the generator and reports
executed vs executable lines plus the UNEXECUTED lines with their source. Scope it to the
functions you ported — an unscoped run reads low and stops meaning anything once a file is
layered.

Each unexecuted line is a missing scenario. The recurring ones are an `except`/`OSError`
arm, a `mkdir`/create-parent call, an attribute write, and a type-pin branch. Build a row
for each: point a temp path at an existing FILE to make `mkdir(parents=True)` fail, set the
attribute to a non-container to hit `isinstance(x, dict)` False, and so on.

## Shape rules that cost a session each

- **One uniform fixture shape per case list.** A list mixing `(text, advance)` and
  `(advance, text)` entries fails at runtime, not at review; encode the shape once.
- **JSON keys must be strings.** A store keyed by a Python tuple serializes its `repr()` if
  you let it — render composite keys explicitly (`f"{k[0]}:{k[1]}"`).
- **Driver stdout is the golden.** No diagnostics; stderr only.
- **Strip volatile substrings** (temp paths, timestamps, uuids) to a `<PLACEHOLDER>`.
- **Assert scenario-name uniqueness** so one row cannot silently collide with another.

## Comparing

Diff dict KEY ORDER too (Python dict order is observable and often load-bearing), compare
by SHAPE where an I/O seam is faked, and compare side-effect ORDER by having the fake append
every call with its arguments — a result diff alone cannot catch a missing or reordered
call. Normalize `{}` against `None`, and `""` against `None` per the reference's actual
return statement rather than Rust idiom.