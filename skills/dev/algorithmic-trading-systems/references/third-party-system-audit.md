# Auditing a third-party trading system before funding it

A supplied repo, a blog backtest, or a vendor pitch gets the same treatment:
recompute its claims from its own artefacts and find the places where the
number and the mechanism disagree. The README is a claim; the trade log is
evidence.

## Order of work

1. **Size it before reading it.** Commit count, date range, files, LOC per
   file, and where the data and logs live. A repo with seven commits in one
   afternoon is a prototype; say so before spending time on its architecture.
2. **Read the config, not the README.** Risk per trade, stop multiple, RR
   floor, confidence threshold, halt levels. These numbers decide whether the
   system is survivable, and they are the first thing a README omits.
3. **Find the real decision path.** Which module produces the signal, which
   scores it, which sizes it, which places the order. Most repos present one
   pipeline; check whether the AI is one call in a chain or genuinely an agent
   with state and feedback.
4. **Recompute every headline metric from the raw trade log.** Win rate, total
   P&L, max drawdown, trades/year, average AND median hold. Do not read these
   off a screenshot. Recomputing is cheap and it is where the story breaks.
5. **Run the three forensic checks below.** These are the ones that catch a
   system whose backtest is empty.
6. **Check the stated purpose against the measured behaviour.** A system sold
   as swing-trading whose median hold is five hours is an intraday system
   wearing a swing label — say so plainly and let the user re-scope.

## Forensic check 1 — is the payoff distribution real?

Load the per-trade results and inspect the distribution of any performance
ratio the system enforces a floor on:

    risk_reward = [float(r["risk_reward"]) for r in trades]
    print(min(risk_reward), max(risk_reward), len(set(risk_reward)))

**A zero-variance ratio is not a finding, it is a setting.** If every trade
carries exactly the same risk:reward, the ratio was configured, not discovered
— and any "win rate × payoff" summary built on it is an artefact of the
config.

Check the corollary too: systems that instruct a model to only take a setup
"when a genuine structural target exists at the required distance" **silently
drop the trades where structure did not offer enough room**. The surviving
sample is pre-filtered toward convenient outcomes. Look at how few trades
remain and whether any were rejected for missing a target.

## Forensic check 2 — do costs exist anywhere?

    git grep -n -i -E 'spread|commission|swap|slippage|commission' -- '*.py'

Then read every hit and classify it. A repository with costs correctly modelled
produces arithmetic — spread multiplied by size, swap applied per night held,
a cost deducted from P&L. What you will often find instead is only:

- a CSV column name carried through from the data schema,
- a log/serialisation field name,
- an order-deviation field passed to the broker API,
- a placeholder array of ones where a spread series should be.

Those are field names, not charges. On an instrument whose median forward move
is a fraction of the stop distance, costs are not a rounding error — compute
the drag against the measured R-multiple before believing any net figure.

## Forensic check 3 — is the model's confidence doing any work?

Take the logged confidence values and count them:

    Counter(d["confidence"] for d in decisions)

**A confidence signal clustered on two or three values is a lookup table.**
When the distribution collapses onto the exact numbers the system prompt
specifies ("5/5 confluence ~0.95, 3/5 ~0.70"), the model is restating an
arithmetic mapping it was handed. A signal that is a deterministic function of
an input carries zero incremental information, and any scoring or calibration
loop built on it is grading a copy of its own input.

Corroborating signs: the confidence in the decision log is not accompanied by
the features that produced it; the same value recurs across different market
states; or the distribution tightens as the prompt gets more prescriptive.

## Variance between reruns is a finding

Run or compare multiple backtests over the same dataset. If outcomes differ by
a large factor (say 1.3k against 6.8k on identical data), the system's edge is
smaller than its parameter noise and neither result means anything. Report the
spread, not the best run.

## What to report back

- **Keep** — engineering that is genuinely better than typical: backtest and
  live sharing one code path rather than a reimplementation, conservative
  same-bar fill assumptions, logging every decision including the ones not
  taken.
- **Set aside** — the parts that conflict with the user's stated goal or
  target venue, stated as a difference of direction rather than a criticism.
- **The disqualifying findings** — lead with the forensics, each tied to the
  artefact that proves it.

Do not soften the verdict to be agreeable, and do not pad it with praise for
the parts that work. The user is funding this with real money and cannot see
the gap between a plausible backtest and a losing account.