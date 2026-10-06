---
name: resource-queue-and-idle-hygiene
description: "Use when queueing GPU/RAM/CPU work or reaping idle services."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [gpu, vram, queue, scheduler, reaper, resources, systemd, hygiene]
    related_skills: [storage-capacity-management, local-llm-hosting]
---

# Resource queue and idle hygiene

## When to Use

Any of these on kurama-core: queueing or scheduling GPU/RAM/CPU-heavy work (local inference, image or
video generation, batch training, a coding-model server); a job that must not start until VRAM is
actually free; stopping services, containers or model servers that have gone idle; reclaiming VRAM
held by nothing; or a workstation whose swap is full and whose load average is far above 1 for a
desktop. Also when the user says localgen, local coding model, "queue it", "clean up when it's idle",
"stop whatever's running", or asks why GPU/RAM is not free.

## Class definition

Class-level skill for arbitrating scarce host resources on kurama-core — 16 GB VRAM, 62 GB RAM,
28 cores — and for leaving the machine clean when work ends. Two halves that must be built
together: a **queue** that admits work only when it fits, and a **reaper** that stops what lingers.
A queue without a reaper only serialises leaks; a reaper without a queue kills work you meant to run.

Standing answer on this host: **`~/Work/infra/rq/rq`**, symlinked to `~/.local/bin/rq`, daemon
`rq.service`, reaper `rq-reap.timer` every 15 min, config `~/.config/rq/services.json`.
Prefer extending it over building a second scheduler — two schedulers double-admit the same VRAM.

## Procedure

1. **Measure the real constraint before designing anything.** `nvidia-smi
   --query-gpu=memory.free --format=csv,noheader,nounits`, `free -h`, `nproc`, `uptime`. On a
   workstation the binding limit is usually *free VRAM right now*, not the total. Quote the free
   figure in your design; a reservation against 16 GB total is meaningless when 13 GB is already
   resident.
2. **Audit what already runs before adding a queue.** List the actual claimants: GPU compute apps
   (`nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv`), docker containers
   (`docker ps --format '{{.Names}}\t{{.Status}}'`), user units, and swap pressure (`swapon --show`;
   per-process `VmSwap` in `/proc/<pid>/status`). Duplicate containers launched by repeated
   `docker run` are common and are pure waste — report them.
3. **Check for an existing guard before writing a new one.** `systemctl --user list-timers` and
   `systemctl --user cat <name>` for storage/cleanup/watchdog units, plus `crontab -l`. On this host
   `storage-guard.timer`, `machine-cleanup.timer` and `localgen-watchdog.timer` already exist. Extend
   one; a competing timer that re-implements a sweep is a second source of truth.
4. **Admit on measured fit, not on declared intent.** A job starts only when
   `gpu_free >= requested`, `MemAvailable >= requested + 2 GiB desktop reserve`, and
   `already_reserved_cores + requested <= nproc`. Log the refusal verbatim
   (`WAIT job: gpu free 193MiB < requested 8192MiB`) — a queue that silently waits is
   indistinguishable from a hung one.
5. **Enforce, do not just reserve.** On this cgroup-v2 host, `systemd-run --user --scope -p
   MemoryMax=NM -p CPUQuota=N%` gives real kernel enforcement with no new dependency. Prefer the
   platform's existing primitive over adding a library — check it works first with a trivial scope.
   This host's user has said plainly: **use any available framework if it means reliable
   implementation.** Treat that as settled for this class. A primitive the kernel enforces beats
   bookkeeping your own scheduler honours only on its own code path, and picking the reliable option
   is not over-engineering — reimplementing correctness someone already got right is. Keep one
   mechanism per guarantee; a second safety net that merely warns is duplication that diverges.
6. **Run every job in its own process group** (`start_new_session=True`) and kill the *group* on
   exit: TERM, wait out the grace period, then KILL. A job whose worker outlives its parent keeps a
   CUDA context and its VRAM forever; this is the single most common way a desktop leaks VRAM.
7. **Run cleanup on every exit path**, in the same place you reap the group — success, non-zero
   exit, and timeout. Cleanup in a `finally` / post-`waitpid` block, never at the end of the happy
   path. Unmount before you `rm -rf` a path that may be a mountpoint.
8. **Make the reaper conservative by construction.** Targets come from an explicit config list with
   a per-service idle threshold, and an unrecognised or incomplete entry is treated as **busy**.
   Missing `idle_minutes` must default to a non-zero value (30), never 0 — a 0 default reaps on the
   first pass. Measure idle from the first pass that sees the service idle, so a busy service resets
   the clock. Ship entries with `"enabled": false` and arm them only after the user chooses.
9. **Prove it end-to-end on the live daemon before reporting.** Queue a real job and show the
   `QUEUE → START → DONE` lines plus the job's own output; then submit an oversized job and show
   the `WAIT` refusal. A queue proven only by unit tests has not been shown to schedule anything.

