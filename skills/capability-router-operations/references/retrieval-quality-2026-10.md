# Measured retrieval quality, latency and coverage (2026-10)

All numbers below were measured on the live machine, not estimated. The eval
lives in `~/Work/tool-router/eval/`; see the `retrieval-eval-harness` skill for
how to run and interpret it.

## Lane baselines

Golden set: 454 queries harvested from 983 real agent sessions (1,046
`skill_view` calls mined from `astra-training.db`), 762-item index.

| lane | R@1 | R@5 | R@10 | MRR | nDCG@10 | false-pick |
|---|---|---|---|---|---|---|
| BM25 | 0.1056 | 0.2944 | 0.3583 | 0.1875 | 0.2321 | 0.816 |
| dense | 0.1222 | 0.2778 | 0.3611 | 0.1950 | 0.2339 | 1.000 |
| fused | 0.1444 | 0.3361 | 0.4139 | 0.2315 | 0.2795 | 1.000 |
| fused + local rerank | 0.1278 | 0.3361 | 0.4139 | 0.2213 | 0.2722 | 1.000 |

Read these as: fusion is worth **+0.039 R@1** over lexical alone; the local
rerank **cost 0.017 R@1 for 4x the lane latency** and is therefore off by
default; and `unreachable@10` is 0.642, so the ceiling is vocabulary, not
ranking. (The false-pick 1.000 rows date from before the count-contract fix:
the default path now abstains when no pick clears the floor, so its
false_pick_rate is low and its abstain_precision high — compare like eras
when reading runs.jsonl history.)

## Fusion: shipped as convex blend, with measured numbers

`fuse()` now computes the convex combination directly: per-query min-max of
both arms, `alpha*dense_n + (1-alpha)*bm25_n`, alpha from config
(`fusion_alpha`), and the fused value **is** what selection cuts on. The
RRF ordering-vs-score mismatch is dead; `select()` has one number.

Golden-set result of the full package (convex fusion + body/trigger indexing
+ exact-name guarantee), measured on 454 queries:

| metric | RRF baseline | convex+body | delta |
|---|---|---|---|
| R@1 | 0.1222 | 0.1833 | +0.0611 |
| R@5 | 0.2694 | 0.3667 | +0.0973 |
| R@10 | 0.3556 | 0.4361 | +0.0805 |
| MRR | 0.1942 | 0.2717 | +0.0775 |
| nDCG@10 | 0.2350 | 0.3129 | +0.0779 |

Attribution: body/trigger indexing alone ≈ +0.025 R@1 / +0.044 R@10; convex
fusion on top ≈ +0.036 / +0.036.

### Wrong-ecosystem demotion must survive fusion

The lexical scorer demotes items whose ecosystem mismatches the query's
(measured leak: an Elixir review skill surfaced at #4 on a React query — its
description words "concurrency"/"streaming" are cross-ecosystem). Two layers,
both required:

- Scorer factor tuned on the golden set: the old 0.3 left the wrong row just
  above min_score on generic words; a hard 0.08 buried it but cost R@1 −0.003
  / MRR −0.003 when a demoted row was genuinely right in an ecosystem-
  ambiguous query. The knee (0.14) kept the baseline while burying the leak.
- The dense lane re-added demoted rows anyway (the item sat at dense rank 2 —
  its dense bonus cleared min_score with no language knowledge), so `fuse()`
  re-applies the demotion to the FUSED score when the item's ecosystem
  mismatches the prompt's, tagging the row. A per-lane penalty that lives only
  in the scorer is invisible to the other lane; re-apply it after the merge.

Post-fix golden set: R@1 0.1611 / R@10 0.4333 — the R@1 dip vs 0.1833 is the
demotion correctly firing on ecosystem-ambiguous queries; MRR holds.

Alpha sweep result (R@1 / R@10): 0.0 → 0.147/0.400 · 0.5 → 0.175/0.381 ·
0.6 → 0.192/0.358 · 1.0 → 0.128/0.339. **Shipped 0.5**: 0.6 buys +0.017 R@1
but costs −0.078 R@10, and recall@10 ("was it on the card at all") is the
operational metric for a routing card. Re-sweep whenever the golden set is
reharvested — alpha drifts with corpus, and the sweep is cheap (cached dense
rankings; only the blend changes). Ablation runs recorded after the
count-contract fix read slightly lower than earlier history because the
default path now correctly abstains instead of topping up with sub-floor
picks — that is the contract working, not a regression.

