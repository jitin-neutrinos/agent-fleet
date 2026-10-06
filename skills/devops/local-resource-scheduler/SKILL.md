---
name: local-resource-scheduler
description: "Use when queuing GPU/RAM/CPU work or reaping idle jobs."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [gpu, vram, queue, scheduler, cgroup, systemd, reaper, cleanup]
    related_skills: [memory-pressure-and-swap, storage-capacity-management]
---

# Local resource scheduler

Class-level skill for building a queue that arbitrates scarce local resources (GPU VRAM, RAM,
CPU) on a single host, plus the idle reaper that keeps the machine hygienic afterwards. Applies to
any workstation running concurrent GPU/CPU jobs — model serving, batch generation, inference
batches, training jobs.

The governing rule: **a reservation that is only documented is not a reservation.** If two jobs can
both decide they fit, one of them will be wrong, and on a 16 GB card the wrong one is an OOM or a
silent slowdown. Measure at admission time and enforce with the kernel.

## When to Use

- Concurrent GPU or heavy-RAM jobs need to share one device without colliding.
- Idle services accumulate VRAM/RAM and nothing stops them when they go quiet.
- A job framework leaks VRAM through orphaned children after the parent exits.
- Asked to "queue", "schedule", "gate", or "reap" local compute.

Do not use it for remote/distributed queues (Celery, SQS) or for storage-space exhaustion.

## Design the arbitration first

1. **Enforce with the platform, not with a comment.** On systemd hosts, `systemd-run --user --scope`
   with `-p MemoryMax=…M -p CPUQuota=…%` gives real kernel enforcement with zero new dependencies.
   Probe for it (`shutil.which("systemd-run")`) at startup and degrade to "documented but uncapped"
   rather than crashing. Prefer an existing platform primitive over adding a dependency.
2. **Admission control measures; it never assumes.** Sample the real free amount per scheduling
   pass (`nvidia-smi --query-gpu=memory.free`, `/proc/meminfo` `MemAvailable`, core count). A
   reservation is a floor to check, not a claim to believe.
3. **Keep headroom for the machine itself.** On a workstation, require RAM available to exceed the
   request by a margin (2 GiB or so). A job that fits exactly available memory still takes the
   desktop down with it.
4. **One writer.** Take an exclusive `flock` for the daemon and exit if it is held — two schedulers
   double-scheduling is worse than no scheduler.
5. **The queue file is the source of truth and is re-read each tick.** A long-lived daemon holding
   only an in-memory list will never see a job submitted by a client that is blocked waiting on that
   same daemon. Reload per tick, write atomically (`tmp` then `rename`).

## Process groups and the orphan leak

- Spawn every job with `start_new_session=True` so it leads its own process group, then reap the
  **group** with `killpg`, escalating TERM → grace period → KILL.
- A job that forks workers and exits leaves those workers re-parented to init but still in the
  group. On a GPU host they keep their CUDA context and hold VRAM forever. This single pattern is
  the most common cause of "VRAM is stuck and nothing is running".
- Prove it in a self-check: parent exits immediately after forking a sleeper, assert the orphan is
  alive, then assert the reap kills it. A test that only checks the parent died proves nothing.
- Run cleanup (unmount, delete scratch) in a `finally`-equivalent on **every** exit path, not the
  happy path.

## The idle reaper

- **Trace ownership before calling anything a duplicate.** Two containers of the same image are the
  normal shape of two *live harnesses* each running its own MCP set, not necessarily waste. For a
  stdio MCP, the container is a pipe-bound child of one specific parent process — match creation time
  against the parent's start (`docker inspect -f '{{.Created}}'` vs the harness process start time;
  a child appears seconds after its parent) to find which harness owns which pair. Two harnesses
  spawning the same server minutes apart is expected behaviour.
