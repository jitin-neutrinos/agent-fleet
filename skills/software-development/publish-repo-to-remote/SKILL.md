---
name: publish-repo-to-remote
description: "Use when pushing a local repo to a new GitHub remote."
version: 1.0.0
author: Hermes Curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [github, git, publish, first-push, filter-repo, secrets, history]
    category: software-development
    related_skills: [github, commit-push]
---

# Publish Repo to a New Remote

**When to use:** any task phrased as "push X repo to remote", "create a new
repo and push this", or "publish this to GitHub" where the local repo already
has commits and no remote yet. NOT for routine commit+push to an existing
remote — that is `commit-push`.

Taking a local repo that ALREADY has history and putting it on a new remote
(e.g. `gh repo create <name> --source .`). The first push ships the entire
history — this skill is the hygiene pass that must happen BEFORE the remote
exists, because after the push, fixing anything means force-pushing every
branch plus a GitHub support ticket to clear caches.

## Always-on rules

- **Audit history, not the working tree.** A secret committed once and later
  deleted is still in every clone of the new remote.
- **Secret hit = rotate the credential first, then rewrite.** Deleting the
  file is not remediation; a rotated credential is.
- **Back up `.git` before any history rewrite** — dated tarball in the
  scratch dir (`~/.hermes/cache/scratch/<repo>-git-backup-<ts>.tar.gz`).
  filter-repo changes every commit hash; the backup is the only way back.
- **Never report the push succeeded from the create command alone** — verify
  the hash round-trips (`git ls-remote origin <branch>` == `git rev-parse
  HEAD`). That is the single sufficient proof the remote holds what you sent.
- **Public repo = state it plainly and confirm before creating.** Internal
  work defaulting to public is an irreversible disclosure decision; if the
  user picks public anyway, run the secret scan anyway and say so.

## Procedure (in order)

1. **Preflight the repo state** — branch, remotes (a pre-existing `origin`
   changes the whole plan), commit count, working tree:
   `git status --porcelain`, `git branch --show-current`, `git remote -v`,
   `git log --oneline -5`.
2. **Confirm visibility with the user BEFORE creating the remote** — private
   vs public is a one-way door for anything already in history.
3. **Secret-scan all tracked history:**

   ```bash
   git grep -nIE '(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key["']?\s*[:=]\s*["'][A-Za-z0-9_-]{16,}|password["']?\s*[:=]\s*["'][^"']{8,})' HEAD -- . ':(exclude)path/to/skip'
   ```

   Empty output = clean. Adjust the exclude for vendor dirs you are about to
   strip anyway; scan them too if they will ship.

4. **Find ignored-but-tracked paths** — anything committed before a
   `.gitignore` rule existed stays tracked forever:

   ```bash
   git ls-files | grep -cE '\.venv/|node_modules/'
   git rev-list --objects HEAD | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '$2>1000000 {s+=$2; n++} END {print n" blobs >1MB, "s/1048576" MB"}'
   du -sh .git
   ```

   A tracked `.venv/` is thousands of files and ~100MB+ of blobs that never
   belonged in git. Strip it if found (step 6); it is already in
   `.gitignore` in any repo that has one, which is exactly why it lingers
   invisibly.

5. **Back up, then commit any pending build artifacts** with `git add -f`
   (see pitfalls) — do it BEFORE the rewrite so the tarball captures the
   final intended state.
6. **Strip the path from all history** (install `git-filter-repo` via the
   host package manager; it is NOT bundled with git):

   ```bash
   git filter-repo --force --invert-paths --path app/backend/.venv
   ```

   Verify: `git ls-files <path> | wc -l` == 0, `git log --oneline | wc -l`
   unchanged (commit COUNT survives, every hash changes), `du -sh .git`
   measurably smaller, `git status --porcelain` clean.

7. **Create, push, verify:**

   ```bash
   gh repo create <name> --public --source=. --remote=origin --description "..."
   git push -u origin <branch>
   git ls-remote origin <branch>   # hash MUST equal: git rev-parse HEAD
   gh repo view owner/<name> --json name,visibility,url,defaultBranchRef,pushedAt
   ```

   Clean up the backup tarball only after the hash match and a working-tree
   check.

## Pitfalls

- **filter-repo DELETES the stripped files from the working tree** — it
  checks out the rewritten HEAD. A stripped `.venv/` loses its `bin/`
  scripts and the backend dies on the spot ("No such file or directory"
  running `.venv/bin/python`). Prevention: `cp -a <runtime dirs> <scratch>`
  BEFORE the rewrite. Recovery when already gone:
  `git --git-dir=<backup>/.git archive HEAD <path> | tar -x -C <parent>
  --strip-components=<N>` — count path components exactly; wrong N scatters
  the venv's root files (bin/, lib/, pyvenv.cfg, console scripts) across the
  project root and you must delete the spill. Prove the restore with
  `.venv/bin/python -c "import <top-level-dep>"`, never just
  `.venv/bin/python --version` (the interpreter starts even when deps and
  scripts are gone).
- **`git add` refuses a file inside a gitignored path even when that file is
  tracked** (e.g. a tracked `dist/index.html` under an ignored `dist/`).
  The "following paths are ignored" hint is not corruption — use `git add -f`
  for those paths. Rebuilt dist bundles that must ship get force-added and
  committed like source.
- **`gh repo create --source . --remote=origin` does not push** unless you
  pass `--push` or run `git push -u origin <branch>` yourself; a create-only
  call leaves an empty remote.
- **Restoring a venv from a plain tar of the working tree does not work**
  when the backup only contains `.git` — the scripts live in git objects;
  extract them from the backup's git-dir with `archive`, not from a tarball
  of files.

## Verification checklist

- [ ] `git ls-remote origin <branch>` hash == `git rev-parse HEAD`
- [ ] `gh repo view` shows the intended visibility (private vs public)
- [ ] stripped path absent on the remote AND on disk
- [ ] runtime dirs restored and importing (`<venv>/bin/python -c "import <dep>"`)
- [ ] `git status --porcelain` clean; backup tarball deleted only after the above
