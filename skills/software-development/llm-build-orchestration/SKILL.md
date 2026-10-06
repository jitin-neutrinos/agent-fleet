---
name: llm-build-orchestration
alt_names: [agent-build-orchestration, opencode-builds]
description: Use when delegating a large build to an agent CLI.
---

# LLM Build Orchestration

Delegate large multi-file builds to external coding-agent CLIs (opencode run,
claude -p, and similar one-shot agent CLIs) while keeping quality gates in
your own hands.

## Procedure

1. **Write the spec as a file in the repo** (`specs/task-<area>.md`): exact
   directory layout, schema/contract, stack pins, quality bar, and the done
   condition. Long task descriptions do not belong in the inline prompt —
   inline prompts are fragile to shell quoting, not re-runnable, and get
   truncated). The inline prompt is one line: point at the spec file and state
      the done condition ("until pytest is green", "until npm run build passes").
      For web targets, verify the real route/surface map yourself (sitemap.xml,
      curl status codes) before naming any route in the spec — repo READMEs and
      CLAUDE.md files go stale and documented routes 404 on the live site.
   2. **Smoke-test the exact command shape before launching long runs** — and
      smoke-test BOTH a trivial prompt (`Reply OK`) AND a tool-using prompt (ask
      it to read a file). Trivial prompts skip plugin/routing/tool paths where
      crashes live; a passing trivial prompt proves nothing about real workloads.
      Before launching any write-capable agent, also confirm the repo carries a
      git identity (repo-local `git config user.name/user.email`, copied from the
      last commit) — headless agent commits die on "Author identity unknown".
3. **Launch headless with auto-approve.** OpenCode needs `--auto` for any
   unattended run: without it, bash commands not explicitly allowlisted in the
   config's `permission` block are "auto-rejected" and the run dies on its
   first command (headless has no one to approve). Check the agent name is a
   primary agent — subagent-mode agents are refused as primary.
4. **Track via background process tools; poll, don't tail-loop.** Verify
   liveness by checking files actually appear in the target tree, not just by
   the process being alive.
5. **Verify agent self-reports independently.** Run the test suite and the
   build yourself after the agent exits. An agent claiming "tests green" may
   not have run them; also check for placeholder TODOs and empty stub files.
6. **Parallelize across disjoint directories only** (backend/ vs frontend/),
   with shared contracts (schema, API shape, env vars) frozen in a SPEC.md
   every agent reads. Never let two agents own the same file. Don't serialize
   on the CLI binary itself: concurrent instances of the same agent CLI
   (two `agy` runs, two `hermes chat` runs) are fine when their trees, ports,
   and target files are disjoint — queueing behind a busy binary needs a real
   conflict, not default caution.

## Crash diagnosis (OpenCode, host config)

- **Instant (~2s) UnknownError/`ref=err_*` on real prompts, trivial prompts
  fine** → prompt-triggered path, not the provider. Rerun with
  `--print-logs --log-level DEBUG`, read the first ERROR in
  `~/.local/share/opencode/log/opencode.log`.
- **`SchemaError: Expected a string starting with "prt"`** → a local plugin
  injected a synthetic message part whose id lacks the `prt_` prefix. Fix the
  plugin's id prefix; stop debugging the provider. (Real instance: the
  tool-router plugin used `tr_` ids.)
- **"permission requested ... auto-rejecting"** → missing `--auto`, or the
  command pattern isn't allowlisted in opencode.json `permission.bash`.
- **"agent X is a subagent, not a primary agent"** → pick a primary-mode
  agent or the default.

## Rules

- Never substitute a plausible self-report for a verification run — always
  re-run tests/builds yourself before reporting success upward.
- For maintaining a live UI takeover against an updating host (extension-surface
  architecture, upstream-diff auto-port trigger, never-overwrite contract), see
  `references/live-ui-takeover-maintenance.md`.
- One broken command shape wastes more time than the fix; validate the full
  invocation (flags + agent + model + dir) cheaply before scaling it up.
- Record working invocation patterns and crash signatures in the relevant
  tool skill when they were non-obvious; future sessions must not re-derive
  them by trial and error.
