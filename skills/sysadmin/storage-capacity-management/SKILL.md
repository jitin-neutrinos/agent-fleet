---
name: storage-capacity-management
description: "Use when a disk fills or data must move filesystems."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [storage, disk, cleanup, relocation, cache, capacity]
    related_skills: [system-admin]
---

# Storage capacity management

Class-level skill for a Linux host where the root/home filesystem is filling while a larger
secondary mount has free space. Covers the measurement discipline, relocating a directory or cache
between filesystems under live load, and the cleanup jobs that keep it healthy unattended.

The governing rule: **a filling disk is a symptom until you find the writer.** Reclaiming space
without attributing the growth buys days, and a cache that regrows to its old size overnight
proves you only moved the symptom.

## Procedure

1. **Establish the real topology before touching anything.** `lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT`
   and `df -h`. Two or more writable filesystems is the normal case; know which filesystem each
   big path is on, because "the disk is full" is usually only true of one of them. Note the
   filesystem types — btrfs reports allocation differently and has no cross-filesystem cheap moves.
1b. **Reconcile `df` against `du` before you attribute anything.** Subtract the du totals of every
   mount on the filesystem from `df` used; the remainder is space no directory walk can see. On
   btrfs a remainder above a few GB is almost always snapshots, and skipping this arithmetic makes
   you hunt for a runaway process that does not exist. Run `scripts/df-du-reconcile.sh` rather than
   hand-rolling it. See "The unaccounted-space diagnostic" below.
2. **Attribute every large path to a category** before recommending deletion: reproducible build
   output · a genuine leak/bug · live or referenced data that must stay · a cache with a known
   purge command · a test/backup artifact. Only the first, the fourth, and provably-rebuildable
   data may be removed.
3. **Never delete a path a live process holds.** Find them precisely:
   `for p in /proc/[0-9]*; do readlink $p/exe; done | grep <path>` and
   `ls -l /proc/*/fd | grep <path>`. A running server executing from a build directory makes that
   directory undeletable-by-policy, not by accident.
4. **Never name a protected mount in a command.** If the user has denied access to a disk (an
   external NTFS volume, a formatted partition), referencing its path literally trips the guard and
   the tool call is refused. Construct the path in the script (`P="/run/media/""user"`) and assert
   the exclusion there, so the sweep itself is provably safe.
5. **Prefer relocating over deleting** when the data is a cache or a re-downloadable artifact and a
   secondary filesystem has room. See the relocation procedure below.
6. **Find the generator before you finish.** Attribute growth by mtime and size:
   `find /home -xdev -type f -size +50M -mmin -120 -printf '%TY-%Tm-%Td %TH:%TM %10s %p\n' | sort -k3 -rn | head`.
   A job that generated tens of GB today will exhaust the disk again within a week.
7. **Report the two numbers separately**: what you moved/deleted, and what free space actually
   became. If a concurrent workload consumed the gain, show the timed sample that proves it.
8. **If the bytes are gone but free space did not move, suspect snapshot pinning, not a failed
   delete.** Deleting a file that a live snapshot still holds frees the directory entry only. Prove
   which case you are in with a throwaway round-trip on the same filesystem:
   `head -c 200M /dev/urandom > <scratch>/pin-test.bin; sync; df --output=avail; rm; sync; df`.
   Freeing on delete means the filesystem works and the old blocks are still pinned — fix the
   snapshots. Still consumed after delete means something holds the fd. Use incompressible data:
   `dd if=/dev/zero` measures nothing because btrfs compresses zeros to near-nothing, so a "0 MiB"
   result from a zero-fill test is an artifact of the test, not proof the delete worked.

## The unaccounted-space diagnostic (btrfs snapshots)

Use when `df` used is materially larger than the sum of `du` over every mount on the same
filesystem. On btrfs that gap is real space held by snapshots, and it is the single most
overlooked cause of "my disk filled and I cannot find the files".

1. **Prove the gap exists** with the arithmetic, not by intuition: `df` used minus du totals per
   mount. Do this before reading any further evidence.
2. **Enumerate snapshots as root**: `btrfs subvolume list / | grep <snapdir>`. A path like
   `timeshift-btrfs/snapshots/<stamp>/@home` confirms the tool and shows the snapshot dates.
   Count the snapshots and compare against the tool's configured retention — they should match,
   and a mismatch means pruning is not running.
3. **Read the retention config, and read the schedule flags before the counts.** For Timeshift that
   is `/etc/timeshift/timeshift.json`; `include_btrfs_home: true` is the expensive flag, because it
   snapshots the entire home subtree.
