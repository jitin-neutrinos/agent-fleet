---
name: rag-training-campaigns
description: Use when fine-tuning or evaluating a RAG retriever on docs.
---

# RAG training campaigns

Orchestration pattern: build the corpus pipeline first (scraper -> cache ->
derived database), then run a measured training campaign on top. Delegate by
strength: Opus-class CLI for plans/audits/review gates, agy (Gemini) for bulk
implementation, local Ollama + cloud GLM for question generation. Run
generators in parallel with resumable todo lists (one worker = one engine,
each skips batches whose output file already exists). When one engine's quota
quota runs out, re-split the remaining todo list to the other engine instead of
waiting for a reset. Concretely: queue dirs are per-engine (`parallel/<engine>/`
in, `parallel/<engine>_out/` out); routing = copy unfinished batch definitions
to another engine's queue dir and relaunch its worker — outputs are
engine-agnostic JSONL. Know each provider's limit horizon: Claude Sonnet
carries a WEEKLY limit (resets on a fixed weekday, mid-campaign), Opus tokens
can run out mid-review, GLM coding-plan keys fail with HTTP errors when the
internet drops. Budget the fallback chain explicitly (e.g. Opus primary ->
GLM -> agy) and check the gate's survival-count floor BEFORE remediating:
quality removals can drop train below the floor, turning a quality fix into a
volume campaign — compare remaining train chunks against the shortfall to
confirm it is solvable by generation.

## Standing gates (never skip)

1. **Review gate before training**: every generated training item is audited by
   the strongest available model before fine-tuning starts. Gate passes on
   survival count + per-batch failure rate, not on a sample.
2. **Purity protocol**: seal datasets (sha256 + chmod 444 + manifest), snapshot
   the serving state BEFORE any test-set exposure, restore after the campaign;
   the final holdout set is read exactly once, at the end.
3. **Baseline first**: score the stock model on every sealed set before tuning.
   Without a baseline no later number is falsifiable.
4. **Iteration budget**: cap eval-loop iterations (6 works) with a plateau rule
   (improvement < noise band twice => stop). Write the stopping rule down
   before starting.
5. **Adversarial plan review before build**: have a second strong model audit
   the training plan end to end (loss choice, eval design, leakage, ops) with
   web research, then treat its GO/NO-GO as binding. Expect NO-GO on a first
   draft — the review's value is exactly the load-bearing details the plan got
   wrong.

## Training-objective research gate

Check current literature BEFORE choosing the loss. As of 2025-2026: MNRL/
contrastive fine-tuning REDUCES effectiveness on embedding models that were
already contrastively supervised (BGE/E5/GTE all lost nDCG in arXiv:2505.19274
while an unsupervised base gained ~12 points — the gain people cite belongs to
the unsupervised case). Prefer cross-encoder listwise distillation
(DistillKLDivLoss, teacher = the reranker already in the serving stack,
~1 positive + 15-19 mined hard negatives, contrastive term kept at ~0.1
weight). AnglE needs graded labels — wrong for (question, gold-chunk) pairs.
Hard negatives: mine within version-twin/sibling groups; drop ambiguous pairs
(false negatives), which is necessary but NOT sufficient — the degradation
persists even with false-negative filtering.

## Dataset rules

- Split at PAGE level plus variant-group and family+slug edges — version twins
  in different pools leak ~20% of the test set. Assert the split: no page, no
  variant group, no family+slug, no near-duplicate in two pools.
- Every question carries an answer span copied verbatim from its source chunk.
  Machine-verify spans; a weak generator then yields FEWER surviving questions,
  not wrong ones — grounding beats quota, never pad. Default span rule is
  8-30 whitespace-separated words with normalized compare, BUT make the rule
  facet-aware: version_pinned spans are legitimately short (URL paths, UI
  labels that differ between versions are the ideal anchor). Forcing the word
  count on them deletes exactly the questions the stratum exists for — accept
  >=8 chars for version_pinned, keep 8-30 words for everything else.
- Batch size for LLM generation: 6-10 chunks per call. 50-chunk calls truncate
  mid-JSON and silently lose half the output.
- Persist rejects with reasons; stamp generator provenance on every item.
- Versioned docs corpora: generate an explicit version-contrast stratum (each
  version-divergent chunk asked against its twin's text -> version_pinned +
  version_agnostic questions). The main pass will not produce these on its own,
  and version_correct@1 — the only discriminating metric — is unmeasurable
  without them. Expect the model to answer in its own field vocabulary
  (`question_type` vs `facet`, `skipped: identical_to_twins` markers) and
  normalize fields at emit time.
- Ban doc-artifact questions in the generation prompt itself: questions asking
  for link URLs, anchor slugs, screenshot resource paths, or "which link
  appears at the top of the page" describe the CMS page structure, not the
  product, and teach the model to hallucinate URL trivia. Ban double-barreled
  questions too ("what does X do and what is its default?") — one ask per
  question, split or drop. Enforce both in the prompt AND in the acceptance
  filter; a prompt-only ban leaks.
