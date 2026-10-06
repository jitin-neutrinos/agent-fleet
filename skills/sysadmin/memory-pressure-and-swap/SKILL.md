---
name: memory-pressure-and-swap
description: "Use when swap is full, RAM short, or a unit dies silently."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [memory, swap, zram, swappiness, performance, oom]
    related_skills: [storage-capacity-management, system-admin]
---

# Memory pressure and swap

Class-level skill for a Linux host whose swap is full, whose RAM looks exhausted, or which stalls
under load. Covers diagnosing whether full swap is a *capacity* problem or a *policy* defect,
draining swap safely on a live desktop, and the guardrail that stops it recurring.

The governing rule: **full swap with RAM to spare is a misconfiguration, not a shortage.** Those
two diagnoses have opposite fixes — one needs more memory, the other needs a lower
`vm.swappiness` — and reading the first as the second sends you shopping for hardware that was
never the problem.

## When to Use

Read this when any of these hold:

- Swap is at or near 100%, or `free -h` shows swap consumed while RAM looks free.
- The host stalls, hangs, or the desktop stutters and swap is suspected.
- A process appears to use far more memory than it should, and swap is implicated
  (`VmSwap` diverges sharply from RSS).
- Someone asks to add, resize, tune or "clear" swap, or to change `vm.swappiness`.

Do NOT use it for disk-space exhaustion — that is `storage-capacity-management`. Nor for a single
process leaking RAM where swap is uninvolved: find the process instead. If `SwapTotal` is 0 there is
nothing to drain, so confirm swap is configured at all before starting.

## Diagnose before touching anything

1. **Read the four numbers together, not swap alone.** From `/proc/meminfo`: `MemTotal`,
   `MemAvailable`, `SwapTotal`, `SwapFree`. Then the tunables:
   `sysctl vm.swappiness vm.vfs_cache_pressure`.
2. **Compute swap used and MemAvailable as percentages.** Exact KiB arithmetic, never rounded
   `free -h` output. A host can show "23 GiB swap used" and "39 GiB available" in the same glance —
   that pair *is* the diagnosis.
3. **Branch on the two states:**

| Swap used | MemAvailable | Diagnosis | Fix |
|---|---|---|---|
| high | plentiful | `vm.swappiness` too high — the kernel paged out working set for no reason | lower swappiness, then drain |
| high | low | genuine capacity pressure | find the holders, add/relieve memory |
| low | low | real, and swap is not the story | find the holders |

4. **Find the actual swap holders**, which is a different list from the RAM holders:
   `for p in /proc/[0-9]*; do s=$(awk '/^VmSwap/{print $2}' $p/status 2>/dev/null); [ -n "$s" ] && [ "$s" -gt 200000 ] && printf "%8.2f GB  %s\n" "$(echo "scale=2;$s/1048576"|bc)" "$(tr '\0' ' ' < $p/cmdline | cut -c1-70)"; done | sort -rn | head`
   Swap is dominated by long-lived daemons that were touched once long ago and never faulted back
   in — an MCP server, a lock-screen greeter, a headless app — so the list rarely matches what the
   user thinks is running.
5. **Check swap priority order**: `swapon --show=NAME,PRIO`. Higher priority is consumed first, so
   compressed RAM should outrank a disk file.

## Fixing the policy defect

- `sysctl -w vm.swappiness=10` and `vm.vfs_cache_pressure=50` for a big-RAM workstation. `100` is the
  kernel default and is wrong whenever RAM is plentiful — it will happily page out and thrash.
- **Persist it**, or it silently reverts on reboot: write `/etc/sysctl.d/60-<name>.conf` and run
  `sysctl --system`. Confirm by re-reading both the live value and the file.
- Raising swappiness is sometimes right (laptop, low RAM, fast resume). Do not lower it blindly on
  a host that genuinely wants aggressive caching — check `MemTotal` against the workload first.

## Lowering swappiness does NOT reclaim what is already swapped

This is the most commonly misread outcome of the whole diagnosis, and it invalidates the obvious
next step. `vm.swappiness` governs only the kernel's *outgoing* decision about what to page out. It
has no effect on pages already in swap. After you set it to 10, swap usage stays exactly where it
was — often back at 100% within minutes — while `MemAvailable` climbs and `Cached` drops to near
zero. That combination looks like the fix failed. It did not; nothing has re-read those pages yet.

