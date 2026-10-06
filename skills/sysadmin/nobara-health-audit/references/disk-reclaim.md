# Disk reclaim: attribute, prove, act, verify

The failure mode this prevents: deleting the wrong 800 MB while the real 50 GB sits
in a place nobody measured. Every step below exists because skipping it produced a
wrong answer at least once.

## 1. Rank consumers before proposing anything

```bash
df -h                                   # every mount, not just /
du -sh ~/Work ~/.cache ~/.hermes 2>/dev/null | sort -rh
du -sh ~/Work/* ~/.cache/* 2>/dev/null | sort -rh | head -20
```

Rule of thumb: the biggest single file you can name is rarely the biggest consumer.
A 780 MB SQLite database is noise next to a 40 GB cache.

**Check every mount before deciding anything is unsalvageable.** A second physical
disk with hundreds of GB free is where cold data belongs; pruning `/home` while
`/mnt/work` sits at 30% treats the symptom.

```bash
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT   # confirm different devices, not two mounts on one
```

## 2. Prove a directory is replaceable before deleting it

**Check what running services pin before classifying anything under a project dir as
rebuildable.** `systemctl --user cat <service>` / `systemctl cat <service>` and grep the
unit's `Environment=` lines for absolute paths into the tree you are about to purge — a
checkpoint, venv, or data dir named in a unit env var is live runtime data, not cache,
even when a sibling directory makes the whole tree look like a training workspace.
Deleting it crashes the service on next restart, and the rebuild (retraining a model,
re-exporting weights) can take far longer than the space was worth. Same check for
crontabs and compose files.

Three real examples of "cache" that was not:

**Cargo/compiled build dirs.** Parallel worktrees each get their own
`CARGO_TARGET_DIR` copy of the same build. Compare them before deciding:

```bash
python3 - <<'PY'
import os
roots=[f'/path/target-w{i}/debug' for i in (1,2,3)]
def sig(r):
    out={}
    for dp,_,fs in os.walk(r):
        for f in fs:
            p=os.path.join(dp,f)
            try:
                if os.path.getsize(p)>1024: out[os.path.relpath(p,r)]=os.path.getsize(p)
            except OSError: pass
    return out
a,b,c=map(sig,roots)
common=set(a)&set(b)&set(c)
print(f"{len(common)}/{len(a)} identical, {sum(a[k] for k in common)/2**20:.0f} MB")
PY
```

If two of three copies are byte-identical, at most one needs to exist.

**HuggingFace `hub/blobs`.** Sharded two levels deep (`blobs/ab/cdef…`), each a
real multi-GB file, referenced by symlinks under `models--*/snapshots/`. A naive
`os.listdir(blobs)` reports every blob as orphaned and you will delete live model
weights. Build the reference set properly:

```bash
python3 - <<'PY'
import os
hub=os.path.expanduser('~/.cache/huggingface/hub')
blobs=os.path.realpath(os.path.join(hub,'blobs'))
ref=set()
for root,dirs,files in os.walk(hub):
    if os.path.realpath(root).startswith(blobs): dirs[:]=[]; continue
    for f in files:
        p=os.path.join(root,f)
        if os.path.islink(p): ref.add(os.path.realpath(p))
total=orph=0
for d in os.listdir(blobs):
    bp=os.path.join(blobs,d)
    if not os.path.isdir(bp): continue      # e.g. .huggingface-shared-blobs
    for f in os.listdir(bp):
        p=os.path.realpath(os.path.join(bp,f))
        try: sz=os.path.getsize(p)
        except OSError: continue
        total+=sz
        if p not in ref: orph+=sz
print(f"total {total/2**30:.1f} GB, orphaned {orph/2**30:.2f} GB")
PY
```

Confirm nothing loads from the cache directly — a service pinned to a local ckpt
path does not, and the model names tell you which entries are TTS/LLM runtime
weights (unreclaimable) versus abandoned experiments (reclaimable).

**npx/uvx per-invocation installs.** `npm cache clean` does not touch
`~/.npm/_npx`, and those dirs ARE in use by running MCP servers. Read `/proc`:

```bash
python3 - <<'PY'
import os
root=os.path.expanduser('~/.npm/_npx')
live=set()
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    try: cl=open(f'/proc/{pid}/cmdline','rb').read().decode('utf8','replace')
    except OSError: continue
    if root+'/' in cl:
        for p in cl.split(root+'/')[1:]: live.add(p.split('/')[0])
for name in sorted(os.listdir(root)):
    if name not in live: print('stale, safe to remove:', name)
PY
```

`mtime` is not sufficient — a daemon can hold a dir open for days.

