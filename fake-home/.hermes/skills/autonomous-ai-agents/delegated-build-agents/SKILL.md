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
     builds take 10–40 min.
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
   socket — and none of that reaches the model, so it is pure blast radius.

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
  every worker so a killed one resumes instead of restarting.
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
  PIL pixel sampling of screenshots; objective and free.
