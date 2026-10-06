---
name: algorithmic-trading-systems
description: "Use when building or reviewing an automated trading bot."
version: 1.0.0
author: kurama-core curator
license: internal
metadata:
  hermes:
    tags: [trading, quant, backtesting, ctrader, ml, risk, broker-api]
    category: dev
    related_skills: [grounded-citations, kurama-work-projects, selfhosted-mcp-ops, local-ai-ollama]
---

# Algorithmic trading systems — research, build, review

Governs the whole class: picking a venue, choosing a strategy, deciding what
the model layer is allowed to do, proving a backtest means anything, and
deciding when (or whether) real money goes behind it.

## When to Use

Use for: automated/algorithmic trading bots, broker-platform automation
(cTrader/cTrader Algo, cBots, Open API, MT5/MT4 EAs), strategy selection for
an instrument, backtest design and validation, ML-for-finance modelling
choices, "should I use an LLM to trade this", prop-firm and broker selection,
and reviewing someone else's trading system before funding it.

Not for: manual trade ideas with no automation, portfolio allocation advice
for long-term holdings, or tax advice (route that to a CA and flag it as such).

## Always-on rules

**State the base rate before the strategy.** Any plan that puts money behind a
retail automated system opens by naming what the evidence actually says about
retail/professional profitability — regulator loss-rate disclosures, published
trader-performance studies, the collapse record of marketed "AI" track records.
Do not soften this to be agreeable; the user is non-technical and cannot see the
gap between a plausible backtest and a losing account. Put the honest number in
prose in plain English, not buried in a footnote.

**Label every strategy claim with its evidence level.** Exactly one of:
`published/peer-reviewed`, `industry-standard practitioner`, or
`anecdotal/blog`. An arXiv preprint claiming 173% in three months is
`anecdotal/blog` until its methodology survives scrutiny — read the
methodology, not the abstract. SEO content farms and broker education pages are
`anecdotal/blog` even when the arithmetic in them is right; say which it is.

**Never let the model layer sit in the execution path unless proven.** An ML or
LLM component that can place an order is an unhedged liability. Default shape:
deterministic rules execute; the model produces an advisory signal or a size
adjustment; a human or a hard rule can veto. Keep the bot able to run with the
model switched off. Keep data ingestion deterministic too — see
`references/model-layer-boundaries.md`.

**A self-improving loop is not justified by its own trend.** Confidence and
accuracy rising over time is what an overfit system looks like from the inside.
Before designing a loop where agents score each other on realised outcomes,
read `references/self-improving-agent-loops.md`: it fixes the trial-count
significance bar, the sample size at which skill becomes distinguishable from
luck, and why calibration quality and predictive skill are separate numbers. Two
rules travel out of it: score a decision only once its horizon has actually
traded (label maturity, not "close it now"), and report calibration and skill
separately, both out-of-fold.

**Show the command and its real output.** Every platform capability claim gets
verified by running it (procedure step 2). Never report a capability as working
from documentation alone — vendor docs describe the desktop/cloud path, which is
not the path you will actually run on.

**Research fan-out is not verification.** Delegated subagents return
self-reports. Their delivered summaries are also truncated in the parent — read
the saved full summary file before synthesising. Re-verify any load-bearing
platform or performance claim yourself before it reaches the user.

Two concrete mechanics for long research fan-outs:

- The delivered summary may be one very long line; a normal line-oriented read
  returns a truncated slice. Parse it as JSON directly (find the first `{` and
  `json.loads` the remainder) and iterate the findings by index, printing only
  the ones you need. Index the list once, then request specific entries, so a
  large research payload never has to enter context wholesale.
- **When the read tool returns a stub but the file is clearly large, open the
  file with plain Python (`open(path).read()`) instead of re-requesting the
  read.** A line-oriented read of a single-line JSON payload returns a truncated
  window and the offset/line controls will not page through it, so retrying the
  read tool with different offsets cannot recover the middle. Reading the file
  directly and slicing it in Python is what actually works.
