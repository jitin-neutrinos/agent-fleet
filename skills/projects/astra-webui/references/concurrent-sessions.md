# Working in a repo another agent session is also editing

This repo gets worked by **multiple Hermes sessions at once** — a chat session
building a feature while another adds pages. The failure mode is not a merge
conflict; it is silent, well-meant interference that reads as your own bug.

## Symptom classes and their causes

| Symptom | Cause |
|---|---|
| Your files appear in someone else's commit message | they staged with `git add -A` |
| A file you never edited fails to compile, on an import you never touched | their lint autofix deleted an import that was momentarily unused, then you used it |
| `git status` shows files you did not create, mid-build | they are mid-feature |
| A red suite in a file you did not write | theirs, not yours |

## Defend in three places

**1. Establish ownership before you start.** `git log --oneline -5` plus
`git status -s`. If the tree is dirty in files outside your task, note them —
they are not yours to fix, revert, or "clean up".

**2. Stage explicit paths, never `-A`.**

```bash
git add src/lib/foo.ts src/lib/foo.check.ts src/components/foo/ \
        package.json package-lock.json
git commit -m "..."
```

`git add -A` in a shared tree silently donates your in-flight work to whoever
commits next, under their message. If a commit of yours picks up a file you never
touched, say so in your report — the work is not lost, but the attribution is.

**3. Treat any file you did not just write as externally owned.** Re-read it
before patching — the patch tool warns when the on-disk copy changed under you,
and that warning is real here, not noise.

## Prove a red suite is yours before fixing it

The cheap move is to "fix" a neighbouring failure and take credit or blame for
it. Stash your own paths and re-run:

```bash
git stash push -- <your paths>
npx tsx scripts/verify-thing.ts ; echo "exit=$?"
git stash pop
```

If the failure persists with your changes removed, it belongs to whoever owns
that code. Report it as pre-existing and leave it alone; offer to take it
separately. Only own a failure that disappears when you stash.

**`git stash push -- <path>` on already-committed work stashes NOTHING and exits 0.** The path is
clean against HEAD, so there is no diff to save; the command "succeeds", the tree is unchanged, and the
re-run measures your code still in place. It reads exactly like "my changes were removed and the bug
persists, so it is not mine" — a conclusion drawn from a test that never removed anything. A
`The stash entry is kept in case you need it again` line on `pop` is the tell.

To actually re-test against pre-change code, materialize the old file:

```bash
cp <file> <scratch>/current.bak                    # so you can prove the restore
git show HEAD~1:<file> > <file>                    # or the branch/commit before the fix
# ... run the gate; it MUST go red here, or the guard cannot fail and proves nothing ...
cp <scratch>/current.bak <file>                    # restore from the COPY, not from git
diff -q <file> <scratch>/current.bak               # assert byte-identical
```

**Restore from the scratch COPY, never `git checkout HEAD -- <file>`.** The checkout form is what a delegate
used to compare pre-fix behaviour and it discarded its own uncommitted fix mid-run — on a tree with several
live sessions that is someone's work gone, and it looked like a successful comparison. `git checkout <path>`
is destructive by design; the copy is one line and cannot lose anything.

**Delegate agents inherit this hazard.** A worker told to "verify your guard fails on pre-fix code" will
reach for `git checkout` or `git stash` on its own initiative, and neither is safe on a shared tree. Put
the materialize-and-restore recipe in the delegation brief verbatim, and diff the file against your backup
after the worker reports.

Requiring the gate to go **red** first is the point: a new guard verified only green has not been shown
capable of failing.

## Resolving a conflict ANOTHER session created

A `stash pop` colliding with an updated upstream leaves `UU <file>` with conflict markers, and the build
stays broken for everyone. It is not yours, but you own clearing it if you are the one blocked.

**Read both sides before choosing, and let a duplicate declaration decide it.** Stash-pop sides are
usually the OLDER code, so taking them re-introduces code HEAD has already moved past:

```bash
git show :2:<file> > /tmp/ours    # "Updated upstream" / current index
git show :3:<file> > /tmp/theirs  # "Stashed changes"
diff -q /tmp/ours <(git show HEAD:<file>)   # ours == HEAD ⇒ taking upstream loses NOTHING
grep -c 'const \[foo, setFoo\]' /tmp/theirs # a declaration HEAD already has ⇒ theirs breaks the build
```

The second command is the decisive one: if the stashed side declares something the upstream side already
declares, accepting it produces a duplicate binding that only surfaces at `tsc`, after the resolution
looks finished. Count declarations on both sides, don't eyeball the hunks.

Then resolve narrowly and prove it:

```bash
git checkout --ours -- <file> && git add <file>
grep -c '<<<<<<<\|>>>>>>>' <file>     # must be 0
git diff HEAD --stat -- <file>        # empty ⇒ byte-identical to HEAD, nothing was lost
```

**Committing is blocked while ANY path is unmerged, even unrelated ones.** A peer's conflict in a file
you never touched refuses your commit. Stage your path explicitly and let git commit just it:

```bash
git commit -m "..." -- <your paths>   # succeeds despite UU elsewhere; verify with git show --stat
```

Verify what the commit actually contains (`git show --stat HEAD`) — a scoped commit is the escape hatch,
not a licence to sweep the other session's files in. Their stash entries stay untouched and recoverable;
never drop them, and say in your report which side you took and why.

## Parking a peer's broken file to get your build green — and getting it back

When a peer's uncommitted file breaks `npm run build`, the only way to verify your own
work is to park theirs:

```bash
git stash push -- src/components/<peer-file>.tsx   # park theirs
npm run build ; echo "build_exit=$?"
git stash pop                                       # give it back
git status --porcelain <peer-file>                  # MUST show " M" again
```

