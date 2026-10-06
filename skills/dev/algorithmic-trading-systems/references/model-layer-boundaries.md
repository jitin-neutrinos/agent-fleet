# Where the model layer belongs — and where it is theatre

The honest split for a retail automated trading system. Research this BEFORE
designing an "AI-powered" architecture, because the default failure is putting
an LLM on the order path.

## Legitimate uses (earn their place)

- **Unstructured text → one numeric feature.** Headlines, filings, official
  statements reduced to a bounded scalar feeding a conventional model. This is
  the strongest argument for an LLM in the stack: it does feature extraction
  from prose, not price prediction.
- **Nightly research digest.** Summarising experiment logs, backtest reports
  and drift metrics into something a human reads. Hours-long latency budget,
  nothing time-critical.
- **RAG over primary documents.** Broker disclosures, central-bank statements,
  economic releases, regulatory notices.
- **Hypothesis generation and code review** over research notebooks — with a
  human reviewing every output before anything runs.
- **Keeping the research log.** An agent that maintains an append-only record
  of experiments, decisions and their evidence.

Rule for all of these: none of them may place an order.

## The boundary is drawn at ingestion too

Jitin's standing spec for a multi-agent trading system: the model layer lives in
**analysis only**. Explicitly outside it —

- **data ingestion** must stay deterministic. A model choosing what to fetch, or
  how to clean a series, makes the input to every downstream evaluation
  unreproducible and unauditable, which destroys the replay you need to defend
  a result;
- **order placement** stays a deterministic executor with a hard risk envelope;
- **the scoring/retraining loop** may use models, but it must consume labelled
  outcomes only, never write back into the decision path unmediated.

The reason is auditability, not caution: a backtest is a claim you may have to
justify, and every step that is not deterministic is a step you cannot replay.

## Theatre (documented failure modes)

- **Numerical backtesting.** An LLM doing arithmetic over price series is
  slower, less accurate and less reproducible than numpy.
- **Price/return prediction.** Studies of general-purpose AI tools on stock
  selection find risk-adjusted returns indistinguishable from benchmarks, with
  alphas statistically insignificant and results explained by ordinary factor
  exposures. Findings *do* appear for specific semantic-factor architectures
  on specific cross-asset samples — treat each as an unverified prior until
  reproduced on your instrument and horizon, never as a design guarantee.
- **Evaluation contaminated by training data.** If a public model has seen the
  same backtests, papers and forum threads you are evaluating on, reported alpha
  is not deployment evidence. This is temporal contamination and it is
  specific to LLMs; classical backtests are less exposed to it.
- **Fine-tuning on the method's own literature manufactures the result.** This
  is the active form of the above, not a hypothetical. Training on papers that
  describe a strategy and then testing that strategy guarantees a win that is
  recall rather than discovery, and no held-out split repairs it — the
  contamination enters at training time, so the test set is clean and the
  result is still false. See `references/domain-finetuning-for-finance.md`.
- **Latency mismatch.** A swing system has hours. A local model at 5-10 tok/s
  on CPU is unusable inside a tick loop and fine for a nightly digest. Measure
  actual tok/s on the actual runtime before designing around it.
- **Hallucinated numbers.** Never let a model report a backtest result; make it
  print and a script parse.

## The latency reality check

Always benchmark on the real runtime, not on assumptions:

1. `ollama ps` while a model is loaded — read the PROCESSOR column. `100% CPU`
   on a machine with a GPU means the runtime fell back to CPU.
2. Confirm the accelerator libraries the package actually ships, not just that
   a card exists. A package with zero CUDA/ROCm libraries will never offload.
3. POST `/api/generate` with a fixed `num_predict` and record wall time,
   `eval_count` and `load_duration`.
4. A load error naming an **unknown model architecture** means the runtime
   predates the model. The fix is upgrading the runtime, not swapping models.

On a 4070 Ti SUPER, single-digit tok/s means CPU fallback regardless of what
the machine has. Report the measured number, never an assumed one.

## Architecture that survives contact

    deterministic rules  ->  risk limits  ->  executor (thin, testable)
                                   ^
                                   |
                    model/advisory signal (can be vetoed or switched off)

- The bot must run correctly with the model layer disabled. If turning the
  model off breaks the system, the model is load-bearing and untested.
- Size adjustments and "no trade" vetoes are safer model outputs than
  direction. A wrong "don't trade today" costs little; a wrong "sell" costs
  real money.
- Export the trained model to a standalone inference format and serve it from
  its own process. On a platform whose in-process runtime cannot package ML
  dependencies (see `references/ctrader-platform.md`), this is the only shape
  that works.
- A swing bot polls for a signal; it does not need a per-tick model call.
  Design the interface around the horizon you actually trade.

## Validating any model claim before it earns capital

- State the falsifiable claim up front: beats what baseline, on what horizon,
  after what costs, on what instrument.
- Compare against the boring baseline (a simple rule-based system), not
  against nothing. Most ML claims are never run against the obvious rules
  baseline that practitioners actually use.
- Use purged/embargoed cross-validation and walk-forward — see
  `references/backtest-validity.md`.
- Count your trials. Every feature, window, model and seed tried is a trial,
  and the count sets the significance bar.
- Demand out-of-sample improvement that survives transaction costs. Gross
  Sharpe ratios in this literature are routinely negative after realistic
  costs — a gross number is not evidence.
- Prefer a model you can explain to the user in one sentence. If the
  justification cannot be stated without adjectives, it is curve-fitting.