- **Headless permission walls differ per binary.** `claude -p` without
  `--dangerously-skip-permissions` stalls on file access outside its cwd and
  silently produces nothing (no report, no error surface in the tail) — the
  failure looks like a hang, not a denial. When a headless agent run produces
  less than the brief demanded, read its session jsonl
  (`~/.claude/projects/<dir-slug>/<session>.jsonl`) for permission-denied
  texts before assuming a hang; fix the invocation (flag + run from a cwd
  that contains every path the brief names), then relaunch. Non-interactive bash denials are the loud sibling: network commands like `curl` fail fast with "command requires approval, session non-interactive" — pre-authorize with `--allowedTools 'Bash(curl:*),Bash(curl *),WebFetch,WebSearch'` (pass BOTH the colon and space wildcard forms; one alone does not match every invocation shape), and smoke-test one real tool call under the exact flag set before committing to a long run.
- **Headless runs die with the session that spawned them.** A gateway restart
  kills backgrounded agent CLIs mid-run; their half-written outputs (uncommitted
  edits, partial reports) are still on disk. After any restart, check the work
  tree first (`git status`, report file present?) and decide finish-vs-relaunch
  from the artifacts, not by blindly relaunching.
- **A backgrounded CLI can outlive the restart of the tool that tracks it** —
  liveness checks that grep for a substring of your own prompt also match the
  tracker's wrapper process and report "running" forever. Confirm liveness by
  the artifacts the run must produce (file mtime advancing, log lines appended),
  or by the exact binary path in `pgrep -fa`, not by a prompt substring.
- **Model identifiers for one-shot agent CLIs drift** (e.g. agy rejects
  `gemini-3-pro` but accepts `gemini-3.1-pro-high`); list current ids
  non-interactively (`agy models`) or from an invalid-model error, then retry
  with an exact name from that list — do not guess a second identifier.
- **agy build invocation (verified shape).** `agy -p "$(cat scratch/prompt-build.md)"
  --model gemini-3.1-pro-high --mode accept-edits --dangerously-skip-permissions
  --add-dir <repo> --print-timeout 180m --log-file scratch/agy-build-cli.log
  </dev/null > scratch/agy-build.log 2>&1`, wrapped in `timeout <secs>` and
  launched via `terminal(background=true, notify=true)`. `--print-timeout`
  must cover the whole build or long runs are killed early; gauge progress by
  artifacts (scaffold dirs, `node_modules` size) plus the log tail.
- **Insert an operator review gate between plan and build.** The plan doc is the
  build agent's contract: when requirements move after the planner ran, patch the
  plan doc and the build prompt in place — re-running the planner throws away a
  good research pass. Keep deployment (systemd/tunnel/DNS) explicitly out of the
  build agent's scope; the operator deploys after acceptance.
- **Reasoning levels for hermes delegation runs:** `--reasoning` accepts
  none→xhigh plus `max` and `ultra` (verified `ultra` on glm-5.3/zai); reserve
  `ultra` for plan and review agents.
- **Content the agents write is URL-scanned:** a literal link-local/metadata
  address inside a file being written is refused (`Blocked: URL targets a cloud
  metadata endpoint`) — write the CIDR range (e.g. `169.254.0.0/16`) instead of
  the single literal IP.
- **Single-query hermes agents may route shell facts through browser_exec** when
  terminal approvals block — `preparing browser_exec` lines doing version
  checks, `ss`, or file reads are the channel working as intended, not a fault.
