---
name: nobara-health-audit
description: >-
  10-area read-only health audit for Nobara hosts.
---

# Nobara Health Audit

## Caveman skill always active (terse; substance kept; warnings plain English)
## Ponytail skill mandatory for any coding — lazy-senior-dev ladder, root cause, one runnable check

### Scope
Read-only diagnostics on Nobara/Nobara-derived Linux host only. Container (ComfyUI, localgen) is out of scope for this skill.

### Standing constraints (every item)
- Never write to, resize, or reformat the NTFS mounts (`/run/media/notjitin/` or `/media/notjitin-ai-models`) or `/boot/efi`.
- `dnf remove` / `dnf autoremove` are destructive: propose, wait for explicit yes, never batch with other ops.
- No reboot is scheduled or triggered automatically. Reboots happen only when the user says so, and only with AI workloads idle.
- `dnf check-update` is allowed (read-only). `dnf upgrade`/`distro-sync` is NOT.
- Sudo: passwordless sudo is not available. Ask the user for the password, then run each command as `echo '<pw>' | sudo -S <cmd>`. Never write the password into files, scripts, or the journal.
- Background workers (generation scripts, long polls) die when the Hermes gateway restarts. Before relying on a 'running' worker after any interruption, confirm its output artifacts (files written) are actually increasing — process existence alone is not proof of progress.
- Long-running multi-step scripts must be saved as repo files and be resumable from on-disk state, never only inline heredocs — scratch-only scripts vanish with the session and cannot be relaunched.

---

## 10-Area Health Audit Procedure

Perform each check in order. Record findings in `~/scratch/health-audit.md`. All commands are read-only unless noted.

### A. FAILED/CRASHING UNITS
```
systemctl --failed
systemctl --user --failed
journalctl -p err -b --no-pager | tail -60
journalctl -p 3..4 -b --no-pager | grep -viE 'audit|bluetooth' | tail -40
```
Severity: CRITICAL = broken now, WARN = degrading/latent, INFO = worth knowing.

### B. OOM / KERNEL ISSUES
```
journalctl -k -b --no-pager | grep -iE 'oom|segfault|gpu|nvidia error|xfail|call trace' | tail -30
dmesg | grep -iE 'error|fail' | tail -20
```

### C. DISK
```
df -h   # flag >85% any mount
df -i   # inodes
sudo btrfs filesystem usage /   # if btrfs
sudo smartctl -H /dev/nvme0n1 /dev/sda 2>/dev/null || echo smartmontools not installed
```

Disk pressure on this class of host is almost never `state.db`. Attribute the bytes
before proposing a fix — see `references/disk-reclaim.md` for the full procedure
(duplicate-build detection, uv/HF cache reality checks, and the move-vs-delete
decision). The short version:

1. **Rank consumers before touching anything**: `du -sh ~/Work ~/.cache ~/.hermes` then
   per-child. Reclaim proposals that skip this step usually target the wrong 800 MB.
2. **A second mount is the answer, not more pruning.** `df -h` every mount first —
   a separate disk with hundreds of GB free is where cold data belongs.
3. **Free space that does not move after a real delete is a measurement question, not a
   failure.** Check `lsof +L1` (deleted-but-open) and whether the FS is btrfs. On the
   zstd-compressed btrfs root, `du` LOGICAL >> physical: a "17 GB" code tree may free
   less than 2 GB. Report and predict in df-free-space terms, never du terms.

### D. MEMORY/PRESSURE
```
free -h
top --sort=-%mem | head -11
cat /proc/pressure/memory /proc/pressure/io 2>/dev/null
```
Swap usage also noted. Interpret: swap full + free RAM + near-zero PSI = stale pages, not current pressure (pitfall 12). When zram is active, also check zswap (pitfall 13).

### D2. CPU HOGS — attribute before acting
```
ps aux --sort=-%cpu | head -12
```
Interpret before killing:
- **A service showing high `ps` %CPU may be burst-on-use, not a runaway loop.** `ps`
  %CPU is averaged over the process lifetime. Confirm with `top -b -H -n1 -p <pid>`
  (per-thread, instantaneous): all threads sleeping at 0.0% = the process is idle now
  and the average is just heavy past usage — audit the logs for what consumed the time
  instead of restarting it as a 'fix'.
- **Headless agent-browser chromium instances** (`--user-data-dir=...agent-browser-chrome-*`)
  are session tooling leftovers: safe to kill, but they respawn — re-check with
  `pgrep -fc agent-browser-chrome` after a delay and keep the one belonging to the
  current session.