- Honest framing, stated in every report: questions generated FROM chunks and
  scored by an index containing those chunks measure SELF-CONSISTENCY, not
  real-user accuracy. Never present synthetic recall as user-facing accuracy.
- On version-duplicated corpora, `relevant_refs` pointing at only the source
  doc is invalid retrieval gold: the span typically appears verbatim in the
  twin-version doc too, so recall@k measures doc redundancy. Rebuild refs by
  matching the span (normalized) against EVERY cached doc and listing all hits;
  expect ~2/3 of records to be multi-doc. Do this before computing any
  retrieval metric.

## Generation worker hygiene (silent-failure modes)

- NEVER write an output file when zero questions survive validation. A 0-byte
  file makes resume logic mark the batch done forever and the queue silently
  shrinks — the reported "done" count then overstates real progress. Count a
  batch complete only if its output exists AND is non-empty; sweep-and-delete
  empty files before requeuing.
- Workers hang as often as they crash: a provider can hold a connection open
  without sending (0% CPU, ESTABLISHED socket, poll_schedule_timeout). A worker
  on one batch for >3x the normal batch time is stuck — kill it and relaunch;
  resume-safe workers make this cheap. Check `elapsed` and open sockets, not
  just process existence.
- Smoke-test ONE batch in the foreground before launching a worker fleet. A bug
  in a shared helper (e.g. a NameError on a main()-local variable used inside
  the filter function) crashes every worker identically and silently — the only
  trace is a traceback in the background-completion notification, and status
  checks keep saying 'running'. Verify one non-empty output file appears before
  scaling out. Same class: normalize engine-name variants inside the model-call
  layer (a second GLM worker instance named glm2 must map to the glm call path)
  or every call fails with an unknown-engine error and the queue finishes with
  0 questions.