- When a subagent is running its own experiments, the live transcript is
  append-only and is where its measured numbers land before the summary exists.
  Read the transcript tail to answer "any update?" questions with real figures
  rather than a status sentence — a measured result delivered early is worth
  more to the user than a completion percentage.
- **Close a stream out; do not let it drift.** A stream that has produced its
  substantive findings but is now chasing vendor pricing pages, or re-verifying
  something already confirmed, will burn an hour for the least load-bearing
  section of the report. Steer it with the full section outline plus an explicit
  "write the file in your next action, no more verification" — and accept
  `UNVERIFIED` in the output rather than leaving a section unwritten. An
  unwritten report is worse than a report with three honest gaps. Steer text is
  queued, not injected, so send it while the child is still mid-flight and
  expect it to land on the following tool result.
- Start assembling the consolidated deliverable from the streams that *have*
  landed while the stragglers run. The tail of the work is not the bottleneck;
  writing the synthesis is.

Report intermediate *measured* findings as they land. A verified number
discovered by a subagent twenty minutes into a long fan-out is worth surfacing
immediately, because it can change what the user does next; do not hold it back
for the consolidated report.

**Audit a supplied trading repo before discussing its design.** When the user
hands you a third-party trading system to review, the audit comes before the
architecture conversation. Recompute its claims from its own artefacts — size
the repo, read the config, then run three forensics: whether the enforced
payoff ratio has any variance, whether costs are charged anywhere or merely
named as fields, and whether the model's confidence is a lookup table echoing
the system prompt. Check the measured holding period against the stated goal.
Report the disqualifying findings plainly and name what is genuinely worth
keeping. See `references/third-party-system-audit.md`.

**When asked to fine-tune on domain literature, name the contamination trap
before scoping the work.** "Train on papers about a method, then test that
method" produces a guaranteed, meaningless result, and unlike ordinary
look-ahead it survives held-out splitting because the contamination entered at
training time. Offer the paths that do work — fine-tune for a defined label or
extraction task, train only on material post-dating the evaluation window, or
use RAG and keep the weights clean. Read
`references/domain-finetuning-for-finance.md`.

**Choose the holding horizon by measurement, before choosing a strategy.** A
horizon is not a taste decision. Run identical signal logic at each candidate
horizon on an identical window and report expectancy in R across a cost grid;
the deciding quantity is friction as a share of one unit of risk, because a
fixed dollar cost against a volatility-scaled stop taxes the short horizon far
harder. Also check how much history each horizon can be validated on — a capped
intraday feed versus decades of daily data makes the two arms unequally
testable, not equally testable-but-different. Read
`references/horizon-selection.md`.

**Check the local cache before downloading anything, and check free disk.**
The model you are about to fetch is often already cached from unrelated work,
and training adds checkpoints and datasets on top of an existing cache. Measure
on-topic fraction of any corpus you find rather than assuming a large
transcript or document dump is domain-relevant.

**Enumerate every mounted filesystem before reporting a storage constraint.**
`df -h` on the home directory shows only that filesystem. The same machine may
carry a fast NVMe mounted at a secondary path with hundreds of GB free plus a
large HDD archive, which makes a "disk is full, must clear space" conclusion
wrong and costs a needless cleanup detour. List mounts first, then judge
capacity — report the drive that fits the workload (fast NVMe for datasets and
checkpoints, since dataloading is the usual training bottleneck), not just the
one that happens to be nearly full.

## Procedure

When auditing a system someone else supplied, follow
`references/third-party-system-audit.md` before this procedure.

1. **Fix the constraints before the ambition.** Instrument, holding horizon
   (intraday / swing days-to-weeks / position months), account size, venue,
   broker, and whether a model layer is wanted at all. A swing bot and an HFT
   bot are different projects; the horizon decides which evidence base applies.