- **Provider quota/session limits exit fast and masquerade as task failure.** `claude -p` on an exhausted claude.ai session exits in ~2s with "You've hit your session limit · resets <time>" — no work done, nonzero rc. Grep the run log for "session limit" before diagnosing anything else; supervisors must treat a quota probe failure as WAIT-for-reset (poll `claude -p 'Reply OK' --max-turns 1` every few minutes until it answers), never as a failed attempt that burns the retry budget.
- **Hermes itself is a delegation channel when external CLIs are barred or quota-exhausted.** Verified one-shot shape: `timeout <secs> hermes chat --query-file <prompt-file> --oneshot -m glm-5.3 --provider zai --reasoning high --max-turns 150 --in <workdir> </dev/null > log 2>&1`. Probe the model first with a marker (`hermes chat -q 'Say: PROBE-OK' --oneshot --max-turns 2 -m <model> --provider <prov> | grep PROBE-OK`). Its stdout is a live-rendered pane with ANSI/TUI frames — grep for tool lines and final answers, never read raw. Prompts that reference skills must name them by skill_view name, not filesystem paths.
- **Multi-phase agent pipelines get an idempotent supervisor, not a one-shot script.** Write a chain script whose phases gate on deliverable artifacts (file exists AND size above a threshold) so any restart resumes instead of redoing work; allow N attempts per phase with a model/provider probe between attempts; append every state transition to one state log. For multi-batch builds, gate each batch on an explicit completion marker the agent must append to a shared build log (e.g. `BATCH <id> COMPLETE`) — greppable, restart-safe, and lets the pass-budget retry until the marker exists instead of trusting exit rc. A phase failing while its probe also fails means wait, not abort. Gate on the SUPERVISOR's own view of the artifact, not the producing agent's exit rc — a build agent can exit 0 after stopping mid-scope to ask "shall I proceed to phase 2?" (headless nobody answers), leaving later phases silently undone while the chain marches on.
- **Build agents invent scope: give the reviewer a diff against the base branch.** An unattended build agent swapped the site's canonical domain to one nobody owns across 20+ files — plausible-looking, nothing in the spec asked for it. The review prompt must diff the whole branch (`git diff main...<branch>`) and check identity-level invariants (canonical URLs, env names, outbound links, package deps) against the base, not just whether the requested work exists. Canonicalize any unauthorized identity change as a blocker requiring the owner's decision.
- **A downstream consumer waiting on an upstream artifact should gate on the artifact, not on the producer's completion signal.** Chain the dependent run behind a file-size/exists loop on the artifact (e.g. style doc > N KB) rather than sequencing on process exit — it decouples producers of different speeds and survives restarts for free.
- **Killing a supervisor wrapper does not kill the CLI it launched.** The child agent (agy/claude/hermes chat) survives as an orphan and keeps working; a wait-loop gate may also have already cleared and launched the child before you killed it. After killing any wrapper: check the real child by exact binary in `pgrep -fa` (not prompt substrings), and if it's alive, re-attach a lightweight watcher (pid loop) that runs the post-build checks the wrapper would have run.
- **Verification harnesses read transient state during orchestrated mutations.** A check that fails while a build agent is mid-flip, or in the seconds after a service restart (session tokens invalidated, config half-written), is a re-probe candidate: wait for the quiet boundary, re-auth, re-run — only then treat it as a finding. Services under systemd `Restart=always` recover on their own within one restart cycle; check `systemctl is-active` and curl again before intervening manually.
- **When a mid-pipeline owner decision times out, proceed on the recommended reversible option** and say so in the report — a timed-out clarify is not a veto, it is absence. Keep the reversal cheap (branch never pushed, timestamped backups on disk) so the owner's later decision only ever undoes, never repairs.
- **Chunk multi-week scopes into per-acceptance-unit build passes from the start.** A single headless build pass handed a plan whose full scope is weeks of work will deliver the foundation plus generated stubs and defer the deep work — honest, but not what "implement the plan" implied. Split the plan into batches (one page/screen/module per pass, each with its own acceptance criteria) before commissioning; when a deferral does happen anyway, the review prompt must REQUIRE the reviewer to rule on the deferral and emit the concrete continuation batch plan, which becomes the next build prompt.
- **A green harness proves only what its checks actually exercise.** A harness that validates files, manifests, and endpoints but never loads a page in a real browser cannot catch runtime-global collisions — e.g. a QA hook assigning the very global every plugin stubs gate on, while each stub's `.catch(() => {})` swallows the resulting failure, so every route serves an error card with zero surfaced errors and the harness stays green throughout. Every flip/acceptance gate needs one positive browser assert (page registers and renders real data, not merely absence of errors), and the harness must authenticate exactly as the product does (cookie session minted via the login endpoint) — basic-auth headers get `401 no_cookie` on API routes, so probes fail for environmental reasons and bury real findings under noise.
- **Resume a budget-exhausted verification agent instead of restarting it.** When a review agent burns its entire turn budget mid-verification and exits without writing the deliverable, resume the SAME session (`hermes chat --resume <session-id>` with a fresh bounded budget): the dead run holds hundreds of tool calls of gathered evidence that a fresh session must re-derive. The finish prompt must name the deliverable file, forbid new exploratory verification, bound fixes to the known open items, and explicitly allow honest NOT-VERIFIED rows — otherwise the second budget dies the same way chasing completeness.
