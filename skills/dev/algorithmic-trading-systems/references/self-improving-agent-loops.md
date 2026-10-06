# Self-improving agent loops — validation before enthusiasm

For any architecture where agents score each other on realised outcomes and
retrain from those scores. The loop is the appealing part and the trap; this
file is the accounting. Read it before designing the feedback loop, not after
the first disappointing Sharpe.

## The load-bearing reframe

**A confidence score that rises over time is the expected shape of an overfit
system.** "Accuracy and confidence keep going up" is what a curve-fit looks
like from the inside. The loop cannot be justified by its own trend; it has to
be justified by out-of-sample, trial-adjusted measurement.

Two numbers that set the bar before any design work:

- **Best-of-N over zero-edge strategies.** Trying N variants of a genuinely
  edge-free system produces a best Sharpe that looks respectable. At N=100 the
  median best Sharpe is ~0.8 and the 99th percentile ~1.2; at N=1000 the median
  is ~1.0. Fat-tailed returns push this higher still. So enumerate your grid
  (agents × features × windows × models × seeds) and count the trials — the
  count sets the significance bar, and it is often far larger than the
  intuition suggests.
- **Sample size needed to distinguish skill from luck.** With W resolved
  trades, a Wilson interval on a win rate spans roughly ±1.96·sqrt(p(1-p)/W).
  At W=30 that is about ±0.20 — a model that always claims "55%" and one that
  genuinely wins 65% are indistinguishable on the data. You need on the order
  of 120 resolved trades before a hit rate means anything. At 10-30 trades per
  year that is **8-12 years of live data**.

Consequence: a low-frequency strategy cannot honestly claim to have validated
its agent confidences within any reasonable horizon. Say that to the user
plainly and design for it: prefer decisions whose quality is *checkable from
year one* (reliability diagrams, hard risk gates, deterministic overrides) over
a score that improves slowly and cannot be distinguished from noise for a
decade.

State the deliverable honestly when you do this: what the design buys is
confidence scores that are *truthful* and checkable early, not a rising
accuracy curve. Say plainly that decision quality will stay flat-to-noisy for
years, and that a rising number which arrived alongside a rising trial counter
is overfitting rather than progress.

## Calibration is not skill — two separate axes

Calibrating a probability is easy and nearly free of information. Do not let a
calibration result be reported as an accuracy result.

- Uncalibrated scores routinely show **negative** Brier skill — worse than
  predicting the base rate.
- **Isotonic regression drives in-sample ECE to exactly 0.0000** while its
  held-out ECE sits around 0.07, and its Brier skill gain collapses from ~+0.24
  in-sample to ~+0.00 held-out. The apparent skill was memorising its own
  labels. Report held-out numbers or report nothing.
- **A useless model with plenty of data calibrates beautifully.** At large N a
  model with no predictive power still reaches near-zero ECE and Brier skill
  around +0.001. Perfect calibration, zero value.

So the loop must track two numbers separately: a calibration metric (reliability
diagram, Brier, expected calibration error, all **out-of-fold**) and a skill
metric (does the calibrated probability beat the base rate out-of-sample).
Report both. A rising ECE with flat skill is an overfit curve being dressed up.

With very few positives, prefer a small-sample correction over a fitted
calibrator — isotonic and beta calibration both overfit hard below a few
hundred examples, and the method choice matters less than the held-out
discipline.

**The gap is usually unclaimed.** Search specifically for whether anyone in your
domain calibrates their agent's confidence; in trading, surveys repeatedly find
zero public implementations, with only the general-purpose LLM-uncertainty
toolkits (which do not include a decision loop) providing the primitives. If
that is still true, it is the differentiator, and the calibration loop becomes
the project's core rather than a reporting afterthought.

## Labels arrive late, and that shapes the whole loop

A swing decision cannot be scored when it is made. It can be scored when the
full holding window has actually traded. Until then the decision is *pending*,
not *wrong*.

The correct shape:

- mark each decision `pending` with a `resolution_date`;
- resolve it only when the horizon has elapsed, using prices that were
  observable at that time;
- match benchmark and instrument on their own session calendars;
- score a trade only once, and never re-score it after later information;
- keep pending decisions in the denominator for anything that counts coverage.

Train on resolved labels only. Retraining on pending or on a partially-filled
window teaches the loop to score itself on its own guesses.

A public reference implementation of this — pending-until-matured, dual-leg
session matching, a recorded resolution date, and a point-in-time test suite
named for look-ahead and settlement — is the file to port rather than reinvent.
Search for settlement/matured-label logic in the agent-framework ecosystem
rather than assuming you must write it.

