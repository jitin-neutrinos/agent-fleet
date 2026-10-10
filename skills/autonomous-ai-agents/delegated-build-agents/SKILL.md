---
name: delegated-build-agents
description: "Orchestrate headless AI coding agent builds with gates."
version: 0.1.0
author: Jitin Nair (notjitin), Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Delegation, OpenCode, GLM, Build-Agents, Headless]
    related_skills: [opencode, claude-code, llm-build-orchestration]
---

# Delegated Build Agents

Pattern for delegating multi-file coding work to headless AI coding agents (OpenCode
with GLM 5.3 via Z.AI coding plan on kurama-core; pattern generalizes to claude -p /
agy). The orchestrator (Hermes) owns the spec, the gates, and verification; the agent
owns keystrokes.

## Procedure

1. **Write the contract before dispatching.** A `specs/task-<name>.md` file in the
   repo: exact file list, schema/endpoints, quality bar, and the terminal gate ("pytest
   green", "npm run build passes"). Long inline prompts get lost on retries; the file
   persists and re-dispatch is one line: "Read specs/task-x.md and execute until
   <gate>."
2. **Dispatch headless with auto-approve.**
   `opencode run --auto "Read specs/task-x.md and do exactly what it says, step by
   step, until <gate>. Start now." --model zai-coding-plan/glm-5.3`
   - Without `--auto`, permission-gated commands are silently auto-rejected and the
     agent dies on its first `find` (symptom: "user rejected permission" in output
     despite no user being present).
   - Run via Hermes `terminal(background=true, notify=true, timeout=3600+)`; long
     builds take 10–40 min. Never dispatch in a foreground call — a user steer or
     interrupt mid-turn SIGKILLs the child worker with no partial credit.
3. **Smoke-test the exact command shape before launching big work.** A trivial prompt
   ('Reply OK') succeeding does NOT prove work prompts succeed — test a prompt that
   triggers file reads/tool calls. Conversely, if trivial prompts pass but all real
   prompts crash in ~2s, suspect a local plugin injecting malformed content (on
   kurama-core it was the tool-router plugin using `tr_` part ids where the schema
   demands `prt_`) — check plugins/config before blaming the provider.
4. **Give the agent a durable task file, not conversation context.** It reads the repo
   itself; specs survive re-dispatch after crashes.
5. **Re-run every gate yourself.** Agent self-reports are claims: run `pytest`/`npm
   run build` in your own terminal and read the key files before reporting done.
6. **Keep ports/services belonging to other projects sacred.** Check `ss -tlnp` before
   choosing ports; when a port collides with a user service, move YOUR service, never
   kill theirs (a mistake here killed the user's MCP server once and required apology).
7. **Sandbox every worker before the first dispatch**, and prove the sandbox with a
   20-line escape test (`references/sandboxed-worker-isolation.md`). A worker inherits
   your whole environment by default — API keys, SSH agent, dual-boot mounts, docker
   socket — and none of that reaches the model, so it is pure blast radius. For file
   isolation without reinstalling deps: `git worktree add` a fresh tree and symlink the
   main checkout's `node_modules` into it — own branch and sources, instant dependencies.

## Bound every headless worker

`hermes chat` defaults to `--max-turns 500` with no wall-clock budget. A worker
handed a large input and neither flag loops until your kill timer fires — and a
kill loses the ENTIRE run (no partial credit), so it retries from scratch. Pass
both, always:

- `--max-turns N` — the tool-call ceiling.
- `--run-budget SECONDS` — wall-clock budget. At 80% elapsed the agent gets a
  one-time wrap-up notice and finishes with a result instead of being killed
  mid-loop. Set it just under your own kill timer (0.9× works) so the clean path
  always wins the race.

Scale the pair with input size, and make the large tier a MULTIPLE of the base,
not an independent constant. A worker reading 3× the usual input needs ~3× the
turns; an independent constant silently overrides an explicit env override (and
a test harness's deliberately short timeout), which is how a "size-scaled" fix
quietly breaks a suite that sets its own small cap.

A cap set too low is its own failure mode: the worker exhausts turns mid-read,
spends the remaining budget writing the wrap-up, and the run is lost anyway. The
worker's own log says `Iteration budget exhausted (N/N)` — that line means raise
the cap, not the timeout.

## When delegation does NOT pay (measure it on the first task)

Delegation is not automatically faster. It pays when the worker can run its own
verification loop end to end and you only review results. It does **not** pay when the
acceptance gates are expensive relative to the code — parity harnesses, mutation
checks, corpus audits — because the worker cannot be trusted to run them, and its
untested output arrives as a liability you must debug yourself.

Rule: on the FIRST delegated task, measure how much of your own time went into
repairing the worker's files versus writing them. That ratio decides whether to
delegate the rest. Concretely, in a parity-gated port: three workers wrote ~4,000
lines that then needed ~15 orchestrator-side fixes plus two hand-written harnesses
before anything was measurable — slower than porting solo, and every repair round
costs a full worker restart.

Two more orchestrator-side costs people forget:
- **A provider rate limit or quota kills workers mid-task with no partial credit.**
  Check the quota before dispatching N workers, not after. Capture the session id of
  every worker and resume (`hermes chat --resume <id> --query-file <continue.md>`) —
  a resumed session keeps its full context and its file work. Wrap the dispatch in a
  bounded retry loop (N attempts, sleep between, re-send a short continue query): an
  outage death can exit 0 with the provider error as the last log words, so judge
  completion by grepping the log tail for outage phrases, never by exit code alone.
  Before trusting fallback providers, verify each one's quota is actually alive; an
  all-dead fallback chain turns every outage into pure wait-and-retry.
- **Harvesting is not free.** If a worker dies, taking its files still means reading
  them skeptically: scan for stubs/`todo!`/`unsafe`, compile, and count executable
  lines against the reference before you believe anything in them.

## Gate design

- Backend tasks end at: `python -m pytest tests -q` green with zero external calls
  (stub/mock external APIs behind config so tests pass offline).
- Frontend tasks end at: `npm run build` green.
- Both gates verified by the orchestrator, not just the agent.

## Pitfalls

- Multiple parallel OpenCode agents in the SAME workdir collide on ports and venvs —
  give each its own scope directory or sequence them.
- An agent killed mid-run can leave orphaned transactions/locks (stuck `running` rows,
  `idle in transaction` DB sessions). Check `pg_stat_activity` after force-killing.
- Frontend visual verification: vision-analyze budget can run out (provider 429) —
  fall back to `playwright browser_evaluate` (getBoundingClientRect for alignment) and
  PIL pixel sampling of screenshots; objective and free. Scroll the whole page
  programmatically BEFORE `fullPage` screenshots — sections that animate in on scroll
  sit at opacity 0 until visited and capture blank. Then vision-review the crops:
  copy arithmetic, SSR-invisible sections and absolutely positioned overlaps pass
  every code gate and still ship broken.
- **A worker's self-reported changes are CLAIMS, not facts.** Fingerprint every
  file it may touch (path → `mtime:size`) before and after the run and diff the two.
  Observed: a worker declared a file it never created and silently edited a second
  one it never mentioned — the log read as success. Store the measured diff next to
  the claims, and surface changed-but-undeclared paths; that is the only way a
  phantom or lost edit becomes visible.
- **Never restart a supervisor while its detached worker is in flight.** The worker
  is a child of the service process, so a restart SIGKILLs it and strands the job in
  its `running` state until a stale-resume timer eventually fires. Check for live
  children before restarting, and prefer deploying UI-only changes when nothing runs.
- **A subagent fan-out that died on the same upstream error within seconds is a
  provider-capacity signal, not a task-shaped one.** Do not re-dispatch the same
  fan-out on the same provider — that re-rolls dice on a known-failed path. Take
  the highest-value slice of the scope inline yourself, finish it, and note the
  uncovered remainder honestly in the report so it is not silently dropped.
- **Do not filter processes by `comm`/name.** The hermes CLI's `comm` is `hermes`,
  not `python`, so `awk '$1=="python"'` reports "nothing running" while nine workers
  are live. Match the args pattern instead — and never on a pattern your own command
  line also contains (`pkill -f` then kills the shell running it).
- **Validate the output CONTENT of the first few results before scaling up.**
  Running one item and reading what it actually produced is the cheapest possible
  gate; skipping it is how a broken batch gets committed to hundreds of items.
  Observed: a run that exited 0 with zero output on every item looked fine by exit
  code, and was only caught by inspecting rows. Do the same before raising
  concurrency — a bigger fleet amplifies a wrong result, it does not average it out.
- **Count the whole population before reporting a defect rate.** Two bad rows out of
  the first two inspected is a sample, not a rate: the remaining rows can invert the
  conclusion (all of them can be legitimately trivial). Grep/query the ENTIRE set,
  classify every row, and only then report a number. Reporting an unverified count
  upward forces the owner to act on a wrong premise and costs a correction later.
- Parallel workers over a SHARED, non-versioned file estate need the collision-safe
  recipe in `references/parallel-batch-over-shared-state.md` — naive parallelism
  silently loses edits with no VCS to recover from.

<!-- canvas-output:start -->
## Canvas output

A hand-off is a surface: a warn `callout` with the next action first, `keyvalue` for exact state (mono paths and hashes), `steps` with exactly one active, a danger `callout` for gotchas, `references` for the files to read. Hand over artifacts and decisions, not the whole workspace.
<!-- canvas-output:end -->