- **Before proposing to stop a duplicate, check what the removal costs and what it saves.** A stdio
  MCP pair typically costs a few MB RSS at 0% CPU — tens of MB total. Deleting it breaks a working
  harness's tools and reclaims nothing measurable, so it is not a hygiene win. Say the number, and
  if the user still wants it, the correct unit of removal is a whole harness process, not individual
  containers: stopping containers behind a live parent leaves that parent holding a broken MCP config.
- **Do not read a low PID as a survivor of a reboot.** Check `uptime -s`; if the host has not
  restarted since the PID was allocated, low PIDs are ordinary reuse. Claiming a container "survived
  a reboot" from its PID alone is a fabrication.
- **Explicit target list, per-service threshold, nothing inferred.** An unrecognised or incomplete
  entry is treated as **busy**, never reaped. Guessing "this looks idle" destroys a model server
  mid-request.
- **Warm-up guard**: never reap a process started less than N seconds ago, so a restarting daemon is
  not mistaken for an idle one. Idle time is measured from the first observation of idleness, and
  any busy observation resets the clock.
- **Ship armed-off.** Generate the config from what the audit actually found, but write entries with
  `enabled: false` and let the user arm each one. Service stops are user decisions; a reaper that
  acts unattended on a wrong threshold is worse than no reaper.
- **Provide `--dry-run` and make it real** — it must not mutate idle-state files or touch services.
  A flag that parses and does nothing is worse than no flag, because it looks like a safety feature.

## Pitfalls

- **Never honour `XDG_STATE_HOME` for shared daemon state.** Hermes sets it to a per-session scratch
  directory, so a client and a daemon started from different sessions write to different queue files:
  the client queues a job the daemon never sees, and it presents as a mysterious timeout. Use one
  absolute path (`~/.local/state/<tool>`), with an explicit `TOOL_STATE_DIR` override for tests only.
- **`argparse.REMAINDER` cannot be mixed with options.** `prog run NAME --wait 30 -- cmd` swallows
  `--wait 30 --` into the remainder, so flags are silently ignored and the command is never found.
  Split argv at the first standalone `--` yourself and parse the two halves separately, keeping CMD
  byte-exact even when it contains args that look like your own flags.
- **A daemon started before your edits runs stale code in memory.** Restart it after every change
  and verify with a real end-to-end job through the service, not by re-running the module by hand —
  a manual run proves the file, not the running process.
- **Register a test module in `sys.modules` before `exec_module`** when loading via
  `SourceFileLoader`: `@dataclass` resolves annotations through `sys.modules[cls.__module__]` and
  raises `AttributeError: 'NoneType'` otherwise.
- **Discover `t_*` checks by introspection, not a hand-written list.** A defined-but-unlisted check
  never runs, and the suite reports `passed 0 failed 0` while looking green. Print the executed
  count so a zero-run suite is visibly wrong.
- **Never prune a finished job a client is still polling for.** Keep recent terminal entries for a
  grace period; otherwise the waiter reports "vanished from queue" instead of the real exit code.
  On `ChildProcessError` (daemon restarted, job is not our child) fall back to liveness checks — do
  not assume done, or a still-running job's reservation is released and a second job starts on top.
- **Report the reaper's decisions with evidence** — VRAM held, idle duration, why it was judged
  idle. A reaper that stops things without a stated reason is indistinguishable from a bug.
- **Ship a guard's reaper targets disarmed and name the decision each one waits on.** Arming a
  service stop unattended on a threshold nobody approved is worse than not shipping the reaper. When
  the audit surfaces a choice ("keep this 13 GB VRAM model warm, or make it on-demand?"), record the
  config with `enabled: false` and say in the report which entries are waiting on which answer.
- **Name your own measurement error before the user's data corrects it.** A wrong attribution you
  retract in the next message ("these are not duplicates", "that was ordinary PID reuse") costs more
  trust than a slower, more careful first pass. Verify the mechanism, not just the coincidence.
- **Distinguish "config already says the right value" from "the fix worked".** A persisted tunable
  at the correct value proves nothing about whether space was reclaimed; read the live usage number
  again after a settling interval and report that.