**Long-lived tool daemons hold cache locks forever.** `uv tool uvx <server>` MCP
servers run for days, so `uv cache prune` never gets the lock and exits
"Cache is currently in-use". A cleanup script that logs that as "skipped" and exits 0
reports success forever while the cache grows. `--force` proceeds.

**Docker images/volumes "reclaimable" per `docker system df` may be load-bearing.**
Before deleting any image or volume, check what references it: `docker ps -a --format
'{{.Names}}\t{{.Status}}\t{{.Image}}'` — an *exited* container's image is safe once the
container is pruned, but a *running* staging/monitoring stack pins its images and
volumes, and `docker rmi`/`volume rm` will refuse (conflict: in use). Respect the
refusal; do not force-remove. Note `docker system df` counts images of stopped
containers as reclaimable — the count lies until `docker container prune` runs.

**Headless agent browsers respawn.** Killing the parent chromium leaves the session
manager free to spawn a fresh one minutes later; verify with `pgrep -fc
'agent-browser-chrome'` after a delay and identify the survivor before killing again —
one browser may be the current session's own tooling (idle, ~0% CPU) and must be kept.

## 3. A cleanup timer that always frees zero is broken

Read the per-step lines in its log, not the summary. Then check whether the growth is
age-based-sweepable at all:

```bash
ls -d <scratch>/<prefix>-* 2>/dev/null | wc -l          # per-run-ID siblings
find <scratch> -maxdepth 1 -name '<prefix>-*' -printf '%T@ %p\n' | sort -rn | head -1
```

