---
name: capability-router-operations
description: "Operate and tune the local capability router."
version: 1.4.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [router, retrieval, bm25, dense, fusion, aliases, latency, skills]
    related_skills: [retrieval-eval-harness, agent-skill-sourcing]
---

# Capability router operations

The local router (`~/Work/tool-router`, entry `~/.tool-router/route`) intercepts
every prompt on every harness and emits a ranked card of skills, MCPs, agents
and commands. This skill is how to change it safely. Measuring quality is
`retrieval-eval-harness`; finding and installing new capabilities is
`agent-skill-sourcing`. The project is published as **ToolR**
(github.com/jitin-neutrinos/ToolR, installer at toolr.jitinnair.com via
`tools/deploy.sh` + a static-file service); the published repo and the working
tree are the same code — deploy after every shipped change, and the installed
skill tree is symlinked to the working tree so the two can never drift.

## Card depth is dynamic: complexity, cliffs, diversity, adoption

A fixed pick count is two failures at once: weak tail rows on simple asks and
missing specialists on complex ones. The layered design, in the order the
stages run:

- **Complexity depth (zero ML)**: derive depth from signals already
  extracted — intent count, prompt length, named file paths, coordinating
  conjunctions. Map to a small ladder (simple/standard/complex), cap by the
  model-tier ceiling, and let an explicit user count win outright.
- **Score-cliff truncation**: cut where relevance actually falls — the
  largest adjacent relative drop above a threshold — never at a flat ratio of
  the leader. Decay noise is gradual; a cliff is a shape.
- **Query-residual diversity**: candidate tokens minus query-shared tokens
  is the part of the task only IT covers; drop a pick whose residual Jaccard
  against an already-kept pick crosses the threshold, keep the higher-scored
  one. ALWAYS keep a small floor (a unanimous corpus is signal too). Skip the
  whole stage when the user asked for an explicit count — the count contract
  outranks diversity, and a new filter stage silently eating the count
  contract is exactly how a selftest goes red; after adding ANY card filter
  stage, probe the count knobs through the installed entrypoint.
- **Adoption-fed adjustment**: harvest (routed → Skill-loaded within a few
  minutes) daily into a frozen JSONL; only when the span covers a full day,
  move depth by ±1 on the loaded rate. Keep the adjustment modest for the
  first several days — one day of data supports a tiebreak, not a policy.

Golden-set ablation is still the shipping gate for all of it: a depth change
is a ranking change.

## A per-lane penalty must be re-applied after fusion

Score-level gates (wrong-ecosystem demotion, generic damping, weak-pick
labels) are computed in the lexical scorer — but the dense arm knows nothing
about them. An item whose *description words* are cross-ecosystem (an Elixir
review skill mentioning "concurrency"/"streaming") vector-matches an off-
ecosystem query at dense rank 2, and its dense bonus clears min_score even
though the scorer had demoted its lexical row below the floor. Re-apply the
penalty to the FUSED score after the lanes merge, tagging the row so the card
can say why it is weak. Tune the demotion factor against the golden set: the
knee sits between the obvious candidates — the old factor left the wrong row
above the floor, a hard factor cost R@1 on genuinely-right rows in
ecosystem-ambiguous queries, and the middle value kept the baseline while
burying the wrong row.

## Delivered ≠ used: measure adoption as its own metric

Retrieval quality (recall/MRR on the golden set) and **adoption** (the model
actually loading what the card names) are different failure surfaces, and only
the first is measured by `eval/`. Before diagnosing "the harness rarely uses
everything", measure the pair:

- **Deliverability per surface**: a card only exists where the interceptor is
  wired AND enabled. An interceptor present on disk but absent from the
  harness's plugin-enable list is a silent no-op — those surfaces route with
  no card at all. Grep the harness's own logs for the card marker, not the
  plugin directory listing: "installed" and "firing every prompt" are
  different claims.
- **Adoption pairing**: over a window, per session, collect the card's pick
  names (regex the pick lines) and the model's actual `Skill` tool inputs
  (`tool_use` records — name Skill, input command value); the pair rate is
  `len(picks & loads) > 0` per card-bearing session. A measured 0% pair rate
  is the decisive finding — no scorer tuning can fix it, because the scorer
  never sees the failure.
