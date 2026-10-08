---
name: capability-router-operations
description: "Operate and tune the local capability router."
version: 1.5.0
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
`agent-skill-sourcing`. The project is published as **Toutur** — toutur.jitinnair.com, repo
github.com/jitin-neutrinos/Toutur (old ToolR name/URLs redirect) — via
`tools/deploy.sh` + a static-file service; the published repo and the working
tree are the same code — deploy after every shipped change.

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
  different claims. Disk + enable-list still is not firing: run the host's own
  plugin DISCOVERY (Hermes: `collect_directory_manifests()` in its venv) and
  require the interceptor's name in the result — a plugin missing its manifest
  or its `register()` is invisible to the host while looking installed. The
  cheapest death test is the timestamp stop: a per-prompt cache or audit file
  whose mtime stopped days ago, against known live traffic, dates the death to
  the last process restart — with no error anywhere, because every stage fails
  open.
- **Adoption pairing**: over a window, per session, collect the card's pick
  names (regex the pick lines) and the model's actual `Skill` tool inputs
  (`tool_use` records — name Skill, input command value); the pair rate is
  `len(picks & loads) > 0` per card-bearing session. A measured 0% pair rate
  is the decisive finding — no scorer tuning can fix it, because the scorer
  never sees the failure.
- **A global adoption ratio across harnesses is fiction — scope the ledger per
  harness.** The failure shape: one harness's PostToolUse hook is the only load
  counter while the denominator counts every route from every harness; the
  resulting single-digit percent reads as total adoption collapse and escalates
  enforcement on a number no harness produced. Rules: per-harness routed/paired
  counters; the gate reads only its OWN harness's ratio; a harness with no load
  source reads null (no verdict), never 0%.
- **The denominator is routes that suggested skills, not all routes.** Most
  routed prompts name zero skill-kind picks (measured ~78%) — an MCP/agent/
  command pick cannot be 'loaded' like a skill, so counting those routes
  dilutes the ratio toward zero regardless of behavior. Filter at record time
  on skill-kind picks, not at report time.
- **Never escalate on absent data — put a measurement floor under the ratio.**
  Below a handful of routed-with-suggestions samples the ratio returns null and
  below-floor is false. A floor evaluated on one or two samples produces the
  same false escalations the per-harness rewrite exists to kill.
- **Hookless harnesses still have a numerator: harvest loads from their session
  store.** A harness that injects the card via a gateway plugin has no load
  hook, but its skill-load tool calls sit in its own session DB — an hourly
  cron counting new loads and new routed prompts since the last run fills the
  ledger off the hot path. State the caveat in the data: bulk harvest cannot
  replay pairing windows over historical traffic, so early paired counts
  undercount until the harvest runs continuously.
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

NEVER let a membership pass reorder or re-scope what it draws from. Measured 2026-10-08 (commit e02aca7): `_top_combined` split skills/others by the tail CUT, not by KIND — a dominant leader (1.87, tail cut 1.029) pushed 40+ sub-cut SKILL rows into `others`, the kind-quota pass filled every slot from that pool, and the fill loop never ran: the true #1 vanished from the card while 0.915 rendered on top. Fix: quota reserves slots for non-skill kinds ONLY (the coverage line's actual promise); skills flow through the fill loop; the output is re-sorted to score order before returning because `_score_cliff` (largest-relative-drop walk) and `diversify` ("rows must be in score order") both assume it. Pinned in `t_quota_keeps_score_order`. Symptom signature to recognise fast: card omits an item that instrumented BM25 ranks #1 — the loss happened in a post-ranking stage, so instrument the stage boundaries, not the scorer.
The same collapse has a SECOND mechanism when the complexity layer hands the card a small n: quota × noise-kinds ≥ n fills every slot before the fill loop runs, and the #1 skill (3.73) vanishes while a 0.72 command renders on top. Reserve one slot for the best skill whenever one cleared the floor (`quota_cap = n - 1` when any skill passed) — the fill loop then spends that slot on the leader, best-score-first. Both mechanisms fail the same way (the quota outlives its 'diversity trim' intent and becomes a leader-removal pass), so test quota behaviour at small n, not just at the default depth.

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

