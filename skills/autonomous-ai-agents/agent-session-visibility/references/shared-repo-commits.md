# Committing in a repo other sessions are editing

Several agents edit one working tree and share one git index. Their staged files and dirty hunks sit beside yours, so a plain `git add` + `git commit` can publish half of someone else's work or commit a deletion nobody intended. `$SCRATCH` below is the Hermes scratch dir (never `/tmp`).

## Before and during edits

- `git status --short` first: every dirty or staged path you did not touch is another session's work in progress. Never `git add -A` or `git add .`; never `git checkout -- <file>` or `git stash` the shared tree (both take their in-flight hunks along with your revert).
- Re-read `git log -3` right before committing: a peer fixing the same defect may already have committed your edit, because it stages whole files.
- Commit each verified fix immediately. An uncommitted edit to a shared file rides along with whichever session commits that file next.

## Commit only your paths, through a throwaway index

```bash
export GIT_INDEX_FILE=$SCRATCH/idx && git read-tree HEAD
for f in <your paths>; do
  git update-index --add --cacheinfo 100644,$(git hash-object -w "$f"),"$f"   # 100755 for executables
done
git diff --cached --stat             # must list ONLY your paths
git commit -F $SCRATCH/msg.txt       # still under GIT_INDEX_FILE
unset GIT_INDEX_FILE
git reset -q HEAD -- <your paths>    # realign the REAL index with the new HEAD
git diff --cached --name-status      # must be empty, or only the other session's entries
```

The final `reset` is mandatory: the real index never saw your commit, so a path you ADDED shows as a staged deletion plus an untracked file, and the next plain `git commit` by anyone commits the deletion.

## A shared file that also holds another session's hunks

Commit a blob you build, not the working-tree file: `git show HEAD:<file> > $SCRATCH/f`, splice in only your change with an anchored replace that asserts exactly one match, `git hash-object -w $SCRATCH/f`, then `update-index --cacheinfo` as above. The typical case is a regression-gate manifest whose newest rows point at a peer's not-yet-committed check files: committing the working file would reference files missing from HEAD and break a clean checkout. Scripted `git add -p` answers drift when the hunks differ from what was expected; build the blob (or a trimmed patch for `git apply --cached`) instead.

## Verify the commit, not the working tree

```bash
git worktree add --detach $SCRATCH/wt HEAD && ln -s "$PWD/node_modules" $SCRATCH/wt/node_modules
git -C $SCRATCH/wt rev-parse --short HEAD    # must equal the commit you made
git -C $SCRATCH/wt status --short            # must be empty
```

Run the type-check, the checks you touched and the regression gate there. Print the HEAD and status first: a failed checkout piped through `tail` silently tests the old commit. To reuse a worktree, `reset --hard` and `clean -fd -e node_modules` before checking out the new HEAD.

A failure that appears ONLY in the clean tree is one of two things:

- a file tracked code imports but nobody committed (an untracked dev helper or resolve shim): commit it on its own, with a message saying why;
- another session's pending work (a manifest row, a new check): leave it alone and report it.
