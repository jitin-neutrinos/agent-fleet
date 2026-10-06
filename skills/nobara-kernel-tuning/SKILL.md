---
name: nobara-kernel-tuning
description: >-
  Nobara kernel tuning research; findings-only until approved.
version: 1.0.0
author: kurama-core
license: MPL-2.0
metadata:
  hermes:
    tags: [nobara, kernel, performance, sysadmin]
    related_skills: [nobara-health-audit, nobara-manager]
---

# Nobara Kernel Tuning

## When to Use
- User asks what kernel/performance optimizations are possible on a Nobara host ('research kernel optimization', 'what can we tune').
- Before proposing any CPU/memory/scheduler change on Nobara. Findings-only until the user approves a specific item.

## Caveman skill always active (terse; substance kept; warnings plain English)
## Ponytail skill mandatory for any coding — lazy-senior-dev ladder, root cause, one runnable check

### Scope
Kernel/CPU/memory/scheduler/I-O performance research and tuning on Nobara hosts. Findings-only by default — the user asks for research first and decides per-finding. Complements `nobara-health-audit` (periodic 10-area sweep); use this when the ask is 'what can we optimize'.

### Standing rules (every instance)
- Recon and research are read-only. No sysctl writes, no cmdline edits, no service toggles until the user approves a specific finding.
- Kernels update only via `nobara-sync install-updates`, reboot only when the user says so with AI/GPU workloads idle. Never propose hand-built/LTO/-O3 custom kernels — they orphan nobara-sync and break the NVIDIA dkms module match.
- Never touch NTFS mounts or /boot/efi (read-only listing only).
- Deliverable: findings doc in `~/scratch/<topic>-findings.md` — ranked findings each with quoted command evidence, an explicit REJECT list with reasons, and a 'suggested order if go' list. Plain-English summary in chat; paths/flags live in the file.

### Procedure
1. **Recon (one or two batched terminal calls, all read-only).**
   - Identity: `uname -a`; `lscpu`; `free -h`; `zramctl`; `swapon --show`; `cat /proc/cmdline`; `nvidia-smi --query-gpu=name,driver_version,persistence_mode,pstate,power.draw --format=csv`.
   - CPU/VM: governor + `scaling_driver` + `intel_pstate/status` + `no_turbo`; EPP current/available; microcode (`grep microcode /proc/cpuinfo`); vulnerability headline; sysctl `vm.swappiness vfs_cache_pressure dirty_* max_map_count`; THP mode; `/proc/pressure/*`.
   - Kernel config: `zgrep -E 'SCHED_CLASS_EXT|LRU_GEN|ZSWAP|HZ_|PREEMPT' /proc/config.gz`; sched_ext state via `ls /sys/kernel/sched_ext`.
   - Stack: power daemons (`thermald tlp power-profiles-daemon tuned`), `systemctl is-active scx_loader nvidia-powerd`, I/O schedulers per block device, btrfs mount opts (`findmnt -T /`), pending kernel (`dnf check-update 'kernel*'` — read-only, allowed).
2. **Research.** Nobara wiki kernel-modifications page (what upstream already does/disables), CachyOS wiki (general tweaks + sched-ext — Nobara rides the CachyOS kernel), kernel.org intel_pstate docs, sched_ext/scx scheduler ecosystem for latency levers. GitHub MCP may stall on device authorization — fall back to `web_search` with `site:github.com` queries instead of retrying the MCP.
3. **Classify each candidate as TUNE or REJECT** using `references/kernel-tuning-decisions.md` — do not re-derive; extend that file if research surfaces a new lever.
4. **Report** per the deliverable contract above, run `done_gate(claims, evidence)` with the commands actually run, and stop. Await per-finding go.

### Pitfalls
- **Swap 100% full with plenty of free RAM and near-zero PSI is stale swap, not pressure** — the kernel never voluntarily pays to pull pages back after a past crunch. Guard (`available > swap used`), then `sudo swapoff -a && sudo swapon -a` drains it. Do not answer this with a swappiness change (see reject list).
- **Check zswap whenever zram is active** (`/sys/module/zswap/parameters/enabled`): both on means every swapped page is compressed twice. CachyOS normally disables zswap by udev rule when zram runs — verify, don't assume.
- **`powersave` governor + EPP `performance` under intel_pstate/HWP is the correct desktop combo** — the governor name is misleading (it is not the generic powersave); don't 'fix' it to the performance governor.
- **`pcie_aspm=off` on a mains-powered desktop is a deliberate latency trade** — don't flag it as a problem.
- **GPU parked at a high P-state with high idle draw**: check `nvidia-smi --query-compute-apps` for a resident AI job before flagging idle power as a tuning issue.