The authority/self-heal gate is the same file-scan shape but with an owner-mandated stricter contract: it must run on EVERY route (no memo — the whole point is catching an update or healing pass that undid the delegation), detect which harness is calling from hook env (TOOLR_HARNESS override, then ANTHROPIC_MODEL/HERMES_MODEL/OPENCODE_MODEL/…), verify BOTH the delegation mandate in that harness's always-on file AND the interception shim (settings.json hook / plugin.yaml / plugin.ts / hooks.json), re-write whatever is missing via the owning installer's idempotent writers, log every repair to a JSONL audit file, and stamp a one-line notice on the card when it repaired something so the user sees the heal. An owner adoption floor (≥75% of routed picks actually loaded) belongs on the same gate: track kept/total in the per-prompt state file, and when below floor after a warmup, escalate the deny-once enforcement to deny-twice with an explicit reason — the smallest lever that changes model behavior without becoming a loop. '~' must be expanded with `Path.home() / path[2:]`, not `/` joins on a string containing '~' — the naive join produces a root-relative path that silently never matches, and the gate then reports missing authority on a machine that granted it.

## Wiring a Hermes gateway plugin so it actually loads (and survives restarts)

- A Hermes directory plugin needs BOTH a `plugin.yaml` manifest (name, version,
  description, author, `provides_hooks`) AND an `__init__.py` exposing
  `register(ctx)` that calls `ctx.register_hook(hook_name, fn)`. Discovery
  (`collect_directory_manifests()` in the Hermes venv) silently skips a
  manifest-less dir — the plugin looks installed and routes nothing. Verify
  with that exact function, not with the directory listing.
- Boot-time plugin activation does not register gateway-transform hooks
  (`pre_gateway_dispatch`); the post-boot path does. After every gateway
  restart the hook is silently dead while files and enablement stay intact.
  Re-arm with `activate_plugin_now("<name>")` run by the Hermes venv
  interpreter, and make it durable with a oneshot systemd user unit pulled by
  a `Wants=` drop-in on `hermes-gateway.service` — every (re)start then
  re-registers the hook automatically (fail-open, ~1 s, audit line in a log).
- The `pre_tool_call` deny shape is `{"action": "block", "message": ...}`;
  `pre_gateway_dispatch` returns `{"action": "rewrite", "text": ...}`.
  Returning None passes untouched — every failure path should.
- NEVER restart the gateway you are chatting through directly — the restart
  kills the conversation mid-turn. Arm it: `systemd-run --user --unit=<name>
  --on-active=120 sh -c 'systemctl --user restart hermes-gateway.service'`,
  finish your reply, and let it fire.
- When a config change must ride along with a plugin install, write it
  through Hermes' own writer (`hermes_cli.config.atomic_config_write`) —
  merging only the keys you touch. The plugins.enabled list is a list-valued
  key: pass the FULL new list as a one-key dict, not a hand-edited dump.

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

## Publishing the router as a product (Toutur)

The repo is public (github.com/jitin-neutrinos/Toutur) with a hosted one-line
installer (`curl -fsSL toutur.jitinnair.com/install.sh | bash`) served by a
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
  (`install.sh`, checksums) must be `no-store`. An origin that EVER served a
  long TTL for a mutable URL poisons edge objects that outlive the origin
  fix — without a CDN API token there is no purge, so also publish immutable
  versioned twins of mutable files (e.g. `checksums-<stamp>.txt` whose name
  matches the immutable-cache regex) and verify what the edge serves with
  cache-busted requests (`?v=$RANDOM`), never only the origin.
