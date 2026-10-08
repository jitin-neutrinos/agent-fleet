---
name: llm-token-cost-accounting
kind: skill
description: Audit and repair LLM token usage and cost tracking.
---

# LLM token + cost accounting across harnesses

Class-level skill for any work on token-usage capture, cost attribution, or cache
accounting for one or more agent harnesses (Claude Code, opencode, agy, Hermes,
Codex, …) feeding a shared tracker or dashboard. Trigger: a usage tracker reports
$0.00, mislabels providers, omits cache economics, or historical usage/cost
figures need correcting.

## Procedure

1. **Back up before the first edit.** The collector and its database are usually
   outside version control, so make timestamped copies of BOTH and say where
   they went. Retroactive repair rewrites rows; there is no undo.
2. **Read the live source of truth first.** The proxy/upstream `/stats` (or
   equivalent) usually exposes far richer accounting than the collector uses:
   per-model `tokens_sent`, and a `prefix_cache` block with `cache_read_tokens`,
   `cache_write_tokens` and `uncached_input_tokens` per provider. Enumerate the
   keys before deciding what is "unavailable".
3. **Reproduce the defect numerically before fixing it.** Query the DB grouped by
   `harness, provider, model_key` and count how many rows carry the wrong label.
   A misattribution you have not counted is one you cannot claim to have fixed.
4. **Fix the resolver, then re-price history with the SAME resolver** so retro
   rows and new rows are computed by one code path.
5. **Dry-run into a throwaway database.** Repoint the module's DB path at a temp
   file, poll the live source, and assert the invariants on the output before
   touching the real DB.
6. **Restart the tracker and verify a FRESH poll**, not just the repaired
   history — check invariants on rows the new code actually wrote.

## The five attribution/cost defects, in the order they bite

- **A route/endpoint name hard-mapped to a model.** Names like
  `passthrough:models` are OpenAI-compatible ROUTES, not models; mapping one to a
  real model mislabels every request through it. Measured: 117 of 195 rows on a
  box with no OpenAI usage. Keep an explicit route set that can never become a
  model id, and resolve the provider FROM THE MODEL ID, because a route-keyed
  provider map reports the route's provider regardless of who served the call.
- **Reported model ids differ from pricing aliases in TWO ways at once.** A dated
  id (`…-4-5-20251001`) differs from the alias (`…-4.5`) by a trailing date AND
  by dashes-vs-dots. Fixing only one still yields $0.00 — normalise BOTH (strip
  the date, flatten separators) before lookup, and test the exact reported id.
- **Cache reads billed at full input price.** Usually the largest inflation,
  because prompt sizes are dominated by cached prefixes. Split the prompt into
  fresh input / cache reads / cache writes and bill each at its own rate.
  Measured: 91.6% of all input tokens were cache reads.
- **A per-provider lifetime total applied per model.** Applying one
  provider-level cache figure to every one of that provider's models
  double-counts it (measured 2× on a two-model agent). Apply it once per provider.
- **An agent-level aggregate multiplied across that agent's models.** Split
  aggregates proportionally, or use per-model totals when the source exposes
  them. Route rows carry no generation: zero input, zero output, and they must
  never absorb an agent's totals.

## Retroactive repair

- Prefer re-pricing with the **observed cache ratio** from the upstream source
  over inventing a split you cannot prove; state the assumption in the report and
  note that the figure scales with it.
- Do not report an intermediate number as final. Attribution repair alone moves a
  total UP (a $0.00 row becomes a priced one); cache repair then moves it DOWN.
  Give the reconciled figure and the independent cross-check, not the first
  number that looks non-zero.
- Cross-check against the upstream's own lifetime total as an
  ORDER-OF-MAGNITUDE oracle only — per-model costs there can themselves be $0.

## Pitfalls

- **Never break the pathing of a verification harness mid-session.** Inlining
  script tags into a hand-written `file://` HTML page can silently break the
  whole page (a syntax error surfaces only as a `waitForFunction` timeout). Build
  the probe with the same bundler the app uses and keep assertions in a module,
  not in a page template.
- **Assert invariants on the OUTPUT of a dry run, not on the source.** A resolver
  unit test can return `""` for a route and a price for a dated id and still be
  wired so an aggregate doubles a lifetime total; only a dry run over live data
  shows the sum.
- **Unknown pricing must be visible, not silent.** A model with no rate that
  writes `0.0` is indistinguishable from a genuinely free model. Keep a distinct
  marker or report the uncovered models.
- **Cache-vs-compression interference is worth measuring, not assuming.**
  Compressing content inside a cached prefix pays back in cache writes; compare
  bust tokens against compression savings and report the ratio before proposing
  a change.
- **An audit that measures nothing must fail.** Assert a non-zero denominator, or
  a green "all pass" can mean nothing was observed.
- **A tracker daemon crash-looping on port-bind is usually starved by a stale instance of itself that still holds the listener.** Restarting the unit alone just re-loops on `Address already in use`; identify the real port holder with `ss -tlnp` (often an orphaned predecessor or a defunct one), stop that holder first, then start the unit. Otherwise cost data silently never lands while the service still looks configured. If cron/other watchdogs also race for the same port, the unit restart line count balloons in the journal — a diagnostic signal, not the root cause.
- **An aggregate total can misreport while per-slice rows are correct.** When one row looks impossible for an active period, re-read the same source's per-harness/per-model rows before trusting either, then repair or bypass the aggregation path and state which rows are authoritative — later sessions otherwise quote the broken total as fact for months.

## References

- `references/cache-and-ttl.md` — auditing cache TTLs and provider defaults,
  including the silent default-TTL change and compression/caching interference.
- `references/token-optimization-levers.md` — decision table for CUTTING token
  spend without quality loss: provider caching economics and break-evens, batch
  discounts, compaction research anchors (what improves vs degrades quality),
  and the usage fields that prove a cache actually hit.