### Body indexing and the identity-field label rule

SKILL.md bodies (first ~120 words), "Use when ..." clauses and quoted
trigger phrases are extracted at build time (stdlib only, `body_extract.py`)
and baked into BM25 tokens AND the dense-embedding text — both lanes see the
same corpus. Index grew to ~1.0 MB with the 120-word cap; measure recall
before extending it.

Consequence: a 'weak pick' label must be derived from **identity fields
(name/description/aliases) only**. A body-only hit (the skill's body mentions
"hermes chat", the query says "chat composer") otherwise clears the label
and the pick never gets flagged. Body hits display in `hits`; they do not
clear labels.

### Exact-name guarantee

A prompt naming a capability exactly keeps it in the output regardless of
blend rank — the hoist is in `fuse()` and mirrors score()'s own
explicitness test (suppressed for one-word generic names) so the two cannot
disagree. NOT optional plumbing: the prompt must be *passed* (`fuse(...,
prompt=prompt)` plumbed through `_route_once` and the eval lanes). Reading
it from a field on the row silently becomes dead code every caller forgets
to set — one golden-set probe ('use the <exact name>' query) through the
installed CLI proves it live: with the name in the prompt the item sits at
position 1, without it, deep in the list.

### Model-aware card sizing (shipped)

Resolver source order: hook env (`TOOLR_MODEL`, `ANTHROPIC_MODEL`,
`CLAUDE_MODEL`, `HERMES_MODEL`, `OPENCODE_MODEL`, `GEMINI_MODEL`, `AGY_MODEL`)
→ the gateway's session store (`~/.hermes/state.db` `sessions.model`, most
recently active, read-only, TTL-memoised) → user-editable
`~/.tool-router/model-overrides.json` → built-in per-family profiles →
conservative prior. The Hermes tool-router plugin stamps the session model as
`HERMES_MODEL` at `pre_gateway_dispatch` so the env scan wins on the gateway
machine. Decision precedence: explicit user count > `TOOLR_MAX_PICKS` env >
config `decision.max_picks` > tier/ctx-derived cap; unknown models keep the
old default behavior exactly. Pricing refresh (`scripts/modelcontext.py
refresh`, OpenRouter catalog) is an offline command, never on the route.

## The fusion contract problem

`fuse()` ordered by the RRF key while the selection cut on a *different* field
(`score` = BM25-relative + dense bonus). One ordering was computed and
discarded. With k=60 and two arms the RRF key is nearly flat at the head —
ranks 0 to 5 span 1.7% of the maximum — so it carries almost no information
about which of two agreeing items is better.

Published evidence (Bruch, Gai & Ingber, ACM TOIS 42(1), arXiv:2210.11934)
reverses the usual folklore: a convex combination of normalised scores beats
RRF(60,60) on NDCG across nine datasets in- and out-of-domain, and **alpha
converges with under 5% of training data** — tens of labels is the right
budget. RRF "does not generalize well out-of-domain"; adding a third parameter
(`rrf-CC`) made no significant difference.

So: compute both arms' scores, normalise per query (BM25 floor 0, cosine floor
-1), fuse as `alpha*cos_n + (1-alpha)*bm25_n`, sweep alpha in 0.3-0.8, and
**make the selection cut on the same fused value** or the change is decorative.

## Latency, per stage

| stage | cost |
|---|---|
| BM25 score (759 items) | 4 ms |
| dense embed (local, 768-dim) | ~400 ms |
| local rerank | ~800 ms (off by default) |
| prompt rewrite | **removed** — no model call on the path |
| full route, current | **0.17 s** (10/10 runs, 0.16-0.19 s) |

Before the fixes: 27.9 s typical, and one route spent **57 s** in a single
registry search on the hot path. The gap was not a constant factor — it was
network calls that belonged off the path entirely. Deleting the rewrite stage,
not tuning it, is what closed the gap.

## Model reality on this box