- **End-to-end test the installer from a clean context, per OS** — not the dev
  machine's already-installed state: `curl … | bash` into a temp HOME is the
  only run that proves a stranger's path, and a Linux temp-HOME run proves
  nothing about Windows. Three Windows-only defects invisible to every Linux
  test: (1) directory symlinks need Developer Mode or admin (`WinError 1314`)
  — probe symlink capability once with a throwaway link and fall back to
  copying silently; (2) Windows Store Python has no `python3.exe` alias, so
  hook commands hardcoded `python3` install "successfully" and never fire —
  build every hook command from the installer's own `sys.executable`, quoted;
  (3) PowerShell 5.1 conhost prints ANSI escape codes as raw stacked lines
  unless VT processing is enabled (SetConsoleMode) before any rendering.
- **Installer payloads must be self-contained**: every module a harness branch
  imports at install time must be inside the shipped file list. A wirer living
  outside the published payload crashes install on exactly the machines that
  detect that harness — the public path, which the dev machine can never hit
  because its working tree has everything.
- **A hosted landing page is part of the product — QA animations as the user
  receives them, not as code.** GSAP `.from()` tweens toward the element's
  CURRENT value, so against a CSS `opacity:0` reveal class it animates 0→0:
  an invisible hero with zero console errors. Force the end-state first
  (`el.style.opacity = 1`), then `fromTo` with explicit from/to. Screenshot
  only after entrance timelines complete — a mid-animation frame grades as a
  broken layout in vision QA. ScrollTrigger-driven counters resting a few px
  below their start line at load never fire: trigger above-the-fold counters
  immediately (no ScrollTrigger) and call `ScrollTrigger.refresh()` on
  `document.fonts.ready`, because web-font load shifts layout past trigger
  lines.
- **Renaming a published product: split user-facing from runtime identifiers,
  and sweep them differently.** Display names, URLs, repo links, install-dir
  defaults and docs get the new name; internal runtime identifiers (~/.tool-router
  paths, the `route` command, the skill slug, env var prefixes, systemd unit
  names) stay — renaming them breaks self-heal markers, existing users'
  installs and every rulebook quote at once, for zero visible gain. GitHub
  rename auto-redirects old repo URLs, so existing `git pull` flows survive.
- **A new hostname go-live is four steps, and the cache purge is not optional:**
  `cloudflared tunnel route dns -f <tunnel-id> <host>` → add the ingress rule
  (old hostname kept alongside, so existing links never 404) → `kill -HUP` the
  cloudflared PID (config does not hot-reload without it) → purge the zone
  cache, because the pre-reload window's 404s were already cached under the
  zone's 1-year catch-all rule and will otherwise serve stale for a year.
  Probe with cache-busted requests (`?nocache=$(date +%s)`); a plain curl can
  read the poisoned edge entry and send you debugging a healthy origin.
- **install.py --copy destroys same-file-linked skill dirs on SameFileError.**
  When a harness skill dir is a hardlink/same-file into the canonical
  ~/.agents pack, the copy path crashes mid-run and leaves earlier-processed
  dirs deleted. Use the fleet sync as the install path, copy the stragglers
  directly, and grep-verify the new content marker in EVERY harness dir — a
  successful exit from a partially-crashed installer proves nothing.
- One local session model is a real resolution source: the harness's session
  store records the model per session and refreshes every turn. A per-turn
  billing-API poll is the forbidden hot-path hop; reading the session store
  (stat + indexed SELECT) is not.
- Precedence knobs must be probed through the *installed* entrypoint
  (`route` launcher), not in-process: a stale copy in the install dir made
  the CLI behave differently from the module tests, and only a launcher-level
  probe showed it. A symlink from the install dir to the working tree removes
  the whole discrepancy class — but AUDIT the symlinks: a harness dir pointing
  at a path that later moved or vanished (e.g. a pre-rename project dir) dangles
  silently and serves whatever stale copy it landed on. `ls -la` every harness
  skill dir after any rename, and repoint with `ln -sfn`.

## Latency is a hard requirement, not a goal

A routing card that arrives after the harness hook timeout is **discarded
silently** — no card, no error. So the budget is a correctness property.

