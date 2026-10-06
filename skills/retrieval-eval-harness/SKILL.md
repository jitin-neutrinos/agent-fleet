---
name: retrieval-eval-harness
description: Use when measuring ranking quality or ablating lanes.
---

# Retrieval eval harness (zero-dependency, assert-based)

For ranking systems where the project convention is stdlib-only Python with
bare-assert self-checks. Canonical instance: `~/Work/tool-router/eval/`.

## Build the golden set from real logs

The strongest automatic label is **the item the system demonstrably consumed**
in response to a query — a `skill_view`/`tool_search`/document-open call. Rank
whatever the system showed *above* that item and you have a preference pair.

Extraction recipe:
1. Load messages, group by session, order by time.
2. Attribute each tool call to the most recent **user** turn.
3. Label = the **first** consumption call for that turn. Later calls in the same
   turn are exploration, not the decision — a 22-tool session otherwise
   contributes 22 acceptable answers.
4. Resolve the label against the live catalogue by exact name after stripping
   any `pack/name` or `plugin:name` qualifier. Never fuzzy-match: a wrong label
   demotes a good item, which is worse than no label.
5. Classify, never collapse:
   - `positive` — label resolves to a live item
   - `negative` — no item exists (score silence, not a miss)
   - `stale`   — the item was consumed but has since been **uninstalled**.
     Exclude it. Scoring it as a negative punishes you for someone else's
     `rm -rf`.
   - `unjudged` — a human/judge never ruled. Keep it **out** of the golden set:
     it is simultaneously a meaningless score and a question that can never be
     asked, because dedup then excludes it from the question pool too.

Dedup on normalised text (lowercase, non-alphanumerics collapsed to single
spaces). One prompt seen in 3 sessions is one query, not 3 rows.

## Metrics

Report positives and negatives in **separate blocks**. Never average them.

- `recall@k` — fraction of labelled queries with a correct item in the top k.
- `MRR` — mean of 1/rank of the *best* correct hit. Rewards rank 1.
- `nDCG@k` — place each gain at its **true** rank. Dense-packing the gold hits
  into a list re-seats them at rank 1 and returns a constant; this is the
  classic DCG bug and it silently deletes all ordering signal.
- `abstain_precision` / `false_pick_rate` — on no-correct-answer queries, did
  the system return nothing. This is the guard that stops a recall gain bought
  with false positives.
- `unreachable@k` — fraction of labelled queries whose correct item never
  appears. High values mean **vocabulary** gaps, not ranking gaps: fix
  descriptions and aliases before touching the scorer.

Plain accuracy is misleading and worth demonstrating in a test: a system that
misses all 50 positives and correctly abstains on all 50 negatives scores 0.50
accuracy with 0.0 recall.

## Ablation and attribution

- Hold fixed: the same index object, `stack=[]`, `learned={}`, same query file.
  Then a delta is attributable to the lane that moved.
- Pure-Python lanes (BM25) are deterministic: no RNG, clock, or network. Prove
  it with a 3x repeat assert and a 3x `build_index` order check, then trust
  single numbers.
- Remote-embedding / model lanes are not reproducible. Always report
  `--repeat N` min/max spread alongside the number.
- **Lane health flag.** If the production code swallows a lane failure and
  falls back, a degraded lane scores *identically* to the fallback and the table
  reads as "fusion adds nothing". Have every lane return `(rows, healthy)`,
  print a `deg` column, and gate `--assert` on it. This is not optional — it
  catches bugs that otherwise present as a plausible-looking zero.

## Learning to rank from sparse feedback

Do not train on "no complaint" — that is position bias (Joachims 2002/2007).
Learn from **counterfactual pairs**: same query, two orderings, one confirmed.
Weight each observation by `1/(1+log2(1+rank))` (inverse propensity) so deep
picks cannot out-vote top ones.

Update rule, asymmetric on purpose:
```
learned[preferred]    += 0.25 * w
learned[dispreferred] -= 0.10 * w
clamp to [0, 2]
```
Gaining 2.5x slower than losing stops one lucky match entrenching an item
while one confirmed miss demotes it at once. Keep gains small enough that
learning only breaks ties (5 matched pairs is about half the name-boost).

Loop: watch traffic -> mine behaviour labels -> **ask only where lanes disagree**
and the top-2 gap is small -> learn -> verify with `--assert`; revert any weight
that did not move recall.

**Always report held-out.** Train on a hash-split half, score the other. If the
held-out gain is about the in-sample gain, it generalises; if not, it memorised.

## Robustness classes to check

Long prompts (must match their prefix — only true if tokenize dedups),
non-English (silence is fine, a confident wrong pick is not), no capability
named, a capability that no longer exists (must not fuzzy-match a lookalike),
near-duplicate names, prompt injection (injected text must not steer the pick),
malformed non-string types, and route latency.

Put known defects in an `XFAIL` dict and report them as `KNOWN` while still
exiting 0, so a CI gate stays green while the defect stays visible. Print
`XPASS` when one starts passing.

## Two traps worth remembering

1. **Live state is not a dataset.** The router's `gaps.json` is rewritten on
   every route and pruned at 30 days — it went 299 -> 234 intents while the
   harness was being measured. Harvest once, freeze to JSONL, never read it at
   score time.
2. **Non-ASCII tokens silently vanish.** `tokenize` on Hindi/Japanese prompts
   returned 0 rows with a 0.0 ms runtime — the regex is ASCII-only, so it never
   even tries. That reads as "the router abstained appropriately" when it means
   "the router is blind to these languages". Assert on a non-English probe that
   actually scores something.

## What to log per run

One JSONL line per lane: timestamp, lane, all metrics, query-set path, query
count, `index_items` (corpus-drift canary), repeat count, and a `sig` hash of
(lane, metrics) so an unchanged lane is recognisable at a glance.