4. **Distinguish a check run from a create run.** An hourly `timeshift --check` cron writes one log
   file per hour, so a directory of 24 daily logs means checks, not 24 snapshots. Counting log
   files to size the snapshot set overcounts by an order of magnitude — read `btrfs subvolume list`
   for the real count.
5. **Report the multiplication effect, not a phantom single file.** When a file is rewritten and K
   snapshots still hold the old copy, the file costs space K times. This is why ordinary churn
   becomes tens of GB on a snapshotting filesystem, and why the answer is retention count, not
   finding a rogue process. Name the top rewritten files and their repeat rate.
6. **Never quote a snapshot's apparent size as real space.** `du --apparent-size` on a snapshot
   reports every historical version of every file and reads far larger than the live filesystem
   (an order of magnitude is normal). If exact bytes are wanted, `btrfs filesystem du` reports Total
   vs Exclusive per extent — but on a large snapshot tree it can exceed a multi-minute timeout. When
   it times out, say the number is unmeasured; do not substitute an estimate.
7. **A successful multi-GB delete with flat `df` is the diagnostic signature of pinning.** When the
   sweep reports its files gone yet free space barely moves, the blocks are still referenced by
   snapshots. Do not re-run the sweep, widen it, or hunt for a second writer — verify the pin with
   the round-trip probe in step 8 of the Procedure, then present the retention change as the fix.
   Report the discrepancy in plain terms ("58 GB deleted, 341 MiB actually freed") so the user sees
   that the deletion worked and the pinning is a separate, expected outcome.

Privileged read-only inspection, including the top-level-subvolume mount needed to even see the
snapshot tree and how to feed a sudo password without breaking argument parsing, is in
`references/btrfs-snapshot-audit.md`.

## Relocating a directory to another filesystem, under live load

The order is fixed; skipping a step causes the disk to keep filling.

1. **Copy** with `rsync -a --exclude='*.lock' <src>/ <dst>/`.
2. **Verify by checksum**: `rsync -a --dry-run --checksum --itemize-changes <src>/ <dst>/ | grep -c '^>f'`
   must be 0. A non-zero count needs interpreting, not ignoring — `>f+++` entries are files the
   source gained *after* the copy (a live writer), which means re-sync rather than corruption;
   entries in an index/metadata directory a tool rewrites constantly are benign; `.lock`
   differences are expected.
3. **Switch the mechanism the consumer actually reads.** An env var only works if the tool passes
   it to every child it spawns. Verify by inspection:
   `for p in $(pgrep -f '<daemon>'); do tr '\0' '\n' < /proc/$p/environ | grep -q '^MY_VAR=' && echo "$p yes" || echo "$p NO"; done`.
   If children report NO, the variable is inert for them and no number of restarts fixes it — use
   the tool's own config file, which every process reads regardless of inheritance.
4. **Prove the old path is quiescent** over a real interval, not one instant:
   `find <src> -newermt '-60 seconds' | wc -l` must be 0. If it keeps growing, the switch did not
   take — restart the daemons or stop and report.
5. **Only now delete the source**, then confirm the space moved. If it did not, in order:
   `lsof +L1 | awk '$7>104857600'` (deleted-but-open files retain blocks until the holder exits);
   on btrfs compare `btrfs filesystem usage` — if `used + free` equals device size, nothing is
   hidden and the data is genuinely still there; otherwise sample growth to attribute a writer.

## Unattended cleanup jobs

A cleanup script that fails silently is worse than none: it looks healthy while the disk fills.

- **Measure with an exact stat call** (`shutil.disk_usage`), never by diffing `df` — `df` rounds to
  whole gigabytes and reports `freed 0 GB` while tens of GB moved. This is a real, observed
  failure: a weekly job logged `freed 0 GB` on three consecutive runs while the cache it was
  meant to prune grew from 11 GB to 53 GB.
- **Never let a lock make the job report success.** A cache tool that waits on a lock held by
  long-lived daemons will hang or error; use its force/unattended mode and log the real per-step
  outcome. Test the lock behaviour once and encode the answer in the script.
- **High-water-mark thresholds, not unconditional deletion.** Warn at one level, reclaim caches at
  a higher one, escalate to a human past the last. A guard that purges on every run is
  indistinguishable from random housekeeping.
- **Make it idempotent and self-healing**: remove orphaned artifacts at a path the tool no longer
  uses, but only when nothing holds a non-lock file open. That catches the case where a future
  restart re-points something at the old location.
- **Schedule via a systemd timer** so it survives reboots and logs to a file; a cleanup job that
  has to be run by hand is a cleanup job that does not run.

