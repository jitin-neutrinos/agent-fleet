# Integrating harvested worker modules

A worker's delivered module is **untrusted input** until you have compiled it, run its tests, and
compared its diff against the reference. This is the checklist for the harvest step, in order.

Workers are usually good at the port and sloppy at the fixture layer — the port's logic compiles and
the failures concentrate in `#[cfg(test)]` code. Budget your time accordingly: assume the module is
mostly right and the tests are mostly wrong.

## 1. Compile the lib first, in your own tree

Copy each module in, register it in `lib.rs`, and build `--lib` BEFORE touching tests. The lib build
surfaces real integration errors (missing trait methods, wrong imports) with none of the test-layer
noise.

**A missing seam method is the signature of a worker that read the reference but declared the trait
from memory.** One cluster called `host.failed_platform_count(rec)` without declaring it — while its
own module header *documented the distinction correctly*. Declare it from the reference, not from
the call site: `len(self._failed_platforms)` is a **map size**, not the length of the error list that
a naive reading would pass, and the two diverge whenever a platform is queued twice.

## 2. Then fix the test-layer mechanical errors

These are predictable and all mechanical. Expect them in worker output:

| Compiler error | Cause | Fix |
|---|---|---|
| `Cell<T> cannot be shared between threads safely` | the seams are `Send + Sync`; `Cell`/`RefCell` are not | `Mutex<T>`; `.get()`→`*x.lock().unwrap()`, `.set(v)`→`*x.lock().unwrap() = v`, `.borrow()`→`.lock().unwrap()`. Sweep fully-qualified `std::cell::RefCell::new` too, not just the bare form |
| `use of unstable library feature 'str_as_str'` | calling `.as_str()` on a `&'static str` field | drop the call — the field is already `&str` |
| `cannot assign to f.x, as f is not declared as mutable` | `let f = Fake::new();` then `f.x = …` | scan for the pattern and make the binding `let mut f` — do it by looking ahead a few lines for an assignment, not globally |
| `temporary value dropped while borrowed` | `let v: Vec<&str> = rec.records().iter()…collect()` borrows a temporary | bind `let _records = rec.records();` first, then borrow from the binding |
| `mismatched types: Option<&str>` vs `Option<String>` / `Result<_,PyExc>` | the worker assumed the field's shape | read the port's own struct declaration, not the test's assumption |

After that pass, re-read the remaining failures individually — they are genuine.

## 3. Verify each red test against the reference, not against your expectation

A worker's test can assert the **opposite** of the reference. Measured: a test asserted that a null
resume-marker over an ancient `updated_at` is *not* stale, while the reference's
`marker = entry.last_resume_marked_at or entry.updated_at` is a first-truthy operand that makes it
stale. The port was right; the test was wrong.

**Procedure:** for each failure, read the reference line the test names, write the expected value
from that line, and correct whichever side disagrees. Then ADD the complementary row the original
test was reaching for — here, the null marker over a *fresh* `updated_at`, which is the arm the
fall-through actually buys. A corrected assertion with no positive counterpart leaves the arm
uncovered.

When you change a default to fix a group of tests, re-run the WHOLE module and compare the pass
count to before. A fix that lowers the pass count is a wrong fix even when it removes the failure
you were chasing.

## 4. A fixture must model the store's MUTATIONS, not just its reads

The most expensive fixture bug class, because it presents as a hang in the PORT.

A fake that answers reads but never applies the reference's own write-back leaves the store in a
state the real store would have left. A delivery-ledger fixture that never removed a row on
`mark_delivered` kept re-offering a deadline the worker had already delivered, and
`redeliver_after_wait` spun **1.18 million times** in a passing-looking test.

Rules:
- **When the reference mutates a store, the fake must mutate it too.** `mark_delivered` removes the
  row from `pending_retries`; if the fake only bumps a counter, every `while running:` loop over that
  store is infinite.
- **A `bool` fixture field defaults to `false` under `..Default::default()`.** If `false` means "the
  store does not clean up", a fixture built with the spread operator silently models the wrong world.
  Give the field a manual `Default` whose value matches reality, and say why in the impl's doc
  comment.
- **The fake must match rows by the SAME normalised key the port builds.** A retire predicate
  comparing a raw `Option<&str>` profile against the row's `"default"` never matches, so the row is
  never retired and the loop spins. Construct the key through the port's own constructor
  (`FloodKey::new(platform, profile)`, which applies `profile or "default"`) rather than
  re-deriving the comparison.
- **A test binary that exceeds its timeout is a fixture lie until proven otherwise.** Confirm by
  running the module's tests one cluster at a time with a short timeout, then the single hanging
  test by exact name, then add a temporary counter print in the fake's read method and count the
  iterations. A loop that re-selects the same input forever is a store that never changed.

## 5. Sequencing note

Fix the HARNESS before the port. A fixture that lies produces failures that look like port bugs,
and "correcting" the port to satisfy a lying fixture breaks the rows that were right.