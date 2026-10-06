# btrfs snapshot forensics

## When to Use

Read this when all of the following hold:
- The filesystem is btrfs (`findmnt -no FSTYPE <mount>` says `btrfs`).
- `df` used exceeds the sum of `du -xs` over every mount on that filesystem by more than a few GB.
- You need root, and a snapshotting tool (Timeshift, Snapper, btrfs-assistant, custom) is in play.

Skip it on ext4/xfs — there are no snapshots, so an unaccounted gap means something else entirely
(deleted-but-open files, a second device sharing the mount, or bad accounting). Check
`lsof +L1` first on those.

Depth for the unaccounted-space diagnostic in SKILL.md.

## Why the gap exists

`du` walks directory trees from a mount. A btrfs snapshot is a subvolume, not a directory reachable
from any live mount, so snapshot-held extents are invisible to `du` while fully consuming the device.
`df` counts them. That is the whole mechanism — no corruption, no leaked-deleted-file weirdness.

Corollary: the more snapshots you keep, the more every single file rewrite costs you. Rewrite a file
once, and if 8 snapshots still hold the previous version, you paid for 9 copies of it. Churny
workloads (search indexes, SQLite state, agent session DBs, build caches) turn into tens of GB
without any single large new file ever appearing.

## Timeshift specifics

Config: `/etc/timeshift/timeshift.json`.

| Key | Why it matters |
|---|---|
| `btrfs_mode` | must be `true` for subvolume snapshots |
| `include_btrfs_home` | `true` snapshots the whole home subtree — usually the single biggest cost |
| `schedule_daily` / `count_daily` | retention for the daily tier |
| `schedule_boot` / `count_boot` | retention for boot-triggered snapshots |
| `snapshot_count` | `0` means the per-tier counts are authoritative, not a global cap |

Total expected snapshots ≈ `count_daily + count_boot + count_weekly + count_monthly`. Compare that to
the real subvolume count; a surplus means pruning is not running.

**Check runs look like create runs.** `/etc/cron.d/timeshift-hourly` running
`timeshift --check --scripted` hourly produces one log per hour in `/var/log/timeshift/`, so ~24 logs
per day appear for every day the host has been up. These are retention checks, not snapshots. Size
the snapshot set from `btrfs subvolume list`, never from the log count.

Snapshot paths live under a top-level subvolume (typically id 5), reachable only via root.

## Root-only inspection, and the sudo pitfalls

A sudo password in an env file is fed on stdin. Three failure modes, all of which look like "sudo is
broken" and are not:

1. **An empty prompt string breaks argument parsing.** `sudo -S -p '' cmd` makes sudo print its usage
   and exit — the empty argument swallows the command. Use `sudo -S -p "pw:" cmd`.
2. **Nested sudo inside `bash -c` gets no password.** The stdin feed is consumed by the outer sudo,
   so the inner one prompts and hangs or fails. Elevate a whole script once
   (`sudo -S bash script.sh`) rather than sudoing each command inside a wrapper.
3. **Verify elevation before trusting a negative result.** A `btrfs subvolume list` that returns
   nothing could mean "no snapshots" or "not root". Check `sudo -S id` first; treating the second as
   the first produces a confident false conclusion.

## Seeing the snapshot tree

Snapshots are under top-level subvolume 5 and not present in `/`. To inspect read-only:

```bash
MNT=/run/<audit-name>
mkdir -p "$MNT"
mount -o ro,subvolid=5 /dev/<device> "$MNT"
ls -1 "$MNT"/<snapdir>/snapshots
umount "$MNT" && rmdir "$MNT"
```

Read-only (`ro`) makes this safe, but the mount **survives a tool timeout**, so unmount it in a
follow-up call and verify with `mount | grep -c <audit-name>` → 0. Report the cleanup either way.

Inside the mount, `snapshots/` holds the real set; `snapshots-daily/`, `snapshots-boot/`,
`snapshots-hourly/`, `snapshots-weekly/`, `snapshots-monthly/` are per-tag directories.

## Measuring: what works and what does not

