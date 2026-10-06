# Reaper config and proof

Depth for the queue/reaper class in SKILL.md. Read when adding a service to the reaper,
debugging why a service was or was not reaped, or assembling evidence that admission control
actually works.

## Service spec schema

`~/.config/rq/services.json` — `{"services": [ ... ]}`. Every field is explicit; nothing is inferred.

| Field | Meaning | Trap if wrong |
|---|---|---|
| `name` | label in logs and the idle-state file | must be stable; renaming resets the idle clock |
| `type` | `container` \| `process` | **any other value is treated as BUSY forever** — never reaped |
| `match` | container name, or a `pgrep -f` pattern | too broad matches the agent's own shell and reaps live tooling |
| `enabled` | `false` keeps the entry documented but inert | ship `false` until the user decides |
| `idle_minutes` | threshold, default 30 when absent | **0 reaps on the first pass** — never set 0 in real config |
| `port` | endpoint probe for containers | absent means "running" alone counts as busy, so a wedged container is never reaped |
| `max_gpu_util_pct` | GPU util ceiling for `process` | a single low sample is not idleness |
| `recent_seconds` | warm-up guard; anything younger is spared | too small and a restarting daemon gets killed mid-boot |

Ship every entry with a `_why` string naming the evidence that put it in the list. A reaper entry
without a recorded reason is one nobody will dare to arm later.

## Busy/idle decision

`busy` is the safe default. A service is idle only when every probe agrees:

- **container**: not running → idle. Running but its `port` does not answer with an expected code
  (`200`/`401`/`204`/`302`) → idle (wedged, worth reaping). Running and serving → busy.
- **process**: not found → idle. GPU util above `max_gpu_util_pct` → busy. Age under
  `recent_seconds` → busy. Otherwise idle.

Idle time accumulates from the first pass that observes idle, stored in
`~/.local/state/rq/idle_since.json`. A busy pass deletes the entry, so a service that is busy once
starts its whole idle countdown again.

## Dry-run contract

`rq reap --dry-run` must be genuinely read-only: no `stop_service`, no write to `idle_since.json`.
It is the only safe way to inspect this on a machine you care about, so "dry-run" that mutates state
is worse than no flag at all. Assert in a self-check that the idle-state file is byte-identical after
a dry-run pass.

## Evidence that admission control works

Two runs, and show the log lines verbatim — not a description of them.

Over-admission refused (the real proof; substitute live numbers):

```
rq submit needs-8gb --gpu 8192 --ram 2048 -- sh -c 'echo SHOULD_NOT_RUN'
# log:
WAIT  needs-8gb: gpu free 193MiB < requested 8192MiB
```

Normal admission completed:

```
QUEUE(run) e2e-final :: sh -c 'echo HELLO_FROM_JOB'
START e2e-final pid=1359798 pgid=1359798 gpu=0MiB ram=0MiB cpu=1 [CPUQuota=100%] :: ...
DONE  e2e-final exit=0 in 2.0s
# job log:
HELLO_FROM_JOB
```

Also worth showing: `systemctl --user show rq.service -p MemoryMax --value` returning a real byte
count, which proves the cap is applied by the kernel and not merely documented.

## Debugging a daemon that ignores submitted work

"Client queued it, daemon never ran it" has exactly three causes. Check in this order.

1. **Split state path.** Compare what the client wrote against what the daemon opened:
   `find ~ -name queue.json -path '*<tool>*'`, then
   `tr '\0' '\n' < /proc/<daemon-pid>/environ | grep XDG`. Two `queue.json` files with different
   contents is conclusive. Fix: pin to a fixed per-user path, keep one test-only override.
2. **Stale code.** `ls -l /proc/<daemon-pid>/cwd`, compare the binary's mtime with the daemon's
   `ActiveEnterTimestamp`. A daemon started before your edit runs the old module forever.
3. **Lock held elsewhere.** `fuser -v <lockfile>`; `cat /proc/<daemon-pid>/wchan` and
   `cat /proc/<daemon-pid>/syscall`. `hrtimer_nanosleep` means it is in its poll loop (so the loop is
   raising and being swallowed); a flock wait means a second daemon holds it.

## Self-check registration

Discover checks by naming convention and assert the count is non-zero:

```python
CHECKS = [(n, f) for n, f in sorted(globals().items()) if n.startswith("t_") and callable(f)]
assert CHECKS, "no checks discovered — the suite would report a clean sheet while testing nothing"
for name, fn in CHECKS:
    check(name, fn)
```

For a single-file tool, load it under a private module name and **register it in `sys.modules`
before `exec_module`** — `@dataclass` resolves annotations via `sys.modules[cls.__module__]` and
raises `AttributeError: 'NoneType' object has no attribute '__dict__'` otherwise.

Run the suite at least three consecutive times before calling it stable: a race that shows up once
in three is the normal case for anything involving a daemon and a client.

## The `set -u` guard bug

A safety assert written as `case "$ALLOW" in *"$p"*) ...` aborts on an unset variable before any work
happens, so the guard provides no protection on its first and only run — and the failure presents as
a permissions error, not a logic error. Write it as:

```bash
readonly NEVER=( "/abs/path/one" "/abs/path/two" )
assert_not_protected() {
  local p="$1" pref
  case "$p" in /*) ;; *) log "ABORT: refusing relative path $p"; exit 1 ;; esac
  for pref in "${NEVER[@]}"; do
    case "$p" in "$pref"|"$pref"/*) log "ABORT: $p is protected"; exit 1 ;; esac
  done
}
```

Assert before **every** deletion, not once at start-up — a future edit that appends a target must fail
loudly on its own line.