- **plasmashell running hot for days** is a glitching desktop shell, not a bug to
  debug: `systemctl --user restart plasma-plasmashell.service` (user-level, safe).
- **Do process KILLS from execute_code, not terminal.** `kill -9 $(pgrep -f PAT)`
  from shell can terminate the executing shell itself when the PAT matches its own
  command line. In execute_code: `for p in $(pgrep -f PAT): os.kill(p, 9)` — the
  Python process matches no pattern it kills.

### E. PACKAGE INTEGRITY
```
rpm -Va 2>/dev/null | grep -vE 'S\.5|missing.*doc' | head -30
sudo dnf check 2>&1 | head -20
dnf list extras 2>&1 | head -10
dnf repoquery --unneeded 2>/dev/null | head -15
```

### F. UPDATES HELD BACK
```
dnf check-update 2>&1 | tail -20
```
Read-only check. Do NOT update.

### G. SERVICES
```
systemctl list-timers --all | grep -i fail
coredumpctl list --no-pager 2>/dev/null | tail -15
coredumpctl info --no-pager 2>/dev/null | grep -E 'Command Line|Signal|Counter' | head -20
```

### H. NETWORK
```
ip -br addr
resolvectl status | head -15
ss -tlnp 2>/dev/null | head -20
```

### I. NVIDIA STACK
```
nvidia-smi
cat /proc/driver/nvidia/version 2>/dev/null
systemctl status nvidia-persistenced 2>&1 | head -5
```

### J. LOG DISK USAGE
```
du -sh /var/log 2>/dev/null
journalctl --disk-usage
```

### K. AGENT ACTIVITY DATA (usage-report source of truth)
When the audit includes "how is the agent being used" questions, pull numbers from
the live databases — never from the token tracker's aggregate row (known-broken:
$0.00 cost, zero output tokens; per-harness rows only).
- Sessions/messages/tool-calls by surface: read-only attach of
  `~/.hermes/state.db` (`sessions`: source, message_count, tool_call_count,
  started_at epoch; `session_model_usage`: per-model calls/tokens, `task=''` rows
  are the main task). Open with `file:...?mode=ro` URI — never open the live DB
  read-write from a report.
- Memory growth/topics: `~/.hermes/memory_store.db` (`facts` table,
  `created_at`/`retrieval_count`/`category`).
- Cron health: `~/.hermes/cron/executions.db` (`executions` by job_id + status).
- `sqlite3` CLI is not installed on this host; use python3 `sqlite3` module.
- Never run an unbounded recursive directory walk from a report cell — it exceeds
  the execution timeout. Use bounded `find -maxdepth` in terminal instead.
- Costs from these DBs are estimates (subscription models record partial
  usage); label them as estimates in the report.

---

## Severity ratings (per finding)
- CRITICAL = broken now, requires immediate attention
- WARN = degrading/latent, worth tracking
- INFO = worth knowing, no immediate action


## Pitfalls & Gotchas
1. **System updates**: only via `nobara-sync` (e.g. `nobara-sync install-updates`), never bare `dnf upgrade`. It groups transactions Kernel → Graphics → Core → Desktop → Non-essential with per-group rollback.
2. **btrfs swapfile**: must use `btrfs filesystem mkswapfile`, NOT `fallocate` + `chattr +C` (that path corrupts if file already extended). Persist via fstab line `/swap/swapfile none swap defaults,pri=-2 0 0` — lower priority than zram so zram fills first.
3. **NTFS mounts**: never touch `/run/media/notjitin/` or `/boot/efi` beyond read-only listing.
4. **Baloo indexer**: errors drown other logs; rewrite `~/.config/baloofilerc` with explicit include/exclude paths and restart the indexer before blaming other sources.
5. **rpm -Va**: many benign entries (doc S.5, missing doc); filter with `-vE 'S\.5|missing.*doc'`.
6. **zram pinned full**: add a disk-backed swapfile; do not grow zram (it consumes the RAM you are protecting).
7. **Failing XDG autostart entries**: mask at user level — copy the .desktop from `/etc/xdg/autostart/` to `~/.config/autostart/` with `Hidden=true`, then `systemctl --user reset-failed`. Survives package updates, unlike deleting the system file.
8. **smartmontools check**: `smartctl -H` on each disk; enable `smartd` for continuous monitoring. If no local MTA, prefer a weekly systemd timer running smartctl into the journal.
9. **A plain `dnf install` can pull a PENDING NVIDIA driver upgrade into the transaction.** If the running kernel module is older than the userspace it brings in, NVML breaks (`Failed to initialize NVML: Driver/library version mismatch`) and every new GPU client fails with it — while already-running processes keep working, so the symptom looks unrelated to the install you just ran. Before any install: `sudo dnf5 install --assumeno ...` and read the transaction; when installing build dependencies or toolchains, exclude the driver explicitly: `--exclude='nvidia-*' --exclude='libnvidia-*'`. Repair without a reboot using **explicit** version specs, because plain `dnf5 downgrade` picks the previous *repo* version rather than the version that was installed:
   ```
   sudo dnf5 downgrade -y nvidia-driver-libs-<ver> nvidia-driver-<ver> libnvidia-ml-<ver> \
     dkms-nvidia-<ver> nvidia-kmod-common-<ver> ...   # same <ver> for every package
   nvidia-smi --query-gpu=driver_version --format=csv  # confirm userspace
   ```
   If the upgrade has already been taken, a reboot is the other consistent state (module and userspace then match). Accepting it is not free: a driver upgrade needs an idle GPU and a reboot, so schedule it deliberately rather than discovering it mid-task.