**Linux never proactively faults cold pages back into RAM.** There is no timer, no threshold, and
no daemon that does this. A process's swapped pages return only when it *actually touches* them. A
request/response daemon — an MCP server, an HTTP API, an idle inference endpoint — touches nothing
between calls, so its swapped pages can sit there indefinitely no matter how much RAM is free.

So the honest answer to "is it draining naturally?" is **no, and it never will be on its own**. Do
not wait on it, and do not re-tune `vm.swappiness` a second time hoping for different luck.

The only ways to actually reclaim a specific process's swap, in order of preference:

1. **Restart the service.** Instant and complete, and for a request/response daemon the downtime is
   the gap between calls — usually invisible to callers. This is the right fix. It is a service
   restart, so ask first, and prefer the process with the largest `VmSwap` rather than the largest
   RSS.
2. **Force fault-in by writing.** Writes fault pages in; reads do not. Read the process's writable
   private anonymous mappings from `/proc/<pid>/mem` and rewrite each page with its existing value
   (`mem.seek(addr); b=mem.read(1); mem.seek(addr); mem.write(b)`). This demonstrably works — RSS
   rises and swap falls by the same amount — but it runs at roughly 200 MB/min, so a 4 GB holder
   needs ~20 minutes, and it perturbs a live process's memory. Read-only probing of the same
   mappings moves nothing; that is expected, not a failed test.

There is no global lever. After fixing the worst holder, expect the rest to still be swapped and say
so, because "swap is fixed" implies a system-wide effect that does not exist.

Verify the fix with the number the user cares about: swap used before → after, and the reclaimed
process's new `VmSwap` (0.00 GB right after a restart proves it worked).

## Draining swap safely on a live desktop

Order is fixed. Skipping a step is how a swap cycle turns into an OOM kill.

1. **Compute headroom first and abort if there is not enough.** Pulling swap back in costs real
   RAM. Require roughly the swap-in size plus a margin:
   `awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}/SwapTotal/{st=$2}/SwapFree/{sf=$2}END{printf "%.2f GB avail, %.2f GB to pull in, %.2f GB headroom\n", a/1048576,(st-sf)/1048576,(a-(st-sf))/1048576}' /proc/meminfo`
   Abort below ~9 GB available. A `swapoff` that runs the machine out of RAM is worse than full swap.
2. **One device at a time, never both.** Disabling everything at once removes the fallback that makes
   the operation survivable.
3. **`sync`, then `swapoff <one device>`.** Expect minutes, not seconds — draining 16 GB of
   disk-backed swap took over three. Set a generous timeout and do not kill it mid-flight.
4. **For zram, size the real cost correctly.** Read `/sys/block/zram0/mm_stat`: field 1 is the
   original (decompressed) data size, which is what swap-in will cost in RAM. zram holding 7.27 GB
   in 3.13 GB means draining it costs ~7.3 GB of RAM, not 8.
5. **Re-enable with matching priority.** `swapon -p 100 /dev/zram0` for compressed RAM (fast) and
   `swapon -p -2 /swap/swapfile` for the disk file (slow), so the fast device absorbs pressure first.
   Keep `/etc/fstab` priorities consistent or a reboot reorders them.
6. **A reset zram device is not a swap device.** After `echo 1 > /sys/block/zram0/reset`,
   `swapon` fails with `read swap header failed` until the device is recreated. Check whether the
   distro's zram is managed by a systemd generator (`systemd-zram-setup@zram0.service` running
   `zram-generator --setup-device`) — if so, the generator owns setup and a manual `reset` has
   bypassed it, so recreate the swap area before re-enabling.

## Guardrail

A guard that silently cycles swap under load is how a slow machine becomes a frozen one. The guard
should **detect and escalate, never drain**. Thresholds: warn ~40% swap used, escalate ~80%, and
treat "swap ≥80% while MemAvailable ≥25%" as an explicit *misconfiguration* alert naming
`vm.swappiness`, because that pairing is the diagnostic signature of the policy defect above.