If the newest is minutes old, `find -mtime +1` will never touch it — the leak is
faster than the sweep. Fix the writer (point test artifacts at `TMPDIR`, not an
agent's scratch dir); deleting the backlog without that just resets the clock.

## 4. Cross-filesystem moves: copy, prove, run, then delete

`mv` across devices is copy+delete. A partial failure leaves the source half gone.

```bash
rsync -a --exclude='*.tmp' /src/ /dst/
rsync -a --dry-run --checksum --itemize-changes /src/ /dst/ | grep -c '^>f'   # expect 0
/dst/platform-tools/adb version                                                # run a real binary
rm -rf /src && ln -s /dst /src        # symlink keeps latent absolute paths working
```

File counts must match, not just sizes. A btrfs source and an ext4 destination will
never agree on `du` (compression) — compare file counts and checksums instead.

**Cutover pattern for a tree pinned by live services** (proven on a Next.js server
plus docker bind mounts): `rsync -aH` the tree, stop the services/containers writing
into it, re-rsync any live-writable state (an open SQLite db+WAL cannot be
verified mid-copy), `mv /src /src.moving && ln -s /dst /src`, run a real binary and
open a real data file THROUGH the symlink, restart everything, and only after every
service and container reports healthy again, `rm -rf /src.moving`. Running
containers hold their OLD resolved mount, so they must be stopped at cutover and
started after the swap — new mounts resolve through the symlink transparently.

**Expected free-space movement under btrfs compress=zstd: little.** `du` reports
LOGICAL bytes; the filesystem stores text/code at a fraction of that on disk, so
moving a "17 GB" tree of code may free only ~1.5 GB physical. That is not a bug —
check `findmnt <mount> -o OPTIONS` for `compress=` and set expectations up front:
text/code-heavy moves buy little space; media and model weights compress poorly so
they buy nearly full `du` value.

## 5. When free space does not move, diagnose before retrying

### 5a. Invisible usage: physical >> visible logical = snapshots pinning deleted data

If the sum of every `du` walk of the filesystem is far BELOW the partition's `Used`
even accounting for compression (compression makes physical SMALLER than logical, so
physical > logical is the impossible direction), stop hunting file trees — the space
is held by btrfs snapshots. Snapshot scheduler tools (Timeshift, snapper, sanoid) pin
the old extents of everything deleted since each snapshot was taken, so a deletion is
only virtual while a pre-deletion snapshot exists.

```bash
sudo btrfs subvolume list /            # snapshot subvolumes show up here, not in findmnt
sudo timeshift --list                  # if the scheduler is Timeshift
# measure one snapshot: it is not mounted by default — mount read-only first:
sudo mkdir -p /mnt/snap-inspect
sudo mount -o subvolid=<ID>,ro /dev/<partition> /mnt/snap-inspect
sudo compsize /mnt/snap-inspect        # its Disk Usage is what it pins
sudo umount /mnt/snap-inspect
```

`compsize` needs root for the extent ioctl as a regular user fails perm; `compsize`
is the right tool because it reports physical vs referenced per subvolume.

Fix: delete the stale snapshot SETS through the scheduler tool (`sudo timeshift
--delete --snapshot '<name>'`) rather than `btrfs subvolume delete` by hand, so the
scheduler's registry stays consistent; always keep the newest set as the surviving
restore point, and clear its stale lock file if the tool warns. Deletion is
destructive (a snapshot gone = that restore point gone): name exactly which sets will
delete, get explicit user yes, then verify `df -h` free space actually moves before
reporting success. To keep it from recurring, check the scheduler's keep-count.

Timeshift-specific mechanics (verify before hand-deleting): snapshot subvolumes live
under `timeshift-btrfs/snapshots/<stamp>/{@,@home}` at the btrfs FS-tree root
(subvolid=5) — that path does NOT exist inside the mounted `/@`/`/@home` view, so
plain paths under `/` fail with 'No such file or directory'; mount `-o subvolid=5` to
reach them. The `timeshift` CLI can be useless scripted (`--list` silent, `--create
--scripted` segfaults); the proven fallback is manual `btrfs subvolume snapshot` of
`/` and `/home` into a fresh `timeshift-btrfs/snapshots/<timestamp>/` pair (the
scheduler rescans that layout on next run), then delete the stale sets by hand.
ROLL ORDERING RULE: create the new snapshot BEFORE deleting the old set — deleting
first removes the only restore point. Deletion is destructive: name exactly which
sets die, get explicit user yes, verify `df -h` free space actually moves before
reporting success.

**A keep-count in the scheduler config is not the only scheduler.** A `@reboot ...
timeshift --create` cron entry (`/etc/cron.d/timeshift-boot`) force-creates a new
snapshot every boot regardless of `schedule_boot: false` or any count field —
scheduler JSON alone does not stop stacking. To pin a max-N policy durably: set the
counts in the config AND neutralize the boot-create cron (comment the `@reboot` line
out), then assert both with a small self-check script (expected subvolume count, no
`@reboot` create, `df` free-space threshold) and leave it in scratch for future
sessions to run in seconds. Set the retention cap consistent with churn: every live
snapshot pins the pre-change extents of EVERY file deleted after it (an "18 GB"
batch delete can release ~1 GB while such a snapshot stands), so a reclaim job must
either run between snapshot generations or finish with an explicit roll —
delete-old-only-after-new-exists.

### 5b. Freed extents still at 97% in a Data chunk

```bash
lsof +L1 2>/dev/null | awk 'NR>1 && $7>104857600 {printf "%s %.1f GB\n", $1, $7/1073741824}'
btrfs filesystem usage /home | grep -E 'allocated|Unallocated|Used|Free'
```

Reconcile: `used + free` should equal device size. If it does, nothing is hidden —
the bytes really are still on disk and you deleted less than you thought, or a
writer refilled it. If `allocated` far exceeds `used + free`, freed extents have not
returned to the chunk pool and a balance is needed:

```bash
btrfs balance start --full-balance /home    # check supported filters first;
                                            # older builds reject --usage-filter
```

**The arithmetic that catches a self-inflicted mistake:** compare bytes deleted
against the change in free space. They should roughly match. When they do not, the
gap is held-open files or a concurrent writer — and the fastest way to tell is to
re-rank consumers immediately after the delete. If neither explains it, go to 5a:
snapshots are the gap between the physical Used and every visible file.

## 6. Before moving a project tree, count what binds to it

```bash
grep -rlE '/home/<user>/Work' ~/.config/systemd/user/ /etc/systemd/ 2>/dev/null
grep -rhoE '"/home/<user>/Work[^"]*"' <compose files> 2>/dev/null | sort -u
grep -nE '/home/<user>/Work' ~/.bashrc ~/.profile 2>/dev/null
crontab -l | grep -i work

for p in $(ls /proc | grep -E '^[0-9]+$'); do
  cwd=$(readlink /proc/$p/cwd 2>/dev/null); exe=$(readlink /proc/$p/exe 2>/dev/null)
  case "$cwd$exe" in */Work/*) echo "$p $cwd";; esac
done
```

Enumerate containers too: `docker ps` + `docker inspect <n> --format '{range .Mounts}
{{.Source}} {end}'` finds every bind-mount source under the tree — one compose stack
can pin a dozen paths (config files, data dirs, whole project folders).

Four binding classes, ascending cost: systemd `ExecStart=`/`WorkingDirectory=`,
docker bind mounts, shell rc `PATH`/source lines, and absolute paths inside source
files. A running server whose `exe` is inside the tree makes the move a
stop-service operation — never do it mid-session. Count what is ACTIVE
(`systemctl --user is-active` per unit), not just which unit files mention the
path — dozens of inactive pins cost nothing, the active ones set the cutover list.

## 7. Report reclaim honestly

Give the number actually removed, not the number hoped for. When a proposal turned
out smaller than estimated (a cache that was in use, weights that were referenced),
say so and name the real consumer found instead. "Freed 47 GB but free space did not
move because X is still being written" is useful; "freed 47 GB" alone is not.