2. **Probe the platform live, on the real execution path.** Documentation
   describes the GUI. Verify with a container/CLI probe: scaffold a trivial
   bot, build it, run it, read the log. Record which path (desktop / cloud /
   headless) the verified result applies to — capabilities differ per path.
3. **Establish the base rate and the risk maths** before any strategy work.
   Loss-rate disclosures, published trader-performance studies, drawdown
   recovery arithmetic, and the sizing rules that follow from them. This
   section exists to protect the user from himself.
4. **Rank strategies by evidence, then by cost.** Prefer the boring instrument
   with the deepest published evidence over the exciting one. State plainly
   where the honest conclusion is that ML adds little over a simple rules-based
   system at that horizon.
5. **Design the backtest to be falsifiable.** Purged/embargoed
   cross-validation, walk-forward, triple-barrier or explicit labelling, costs
   and slippage modelled from the venue's real spread, no look-ahead, and the
   multiple-testing correction for however many variants were tried. Record the
   number of independent trials — it sets the bar the result must clear.
6. **Define what the model is allowed to do** before training anything: input
   features, prediction target, horizon, and the decision rule that consumes it.
   If you cannot state the falsifiable claim the model must beat, you are
   building a curve-fitter.
7. **Stage the money.** Backtest → walk-forward → shadow/paper → tiny size →
   scale, each with a pass criterion and a time budget. Define the drawdown
   halt and max-risk-per-trade rules before the first live order, not after the
   first loss.

## Pitfalls

- **An enforced payoff ratio with no variance is a config, not a finding.** When
  every trade in the log carries an identical risk:reward, the ratio was
  hardcoded and any win-rate x payoff summary built on it is an artefact.
- **Costs named as fields are not costs.** A spread column in a data schema, a
  log key, an order-deviation argument and a placeholder array of ones are the
  four things that appear instead of a charge. Compute the drag against the
  measured R-multiple before believing any net figure.
- **A model confidence clustered on the prompt's own numbers is a lookup
  table.** If logged confidence collapses onto the values the system prompt
  assigns to each score, it carries no information beyond its input, and a
  calibration loop built on it is grading a copy of its own input.
- **Systems that require a structural target silently pre-filter their own
  sample.** Trades where structure did not offer enough room get dropped, so
  the surviving set is biased toward convenient outcomes.
- **Trusting vendor docs about the path you will not run.** Headless/container
  build paths can silently differ from the desktop path — a documented
  "dependencies resolved automatically at build" may apply only to the desktop
  or cloud builder. Verify by building and inspecting the artifact, not by
  reading.
- **A green build is not a working dependency.** Build success proves the
  project compiles; it does not prove the library was packaged. Inspect the
  emitted manifest and the output directory for the actual package or
  site-packages before telling anyone the model runs in-process.
- **Writes into a container bind mount produce root-owned host files** you then
  cannot edit, and no passwordless sudo to fix it. Copy the project to a
  container-local path inside the container and write there.
- **Relative-path layout is load-bearing in generated project scaffolds.** When
  a build error names a config file, check which directory level the build
  actually reads before assuming the file is missing — read the error's path.
- **Scaffold/authoring commands may require credentials even for local
  scaffolding.** If a scaffold command demands a login, either provide a
  throwaway credential for a local-only operation or hand-author the project
  files from a known-good sample.
- **Hardcoding a broker symbol name is the classic silent killer.** Symbol
  strings, contract sizes, pip semantics and account mode (hedging vs netting)
  are all broker-set, not platform constants. An opposite-side order on a
  netting account closes rather than hedges. Read these from the venue at
  runtime; never hardcode.
- **Pip value off by 100× on metals.** On gold-type instruments a pip is often a
  $0.01 price move with a 100-unit contract, so naive FX pip logic mis-sizes by
  two orders of magnitude. Compute position size from the venue's own reported
  pip size and contract size.