Prove the guard fires before trusting it: temporarily restore the bad tunable, run the guard, and
confirm the alert line appears, then restore the correct value. A guard that has never been seen to
alert is an untested assumption.

Schedule it with a systemd timer (`OnUnitActiveSec=30min`, `Persistent=false`) so it survives
reboots and writes to `~/.local/state/<name>.log`. Report per-step real outcomes — a guard that
logs "OK" while the condition persists is worse than no guard.

## Pitfalls

- **When a chat/agent/daemon session vanishes mid-run with no error shown to the user, sweep the system/kernel journal for `oom-kill`/`systemd-oomd killed` in the incident window BEFORE opening a bug path on the app itself — it saves a full dive into streaming/transport internals.** A memory-pressure kill of a unit that is otherwise healthy produces exactly the user-visible shape of a silently dropped connection (turn stops, no explanation). Map the cgroup named in the OOM/OMM line to its unit (with `oom-kill:` on the kernel line or `oomd killed` on the systemd one), then attribute; only when no OOM is found in the window is it a transport/UI problem.
- **Never drain both swap devices in one command.** Sequential, with a headroom check between, or
  accept an OOM kill as a possible outcome.
- **zram swap-in costs its decompressed size, not its on-disk size.** Reading `mm_stat` field 3
  (memory actually used) instead of field 1 (original data) underestimates the RAM needed to drain.
- **A drained swap device stays drained across the session unless you re-enable it.** Finishing with
  swap off removes headroom you had before; re-enable with the intended priorities and verify.
- **`/dev/zero` probes lie on compressing filesystems.** Use `/dev/urandom` and `sync` between steps
  when measuring whether a delete or a write actually moved blocks.
- **Full swap is frequently blamed on the biggest RAM consumer, which is usually wrong.** Attribute
  with the per-process `VmSwap` walk before proposing to kill anything; the largest RAM process and
  the largest swap process are frequently different daemons.
- **Long-lived MCP servers and lock-screen greeters dominate swap.** They hold swapped pages
  indefinitely without being busy. Restarting the worst holder is often cheaper than any capacity
  change, but it is a service restart — ask first.
- **Report swap recovery in the units the user saw.** "23.41 GB used → 1.3 GB of 23 GB, available
  609 MB → 22 GB" lands; "swap cycled successfully" does not.
- **A process can hold 4 GB of swap and 0.67 GB RSS while being perfectly healthy.** That ratio is
  what cold-but-running looks like, not a leak. Confirm liveness before blaming it: check the
  listener is still bound, count established sockets, and sample CPU ticks across ~20s. A live
  service with 3 connections and a bound port that burned 2 ticks in 20s is idle, not broken —
  and its swap will not return without a restart.
- **Never `pgrep -f` a pattern your own shell command line contains.** The probe matches the shell
  running the probe, so you "measure" your own process and conclude the target holds 0.00 GB. Filter
  the grep/bash wrapper out, or walk `/proc` and print the resolved cmdline so you can see which PID
  is which before believing the number.
- **A service can report active while its port is not yet listening.** Model-loading daemons spend
  seconds to minutes fetching weights before binding. Wait for the log line that names the bind
  (`Uvicorn running on …`, `Router ready`) before declaring it unhealthy, and verify with a real
  request rather than a bare connect check.
- **A 401/unauthorized response from a local MCP endpoint proves it is serving.** Auth rejecting you
  means the app is up, routing, and enforcing credentials. Treat it as a liveness signal and continue
  to the authenticated call rather than reporting the service down.

## References

- `storage-capacity-management` — the neighbouring class. Disk/snapshot space exhaustion; its
  `btrfs-snapshot-audit.md` covers why a large delete can free no space at all, and the
  id-based snapshot-deletion loop that actually works when the tool path fails.
- `local-resource-scheduler` — the neighbouring class for queuing/reaping GPU/RAM/CPU work. Reached
  when jobs (not services) hold VRAM, or when an idle-service stop needs an explicit owner check.
- `system-admin` (user-owned) — general admin command surface. Run
  `hermes curator adopt system-admin` to let this curator maintain it.