- Prose-only delivery has no teeth; the measured consequence is the model
  treating the card as boilerplate. The binding mechanism (`--enforce`:
  PreToolUse deny-once when card-named skills were not loaded, PostToolUse
  clears) is the documented fix — enabling it changes harness behavior, so it
  is an explicit user decision, never a drive-by.
- Close the loop: real usage must reach the learned prior with no human
  step. `route --record` is manual and dies first; the durable wiring is the
  harness's own Skill-load event (PostToolUse hook on Skill -> record the
  loaded name, gain asymmetric with the clamp). An empty learned file after
  weeks of traffic means the feedback step was never wired into any flow —
  check for the automatic path first, not the manual one.

## A kind-representation audit: compare picked share to corpus share

"Why is the card disproportionate in X?" is answered by a measurement, not
inspection: over a sample of real queries, count picks per kind and compare
each kind's picked share with its corpus share. Result on the live corpus:
skills UNDER-picked (73% of corpus, ~54% of picks) while MCPs/commands/fleet
items are over-picked — the per-kind quota deliberately reserves slots. That
bias is a design decision, not a bug; confirm the quota config matches the
intended diversity before touching the scorer, and lower `kind_quota` to 0
to restore pure score order if the user wants it gone.

## When to Use

- A routing card is missing, stale, wrong, or slow on any harness.
- Asking which skills/tools exist for a topic and getting the wrong set.
- Changing the index, the scorer, fusion, the alias tables, or any stage of the
  pipeline.
- A skill or MCP was installed and does not appear in the router.
- The card arrives after a harness hook timeout and seems to vanish.
- A card shows the right domain but the wrong sub-discipline (a motion question
  returning only design skills) — that is a vocabulary gap, see below.

## Model-aware card sizing and the hot-path cost rule

Sizing the card to the calling model's tier and context window is a
feature the user asked for; the allowed inputs are hook-env vars
(`ANTHROPIC_MODEL`, `HERMES_MODEL`, `OPENCODE_MODEL`, `GEMINI_MODEL`, …), a
user-editable override file, and cached catalog data. Success criteria for
any such resolver, measured in one session:

- The resolver never calls the network on the route. Pricing/context refresh
  is a separate command writing a local file; the route reads it. A per-prompt
  billing-API poll reintroduces the exact network hop deletion removed.
- Tuning a count cap to a tier class is measured against the golden set
  before shipping: a cap change is a ranking change, not a UI tweak. One cap
  of 8 cost measurable R@1; retuned ceilings restored it. An explicit user
  count always overrides any derived cap.
- Unknown model must degrade to the default card, not shrink it — the model
  line may say "(unknown)", the behavior must match the old default exactly.
- A fallback prior is a prior, not a measurement: when no model is resolvable,
  the card must SAY "not exposed by harness — conservative default" and name
  the fix (export the env var), never print the default's ctx/tier as if they
  were the session's facts. Prefer a local ground-truth source over the prior:
  the gateway's own session store records the per-session model and refreshes
  on every turn — a stat + one indexed SELECT beats guessing, and beats a
  billing-API poll (never on the hot path). Prefer the per-session env var
  stamped by the invoking harness over the DB when both exist: the DB row is
  machine-global, so a parallel active session can shadow the real one.
- Knob precedence (env > config > derived > user-N) must be probed through
  the *installed* entrypoint, not in-process functions: module tests can pass
  while the CLI path reads a different precedence.

An authority/self-heal gate ("check the harness's always-on docs grant tool
authority; write the delegation block if missing; notice on the card if that
fails") is the same shape: scan small files for a marker, memoise per
process, fail-open to the pre-gate behavior. '~' must be expanded with
`Path.home() / path[2:]`, not `/` joins on a string containing '~' — the naive
join produces a root-relative path that silently never matches, and the gate
then reports missing authority on a machine that granted it.

## The card has two audiences: the model and the user

The model needs the markdown card (contract lines, scores, gates) in its
context. UI surfaces need the same information as a structured surface — a
canvas table of picks with scores, kinds and match reasons, plus decision-
context callouts — because a prose wall in the chat is what the user actually
sees. Rules for the display transform: generate it by PARSING the emitted
card (single source of truth — a separately-built payload drifts), validate
it against the destination surface's schema (closed block-type set, aligned
columns/rows) before shipping, keep the markdown card intact for the model,
and gate the transform on the invoking surface so plain terminals keep prose.
Fail-open: parse failure means the surface shows prose, not that routing
dies. Route the transform through the card cache like the card itself so a
cache hit still renders.