- **Server-side vs client-side trailing stops.** Client-side trailing lives in
  the bot and dies when the bot stops; server-side trailing depends on broker
  support. Know which one you depend on before trusting it across restarts.
- **Backtest entry time is server tick time.** Live adds quote travel, code
  execution and round-trip. Never let a backtest inform a latency-sensitive
  decision without a stated latency budget.
- **Built-in optimisers have no walk-forward.** Exhaustive/grid/genetic search
  over the same history is in-sample selection; without purged CV and a trial
  count, a "best" result is mostly the maximum of noise.
- **Assuming GPU offload because a GPU exists.** Check the runtime's own
  processor report and the accelerator libraries the package actually ships,
  not the presence of a card. Sub-10 tok/s on a modern GPU means CPU fallback.
- **A model architecture newer than the local runtime fails opaquely.** A load
  error naming an unknown architecture means the runtime predates the model —
  the fix is a runtime upgrade, not a different model.
- **Reporting only the average row of an aggregate metric table.** Per-item
  rows carry the real figures; the aggregate is frequently wrong. Quote the
  rows.
- **Presenting a capability the user cannot yet reach.** If the account type,
  licence tier, or broker blocks a path, say so before recommending the design
  that depends on it.
- **A cost expressed as a fraction is not a cost in R.** Cost per round trip is
  naturally a fraction of price; expectancy is reported in R, which is
  normalised by the stop distance in **dollars**. Converting needs
  `cost_dollars = cost_fraction x entry_price`, then divide by the stop. Skip
  the conversion and the cost term is off by a factor of the price level, which
  makes a losing horizon look cost-insensitive across the whole sweep. When a
  cost sweep shows expectancy barely moving as cost rises, suspect this before
  concluding the edge is robust.
- **Reporting a horizon comparison run on unequal history.** Compare the arms on
  their overlap window, then show the longer arm on its full history separately.
  Quoting a 23-year swing result beside a 2-year intraday result is not a
  comparison, it is a rounding error with a decimal point.
- **An intraday backtest that models one fixed spread is meaningless.** The
  platform's fixed-spread mode cannot express the intraday spread/ATR cycle,
  which is the quantity the whole horizon decision turns on. Model the spread
  band yourself, or the comparison measures an artefact of the backtester.
- **Star count is a false-positive signal for a library or repo.** A
  high-star trading repository can be a competition leaderboard with none of the
  architecture you need and no licence, and a blog-cited "free" package can be
  custom-licensed and unavailable while its stated successor 404s. Clone and
  read the decision path; check the licence field, the last commit, whether the
  tests cover the failure modes that matter, and whether its own README
  disclaims it as a scaffold. When a dependency is abandoned or
  licence-encumbered, implement it — a purged/embargoed split is ~30 lines.
- **Validating an imported model against the metric it was trained for.** A
  sentiment classifier scored on human sentiment labels measures whether it
  reads the sentence, not whether it predicts your instrument — and on a
  commodity the two diverge because falling yields and a falling dollar are
  bullish while the sentence reads negative. Score it on forward return, not on
  tone. Same for a volatility model: fit it against the risk job it will do, and
  check whether a second regime is supported before building regime logic on
  top of it.
- **Trusting a harness before trusting its verdicts.** Run it on an instrument
  where the effect is known to exist and one where it is not. If both return
  "no signal", the harness is rubber-stamping and every result from it is void.
- **Retraining on labels that have not matured yet.** A decision is pending, not
  wrong, until its holding window has traded. Resolving early teaches the loop
  to grade itself on its own guesses.
- **A vintage parameter that is accepted and ignored.** Macro series get
  revised, and the common data endpoint takes a "give me this as it was known
  then" parameter, returns HTTP 200 and a full row count, and hands back
  today's revised values anyway. Assert that the row count matches the window
  you requested; if rows appear past your as-of date, the vintage was ignored.
  Only a vintage-aware endpoint truncates. See
  `references/market-and-macro-data-sourcing.md`.