12. **Swap 100% full while RAM sits free is stale swap, not pressure** — pages pushed out during an earlier crunch are never pulled back voluntarily (the kernel will not pay to move them). Confirm memory PSI ~ 0 and `available` > swap used, then drain with `sudo swapoff -a && sudo swapon -a`. Do NOT treat it as a reason to lower swappiness: with zram-first swap, high swappiness is the design (zram is RAM-speed), and lowering it fights the tiering.
13. **Check zswap whenever zram is active** (`/sys/module/zswap/parameters/enabled`): both on means every swapped page is compressed twice, wasting CPU on a redundant zstd pass. CachyOS disables zswap by udev rule when zram runs — verify the rule actually applies before assuming. Fix: `zswap.enabled=0` (runtime test first, persist on cmdline at next reboot).
14. **"Cache" is usually not cache.** Before promising reclaim, walk the store and
    prove each entry is replaceable. HuggingFace `hub/blobs` is sharded two levels
    (`blobs/ab/cdef…`) and referenced by symlinks under `models--*/snapshots/`; walking
    only the top level reports every blob as orphaned and you will delete live model
    weights. Resolve `os.path.realpath` of each snapshot symlink into a reference set,
    then compare. `uv cache prune` takes a shared lock held permanently by long-lived
 `uv tool uvx` MCP daemons — it exits "Cache is currently in-use" forever, and a
 cleanup script that swallows that error will report success for months while the
 cache grows. `--force` is what actually proceeds. `npm cache clean` does NOT touch
 `~/.npm/_npx`; those dirs are per-invocation installs that need their own
 reference check via `/proc/<pid>/cmdline`.
 14b. **Grep `systemctl cat` Environment= lines before deleting anything under a project
 dir.** A checkpoint/venv named in a service unit env var is live runtime data, not
 rebuildable cache — deleting it crashes the service and forces a retrain/rebuild.
 14c. **`docker system df` "reclaimable" counts images pinned by running containers.**
 Check `docker ps -a` status before deleting; respect `rmi`/`volume rm` in-use
 refusals (staging/monitoring stacks are running services, not junk).
15. **A scheduled cleanup that always reports zero freed is a broken script.** Read its
    log for the per-step lines before trusting the run. A "skip on lock busy, log
    success" branch is worse than no timer: it looks like a working policy.
16. **Age thresholds never catch a fast leak.** `find -mtime +1` skips anything written
    within the last day, so a test harness emitting a multi-hundred-MB artifact per run
    is invisible to it. Look for near-identical sibling directories (per-run IDs in the
    name) and for the newest one's mtime — if it is minutes old, nothing age-based will
    ever catch it, and the fix belongs at the writer (point it at `TMPDIR`), not the sweeper.
17. **`du` on a btrfs mount can be smaller than `df` free-space implies for good
    reason.** Check `btrfs filesystem usage <mount>`: `allocated`, `used`, and
    `free` must reconcile against device size. If they do, nothing is hidden and the
    bytes really are still on disk — find the writer. If `allocated` far exceeds
    `used + free`, freed extents have not returned to the pool and a balance is needed
    (check this btrfs version's supported filters; older builds reject
    `--usage-filter` and only accept `--full-balance`).
