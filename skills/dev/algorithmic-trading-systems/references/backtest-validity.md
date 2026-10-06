# Backtest validity — making the result mean something

A backtest is a claim about the future built from the past. Most beautiful
backtests are a measurement of the search that produced them, not of the
strategy.

## The core problem

You try N variants, keep the best, and report it. With many independent trials,
the best in-sample result is mostly the maximum of noise — not an edge. Under
enough trials you can "discover" a profitable strategy in a random walk.

The correction literature that defines the modern field (Lopez de Prado and
co-authors):

- **Purged k-fold cross-validation** — remove training observations whose
  label window overlaps the test window, otherwise the split leaks.
- **Embargo** — additionally drop a gap after the test window, because
  serial correlation means adjacent periods are not independent.
- **Combinatorially symmetric cross-validation (CSCV)** and the **probability
  of backtest overfitting (PBO)** — estimate, per strategy, how often a
  backtest like this is fitted rather than real.
- **Deflated Sharpe ratio** — corrects an observed Sharpe for the number of
  trials, sample length, skew and kurtosis. The striking published result is
  that as few as three independent trials can produce a strategy that is
  likely false.
- **Triple-barrier labelling** — label an event by when a take-profit, a
  stop-loss or a time limit is hit, instead of a fixed horizon that quietly
  encodes a look-ahead.

These are the methodological corrections a reviewer will ask for. Naming them
by name is what distinguishes a serious analysis from a chart picture.

## Checklist before any result reaches the user

- [ ] Costs modelled from the venue's real spread, with slippage and swap —
      not a round number. On gold use a spread *band*, not one value.
- [ ] Signals computed on closed bars only; entry evaluated at the next
      tradable price, never at the bar's own close.
- [ ] Survivorship and look-ahead audited line by line, especially any
      indicator using future data or a warmup that silently reaches forward.
- [ ] The warmup/lag in live matching the backtest. If a moving average needs
      200 bars, the backtest must not trade during the first 200.
- [ ] Train/validation/test split respected, with purge and embargo at every
      boundary.
- [ ] Trial count recorded, and the result judged against the deflated bar.
- [ ] Out-of-sample performance reported alongside in-sample, not instead of.
- [ ] Compared against the boring baseline: buy-and-hold, and the simple
      rules-based system a practitioner would actually run.
- [ ] Robustness sweeps: vary one parameter at a time, check the result does
      not sit on a knife-edge single value.
- [ ] Enough trades to be meaningful. A "Sharpe 2.0" over 12 trades is noise
      with a decimal point.

## The traps that produce a beautiful in-sample result

- **Optimising parameters on the full history.** Exhaustive/grid/genetic search
  without a walk-forward is pure in-sample selection. Platform optimisers that
  offer only those three methods give you nothing here — implement walk-forward
  over disjoint windows yourself.
- **Silent warmup cheating.** Starting the equity curve after the indicators
  have stabilised hides the losing period that would have been traded live.
- **Favouring one direction or one regime** and reporting the window where it
  worked.
- **Using a data source whose spread and swap the live account never had.** Use
  a second, independent historical source for confirmation so you are not
  inheriting one venue's cost assumptions.
- **Realised-versus-assumed slippage drift.** Backtest assumes zero slippage;
  live never delivers it. Measure the difference in the shadow stage and
  re-run the backtest with the observed number.
- **Signal decay over the shadow period.** A signal can be genuinely correct and
  still stop working once widely traded. Track the signal's own statistics
  (hit rate, information coefficient, expected vs realised) — not only P&L.
- **Reporting the aggregate row of a metrics table.** Per-strategy rows carry
  the real numbers; aggregates are frequently wrong.

## Staged validation, with a money gate at each step

| Stage | Duration | Pass criterion |
|---|---|---|
| Backtest + purged CV | days | survives costs, deflated bar, beats boring baseline |
| Walk-forward / OOS | days | consistent sign across folds, no single-window dependence |
| Shadow / paper | weeks | realised vs assumed slippage within budget, zero operational errors, signal not decaying |
| Tiny size live | weeks-months | drawdown inside plan, no execution surprises, bot survives restarts |
| Scale | ongoing | only after the above hold for a full cycle |

Measure more than P&L at every stage: drawdown, exposure, realised vs assumed
slippage, signal statistics, operational error rate, time disconnected. A bot
can be profitable and still be operationally unsound — and that is how it
blows up during the one week you were asleep.

## Risk rules to fix BEFORE the first live order

- Max risk per trade as a fraction of equity. Volatility-scale it: position size
  from the instrument's own volatility and the stop distance, not from a fixed
  lot size.
- Geometric drawdown recovery is brutal — a 50% drawdown requires a 100% gain
  to get back. Size the plan so a plausible losing streak is survivable.
- Max daily loss and max total drawdown, each triggering an automatic halt.
- A drawdown halt that halves size (rather than stopping) is a defensible
  response to a losing streak; decide in advance which you are doing.
- Correlate your positions. Two "different" strategies on the same instrument
  are one position.
- Re-check that the account mode supports the positions the strategy takes.