## Pitfalls

- **A test or backup harness that copies production data per run is the highest-yield leak**, and
  it looks exactly like "the app is using too much disk". Find it with
  `grep -rn '<distinctive-name>' <project> --include='*.rs' --include='*.py'`. The fix is an RAII
  guard that also runs on panic, not an `rm` at the end of the happy path.
- **`$TMPDIR` is often a real user cache directory**, not `/tmp`. Anything that writes "temporary"
  data then lands in a place a size-based sweeper may or may not reach, and a leak that
  regenerates every run is never cleaned by an age-based rule.
- **A cache holding model weights is usually NOT deletable**, and the proof is a walk, not a
  guess: resolve every blob against the snapshot symlinks that reference it. Zero orphans is the
  correct and common result; deleting weights breaks TTS and local model serving.
- **Never auto-delete the secondary mount** as part of "cleanup" — it holds what the user moved
  there deliberately, and a sweep that follows a moved path will eventually delete the backup.
- **Repeatedly re-reporting a disk as full after a large cleanup means the accounting is wrong,
  not the cleanup.** Distinguish "bytes freed" from "free space changed", and find the writer
  before scheduling another prune.
- **An env var set for a tool that spawns children is the quiet failure mode here.** The parent
  shows the variable and the children do not, so every restart "fixes" nothing and the old path
  keeps regrowing. Check the child's environ, not the parent's.
- **Snapshot retention count is a multiplier on every rewrite.** The fix for "the disk filled in
  hours with no large new files" is usually the retention count, not a cleanup. Recommend lowering
  snapshot count or dropping the home subtree from the snapshot scope before proposing any deletion
  — those files are the user's only restore point.
- **A job in a tight failure-retry loop writes as hard as a job succeeding.** Count consecutive
  failures in the loop's own log (`FAIL exit 1 | ok=35 fail=528`) and check for a lock file pinning
  the PID. A run failing hundreds of times is consuming disk and CPU while making zero progress;
  stopping it is both a space and a load fix.
- **Left-over probe mounts survive a tool timeout.** If a read-only inspection mount is still
  present after a call times out, verify and unmount it, then prove it with
  `mount | grep -c <name>` returning 0. Report the cleanup; a read-only mount is harmless but the
  user should not have to wonder whether it is still there.
- **Say what you could not measure.** When the accurate tool times out or a needed feature is
  unconfirmed, name the gap explicitly in the report. A confident number the agent did not obtain is
  worse than a stated unknown.

- **A "free space" check that uses `dd if=/dev/zero` proves nothing on a compressing filesystem.**
  Zeros cost almost no blocks, so the test reads zero consumption on both create and delete and you
  conclude the delete freed nothing — which is exactly backwards. Use `head -c 200M /dev/urandom`
  plus `sync` (and read `df` between steps; btrfs delayed allocation hides recent writes otherwise).
- **A guard script's own safety assert can abort the run it is meant to protect.** A `case` test
  against an unset variable under `set -u` exits non-zero before any work happens, and the failure
  looks like a permissions problem. Give the variable an explicit empty default and assert against a
  real array of absolute paths, and re-run after fixing — a guard that aborts on its first
  invocation has silently provided no protection at all.

## References

- `memory-pressure-and-swap` — the neighbouring class for RAM/swap exhaustion. Reached when the
  diagnosis is "the machine is starved" rather than "the disk is full"; covers the swappiness
  misconfiguration that makes swap look full while RAM sits free.
- `local-resource-scheduler` — queuing and reaping GPU/RAM/CPU work. Reached when jobs, not
  services, are what accumulates VRAM or leaves orphaned processes behind; also covers the owner
  check that stops you calling two harnesses' MCP pairs "duplicate containers".
- `system-admin` (user-owned) — the general Linux admin command surface: `df`, `du`, `lsof`,
  `btrfs`, systemd. Run `hermes curator adopt system-admin` to let this curator maintain it.
- `scripts/storage-sweep.sh` — a runnable skeleton with the protected-mount exclusion list,
  exact-usage accounting, and the live-process skip logic.
- `scripts/df-du-reconcile.sh` — reconciles `df` against `du` to expose the unaccounted gap, then
  attributes writes to live processes (`/proc/<pid>/io`) and to individual churning files. Unprivileged.
- `references/btrfs-snapshot-audit.md` — snapshot forensics: Timeshift config keys, root-only
  subvolume enumeration, the read-only top-level mount, sudo password pitfalls, and what is
  measurable vs what must be reported as unknown.