18. **Do not trust a `mv`-based move across filesystems.** `mv` across devices is a
    copy+delete, and a partial failure leaves the source half gone. Always
    `rsync -a` then prove with `rsync -a --dry-run --checksum --itemize-changes`
    (expect zero differing files), run a real binary from the new path, and only then
    remove the source. For a directory nothing else references, leave a symlink at the
    old path so any latent absolute-path consumer keeps working.
19. **Before moving a project tree, count what binds to it.** Grep systemd units,
    docker compose bind mounts, crontabs, and shell rc files for the absolute path.
    Count processes whose `cwd` or `exe` is inside it. Absent env vars, unit edits,
    path rewrites in source, and compose updates are the real cost of a move — and a
    running server whose exe lives in the tree (e.g. `target/release/`) makes the move
    a stop-service operation, not a file copy.

---

## kurama-core AI stack (applied 2026-10-02)
- Fine-tune venv `~/.venvs/ai-finetune` (python 3.14, system-site-packages): own torch 2.12.1+cu130 (pip resolved it; inherited 2.14 NOT reused for unsloth), unsloth 2026.9.14, liger-kernel 0.8.4, trl/peft/bnb/xformers. Verified end-to-end (GPU matmul, pinned mem, bnb 4-bit, liger train step) via `~/scratch/ai-stack-verify.sh`.
- Isolation rule: venv never touches `~/.local/.../python3.14` user-site (ComfyUI runs from there, torch 2.14.0+cu130) — pip correctly refuses to uninstall cross-env; keep it that way.
- memlock unlimited: `/etc/security/limits.d/99-ai-memlock.conf` + `~/.config/systemd/user/user.slice.d/memlock.conf`. GPU power limit 300W (reset at reboot; reapply `sudo nvidia-smi -pl 300`).
- CUDA toolkit 13.4 (system nvcc at /usr/local/cuda/bin, NOT on PATH): installed via nvidia cuda-fedora44 repo. Driver must be excluded in the transaction: `--exclude='nvidia-driver*' --exclude='dkms-nvidia*'`. GOTCHA: the repo's GPG key filename is UPPERCASE `73CD9B30.pub` (lowercase 404s); always fetch NVIDIA's own cuda-fedora44.repo rather than hand-writing from older-distro templates. Verified by compiling+running a checked sm_89 CUDA binary.
- GOTCHA: `echo pw | sudo -S tee <<heredoc` breaks sudo auth (heredoc feeds stdin, eats the password). Write file to scratch, `sudo cp` instead.

## kurama-core kernel-opt state (applied 2026-10-02)
- zswap DISABLED (was double-compressing over zram): `zswap.enabled=0` persisted via `grubby --update-kernel=ALL --args=...`, runtime off too. Don't re-enable while zram is the primary swap.
- scx_lavd: DISABLED 2026-10-03 (user decision). It was ejected by the kernel watchdog on 2026-10-02 ("runnable task stall", cargo failed 31s) — an upstream scx 1.1.3 bug on kernel 7.2.x (Bazzite #5527, claudeos known-issues corroborate). `systemctl disable --now scx_loader.service`. EEVDF is the intended default. If retrying later use scx_bpfland, not lavd, and soak >=10 min — a 25s check missed a 31s stall.
- LESSON: after enabling any watchdog-governed service (sched_ext, sanoid, etc.), verify the state file AND soak well past the watchdog timeout; "active in systemctl" is not proof it is healthy.
- Self-check: `bash ~/scratch/kernel-opt-check.sh` (updated 2026-10-03; asserts INTENDED state: loader disabled, no BPF sched attached, zswap off, swap sane, GPU power limit reported; grubby check auto-SKIPs without sudo pw).

## Output file
`~/scratch/health-audit.md` — markdown, one-line system summary, then table of findings (severity | area | finding), then per-finding detail with actual command output quoted, then recommended-fixes list (do not apply).

<!-- canvas-output:start -->
## Canvas output

A report is a card with `"page":"a4"`, so it renders as the page it exports as: `badges` for state, `kpi` for what changed, `steps` or `timeline` with done/active/todo/fail, `progress` for coverage or budget, `checklist` for shipped vs deferred, one `callout` for what needs attention. Failures sit in the same card as successes.
<!-- canvas-output:end -->
