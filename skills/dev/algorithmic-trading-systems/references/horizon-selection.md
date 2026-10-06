# Horizon selection — intraday vs swing, measured not assumed

Choosing a holding horizon is the first quantitative decision in a bot build and
it is usually made by vibes ("swing feels safer"). It is measurable, and the
measurement usually kills the intraday option outright.

## The comparison protocol

Run the **same signal logic** at each horizon, parameterised by timeframe, on an
**identical history window**, and report expectancy in R across a cost grid.

Hold constant across horizons, or the comparison is an artefact of fitting one of
them:

- identical signal family and entry/exit rules, only the bar size differs
- next-bar-open entry, past-only indicator windows (shift by one bar)
- SL wins when SL and TP are both inside the same bar (conservative)
- fixed, unoptimised parameters per horizon
- costs charged per round trip

Report **expectancy in R**, not just CAGR. R is the unit that makes horizons
comparable: it normalises away the position size and the instrument's price
level, so a 60-minute trade and a 10-day trade land on one axis.

## The deciding quantity: friction as a share of one unit of risk

Spread and slippage are a roughly **fixed dollar amount** per round trip. A
volatility-scaled stop is proportional to the bar's ATR. Therefore:

```
cost share of risk = (cost_per_round_trip_usd) / (atr_multiple × ATR_usd)
```

Measure this per horizon. It is usually the whole story. On a measured gold
example, with an identical ~$2.34 round-trip cost:

| Horizon | Stop | Cost as % of one unit of risk |
|---|---|---|
| Intraday 1h | $7.55 | **30.9%** |
| Intraday 1h (slow) | $12.09 | 19.3% |
| Swing daily | $129.77 | **1.8%** |

The intraday bot pays the same friction on a far smaller prize. This is not
"costs are higher intraday" — it is a tax on the denominator, and it does not
improve with better fills.

**Diagnostic to separate the two failure modes.** If a configuration shows a
positive gross expectancy and a negative net expectancy, the edge is real but
too small for the friction — that configuration is cost-limited and might
survive an ECN-tier spread. If gross expectancy is *already* negative, no
execution improvement rescues it. Only the second case justifies discarding
the horizon outright.

## The stop-versus-noise mechanism

A volatility stop that is small relative to its own bar's typical range is not a
stop, it is a coin flip. Measure it directly:

- `stop / median_bar_range` — above ~1.0 the stop is wider than normal noise
- fraction of bars whose **own high-low range already exceeds the stop**
- fraction of trades that close on the **entry bar** (immediate stop-outs)

A high entry-bar exit rate is the signature. On the measured example, the
intraday configuration stopped out on the entry bar 60% of the time while the
daily configuration did so 0% of the time — and the median holding period read
as literally 0 bars. That is not a tuning problem; it is a horizon mismatch.

## The data-depth asymmetry

Before choosing, check how much history each horizon can be validated on. Free
and cheap intraday feeds are routinely capped (a common one limits intraday to
~730 days) while daily history goes back decades. Two consequences:

- A short-history hypothesis can only be validated **live**, where there is not
  enough sample to separate skill from luck. State the trade-off explicitly
  rather than treating the two horizons as equally testable.
- When comparing, run the long-horizon arm on the **overlap** window so both
  arms see identical history, then separately report the long horizon on its
  full history as a robustness check. Never compare a 23-year result against a
  2-year one and call it a comparison.

Record the bar counts and date ranges in the output. An asymmetric comparison is
the easiest result in this domain to get wrong by accident.

## Trade-count and time-in-market are the second axis

- **Intraday** multiplies round trips per year (hundreds), each carrying
  slippage, rejection and reconnect exposure. Operational error rate scales with
  order count, so the failure surface grows even when per-trade economics are
  equal.
- **Swing** pays fewer round trips but accrues **financing every night held**.
  Compute annualised drag as nights-in-market × daily rate and compare it to the
  backtested edge before ranking — see the holding-cost rule in SKILL.md.

Neither is free. The comparison is which cost dominates *your* broker's numbers.

## Procedure

1. Fix the candidate horizons and the signal family. Record bar counts and date
   ranges for each; if asymmetric, say so up front.
2. Confirm data depth per horizon against a real historical query for an old
   window, not a live quote.
3. Run the identical-logic comparison on the overlap window.
4. Sweep costs across a realistic band and report expectancy in R at each point.
5. Compute friction-as-share-of-risk per horizon.
6. Diagnose the failure mode: cost-limited (positive gross) vs edge-negative.
7. Check stop-versus-noise and entry-bar exit rate.
8. Only then pick. Report the losing arm's numbers too — an intraday result
   that merely loses is a different finding from one that was never tested.