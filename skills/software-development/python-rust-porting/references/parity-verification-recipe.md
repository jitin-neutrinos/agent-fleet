# Re-verifying a parity suite from scratch

Use when asked "is X verified?", when picking up a project after a gap, or whenever a
suite's green result predates your current working tree.

## Why this exists

A `compare_*.py` pass means only: committed `answers_*.json` == committed `golden_*.json`.
Both are files on disk. If the runner has not been executed since either file was written,
the pass says nothing about the code. Worse, a runner that fails to load its artifact
(exit nonzero, stale answers file left in place) followed by a comparator run produces a
clean, meaningless green.

## Procedure

```bash
# 0. Establish what the suite actually is
grep -rn "models\|fixtures\|ONNX\|CKPT" parity/gen_<area>_golden.py   # what the golden ran against
grep -rn "env::var\|args()" crates/<crate>/src/bin/<area>_parity_run.rs  # what the runner needs
```

Both sides must point at the SAME artifact. For exported models, confirm provenance:

```bash
stat -c '%y %n' parity/golden.json models/<export>.onnx
```

A golden older than the export is a different spec — regenerate the golden (see the
golden generator's own docstring for the venv/command it needs) before trusting any diff.

```bash
# 1. Move stored answers aside so a silent runner failure cannot masquerade as a pass
cp parity/answers_<area>.json /tmp/answers_old.json

# 2. Run the runner. Pass absolute paths when its defaults are relative to its own crate.
TAAL_MODELS=$PWD/models PARITY_DIR=$PWD/parity ./target/release/<area>_parity_run
echo "exit=$?"          # MUST be 0 — read this, not just the next command's output
ls -la parity/answers_<area>.json   # mtime must be NOW, not the stored file's

# 3. Only now compare
python3 parity/compare_<area>.py
```

If exit != 0 the suite is NOT verified — a missing-model error and a genuinely broken
port look identical until you read the exit code.

## Reading the diff once it is honest

- Runner exits 0 but compare fails on `type X != Y` inside a container field → output-shape
  drift, fix the runner to emit the golden's shape.
- Value diff on an attempt/count field → real control-flow difference; trace the
  reference's loop arms before touching either side.
- A section the golden never exercises because its scenario silently ran against a real
  backend instead of the fake → fixture bug, not a port bug. Confirm the fake is actually
  pinned before reading anything into the diff.

## What to report

State the re-run explicitly: "regenerated, 45/45, both sides re-executed", plus which
artifact both sides loaded. If you did not re-run, say "green against stored artifacts,
not re-run this session" — that is a materially weaker claim and the user needs to know
which one they have.
