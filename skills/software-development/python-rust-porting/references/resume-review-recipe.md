# Resuming a long ported-project session from docs

Use when a new session opens on a multi-session port and the request is "review the last
transcripts, check the codebase and the handoff docs, then present your findings before we
continue". The gate is not "I read the handoff" — it is "I re-ran the numbers the handoff
claims, and I read the next target off disk".

## Order that works

1. **List the project root.** One `ls -1` shows the protocol docs, the ledger, the handoff,
   the frozen reference, and the per-session `scratch/` trees. The session status files live
   under `scratch/s<N>/STATUS_S<N>.md` — newer than the handoff, often disagreeing with it.
2. **Read the newest `STATUS_S<N>.md` and `HANDOFF.md` together.** Where they conflict, the
   status file wins (the handoff itself says so). Watch for a status file whose "NEXT" list
   contains a duplicated/stale block appended twice — read the last one.
3. **`git log --oneline -N` + `git status --short` in one pass.** The log gives the banked
   rows with their evidence in the commit subjects; the status shows what is stranded.
4. **`git diff --stat` then diff any modified `golden_*.json` / `gen_*_golden.py` by hand.**
   Classify each as real work or campaign noise (regenerated answers files are noise; a
   generator diff is a fixture change someone made and did not commit).
5. **Re-run the acceptance gates live, in-session.** Workspace test count (aggregate `test
   result:` lines into PASSED/FAILED), `clippy` error count, the symbol audit, the
   last-completed row's parity suites, the tunnel/liveness probe, the slop detector. Quote
   only what you ran; anything not re-run gets labelled "green against stored artifacts,
   not re-run".
6. **Read the next target off disk**, not from the handoff: reference line count, method
   count, and which existing seam its host trait should follow (`grep '^pub trait'` across
   the target crate).

## Reporting shape the owner approves on

One canvas card, in this order: badges (HEAD, arc state, next item, tree state) → a
success callout stating what was re-verified and how → a KPI row (the aggregate test count
with its trend across sessions) → a per-row evidence table (row | module | parity | mutation
| refcov | state) → a warn callout for anything stranded → the next-arc table with reference
line counts → a callout naming the porting method for the next module → a checklist with
done/open items → a gotchas callout → references.

Close by asking for approval to start the next row and surface any decision the owner
should make (e.g. whether to bank a stranded fixture separately or with the next commit).

## Pitfalls

- **Do not treat a doc claim as verified.** Re-run it. The owner has twice caught a handoff
  number that no longer matched the tree.
- **A big untracked/modified list is usually campaign output.** Answers files, scratch
  logs, a regenerated golden. Say so in one line and do not treat it as uncommitted work —
  but DO name any file that is real work (an edited generator is real work).
- **Never quote a test count taken while the campaign is mid-campaign.** The campaign's
  mutation gates break source files on purpose and share the tree; a workspace test run in
  that window reads sabotaged code (measured: 740/1 while every clean-tree run is 763/0).
  `git status -- crates/` naming a file the mutation list targets confirms it — a failure
  then is the gate working, not a defect. Re-run on the restored tree before reporting;
  the honest number is the last clean-tree one already in the campaign log.
- **Check for a running mutation loop before re-running anything.**
  `ps -eo pid,cmd | grep mutation_check` — `pkill -f mutation_check` matches your own
  shell and reports a false RUNNING.
- **Copy gate commands from the campaign script verbatim** (runner binary name and
  `target/mut` vs `target/release` path both matter). See the harness-layout section of
  SKILL.md; a wrong invocation shows as a comparator crash, not as a parity failure.
- **Reconstruction from a handoff's prose drifts.** Session status files accumulate stale
  "NEXT" blocks; the last commit's subject is the most reliable one-line state.