## Publishing the router as a product (ToolR)

The repo is public (github.com/jitin-neutrinos/ToolR) with a hosted one-line
installer (`curl -fsSL toolr.jitinnair.com/install.sh | bash`) served by a
small static service behind the cloudflared tunnel. Rules that shipped with
it:

- **De-personalise before publishing**: no home-dir absolutes in scripts (env
  vars with sane fallbacks), no session data in the shipped tree, no private
  project names in upstream alias/comment text that a stranger's install
  would carry. Golden-set labels may reference private skills; note that the
  reference set is the owner's.
- **The hosted copy must never be stale**: the installer clones the repo, so
  a stale `install.sh` on the CDN points users at a repo that moved (wrong
  URL after a rename = install fails for everyone). Redeploy in the same
  change that ships repo-side edits, and verify the served bytes, not the
  local file.
- **Serve with explicit cache headers**: a naive static server lets the edge
  cache a mutable script; users then run yesterday's installer against
  today's repo. Hash-named artifacts may cache forever; mutable entrypoints
  (`install.sh`, checksums) must be `no-store`.
- **End-to-end test the installer from a clean context**, not the dev
  machine's already-installed state: `curl … | bash` into a temp HOME is the
  only run that proves a stranger's path.
- One local session model is a real resolution source: the harness's session
  store records the model per session and refreshes every turn. A per-turn
  billing-API poll is the forbidden hot-path hop; reading the session store
  (stat + indexed SELECT) is not.
- Precedence knobs must be probed through the *installed* entrypoint
  (`route` launcher), not in-process: a stale copy in the install dir made
  the CLI behave differently from the module tests, and only a launcher-level
  probe showed it. A symlink from the install dir to the working tree removes
  the whole discrepancy class.

## Latency is a hard requirement, not a goal

A routing card that arrives after the harness hook timeout is **discarded
silently** — no card, no error. So the budget is a correctness property.

- Measure the per-stage cost before changing anything: BM25 ~4 ms, dense embed
  ~400 ms, local rerank ~800 ms (off by default). The whole route is 0.17 s
  today; anything that moves it toward seconds needs a measurement, not a
  guess.
- Enforce the budget **between stages, never mid-flight**, so the card is always
  coherent. Skip the optional stage when the remaining budget cannot cover the
  call plus what follows it, and say so in the card — a silent skip reads as a
  broken stage.
- **Never put a network call on the hot path.** One registry search measured
  57 s inside a single route. Move the whole lifecycle to a detached background
  child (stamp-file rate limit, e.g. one sweep a minute), keep only the cheap
  local record inline. The card must never depend on the child's result.
- Check the hook timeout in the harness config against the measured worst case
  and leave headroom. If the harness exposes one, set it; do not rely on the
  router being fast enough.

## Sourcing and installs need a relevance gate, not just safety gates

Free-ness, install count and injection-screening say nothing about whether a
candidate does what was asked. Measured failure: a multi-role chatroom skill
was auto-installed for `fix the astra chat streaming bug` because it matched
the word "chat".

- Cheap deterministic gates first (kind, free, install count) — a local model
  call is 4.5 s and must never be spent on a candidate already disqualified.
- Then a **relevance judge**, fail-closed: `None` (judge down or unparseable)
  must mean "do not install". Never map uncertainty to permission.
- Cache registry results per intent. Nothing is installed from a cache without a
  freshness check, so a cache is a latency win, not a safety hole.
- On rollback, clear the intent's installed marker too, or the intent stays
  locked out against the correct candidate forever.

## Delete a stage before you optimise it

The prompt-rewrite (LLM) stage was removed: the hook routes the user's own words
and makes no model call. Route latency went from a 2.5-5.5 s median with 15-18 s
outliers to a flat 0.17 s, inside a 5 s hook budget.

Reach for deletion when **all three** hold — check them in this order:

1. **Is its only unique output already produced for free?** The rewrite's sole
   contribution over the card was a `Use:` line naming the picks. The card
   already emits the same list with scores and match reasons, and ships whether
   or not any model answered. Duplicated output does not justify a network hop.
2. **Is the provider unreliable in a way you cannot engineer around?** Free
   tiers returned HTTP 200 with an **empty body** on ~1 call in 5 for identical
   requests. Deadline, retry and circuit breaker all still left the stage slower
   than simply removing it. Do not escalate complexity to rescue a stage whose
   provider cannot be made dependable.