**`git stash pop` inside a chained `&&` silently does not restore, and nothing in the
output tells you.** The observed pattern is `git stash pop >/dev/null 2>&1` followed by
an unrelated `echo` — when pop fails or conflicts, the chain continues and the session
reports success over a file that is still stashed. The peer's work then sits in
`stash@{0}` while everyone believes it is on disk.

Make the restore self-verifying, every time:

```bash
git stash pop >/dev/null 2>&1
[ -z "$(git status --porcelain <peer-file>)" ] && \
  git checkout "stash@{0}" -- <peer-file> && git restore --staged <peer-file>
git status --porcelain <peer-file>     # read it; blank means their work is GONE
```

Two traps in that fallback. `git checkout stash@{0} -- <path>` **stages** the file as a
side effect (`M ` not ` M`), so the next plain `git commit` sweeps the peer's work into
yours — follow it with `git restore --staged <path>` to hand it back the way you found
it. And quote `"stash@{0}"`: unquoted, the shell brace-expands and the checkout misses.

If the peer's file is genuinely mid-edit and broken, say so in your report rather than
fixing it, and never let your commit carry it. Verify their stash entries survive your
push/pop cycle (`git stash list`), because a peer's WIP is their only copy.

## Recovering work a peer reverted wholesale

A peer commit that rewrites a file you own does not show up as a conflict — it lands, HEAD moves, and
your version is gone from the working tree while your commits still sit in history. The symptom is a
sudden collapse in size (an 894-line feature file reads back as its 469-line ancestor).

**Your work is in git, not lost.** Confirm before panicking, and identify WHO reverted it:

```bash
git log --oneline -6                                  # is your commit still reachable?
git merge-base --is-ancestor <your-sha> HEAD && echo "in history" || echo "gone"
git log --oneline <your-sha>..HEAD -- <the-file>     # which commits touched it after you
git diff <your-sha> HEAD -- <the-file> | grep '^+' | grep -v '^+++'   # what they ADDED
```

That last command is the one that decides the merge. Read the added lines: a pure revert (only removals,
plus whitespace/comment churn) means take your version wholesale. If they added real work — a new token
class, a renamed role, a11y attributes — port those forward instead of discarding them, or you will
re-break whatever they were mid-fix. In this session the peer's commits contributed exactly two things
worth keeping (`ast-sk` skeleton class, and the `cyanx` → `accent` role-token rename) inside an
otherwise wholesale revert.

```bash
git show <your-sha>:<file> > <file>        # recover
# ...port their additions...
git add <file> && git commit -m "restore(<area>): re-apply <feature> lost to concurrent reverts"
```

Never `git revert` the peer's commits to win the race — they are someone's active work, and the next
revert escalates. Restore, port, commit forward, and say in the report which peer commits you built on.

## A raw NUL byte makes grep silently skip the file

`chat-timeline.tsx` joins memo signatures with `blocks.map(b => b.source).join("\0")`. One
control byte makes `grep` AND `ripgrep` treat the whole file as binary and print nothing —
so `grep -rn "planTurnCanvases" src/` returns zero hits for the very file that consumes the
API you are debugging. An earlier run in the same session DID list the file, which is what
makes it read as "the search works".

Before concluding a symbol is unused, check the file for control bytes and re-search with `-a`:

```bash
python3 -c "b=open('src/components/chat-timeline.tsx','rb').read(); print([i for i,c in enumerate(b) if c<9])"
grep -an "<symbol>" src/components/chat-timeline.tsx
```

The byte is normally legitimate (chosen as a separator precisely because NUL cannot occur in
the data). Do NOT "fix" it — it only breaks searching. Use `grep -a` or `read_file`.

## A new `*.check.*` file must be pinned in the regression manifest

`scripts/regression-gate.check.mjs` fails on any `*.check.*` not reachable from its
`REGRESSIONS` array, so a new guard that escapes the manifest turns the whole gate red.
Add the row in the SAME change:

```js
{ id: "RG-0NN", found: "<date>", symptom: "<the bug>", guard: "src/lib/<new>.check.ts" }
```

The manifest file is often itself UNTRACKED, or TRACKED-but-dirty, because it is shared by every
session pinning a guard. Edit it so the gate passes, but do NOT `git add` it by default — committing it
claims work you do not own, and rows whose `guard:` file is still untracked will break a fresh checkout.
Commit your source + check and report the manifest as needing reconciliation.

**Re-read it immediately before patching.** The patch tool warns when the on-disk copy changed under you;
in a shared tree that warning means a peer committed rows seconds earlier, and ids you picked may already
be taken. Take the next free `RG-NNN`, then prove no duplicate landed:

```bash
grep -o 'id: "RG-[0-9]*"' scripts/regression-gate.check.mjs | sort | uniq -d   # must be empty
```

**A manifest row can name a guard file that no longer exists.** Peers move and delete their own check files
mid-flight, so the failing row CHANGES between runs (`etiquette.check.ts` one minute, `ingest.check.mjs`
the next). That is a live shared file, not your regression — re-read the failure text before reacting, and
never "fix" it by pinning a row for someone else's in-flight file.

## Consent-gated commands: batch them or lose the session

`npm install`, `npx <tool>`, `systemctl --user restart` and similar each block
on their own approval prompt that **times out after ~5 minutes**. Three of them
run separately cost ~15 minutes of dead time, and the timeouts look like hangs.

- Put every approval-gated command for a step into **one** shell call.
- Or resolve approval once up front with a `clarify` question offering the real
  choices (install the dependency vs. hand-roll the feature), then proceed
  without re-asking.
- Restart approval is granted separately from install approval — getting one
  does not carry the other.