| Method | Result | Use for |
|---|---|---|
| `du --apparent-size <snapshot>` | Wildly inflated — a 276 GB home can read as 418 GB, because every historical version of every rewritten file is visible at once | Never quote as real space |
| `btrfs filesystem du -s <path>` | Accurate: Total vs Exclusive per extent, shared extents counted once | The correct tool, but can exceed a multi-minute timeout on a large snapshot tree |
| `btrfs qgroup show -reF <subvolid>` | Per-subvolume Referenced vs Exclusive | Needs qgroups enabled; confirm with `btrfs qgroup show` accepting an argument before relying on it |
| `btrfs filesystem usage /` | Whole-device totals, instant | Cheap cross-check that the gap is real |

`btrfs filesystem du` has no `--apparent-size` flag; passing it errors out.

**When the accurate measurement times out, report it as unmeasured.** Do not fall back to an
apparent-size number dressed up as real, and do not invent a per-snapshot split. A stated unknown is
useful; a fabricated figure is worse than no figure.

## Why deleting files frees nothing (the pinning effect)

Deleting a file that any live snapshot still references frees the directory entry but not the
extents. The snapshot holds its own reference to those blocks, so `df` stays flat while `du` on the
live tree drops. This is expected, not a failed delete, and it is the single most misread outcome in
a cleanup sweep: the log says "deleted 58 GB", free space moved 341 MiB, and both numbers are true.

Diagnose it in one round-trip on the same filesystem:

```bash
P=<scratch>/pin-test.bin
B=$(df --output=avail -B1 /home | tail -1)
head -c 200M /dev/urandom > "$P"; sync; sleep 2
M=$(df --output=avail -B1 /home | tail -1)
rm -f "$P"; sync; sleep 2
A=$(df --output=avail -B1 /home | tail -1)
```

- Consumed on create, released on delete → the filesystem frees normally, so whatever stayed pinned
  is held by snapshots. Fix the retention; the deletion already succeeded.
- Consumed on create, still consumed after delete → a live process holds the fd. Find it with
  `lsof +L1 | awk '$7>52428800'`.

Use `/dev/urandom`, never `/dev/zero`: btrfs compresses a zero fill to almost nothing, so a zero-fill
probe reads 0 MiB on both steps and looks like "the delete freed nothing" when it freed everything.
Also `sync` between steps — btrfs delayed allocation will otherwise hide a write that already
happened, making a working delete look broken.

Once pinned, only three things release the blocks: deleting the snapshot that holds them, pruning old
snapshots so retention drops below the count, or overwriting the file in place so every snapshot's
copy becomes garbage. Retention pruning is the right answer for a swept batch.

## Remediation options, safest first

1. Delete redundant backup archives and provably-regenerable scratch — no snapshot involvement.
2. Lower retention: fewer `count_daily` / `count_boot` tiers. This is the biggest lever on
   multiplication and costs only restore depth.
3. Set `include_btrfs_home` to `false` to snapshot root only. Largest saving, loses home restores.
4. Delete old snapshots. **Prefer the tool (`timeshift --delete <stamp>`) but verify it actually
   worked**, and be ready to fall back to direct subvolume deletion — see "Deleting snapshots for real"
   below for the id-based procedure and the three ways the tool path fails.

Present 2 and 3 as proposals with the tradeoff named, and let the user choose. Snapshots are the
user's only restore point — never delete them as part of a generic "cleanup" sweep. **Change the
config BEFORE deleting**, so retention protects the intended survivors even if the deletion is
interrupted.

## Deleting snapshots for real

Retention config alone releases nothing. Pinned blocks stay until the snapshot subvolumes are gone,
and the deletion must be verified rather than assumed.

**The tool path fails three ways, none of which look like failure if you only read the exit code:**

1. **Stale lock → segfault.** `timeshift --delete` can die with SIGSEGV and dump core. The next
   invocation prints `[Warning] Deleted invalid lock` and then works. Re-run once before concluding
   the tool is unusable; do not read the segfault as "permission denied" or "snapshot corrupt".