3. **Does it sit on the critical path of every message?** A hook stage runs on
   every single message; its cost is multiplied by the whole session.

- **Audit before deleting**: keep the module, keep its tests, and pin the
  expensive-to-rediscover findings in a self-check so the knowledge survives the
  code. The gateway header requirements alone cost a long probe to find.
- **Pin the removal**, not just the absence of a call: assert the pipeline does
  not import the module, every caller passes the disable flag explicitly, and a
  measured route stays inside budget. Otherwise a well-meaning edit puts the
  network call straight back.
- When a user steers you mid-task toward deletion, treat it as a signal that
  earlier work was solving the wrong layer. Escalating reliability on a
  redundant stage is the failure mode to watch for in yourself.

### If you ever reinstate an LLM stage

- **A harness hook is a separate OS process that runs before the harness
  dispatches the turn.** It cannot call the model that is about to answer — that
  model has not loaded the prompt yet. Do not promise "rewrite with a sub-agent
  on the parent model"; state the constraint and deliver the nearest real thing.
- What is knowable is the **session model**, which harnesses export into the
  hook environment. Resolve an explicit override first, then map the session
  model **down to its fast sibling** (a 6-line structured rewrite is not a
  reasoning task), then fall back to a free default.
- Pass the ranked picks in and require a `Use:` line naming each with a reason,
  forbidding invented names. Demanding a capability list when none was found
  yields a confident "none identified" for a request that does have one.
- Do not reuse a harness's own session token for a vendor API. A login token is
  scoped to the harness's endpoints and the vendor API rejects it; that is a
  credential boundary, not a hurdle to work around.

See `references/free-model-gateways.md` for the header, empty-body and
backoff findings that any free-tier LLM stage has to handle.

## Vocabulary is the dominant failure mode

Measure `unreachable@k` before tuning the scorer. When most labelled queries
share no tokens with their own answer, the gap is descriptions and aliases, not
ranking — a scoring change will not move it.

Use two directional layers, and never let them double-count:

- **Index-side** (capability -> extra terms), applied at index time so every
  retrieval lane sees it at once. Prefer many precise terms over few broad ones.
- **Query-side** (words the user types -> concepts), applied in tokenize. Map
  the words real users type, including inflections the table missed
  (`janky`/`jank`, `choppy`, `stuttering`).
- Audit for **phantom keys** (a key matching no live capability is dead weight
  the moment it is written) and for **generic-only aliases** — a token the
  scorer damps in both the score and its denominator moves nothing.
- Verify the fix on the exact query that failed, and pin it in a self-check.

## Corpus coverage: measure the tree, not the name

- Dedupe is usually first-wins by name, so a skill present in several harness
  trees is indexed once. **Count what is genuinely unreachable by comparing
  content, not by asking which path an item came from** — a path-count of zero
  can mean the tree is absent, or that every one of its skills is already
  indexed from elsewhere. Report the distinction honestly; the second case is
  not a bug.
- Depth matters per layout: a flat `<root>/<name>/SKILL.md` and a categorised
  `<root>/<category>/<name>/SKILL.md` tree need different walk depths, and a
  superset tree added as a root must come **last** so first-wins dedupe keeps it
  from perturbing existing entries.
- A directory watcher fires for flat files but not for changes inside a nested
  subdirectory, and atomic directory renames — how skills usually arrive — are
  missed outright. When a full rebuild is cheap (sub-second for ~800 items), a
  **timer beats a watcher**: it cannot miss anything and costs nothing. A
  path unit that has hit its start limit is worse than none, because it looks
  configured.

## The CLI is the product: an agent's first call must not fail

Agents call this by running the command, not by reading the code. Two measured
defects came from that surface, and both were invisible to the tests:

- **Accept the count as a flag AND in the text**, with precedence
  flag > prompt > config, clamped to a sane range; a count a user can type in
  two places must agree in both. `-n/--top/--count N` shipped 2026-10-05 and is
  verified on the installed router (42/42 selftests, run of
  `route --top 20 "..."` returning exactly 20), but a skill documenting a CLI
  fix is still not evidence the fix shipped — the installed binary is the only
  authority, so confirm with `route --help` before relying on any flag.