## The client/daemon state-path trap

The highest-cost bug in this class, and it presents as an unexplained timeout.

A long-lived daemon and a short-lived client must agree on one absolute queue path. If the path is
derived from `XDG_STATE_HOME`, they do not: agent sessions on this host set `XDG_STATE_HOME` to a
per-session scratch directory, so the client writes `queue.json` somewhere the daemon never reads.
The job sits `queued` forever and `rq run` reports a bare timeout.

- **Pin shared state to a fixed per-user path** (`~/.local/state/<tool>`), not an XDG var. Keep one
  explicit override (`TOOL_STATE_DIR`) purely for tests.
- **Reload from disk on every tick.** A daemon holding only its in-memory list cannot see jobs
  submitted by a client after it started; the file must be the single source of truth.
- **Restart the daemon after deploying code changes** — it keeps running the old module otherwise,
  and the symptom (client writes a file, daemon ignores it) looks identical to a logic bug.
- **Prove elevation or path agreement before trusting a negative.** "The daemon never saw it" has
  three causes (stale code, split state path, lock held elsewhere); check `/proc/<daemon-pid>/environ`,
  `ls -l /proc/<pid>/fd` for the file it actually opened, and the daemon's start time against the
  file's mtime.

## Pitfalls

- **Never let a reaper guess that a process looks idle.** VRAM utilisation sampled at one instant is
  not idleness; a model server between requests reads 0%. Require the process to have been idle across
  repeated passes, with a warm-up guard that spares anything started within the last few minutes.
- **A service that is "up" is not necessarily serving.** A container can be `running` while its port
  returns nothing. Probe the endpoint before declaring it busy, or the reaper will never reap a
  wedged container and will reap a healthy idle one.
- **`waitpid` on a job you did not spawn raises `ChildProcessError`.** After a daemon restart the
  running job is no longer its child. Fall back to `/proc/<pid>/stat` liveness (treating `Z` as dead);
  assuming "done" releases a reservation that is still really in use and lets a second job start on
  top of a live one.
- **Pruning job history can eat a result a waiting client is still reading.** Keep finished entries
  for a grace period (minutes) before dropping them, and never prune `queued`/`running` rows.
- **A bare `except` around the scheduler loop turns every bug into silence.** The daemon stays
  `active` with one task and near-zero CPU while nothing ticks. Log the exception type and message;
  when the daemon is idle, confirm it is in its sleep and not wedged on a lock (`/proc/<pid>/wchan`,
  `/proc/<pid>/syscall`).
- **A flag that is parsed but does nothing is worse than no flag.** Implement `--dry-run` for every
  destructive sweep, and have it touch no state at all, so it is safe to run on a machine you care
  about.
- **Self-checks that are defined but never invoked report a clean sheet.** Register checks by
  discovery (`t_*` functions) rather than a hand-maintained list, and assert a non-zero count so an
  empty run fails instead of printing `passed 0`.
- **Verify deletion of an archive before deleting its siblings.** Check the keeper opens and lists
  (`tar tzf <file> | wc -l`) plus the gzip magic bytes. Keeping the newest by mtime is only correct
  once the newest is proven intact.
- **Destructive sweeps must assert their own exclusions at runtime** against a real array of absolute
  paths, with every variable given a safe default — an assert that trips on an unset variable under
  `set -u` aborts the run and silently provides no protection at all.
- **Verify your own safety rails actually run before relying on them.** An assertion that aborts on
  its first invocation, or a `--dry-run` that still writes state, is worse than no rail because the
  machine looks protected. Run the guard once and read its log line.

## User preference recorded here

When asked to build infrastructure for this host, prefer a proven platform primitive or framework
over hand-rolled logic **when that is what makes it reliable** — the user has authorised this
directly ("use any available framework if it means reliable implementation"). Do not re-argue for a
shorter hand-rolled version that trades away the guarantee, and do not read framework use as
over-engineering in this class. Enforce guarantees where they cannot be bypassed (cgroups, process
groups, aborting guards), not in advisory config your own code path honours.

## Reporting

State what was deleted or reaped, what was left alone, and what was deliberately NOT touched with
the reason. For anything irreversible, or for a decision that trades a capability for headroom
(snapshot retention, a service you may need), present it as a proposal with the tradeoff named and
wait — do not act on a question you asked and never got answered. Say plainly when a number is
unmeasured rather than estimating it.

## References

- `references/reaper-config-and-evidence.md` — service-spec schema, the dry-run contract, the
  evidence lines that prove admission control and reaping, and the `set -u` guard bug.
- `storage-capacity-management` — the disk side: snapshot pinning, capacity guards, safe sweeps.
- `local-llm-hosting` — what the VRAM reservation is for; the local coding server is the usual
  reason 13 GB of a 16 GB card is resident.