2. **Path-based delete can never work here.** `btrfs subvolume delete <path>` fails with
   `Could not statfs: No such file or directory`, because these subvolumes live under top-level
   `subvolid=5` — a namespace not mounted anywhere live. The path printed by `btrfs subvolume list`
   is relative to top-level, so it does not exist from the root mount.
3. **Deleting by id silently requires an explicit flag.** The working form is
   `btrfs subvolume delete -i <id> <path>`. A bare id, or a missing `-i`, produces the same statfs
   error, because without the flag btrfs treats the argument as a path.

**Parse the listing by field position, verified before use.** The header is literally
`ID <id> gen <gen> top level 5 path <path>`, so the **subvolume id is field 2** — field 1 is the
string `ID`. An awk that grabs `$3` or later passes the literal word `ID` as the id, deletes nothing,
and still reports success.

The snapshot name is **component 3** of the path (`timeshift-btrfs/snapshots/<NAME>/<@|@home>`), not
4. When unsure, print the split first:
`awk '{n=split($NF,a,"/"); print "components="n; for(i=1;i<=n;i++) print a[i], "|id=" $2}'`.

**Assert on the survivor count, not on the absence of errors.** A keep-filter that matches nothing
leaves every snapshot in place and the script still prints `deleted ok=0 fail=0`, which reads as a
clean no-op run. Verify the remaining subvolume count equals what retention expects.

**Reclaiming space is a separate, later step.** Deletion queues extents for removal; free space does
not move until the transaction commits. Run `sync` then `btrfs filesystem sync /`, allow time, and
re-read `btrfs filesystem usage` — the reclaim trails the deletion by minutes. If you reach for
`btrfs balance` as a helper, check its flags first; some builds reject `--one-tier`.

## A working keep-then-delete loop

Get the id map and the keep-list into associative arrays, then filter **per snapshot inside the
loop**. Two bugs live here and both fail silently while printing `deleted ok=0 fail=0`:

- Filtering by running `grep` over the whole keep-list once and reusing the verdict, instead of
  per snapshot, makes every snapshot look kept (or none). Do the match inside the loop body.
- Accumulating snapshots into one variable and `grep`-ing the result against a glob makes the whole
  variable a single test subject, so nothing ever matches. Use `mapfile` into real arrays and
  compare with `grep -Fxq` on one element at a time.

```bash
declare -A IDS KINDS
while read -r name id; do
  [ -z "$name" ] && continue
  IDS["$name"]="${IDS[$name]:-} $id"
  case "$name" in 2026-09-27_*) KINDS["$name"]=B ;; *) KINDS["$name"]=D ;; esac
done < <(btrfs subvolume list / 2>/dev/null | grep -i timeshift |
         awk '{split($NF,a,"/"); print a[3], $2}')   # name = component 3, id = field 2

mapfile -t ALL < <(printf '%s\n' "${!IDS[@]}" | sort)
mapfile -t DAILYS < <(printf '%s\n' "${ALL[@]}" | grep -v '2026-09-27')  # boot tier separate
DAILY_KEEP=$(printf '%s\n' "${DAILYS[@]}" | tail -n 2)

for name in "${ALL[@]}"; do
  if printf '%s\n' "$DAILY_KEEP" | grep -Fxq "$name"; then
    echo "  KEEP    $name [${KINDS[$name]}] ids:${IDS[$name]}"; continue
  fi
  for id in ${IDS[$name]}; do
    btrfs subvolume delete -i "$id" / && echo "  DELETED $name (subvol $id)"
  done
done
```

Verify afterwards by counting what is left, not by trusting the exit codes:

```bash
btrfs subvolume list / 2>/dev/null | grep -i timeshift |
  awk '{split($NF,a,"/"); print a[3]}' | sort | uniq -c
```

A correct run reports the kept snapshots with a count of 2 each (`@` and `@home`) and a total
subvolume count equal to twice the snapshot count. Anything else means the filter misfired.

**Change the config first, delete second.** Editing `count_daily`/`count_boot` before deleting means
retention protects the intended survivors even if the delete run is interrupted partway.