- `gemini-flash-latest` returns **HTTP 429 quota exhausted**. Listed first, it
  meant every rewrite burned a failed call before falling back, then tripped
  the breaker and silently disabled the stage.
- `gemini-2.5-flash` returns **HTTP 404 "no longer available to new users"**.
- `gemini-flash-lite-latest` answers in ~0.4 s on the same key.
- A harness's own login token (Claude Code's OAuth bearer) is **rejected by the
  vendor API with 401 "API key is invalid"** — it is scoped to the harness's
  endpoints. Do not attempt to reuse it.
- opencode-go and OpenRouter both need a browser `User-Agent` or they answer
  `403 error code: 1010` (Cloudflare, not auth), and opencode-go additionally
  needs `X-Session-Id`. Both return `200` with an **empty body** intermittently.
  See `free-model-gateways.md`.

## Open coverage gaps

- **MCP tools are not indexed.** Servers are indexed by name only; a live
  `tools/list` sweep found hundreds of tools across reachable servers, the large
  majority absent from the index. A request phrased as a tool action cannot
  reach the server that provides it.
- **Local binaries have no metadata source.** `~/.local/bin` holds well over a
  hundred user-installed tools with no descriptions to index.
- `~/.gemini/config/mcp_config.json` is not in the MCP config list.

- Kind-representation audit (why is the card disproportionate in X?): over a
  sample of real queries, count picks per kind and compare picked share with
  corpus share. Measured: skills under-picked (73% of corpus → ~54% of picks)
  while MCPs/commands/fleet items are over-picked — the `kind_quota`
  deliberately reserves non-skill slots. A design decision, not a bug; confirm
  the intended diversity before touching the scorer, and `kind_quota: 0`
  restores pure score order.

## Adoption: delivered ≠ used (measured first time)

Retrieval metrics above measure ranking; **adoption** — the model actually
loading a pick — is a separate failure surface the eval never sees. First
measurement, 14-day window over Claude Code session logs only:

- 47 card-bearing sessions, 5 total `Skill` tool_use invocations, **0 sessions
  where a card-named skill was loaded** — 0% adoption with prose-only delivery.
- Hermes gateway surfaces delivered NO cards at all: the interceptor plugin
  was on disk but absent from `plugins.enabled` — a silent no-op for weeks.
  Available-and-enabled are different claims; grep the harness's own logs for
  the card marker to distinguish them.
- Fixes shipped: enable the plugin (config line + gateway restart);
  wire Claude's `PreToolUse` deny-once gate + `PostToolUse(Skill)` clear
  (the `--enforce` mechanism, previously dormant); and have the PostToolUse
  hook record loaded picks into `learned.json` (+0.25, clamp 2.0 — the
  same asymmetric rule as `route --record`). That last connection closed the
  learning loop automatically: the manual record command had never been
  invoked once and the prior file was empty after weeks of traffic.
- The listening-loop lesson: adoption pairing is computed from real
  `tool_use` records in session logs (name Skill, input command), per
  card-bearing session, `len(picks & loads) > 0`. A scorer change cannot fix
  a delivery/adoption failure — check the pipe before the ranking.

Open follow-up: unverified post-enforce adoption delta — re-measure the pair
rate after a real enforced week (Claude quota blocked the live-fire in the
session that wired it).

## Sources worth reusing

- Bruch, Gai & Ingber, *An Analysis of Fusion Functions for Hybrid Retrieval* —
  https://arxiv.org/abs/2210.11934
- Cormack, Clarke & Büttcher, *RRF outperforms Condorcet and individual Rank
  Learning Methods* (SIGIR 2009) — https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf
- Chen et al., *Parameterized Dense-Sparse Fusion* (documents a cross-encoder
  *regressing* nDCG over equal-weight fusion) — https://arxiv.org/html/2609.22770v2
- SemEval-2026 Task 8 reranker comparison (pool size peaks at k=20-50, degrades
  by k=500) — https://arxiv.org/html/2605.12028v1
- HyDE, arXiv:2212.10496 — for why HyDE is wrong for a corpus of real named
  capabilities: its failure mode is inventing plausible names, and here the name
  *is* the signal.
- Official MCP registry, keyless and paginated:
  https://registry.modelcontextprotocol.io/v0.1/servers