Check whether your online-learning library already ships the delayed-feedback
primitive before building it: some carry a simulate-with-delay helper that
yields an unlabeled example first and re-yields it once the horizon elapses.

## Multi-agent combination: the evidence is mostly negative

Do not assume N agents plus a judge beats one strong agent.

- Multi-agent debate benchmarks report it often **failing to beat simple
  single-agent chain-of-thought and self-consistency** while consuming
  substantially more compute.
- Debate can **decrease** accuracy over time — models shift from correct to
  incorrect in response to peers, even when stronger models outnumber weaker
  ones.
- Practitioner reviews of their own papers have preferred a single frontier
  pass over a debate tool costing ~30× the tokens.

What does have backing:

- **Model heterogeneity.** Put each analyst on a different model family. Three
  copies of one model produce correlated errors, and the judge cannot see the
  disagreement that carries information.
- **A judge that is not one of the analysts.** Self-preference bias is
  documented across every model family tested — an agent grading its own output
  is not an independent check.
- **Combination logic that fails closed.** On LLM error, timeout or malformed
  output, abstain rather than default to a direction. Handle per-analyst
  permissions explicitly so a long-only analyst cannot manufacture short
  evidence, and exclude abstentions from the aggregate rather than scoring them
  as neutral.

Have the judge read **scores, not essays**, and prefer weighted blending over
free-text adjudication. If you do want an LLM to rank candidates, use a
pairwise-reranking shape rather than asking one model to grade prose.

## Reflection needs a verifiable external signal

Self-reflection without ground truth performs at baseline. In the standard
ablation, removing the reflection step lands exactly on the base score; the
gain comes from the external verifier, and the headline figure that made the
technique famous was inflated by test-execution false positives.

For a trading agent the only acceptable external signal is **realised outcome**
— actual P&L, actual fill, actual slippage. Never the model's own opinion of
whether it did well. If the agent reviews its own past decisions, the review
input must contain the resolved outcome, not the agent's forecast.

The review should be structured rather than free prose: what was predicted, what
happened, what was missed, what changes next time. Persist those lessons with a
timestamp and a reference to the trade, then inject only the most recent few
into subsequent prompts. Injecting an unbounded lesson log grows context without
adding evidence.

Pair it with a rolling-gate check — a hard accuracy/risk threshold over a
trailing window of resolved trades — so the system declines to scale until it
has earned it on sample size rather than on a streak.

## Validate sentiment on direction, not on tone

A sentiment model is scored as "accurate" by agreement with human sentiment
labels — which measures whether it reads the sentence, not whether it predicts
the instrument. On a commodity these diverge hard, because the same phrasing
inverts: falling yields and a falling dollar are *bullish* for gold while the
sentence reads as negative.

Generic finance lexicons and finance-pretrained classifiers inherit this
directly — a classifier will confidently score "yields climb, pressuring
gold" as positive. Prefix-framing or prompt-tuning makes it worse, not better.

So: measure any sentiment component on **forward return of your instrument**,
and prefer the approach that wins there even if its headline accuracy is
lower. In practice a general instruct model asked for the instrument-specific
direction has beaten a purpose-built finance classifier on exactly this test,
at CPU-only latency that a batch job can absorb.

Prefer the **shape** of a working sentiment component over a scalar: classify
the event class (hawkish/dovish, which variable moved) and hand the directional
call to the component that owns the underlying driver. A classifier is
defensible to train; a sentiment score is not.

## Same for every borrowed model

- Validate a volatility model against the risk job it will do. Textbook
  conditional-volatility models can lose to a flat historical sigma on VaR
  accuracy — fewer parameters, lower error.
- Fit regime-switching models and check whether a second regime is supported at
  all before building logic on it; a single-state fit is a valid answer and
  means the regime overlay is unsupported.
- Run a control: the same pipeline on an instrument where the effect is known
  to exist versus one where it is not. If both return "no signal", the harness
  is rubber-stamping and every verdict from it is void.
- **Test each borrowed feature against the dominant drivers first.** Regress the
  target on the drivers that are known to dominate it, then measure the new
  feature's increment. A component whose contribution has not been isolated is
  unmeasurable, and shipping or sizing it on its own score is a mistake.

Negative results do not transfer across horizons automatically. A volatility
model that loses to a flat sigma at a one-day horizon may win at a multi-week
one. Re-run the comparison at the horizon you will actually trade before
choosing.

## Triage third-party trading repos by reading, not by stars

Star count is a false-positive signal. A repository with tens of thousands of
stars can be a competition leaderboard with none of the architecture you need,
and can carry no licence at all. Clone it and look for the decision path.