- Measure the per-stage cost before changing anything: BM25 ~4 ms, dense embed
  ~350 ms cold / ~40 ms warm, local rerank ~800 ms (off by default). The whole
  warm route is 0.23–0.38 s measured across entrypoints (pipeline / CLI /
  hook JSON); anything that moves it toward seconds needs a measurement, not a
  guess. When a latency-budget selftest fails in the full run but passes
  alone, suspect concurrent embed traffic before suspecting your diff (stash-
  bisect proves it in one command).
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
- **Pin a test's latency envelope to the PRODUCTION budget, never to a number
  observed while an expensive stage happened to skip.** Corpus composition
  changes flip skip-gates: adding sourced skills raised the score leader
  enough that the decisive-gap gate stopped skipping the CPU rerank for a
  pinned prompt (~3.75 s, sanctioned, local, inside the 5 s hook budget) and
  a 2 s test assert started failing with no regression anywhere. The
  structural asserts (no network call, no rewriter import) are the teeth;
  the timing assert is an envelope, and an envelope tighter than production
  turns a sanctioned stage into a false alarm.

## Sourcing and installs need a relevance gate, not just safety gates

Shipped commands: `route --finder "<need>"` (search registries, inspect real
SKILL.md bodies + scripts, injection-screen, IOC + typosquat check, list with
commit SHAs) and `route --finder-install <n>[:sha]` (install pinned to the
reviewed commit, refuse on sha drift, then verify the route fires). `--source`
remains as the legacy listing-only path.

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
- **Screen the BODY, not the listing.** The 2026 marketplace audits (ClawHavoc,
  ToxicSkills, Unit 42) proved semantic attacks hide agent-directed instructions
  in SKILL.md bodies that code scanners read as documentation — listing text and
  install counts are not safety. Before any trust decision: clone the repo,
  read the real SKILL.md + inline scripts, run the injection screen over body +
  scripts combined, scan for destructive IOCs (curl|sh pipes, base64 decodes,
  credential paths, exfil hosts, raw IPs, persistence edits), and flag
  near-name publishers (edit-distance <=2 against a known-publisher list;
  typosquat clones are how campaigns spread). Body unavailable = never
  auto-install (fail closed), display-only in HITL.
- **Install at the reviewed commit.** Record the sha the screen approved and
  pass it to the installer; refuse the install when the repo's current sha has
  moved since review — 'reviewed once != trusted forever', and the pin is what
  makes upstream rug-pulls detectable instead of silent.
- **Close the loop after install: re-route the original prompt and check the
  installed skill now surfaces in the picks.** 'Installed but never fires'
  (description never matches) is the dominant post-install failure, and no
  registry checks it. Report 'route fires' vs 'not in top picks' explicitly.
  The verify loop has three silent-failure traps, each producing a confident
  wrong answer instead of an error: (1) the CLI's `--json` output is the HOOK
  ENVELOPE — card text only, no pick list — so verify must read the per-route
  state file (`last_route.json`) the CLI always writes; parsing stdout for
  `picks` yields `[]` forever and reads as 'installed but never fires'.
  (2) Anchor the check to the INTENT's install, not the most recent install
  overall — with several sourced intents, 'latest' names the wrong skill and
  a perfectly firing card grades as a failure. (3) The install marker must
  CREATE the intent entry when absent: finder installs do not record gaps,
  so a marker that only updates existing entries is silently dropped and
  trap (2) returns. Never swallow the marker write in a bare `except` — the
  swallow is what turned a data-shape quirk into a wrong verdict. All three
  traps were found by running the real lifecycle end-to-end against a FRESH
  intent while every unit test stayed green — sign a new sourcing feature off
  with at least one full finder→install→verify→rollback run per intent shape,
  never on unit tests alone.