- Removing reviewed-bad records: remove by exact record identity (file line
  position or unique id), NEVER by shared chunk_id — several questions often
  share one chunk, and chunk-keyed removal deletes good questions with bad
  (verify removal count equals the review's remove-list length).
- Record ids differ across pipeline stages (pool files carry UUIDs, review
  emit files carry sequential ragtrain-N ids). Map removals through the EMIT
  file's line order, not through id equality.
- A gateway/session restart kills background workers and any batch files built
  in-memory but not yet written to disk. After any restart: check the worker
  PID first, rebuild missing batch files from surviving state JSON, and ignore
  a pgrep hit on your own command line (it matches itself). A "0 files done,
  worker running" reading means nothing was actually generating — verify a
  completed output file appeared before trusting the status.

## Pipeline source-of-truth (build wipes output-file edits)

`validate_datasets.py build` REGENERATES `datasets/<pool>.jsonl` from the
`gen_out/<pool>/` batch files. Direct edits to the pool output files are
silently wiped by the next build. Apply ALL remediation (gate removals, regen
merges) to the gen_out source batch files, then rebuild — never to the output
files alone. After a mass source-level removal, re-run the pattern scan once
more: records from OTHER generator passes can carry the same defect classes
and survive the first scrub. If a removal over-deletes (several questions
share one chunk), restore the extras from the removed-records backup keyed by
unique record id, and assert removed == expected before writing.

## Review gate (remediation loop)

- Run the gate with a two-tier protocol: 100% pattern scan (duplicates, banned
  phrases, double-barreled, doc-artifacts) + ~10% deep verification against
  source docs. Pre-build the deep sample file so the reviewer spends its
  budget on judgment, not mechanics. Manually adjudicate heuristic hits —
  expect ~1/3 of regex matches to be false positives (version numbers in the
  doc's own examples, ports, platform URLs).
- Expect the gate to find MORE than the first-pass validator did: validators
  check shape, the gate checks meaning. Budget a remediation loop: remove
  rejects, fix the generator prompt at the root, regenerate with a strict
  acceptance filter (span required + verbatim), then re-run the gate.
- Guard the survival-count floor: removals plus validator drops can push the
  train pool below the gate's minimum. Regenerate before re-running the gate,
  and count what the gate will count.

## Campaign checkpointing across sessions

Long campaigns span sessions and get interrupted. Before ending a session,
write a state snapshot (progress doc + machine-readable state files: pools,
todo lists, validation reports, sealed manifests) so the next session resumes
by reading files, not by re-deriving. Resume procedure: (1) inventory what
exists (batch outputs, sealed files, reports), (2) run the validator in
check-only mode, (3) restart only the incomplete stage's workers.

## Serving-stack phase (after the campaign concludes)

When the campaign ends (often with a negative training result — that IS a valid
outcome, report it straight), the measured wins that beat fine-tuning were, in
order of ROI: (1) hybrid retrieval — BM25 + dense fused with RRF (k=60),
BM25 alone can beat dense on identifier-heavy docs; (2) contextual chunk text —
prepend the chunk's breadcrumb/heading-path into the embedded string (zero cost,
+2-4pp); (3) a stronger small embedder — but ONLY a sealed-eval bake-off proves
it transfers, benchmark deltas are hypotheses. Retire the cross-encoder reranker
once the embedder gets strong enough that it stops adding recall/MRR. Full
Full measured matrix and serving pitfalls live in `references/serving-stack.md`;
that reference also carries the named-tunnel deployment procedure, the
harness-registration commands for every CLI (with their interactive-prompt
gotchas), and a ready `scripts/install-mcp-everywhere.sh` that detects all
installed harnesses and registers the MCP in each (install/--remove, idempotent).

User preferences for this work: demand honest calibration over optimistic
claims (a negative result is reported as a negative result, never spun);
every number in a report is measured, never assumed; cloud models only for
generation/review work when the no-local-models mandate is active; evals run
on GPU where a GPU path exists, and CPU-timings on GitHub runners are measured
live, not assumed. The serving MCP is deployed on a permanent Cloudflare
tunnel hostname with a public `curl | bash` installer (`scripts/install-
neutrinos-docs-mcp.py`) — when the serving stack changes, update BOTH the
tunnel-hosted installer copy and the skill script so they stay in sync.

## Pitfalls

- When a validator mass-rejects, suspect the validator's index before the data:
  an index missing the text field fails EVERY span check (looks like 94% of the
  data is bad when the validator is broken). Independently sample rejections
  against the source corpus before accepting the number.
- Kill generation process trees by the TOP-LEVEL driver PID. ThreadPool workers
  respawn children until their parent dies; killing leaf `gen_questions.py`
  PIDs one by one never catches up because new leaves keep appearing.
- Metric priority for versioned docs corpora: chunk_recall@10, mrr@10,
  version_correct@1, duplicate_rate@5; page-level recall@10 is a no-regression
  guardrail only, and its 0.99-style targets are near-meaningless under
  self-consistency bias.
- Z.ai/GLM subscription keys work ONLY on the coding endpoint
  (api.z.ai/api/coding/paas/v4) with thinking enabled; the general endpoint
  rejects the same key with a misleading 'insufficient balance' error (HTTP
  400 code 1113). When told a key "has balance", probe model-by-model across
  both endpoints before concluding — the /models list also lies about which
  IDs the key can use. Key lives in a 0600 file, never in config or git.
- Removal by report line: parse the gate report into pool->line->reason, then remove
  pool records BY POSITION (review line = pool position; emit preserves order).
  Never remove by shared chunk_id — several questions often share one chunk and
  chunk-keyed removal deletes good questions with bad. Assert removed == expected.
- Replacement regeneration: group removed records by source chunk, re-run GLM 5.3
  with the patched prompts (3-4 q/chunk), and accept only records passing the same
  strict filter: span required, 8+ chars, normalized-verbatim in chunk, no
  doc-artifact phrasing, single ask. Two attempts at a chunk producing zero
  acceptances usually means transient API failure, not a hopeless chunk — retry
  later. Run the prompt + filter patterns from `references/review-gate-runbook.md`.
- Claude CLI print mode: the prompt is the positional argument — `-p` swallows
  the next flag's value if ordering slips. A run that hits --max-turns exits
  without writing outputs; `--continue` the same session to finish, it retains
  all researched context. Model aliases: the exact thinking-model IDs are not
  always valid — `--model opus` resolves where explicit versioned IDs fail.
- agy CLI: `-p` also swallows the following flag — put `--effort high` BEFORE
  `-p "prompt"` and pass `--print-timeout` for long tasks (default 5m kills
  deep-work runs).
- opencode headless runs auto-REJECT any bash command not on the config
  allowlist (`permission.bash` in opencode.json) — 'ask' is unanswerable in
  print mode and the agent stalls then dies on its first unlisted command.
  Allowlist the read-only verbs (ls/cat/head/wc/grep/find) before launching a
  headless review. Also: `small_model` defaults to a LOCAL ollama model for
  session titles — repoint it at the cloud provider when the no-local-models
  mandate is active, and grep the opencode log (`providerID=`/`modelID=`
  counts per session id) to verify which model actually served each call.
- GPU contention: an embedding-trainer and a local LLM generator fight for
  16 GB VRAM. Sequence them (generate -> free GPU -> train) or drop generator
  workers before training starts.
- API rate limits cap effective parallelism, not worker count: adding workers
  past the provider's concurrent-call ceiling yields zero throughput gain.
  Measure batches/hour after scaling out; if it plateaued, the limit is the
  API, and the only lever is a second provider/engine on the remaining todo
  list (resumable skip-existing workers make the split trivial).
- Cloud generation calls with many-chunk prompts can return HTTP 200 with an
  EMPTY body (silent truncation) — validate raw response length before
  parsing and treat zero-line outputs as a retryable failure, not an empty
  result.
- Vendor sub-agents (Claude Task tool, agy) inherit the parent's turn/timeout
  budget: give parallel-batch jobs an explicit per-batch retry + resumable
  todo list so a killed parent loses only the in-flight batch, and resume is
  `skip existing outputs`.