- **Choosing a data source because its live endpoint answers.** Free tiers
  commonly serve current quotes while limiting or omitting history, and
  aggressive per-request rate limits can turn a multi-year backfill into weeks
  of wall-clock. Verify with a real historical query for an old window, find
  the earliest date actually downloadable, and compute the backfill time before
  designing the pipeline around it.
- **A price-action concept library is not a strategy.** Implementations of
  retail price-action vocabularies (fair-value gaps, order blocks, structure
  breaks) are useful as *feature generators* feeding a conventional model. They
  carry no published edge, and a signal built only from them inherits none.
- **Holding costs can outweigh the strategy edge, so read the broker's cost
  panel before choosing one.** For any multi-night hold, compute the annualised
  financing drag first — nights in market × daily funding rate — and compare it
  to the backtested edge before ranking strategies. A trend system that holds a
  position ~70% of calendar nights can show a positive gross CAGR and a negative
  net one purely from funding, because the drag scales with *time in market*
  rather than per-trade size; a per-trade cost figure hides this. For a
  multi-night instrument the funding rate is a strategy-selection input, and
  moving from a CFD to the underlying future can be a larger edge than any
  choice between signal families.
- **Add a new feature only after you know what already explains the variance.**
  When a driver dominates an instrument (e.g. an asset whose price is largely a
  function of real rates and the dollar), a new weak feature's contribution is
  unmeasurable until you have regressed the target on the dominant drivers
  first. Do not ship, size, or claim credit for a component whose increment over
  the baseline has not been tested.

## references/

- `references/horizon-selection.md` — choosing intraday vs swing by
  measurement: the identical-logic comparison protocol, friction as a share of
  one unit of risk, the stop-versus-noise diagnostic, data-depth asymmetry, and
  trade-count vs time-in-market as the second axis.
- `references/ctrader-platform.md` — cTrader/Algo automation surfaces,
  verified Linux execution path, packaging behaviour, Open API maintenance
  state, symbol/account gotchas, CLI auth conventions.
- `references/model-layer-boundaries.md` — where ML and local LLMs legitimately
  earn their place in a trading pipeline vs where they are theatre, with the
  validation techniques for both claims.
- `references/backtest-validity.md` — purged/embargoed CV, walk-forward,
  multiple-testing correction, cost modelling, and the traps that produce a
  beautiful in-sample result.
- `references/third-party-system-audit.md` — auditing a supplied trading repo
  before funding it: recompute its metrics from its own trade log, and the three
  forensics that catch an empty backtest (zero-variance payoff ratio, costs named
  but never charged, confidence as a lookup table).
- `references/market-and-macro-data-sourcing.md` — choosing data sources and
  proving their provenance: the macro-revision trap where a vintage parameter
  is silently ignored, verifying a source with a real historical query instead
  of a live one, pricing a backfill against rate limits before designing
  around it, and point-in-time join discipline.
- `references/self-improving-agent-loops.md` — designing or reviewing a loop
  where agents score each other and retrain: multiple-trial significance,
  sample size vs skill, calibration-vs-skill, label maturity, multi-agent
  combination evidence, validating imported models against the downstream task
  rather than their training metric, and the deterministic-override pattern to
  borrow from public repos.
- `references/domain-finetuning-for-finance.md` — when the ask is to fine-tune
  models on finance papers, arXiv or market data: the contamination trap that
  held-out splitting cannot fix, which fine-tuning objectives are defensible,
  sizing and cache checks before a training run, and transcript-corpus risks.

<!-- canvas-output:start -->
## Canvas output

Plan in editable cards: a `spreadsheet` for the task table the reader will adjust, a `document` for the spec, `steps` for the sequence, `progress` for budget, `timeline` for milestones, and a warn `callout` naming the riskiest assumption.
<!-- canvas-output:end -->