- **A corpus change and the dense rebuild are not atomic.** Vectors refresh
  on the reindex timer/full rebuild, so a route in the window fuses stale
  dense hashes against a fresh BM25 index and the card can flip between
  junk and correct across runs. Any post-install verification settles and
  retries once before declaring 'not in top picks', and the reindex line's
  `embedded: N` count is the evidence the dense lane actually refreshed
  (`0 embedded, N reused` after a corpus grew = the new item is missing
  from the semantic lane).
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
- When instrumented behavior contradicts your line-by-line reading of a function,
  inline-replicate the function's internals with the REAL rows before widening the
  search — a comment or docstring can describe an older intent ("quota reserves
  non-skill slots" sitting over a split by score cut), and the comment/code
  divergence IS the bug. Reading harder never finds it; running the pieces does.
- Deduction has a budget: when two instrumented runs of the same code disagree,
  suspect input/environment differences (stack tokens, learned priors, env vars,
  breakers) before suspecting nondeterminism — and replicate the caller exactly
  (same args, same env) before believing either run.
- The runner must report a raising check and continue. One check that throws
  aborts the run and hides every other check's state.
- When a check fails in the full run but passes in isolation, bisect with
  `git stash` BEFORE assuming your change caused it — live-service contention
  (concurrent embed calls, busy local models) reproduces the exact
  latency-budget-failure signature your edit is suspected of. Pin the
  isolation-vs-suite difference as the diagnostic, not as a skip.
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
  Corollary: CLEAR the breaker files (`~/.tool-router/breaker-*.json`) before
  diagnosing any remote lane as dead — an open breaker makes every probe return
  `[]` in milliseconds, and a fail-open function fed a wrong argument returns
  `[]` just as silently. Zero rows from a lane probe means "breaker, bad args,
  or genuinely dead", in that order of likelihood.
- A short `"Reply with exactly: OK"` probe ranked candidate models one way and
  the real payload ranked them another. Toy probes measure queue depth, not
  capability.

Prefer the cheap falsification before the claim: one extra command that could
disprove the sentence beats a confident paragraph you later have to retract.

## Config sentinel: agent config writes are hook-guarded (2026-10-08)

A tool-router session's valid-YAML SUBSET rewrite of `~/.hermes/config.yaml`
dropped `dashboard.basic_auth` + 60 MCP servers for hours (astra "busy 503").
Guards live in `~/.hermes/plugins/config-sentinel` (+ `claude_hook.py` wired
into `~/.claude/settings.json` PreToolUse/PostToolUse): snapshot before gated
calls, sentinel key-check after, atomic auto-restore from the newest
sentinel-valid backup, escalate after 3 restores/hour. Rules that came out of
building it:

- **Verify sentinel keys against the LIVE healthy file before enabling.** The
  first list included `dashboard.basic_auth.password_hash` — but this host's
  password comes from `.env`, so the healthy file legitimately lacks it: the
  guard "restored" the healthy file over itself 4x and escalated on every
  call within a minute of going live. A sentinel key absent from the real
  healthy state is a false stub signal; derive the list from the live file,
  never from what the config "should" contain.
- Valid YAML passes every parse check; only a KEY-SUPERSET check catches a
  stub (PCHECK OSDI'16: config errors of this class are semantic, not
  syntactic — Hermes's own recovery only serves `.good` backups on parse
  FAILURE, so a valid stub sails through).
- The guard's own config lives in the plugin dir, NOT in config.yaml — the
  guard must not depend on the file it guards.
- The rulebook mandate also ships in `install.py` MANDATE (all harness
  AGENTS/CLAUDE/GEMINI rulebooks) and the published ToolR pack — re-running
  `install.py` keeps it; selfcheck: `python3
  ~/.hermes/plugins/config-sentinel/selfcheck.py` (17 asserts, sandboxed).

## References

- `references/retrieval-quality-2026-10.md` — measured baselines, fusion
  findings, model/latency tables, and the open coverage gaps.
- `references/free-model-gateways.md` — opencode-go and OpenRouter quirks for any
  free-tier model call: the required browser `User-Agent` and `X-Session-Id`
  headers, HTTP 200 with an empty body, and why toy-prompt latency does not
  transfer.