Checklist: does the repo actually implement the claimed architecture; does it
have a licence; is the last commit recent; do the tests cover the failure modes
that matter (look for tests named for look-ahead, point-in-time joins,
settlement); and does its own README disclaim it as a research scaffold rather
than a strategy.

**Run the repos' test suites.** A suite that fails on a clean dependency set,
or that passes while the library it guards silently repaints, tells you more
about the repo than any README claim. Look for tests named for the failure mode
you care about; their absence is the finding.

**Check whether a feature library repaints.** Where an indicator computes
swing or extremum labels from a window that needs future bars to confirm, the
labels arrive early unless they are explicitly shifted by the confirmation lag.
Verify with a truncation test — take a prefix of the series and confirm no label
changes — because many such libraries do not document the shift and do not warn.

Also verify the dependency graph against registries before planning around it —
packages described as free in blog posts are sometimes custom-licensed and
unavailable, and the "successor" of a deprecated framework is sometimes a 404.
Implement short, well-understood algorithms yourself when the library is
abandoned or licence-encumbered; a purged/embargoed split is a small amount of
code.

## Structured output robustness

Nobody in this space retries with the validation error fed back. Most
implementations fail closed — any parse failure means no trade — and that is
fine as a floor, but it silently converts a formatting problem into a skipped
signal.

The shape worth implementing: constrained/validated decode → field-level
coercion that repairs an optional numeric field instead of discarding the whole
decision → one repair attempt carrying the validation error → hard reject with
the reason logged. Field-level repair matters most for numeric fields, where a
string like "15%" or a percent where an absolute was expected becomes a
wrong-sized order rather than a parse failure.

Keep the scoring layer and the execution layer as separate processes with a
schema between them. A scoring module that also simulates a portfolio will
grow into one, and then its accuracy numbers stop measuring decision quality.

## The architecture that survives this

    deterministic features  ->  agents (advisory, heterogeneous)
                                        |
                          deterministic aggregation + overrides
                                        |
                                 risk gates (hard)
                                        |
                              executor, no model in the path

Two patterns do most of the work:

1. **Compute everything numerically first; the model synthesises a decision
   from a compact digest.** Never let the model see raw series or do the
   arithmetic. The LLM gets a pre-computed brief of a few hundred tokens, not
   the OHLCV.
2. **Override the model's self-reported numbers with recomputed values before
   any gate reads them.** A model asked to report its own signal count or its
   own conviction will produce plausible numbers that carry no information;
   recomputing them makes the gates real. This is the single most valuable
   pattern to borrow from any public trading repo, and it is the direct antidote
   to the fabricated-confidence failure in
   `references/third-party-system-audit.md`.
3. **Recompute the model's own arithmetic and reject on disagreement.** The
   strongest version of the override: take the entry/stop/target the model
   proposed, recompute its own payoff ratio deterministically, and reject the
   decision if the two disagree beyond a tolerance. Also check stop/target
   ordering against direction, that the setup identifier it echoed matches the
   one supplied, and that the input it cited is not stale. Cheap, and it is the
   only check that catches a model that reasons fluently and computes wrongly.

Two independent public implementations arrived at the deterministic-override
pattern from different starting points. When separate authors converge on the
same safeguard, treat it as the required design rather than one team's taste.

Add a signal-persistence requirement before the risk engine — a single-period
shift is noise, require agreement across consecutive periods — so no confidence
score can shortcut the gate. Make those gates hard deterministic code that runs
*before* the risk engine, so nothing a model asserts can bypass them.

Keep the risk engine entirely free of model input. Sizing, halts and exposure
caps are not the model's to reason about.

## Orchestration: pick the laziest thing that is correct

For a single-node system, ingestion does not need a distributed log. A cron
timer plus a columnar file store with dated, diffable snapshots gives replay and
audit for a fraction of the moving parts, and it makes backtest/live parity
*easier* because one dated file is directly comparable to one replayed file.
A distributed append-only log makes parity harder without making it more
correct. Take the snapshot option.

Size the storage before choosing a database. For a daily-horizon retail
instrument, a few years of M1 bars is tens of megabytes and a few years of
ticks is single-digit gigabytes — both fit comfortably in RAM. Measured row
densities also favour plain columnar files over a purpose-built time-series
store on identical data. Reach for a distributed TSDB when you have measured
that you need it, not because the pattern is common.

Durable-execution engines earn their cost only when a partial cycle must be
resumed exactly — and note that their own replay guarantees commonly exclude
the external calls and database work that dominate an ingestion cycle, so the
idempotency you need still has to be designed by hand. For market-data
ingestion on one machine, idempotent re-runnable steps plus a snapshot
directory already give you the property you actually want.