- **A requested count was not delivered.** Asking for 20 returned 19: a score
  floor and a per-kind tail cut removed real candidates and nothing topped the
  list back up. **If the caller asks for N and the corpus has N candidates,
  return N** — the card prints each score, so a weak tail pick reads as weak
  instead of vanishing. Under-filling is a silent lie about your own output.
- **A bad flag must teach, not wall.** The argparse default prints a usage block
  with no example, which left the caller guessing. Override the parser's error
  path to print the nearest **real** option plus one worked example. Verify the
  suggestion is a real option: the first attempt here echoed the bad flag back
  (`--top --topp`), which is the same failure with more words. Pin "must not
  echo the bad flag" in a check.
- **Keep `--help` true.** It must describe what the tool does, end with a worked
  example, and never advertise a stage that was removed — a stale help string
  is worse than none, because it is authoritative-looking.

Discoverability is not the same as documentation. After changing the interface,
update **everywhere an agent learns it**: the skill, the harness rulebooks that
are auto-loaded (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md` copies), and `--help`.
Rulebooks drift silently — they described a four-stage pipeline with a rewrite
stage that no longer existed, and none of them mentioned the count flag. When
one copy changes, the others are already wrong.

Make the instruction explicit, not implied: state that when the user says "use
the tool router", run the command, do not re-derive the pick list by hand, and
do not guess at flags.

## Route on the DOMAIN, not on the surface the user is typing into

A card that names the product named in the user's message but the wrong discipline is a
vocabulary failure wearing a costume. Measured case: a request to resume an insurance
AI-platform project returned three web-UI front-end skills and a HuggingFace download
skill, because the user's phrasing carried the host app's name and the words "session",
"work" and "build" — every one of them present in the session transcript, none of them part
of the task.

- **Strip the surface vocabulary before routing.** The product name, "session", "continue",
  "chat", "webui", "report" describe WHERE the message was typed, not WHAT it asks. Remove
  them from the query; they are the highest-frequency tokens in a chat session and they
  outvote the real content.
- **The domain noun is the signal, and it is often the rarest token in the message.** For an
  insurance-AI build the discriminating words were `model`, `extraction`, `training` — one
  appeared in a skill title, the others in a description. Score survives when the rare token
  is there; it collapses when the query is all high-frequency furniture.
- **A card whose picks share no vocabulary with the noun the user used is visibly wrong** —
  trust that read. `matched:` lines expose which tokens fired; when they are all generic
  and none is the domain noun, the card has matched the wrapper, not the task. Check
  those lines FIRST on every card, before acting on the picks: one glance at the
  `matched:` set is cheaper than loading three irrelevant skills and noticing afterwards.
- **Re-route once with domain terms and use both.** Say in the reply which card served what,
  and when the first one misfired, say so rather than silently proceeding — a wrong card
  quietly loaded three irrelevant skills and delayed the real work.

## Route once per PHASE, not once per request

A multi-phase ask ("overhaul the engine, then revamp the page it lives on") does
NOT route well as one blended query. Run the router separately per phase, each
with that phase's own vocabulary, and run both before acting.

- The vocabulary gap is the whole point of a second pass. A theme-engine query
  returned engineering skills and a design-query for the same task returned
  `glassmorphism`, `impeccable`, `frontend-design`, `supanova-premium-aesthetic`,
  `web-design-guidelines` — the design-revamp phase's actual toolkit. A single
  blended card mixed the two and surfaced neither cleanly.
- Two calls overlap by roughly one skill, which is the cost; under-delivering a
  phase its missing specialists is the alternative.
- Keep both cards. The phase-2 card is what names the visual skill to load before
  editing, so it must be read at the phase-2 boundary, not just at the start.
- Say in the reply which phase each card served, so a weak card can be attributed
  instead of silently believed.

## Two contracts that collide on the same knob: pronounced counts and abstention

A sub-floor top-up that fills a requested count to N also fills the default
card with weak picks. Gate it on *how the count arrived*: an explicit
user count (flag or number in the prompt) must fill to N; a defaulted count
must not, or a prompt naming nothing routable emits ten sub-threshold picks.
Deriving the predicate from `n_override`/`user_n()` (the count's origin),
not from N itself, resolves the collision in one parameter.

After a rich-index change, re-derive weak-pick labels from **identity fields
only** (name/description/aliases): body-only token hits otherwise clear a
'weak' label a realistic probe depends on and a selftest catches it. Identity
evidence is what the label means; body text is display evidence.

An injected-context card whose new lines appear on one code path but not
another is a stale-distribution symptom: grep for which copy (a symlinked
install dir vs the working repo) the entrypoint actually executes before
debugging the feature itself. A one-line symlink to the working tree removes
the whole discrepancy class.

## An alias layer must survive the save/load round trip

Measured failure (2026-10-05): the entire alias layer was a silent no-op in
production for its whole life. It worked in fresh `build_index()` runs and in
selftests — and did nothing on any real route.

- `save_index()` strips `tokens` to keep `index.json` small; `load_index()`
  then recomputed them from name+desc+extra ONLY. **Any derived field stripped
  at save time must be re-derived at load time by the same code that created
  it**, or the persisted state and the in-process state are two different
  corpora. The regression test must exercise the round trip, not a fresh build.
- The dense lane embedded `kind: name. desc` only, so the semantic lane never
  learned the alias vocabulary and its vectors actively demoted exactly the
  skills the aliases were added to promote — while RRF (rank-only, flat head)
  rewarded its wrong top hits. **Every retrieval lane must consume the same
  enriched text**; enriching one lane and not the other makes fusion
  counterproductive. Changing embedded text invalidates the vectors: the
  content hash does not change when alias text does, so the incremental
  builder reuses stale vectors — move the `.npz` AND `.meta.json` aside for a
  full rebuild.
- A project-specific skill must not win a generic request on a shared
  adjective (`revamp`/`overhaul`/`enhance` are real signal but weak evidence
  of topical fit). Demote adjective-only matches and LABEL them in the card so
  a weak pick reads as weak — but the ordering fix for the residual score gap
  ("chat" outweighs "composer") is score-aware fusion per the research note,
  measured against the golden set, NOT a drive-by sort key: one was tried and
  reverted the same day for breaking the opposite case (a real project
  request lost its own skill) and desyncing printed score from printed order.

## Self-check discipline

- One named regression per defect, each citing the measurement that motivated
  it. A check with no measurement behind it is a guess.
- **The runner must report a raising check and continue.** One check that throws
  aborts the run and hides every other check's state.
- Assert against a function's *code default* when it memoises into a module
  global, or the assertion silently tests whatever an earlier check loaded.
- Monkeypatch the layer under test, not its caller, and restore module globals
  in `finally` — leaked env and cached config make later checks non-deterministic.
- In tests, strip session-model env vars and fake credentials: on a live harness
  the real environment leaks in and the fallback path becomes untestable.

## Reporting

State measured numbers with the command that produced them. When a claim turns
out wrong mid-session (an inflated count, a wrong root cause), correct it
explicitly and say which part was the error — the number, the cause, or the
premise. Never let a corrected figure stand next to the original one.

**Verify the measurement measures what the sentence claims.** Three real errors
in one session, all in my own reporting, none caught by a test:

- I claimed a corpus tree was entirely invisible, measured as "0 items sourced
  from this path". The path genuinely was never read, but comparing **content
  hashes** across trees showed nearly all its skills were already indexed under
  the same names from a different tree. The real number was a handful, not
  hundreds. When a path count is zero, distinguish *the path is not read* from
  *everything in it is already indexed elsewhere* before naming a magnitude.
- I reported a lane scoring exactly 0.0 as a quality finding. It was a degraded
  run: a breaker tripped under contention, every query silently fell back, and
  the lane returned a hard zero. **A bimodal spread — values clustering at 0 and
  at a healthy value — is a harness fault, not variance.** Have the harness flag
  lane health and drop degraded rows from the regression log; a false zero reads
  as "this technique is worthless" and can get a working method deleted.
- A short `"Reply with exactly: OK"` probe ranked candidate models one way and
  the real payload ranked them another. Toy probes measure queue depth, not
  capability.

Prefer the cheap falsification before the claim: one extra command that could
disprove the sentence beats a confident paragraph you later have to retract.

## References

- `references/retrieval-quality-2026-10.md` — measured baselines, fusion
  findings, model/latency tables, and the open coverage gaps.
- `references/free-model-gateways.md` — opencode-go and OpenRouter quirks for any
  free-tier model call: the required browser `User-Agent` and `X-Session-Id`
  headers, HTTP 200 with an empty body, and why toy-prompt latency does not
  transfer.
