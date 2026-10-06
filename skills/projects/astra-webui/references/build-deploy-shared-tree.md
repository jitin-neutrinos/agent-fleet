Deployment workflow for astra-webui (sister repo, ~/Work/projects/astra-webui), with the sharing rules that keep four harnesses from clobbering each other.

## The verify chain (run top to bottom after ANY src change)

1. Typecheck the repo, not the file: `npx tsc -b --noEmit` (the shared dirty tree carries sibling sessions' WIP; a full-repo check is the only honest gate).
2. Targeted CSS checks: `node scripts/css-chat-surface.check.mjs` — compiles src/index.css through the real pipeline into a throwaway dir and asserts emitted rules as SETS (lightningcss reorders declarations; compare decls as Sets). Update this check when you change a guarded rule — it pins the owner's asks (welcome-card centering, mobile rail clamp, composer parent plate, gap 5px, no-nested-blur, persistent accent glows, touch hidden).
3. Pure-logic checks touched by the change (e.g. `npx tsx --test src/lib/overflow-fit.check.ts` when touching composer fit).
4. `npm run build` (regex: grep for `built in`, ignore the chunk-size warning), then grep the SERVED hashed bundle: `grep -o "<pattern>" dist/assets/index-*.css` — the minifier reorders shorthand values, so grep stable substrings (class names, single properties), never author-order sequences.
5. `systemctl --user restart astra-webui.service` → `is-active` → `bash scripts/selfcheck.sh http://127.0.0.1:3011` with the env file sourced (`set -a; . ~/.config/astra-webui/env; set +a`) → "ALL PASS".
6. Live DOM geometry probes (see `references/deployed-geometry-probe.md`) at desktop + 390px mobile, with CDP cache disabled. Then hand visual sign-off to the owner: state plainly what was measured, what is owner-eyeball.

## Sharing rules (the tree is NEVER clean)

- **Concurrent sessions keep `src/index.css`, `src/App.tsx`, chat-landing and companions dirty.** Never `git add <file>` for a shared file, and never `git stash --keep-index --include-untracked` — the stash sweep grabs siblings' in-flight work (recoverable with pop, but it hides their state mid-session; do not repeat that mistake).
- **Hunk-level commit:** `git diff HEAD -- <file>` to scratch → split on `@@` → keep only hunks whose added lines carry a signature ONLY your edit contains (pick a unique phrase from your comment block) → `git apply --cached <filtered.patch>` → `git add` your own whole files (new checks, new .ts modules) → commit. Verify with `git diff --cached --stat` first: the shared file must show only your few lines. False positives happen when a signature is generic (e.g. `gap: 5px` matches an unrelated 250-line hunk) — narrow the signature or drop that hunk rather than sweeping sibling work.
- **Sizes to expect:** a two-line rule change lands as `src/index.css | 20 +-`; if the pre-commit stat shows +270 on a shared file, you swept someone.
- **AGENTS.md in the repo root is the shared lesson ledger.** Lessons get appended as `## <topic>` sections (plain markdown, no frontmatter); the skill's references/ mirror the durable ones.
- **Never commit:** served `dist/`, `data/*.jsonl`, `graphify-out/*`, `src/index.css.pre-tok`, `.cache/` state files, other sessions' untracked scratch (`gtest-*.ts`, `solo4.json`).

## State reads that stop wasted rounds

- After mid-session interrupts, resume from the LAST completed tool result; never re-run recon (read the skill body's resume rule).
- A deployed fix can "come back" — the build may have been blocked by a sibling TS error, so fixes never reached dist. Diagnose SERVED vs src FIRST (grep the hashed bundle), then git, then CSS order.
- `write_file` refuses to overwrite a file it thinks you haven't fully read (including files you wrote earlier, if anything else wrote since). Do not loop: switch to `patch`, or read the file fully once.
