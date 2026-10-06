---
name: agentive-pipeline
description: Use when orchestrating builds across Hermes, agy and Claude.
---

# Agentive Pipeline (personal methodology)

The established orchestration: Hermes orchestrates + gates; specialist harnesses do the heavy phases. Fine to run a single phase when that's all the task needs.

## The chain

```
recon → engineered prompt → [Hermes glm-5.3 ultra PLAN] → operator gate
     → [agy Gemini Pro BUILD] → [Claude Code Sonnet TEST/REVIEW/FIX] → Hermes final tests+evals → report
```

## Phase recipes (exact invocations that work on this machine)

**0. Recon (Hermes, before any prompt):** confirm repo identity, current nav/routes/components, tool availability on the machine (ffmpeg, soffice, hermes CLI, browsers), router pass (`~/.tool-router/route "<request>"`). The engineered prompt must contain only verified facts — never guessed paths.

**1. Engineered prompt (Hermes):** role → verified product context (frozen constraints listed explicitly) → numbered requirements R1–Rn with backend reality baked in → forced output format (file-by-file map, API surface, queue strategy, compat notes, per-requirement test checklist, top-3 risks) → done condition ("implementer never needs a clarifying question") → terse style instruction. Non-goals section prevents scope creep.

**2. PLAN — Hermes glm-5.3 ultra:**
```bash
cd <repo> && hermes chat --query-file <prompt>.md --oneshot -m glm-5.3 --provider zai --reasoning ultra --max-turns 60 --no-restore-cwd > plan.log 2>&1
```
Background + notify. Output = the plan doc.

**3. Operator gate (always):** read the plan yourself before implementation. This is where post-prompt directives get patched in. Do not skip.

**4. BUILD — agy Gemini 3.1 Pro:**
```bash
cd <repo> && agy -p "$(cat build-prompt.md)" --model gemini-3.1-pro-high --mode accept-edits --dangerously-skip-permissions --add-dir <repo> --print-timeout 180m --log-file build-cli.log > build.log 2>&1
```
Build agent never deploys — no systemd, no tunnel/DNS, no sudo.

**5. TEST/REVIEW — Claude Code Sonnet:** `claude -p "$(cat test-prompt.md)" --model sonnet --max-turns 150 --dangerously-skip-permissions` — runs tests, reviews, fixes identified issues.

**6. VERIFY — Hermes:** run the extensive tests/evals yourself, check live artifacts (health endpoints, files on disk, ffprobe/DB rows), then report honestly: what passed, what failed, what's deferred.

## Delegating to opencode workers (verified 2026-10-04)

The owner may require sub-agents on opencode (`space-bunny-free` via `opencode-go`) instead of the parent's model. Mechanics that bit:

- **Pin the children, or they inherit the parent's model.** `delegation:` in `~/.hermes/config.yaml` needs `provider: opencode-go`, `model: space-bunny-free` and a `fallback_providers` list (pinned children never borrow the parent's chain). `delegate_task(action="list")` shows each child's `model`; the proof is `~/.hermes/state.db` (`sessions.model`, `billing_provider`). The config is re-read at spawn, so it only affects children spawned AFTER the edit; stop and re-dispatch earlier ones.
- **Implementer worker = one-shot CLI in a throwaway worktree**, not `delegate_task`: `hermes chat --query-file <ABSOLUTE path> --oneshot -m space-bunny-free --provider opencode-go -t terminal,file --ignore-rules --yolo --in <worktree> --max-turns 120 --run-budget 2400 --source tool -Q`. `--in` changes directory BEFORE the query file is read, so a relative path fails. Without `--yolo`, single-query mode (`approvals.single_query_mode: deny`) refuses the `terminal` tool and the worker cannot run its own gates. `--yolo` does not bypass `approvals.deny` or the hardline list: `_floor_block` runs before the yolo return in `tools/approval.py`.
- **Worktree recipe:** `git worktree add --detach <dir> HEAD`, symlink `node_modules`, and copy untracked helper files the checks need (here `scripts/ts-resolve*.mjs` are untracked in the repo). Apply the reviewed diff to the main checkout with `git apply --check` then `git apply`, after confirming those paths are clean there (the repo is shared with other sessions).
- **A work order is the whole prompt:** ground rules, the verified root cause, exact old/new snippets, the tests to add, gates with the expected output. Workers follow it literally and report honestly; they cannot see your conversation.
- **Always review the diff yourself and write an end-to-end acceptance test that FAILS on HEAD and PASSES after.** On the reactive-canvas change the worker's own 105 unit tests were green while three real defects remained (a bound KPI printed `[object Object]` in the derived title, copy-as-markdown exported a header-only table, seeding the shared fallback store would leak one card's default into another). Neutralise your fix once to prove the new test bites.
- **Never `pkill -f` a pattern that also matches your own shell command line**; it kills the command running the pkill.

## Cross-cutting rules

- **Ponytail in every prompt** handed to any harness (laziest-working-solution, stdlib first, no speculative deps). **Caveman in Hermes replies** to the user (terse, substance kept).
- **Deploy only after user's go** (except established preview refresh scripts the user has pre-authorized, e.g. post-download-refresh.sh).
- **Honest reporting at every handoff**: failures and deferrals stated in the same message as successes.
- Verify claimed milestones yourself (grep stubs, check processes/ports, ffprobe files) — agents over-report completion.
- Long phases run background+notify (`notify=true`); logs to a per-project scratch dir (`~/Work/scratch/<project>/`). The session's status file (`scratch/s*/*STATUS*`) must name what's verified (command + output), what's in-flight (unverified in-progress), what's deferred (explicit, not implied), and the concrete next module/step — never a generic "want me to continue?". Before finishing a turn on a multi-session arc, write that file so a one-word reply unblocks the next session without re-deriving state from conversation history.
- **Continue the arc without pausing.** Batch small files per cycle; keep going through the arc's ledger rows; stop early only on a real blocker staged with its unblock condition stated in one line (e.g. "mutation run blocked by cargo rebuild; say 'continue' and it resumes"). A turn that ends with an open interactive prompt (clarify form, unconfirmed destructive action) on an unattended mobile surface is a blocked session — prefer finishing a bounded verification step over leaving the prompt open.
- **Parallel execution is the default.** Run `/bg` (background agent/task) and `/steer` (course correction) in parallel, never sequentially; `/bg` must surface a visible UI showing live status (kpi/progress/step cards via the canvas directive), not a hidden process. `/bg` and `/steer` are the user's named commands — execute them as parallel, never treat them as sequential pipeline stages.
- **Continue from previous session state.** When a multi-session project resumes, read its HANDOFF.md and PORT-STATUS.md first — never restart from memory. Confirm what's verified (ledger row + command evidence), what's open, and what's deferred.
- `.ts` ESM tests (`.check.ts` in `"type":"module"` repos): bare `node --test` fails with `ERR_MODULE_NOT_FOUND`; use `npx tsx --test`. See `references/esm-ts-testing.md`.
- **User interaction: brief, natural greeting; ask what's next; keep chat terse.** Technical detail stays in artifacts (files, logs, code comments), not spoken answers. Use plain-English analogies only when explaining to a non-technical reader (e.g. terminal UI = steering wheel; gateway session = delivery driver check).

## Install/sync (for cross-harness availability)
Hermes keeps the skill in ~/.hermes/skills/; agent-fleet sync stages it to claude/opencode/agy trees on the 6h timer. Verify with each harness's own probe.
