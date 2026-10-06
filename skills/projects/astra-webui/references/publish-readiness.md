# Public-repo readiness audit

Use before: pushing a long private backlog, flipping a repo public, or announcing a release URL.
Owner requirement: **audit and present findings + an ordered plan; do not push.** Wait for an explicit go.

## Order of operations

1. **Visibility + license** — `gh repo view <slug> --json name,visibility,url,description,isPrivate`. Often the repo is *already* public and the real work is hygiene, not publishing.
2. **Working tree vs remote gap** — `git log --oneline origin/main..HEAD`. Unpushed commits are the highest-severity finding: unrecoverable on a single disk.
3. **Untracked files** — `git status --short`. For each, decide whether a *tracked* file already imports it (see pitfall below).
4. **Fresh-clone build probe** — the real gate (recipe below).
5. **Secret scan, with adjudication** — see pitfall "regex hits are candidates".
6. **Portability scan** — `git grep -nE '/home/<user>' -- server/ src/ scripts/` and a grep for personal hostnames. Soft `process.env.HOME || "/home/<user>"` fallbacks are survivable; bare `const X = "/home/<user>/..."` constants break every cloner.
7. **Privacy scan of tracked runtime state** — `git ls-files data/` and read the small JSON/JSONL files that ARE tracked. Ledgers of real sessions leak command history even with zero credentials in them.
8. **CI presence** — `ls .github/workflows`. Native-platform workflows do not imply the web app is built or tested on PRs.
9. **Report** — severity table + ordered steps in the owner's canvas format. State failures and deferrals in the same card as successes.

## Fresh-clone build probe

A green working-tree build says nothing about what a cloner receives. Untracked files satisfy local imports that the clone lacks.

```bash
W=<scratch>/clone-test; rm -rf "$W"; mkdir -p "$W"
git archive HEAD | tar -x -C "$W"          # exactly the committed tree
ln -s "$PWD/node_modules" "$W/node_modules" # reuse deps; never reinstall
cd "$W" && npm run build                    # the package script, NOT bare tsc
```

`git archive` is preferred over `git clone` because it cannot be fooled by the local index, and it needs no network. Run the clone's build **and** the working tree's build: three outcomes matter — clone fails / both pass (clean), clone fails / tree passes (**orphaned untracked source**, the urgent case), clone passes / tree fails (broken working tree).

## Pitfalls

- **`tsc --noEmit` is a no-op in a project-references repo.** A root `tsconfig.json` of `{"files": []}` plus `references` means a bare `tsc --noEmit` type-checks nothing and exits 0 — it will happily "pass" a tree full of missing modules. Always run the package's own build script (`tsc -b && vite build`) or `tsc -b --noEmit`. If a no-op check passes, suspect the check before trusting it.
- **A commit that adds an import without adding the module breaks every clone while the local tree still builds.** The untracked file masks it locally. Diagnose by comparing mtimes against the introducing commit: `git log -S'./components/x' -- src/App.tsx`, then `stat -c '%y' src/components/x.tsx`. Files *older* than the commit that imports them were left behind — that ordering is the proof, and it also answers the "is another agent mid-write on this?" question without guessing.
- **Secret-scan regex hits are candidates, not findings.** Adjudicate every hit against surrounding context before reporting. Recurring false positives: Android permission/namespace strings that contain key-like substrings, self-test fixtures named `*-secret-*` / `check-password-*`, asset content hashes, package-manager integrity hashes. Report false positives explicitly alongside real hits — an audit that cries wolf teaches the owner to skip the next one.
- **Credentials absent does not mean privacy absent.** Encrypted-at-rest vaults, `0600` env files outside the repo, and gitignored data dirs are all correct; say so as a verified-clean finding. The leak that remains is usually *activity* history in tracked ledgers.
- **Bulk size is not the problem — `git ls-files` bytes are.** Check the tracked total (`git ls-files -z | xargs -0 du -ch | tail -1`) rather than worktree `du`, which counts gitignored `node_modules` and databases.
- **Concurrent-session trees**: never commit untracked files blind. Prove ownership first (the mtime/import-ordering check above), and if the evidence is ambiguous, report and wait instead of committing.
