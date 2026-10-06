# Parallel batch work over a shared, non-versioned file estate

When N workers each read one input and all write into the SAME tree of files
(skills, agent docs, project docs, any generated estate), naive parallelism loses
edits. Two workers writing one file is last-write-wins: the loser's change is gone
and nothing reports it. If that tree is not a git repo there is no branch to merge
from and no reflog to recover — the loss is silent and permanent.

## Decision: can you parallelise at all?

1. **Is the estate under version control?** If yes, the clean answer is isolate-and-
   merge: give each worker its own worktree/clone, then merge. Do not hand-roll
   concurrency control over a repo that already solves it.
2. **Is it not versioned?** Then either serialize, or use optimistic concurrency
   below. Serializing N=850 items is often hours; the recipe below buys real
   parallelism without the corruption risk.
3. **Do the workers actually touch overlapping files?** If each writes a distinct
   output path, run them fully parallel and skip all of this. Measure before
   building machinery — a fleet where 90% of runs touch nothing in common needs no
   collision pass at all.

## Optimistic concurrency recipe (no VCS required)

Run the batch in parallel, then repair the collisions after the fact:

1. **Before each run**, fingerprint the estate: walk the writable roots and record
   `absolutePath -> "mtimeMs:size"`. Cheap (stat only, never read file bodies) and
   bounded — cap the walk depth and skip `node_modules`/`.git`/dotdirs so a runaway
   tree cannot stall a run.
2. **After each run**, fingerprint again and diff. A path only in `after` was
   created, only in `before` was deleted, a changed signature was edited. Keep that
   per-run file set, plus the run's `start`/`end` wall-clock stamps.
3. **Collision pass:** two runs collided iff their time windows OVERLAP **and**
   their changed-file sets INTERSECT. Both conditions are required — overlapping runs
   on different files are safe, and same-file runs that never coexisted are safe.
4. **Re-run only the collided items, serially.** One at a time, so the final state
   is a complete edit rather than whichever write happened to land last. Report the
   collision count; a high count means the estate is contended and the concurrency
   should come down.

## Boundaries and gotchas that cost real time

- **Touching windows are not overlapping.** `a.end === b.start` means one run ended
  the instant the next began — sequential, not concurrent. Use `a.end <= b.start`
  as the "no overlap" test. An off-by-one here flags innocent pairs and re-runs work
  for nothing; write the boundary case as an explicit test fixture.
- **A no-op run can never collide.** An empty changed-file set intersects nothing,
  so a worker that edited nothing is never flagged. Do not special-case it.
- **Guard the fleet across processes, not just within one.** An in-process flag
  cannot see a second runner (a service timer vs a detached batch). Use a pid-file
  lock: write `{pid, at}`, treat the lock as held only when that pid is still alive
  (`process.kill(pid, 0)`), and release only your own pid. Fail OPEN on any lock I/O
  error — a broken lock must not block the work.
- **Share the state DB safely.** With two processes on one SQLite file, set
  `PRAGMA busy_timeout` (10s is plenty) so the non-writing process waits instead of
  throwing `SQLITE_BUSY` mid-run. WAL already allows concurrent readers.
- **`nohup ... &` is NOT detached enough — use a supervisor.** A backgrounded
  runner still dies when the shell that launched it is killed, which happens the
  moment the agent's own tool call ends or a later command in the same shell is
  killed. Launch it as a transient unit instead:
  `systemd-run --user --unit=<name> --collect --working-directory=<repo> /usr/bin/node scripts/run-batch.mjs <args>`.
  Then the job survives the session, and `systemctl --user is-active <name>` plus
  `systemctl --user stop <name>` are the liveness and stop controls. Verify it is
  really up (`is-active` = active AND the worker processes exist) before walking away
  — a runner that died 30s in looks identical to one that is grinding until you
  check the artifact count.
- **A worker that exits 0 having produced NO output at all is a FAILURE, not a
  no-op.** Judge success on content, not exit code: total silence (empty log, no
  claims, no changes) means the model never answered — a provider error or a weak
  fallback model that answered uselessly — while the process still returned 0. Only
  an explicit "nothing to do" answer passes. Record the silent run as failed so the
  batch reports it; treating it as done silently marks the whole backlog complete
  with nothing analysed.
- **Preflight the provider before launching a large batch.** A quota-exhausted
  provider does not fail loudly — the harness falls through its fallback chain and
  the batch keeps "succeeding" on a model that cannot do the job, producing the
  empty-output runs above. Read the agent error log's tail for a recent
  `429`/`RateLimitError`/`quota`/`Exhausted` line (with its reset time) and ABORT
  the batch with that reason rather than starting it. A batch that refuses to start
  is cheap; one that marks 850 items done without work is expensive and must be
  unwound by hand.
- **Throttle the progress log.** One line per completion across 8 workers floods
  the log; coalesce by time and always emit retry/terminal lines.
- **Test the collision predicate directly.** Export it as a pure function and pin it
  with fixtures: same-file+overlap, same-file+disjoint, different-file+overlap,
  no-op+overlap, three-way overlap, mixed batch. It is the load-bearing decision
  behind the whole scheme and the cheapest thing to get subtly wrong.
