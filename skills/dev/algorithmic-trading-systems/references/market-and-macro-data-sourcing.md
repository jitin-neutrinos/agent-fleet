# Market and macro data sourcing — provenance is the feature

Where the data for an automated trading system comes from, and the specific
mechanisms that silently corrupt a backtest. Read before designing the
ingestion engine, because every trap here fails *quietly*: HTTP 200, plausible
numbers, no warning.

## The revision trap: asking for "as it was known then" and not getting it

Macro series are revised. Payrolls get revised, GDP gets revised, CPI gets
revised. A backtest that joins the *final revised* value onto a historical date
has look-ahead baked in — and it is the most common contamination in
fundamental strategies, precisely because the API returns success.

**The mechanism to check:** does the endpoint actually honour the vintage
parameter you passed, or does it accept it and ignore it?

A verified test on the same series and window:

| Request | Rows returned | Early-period value |
|---|---|---|
| main CSV endpoint **with** vintage parameter | full history | matches today's revised series |
| vintage-aware endpoint (ALFRED) with vintage | truncated to the vintage | the value as published then |
| main CSV endpoint, no vintage | full history | matches today's revised series |

The main endpoint accepted the vintage parameter, returned HTTP 200, returned
the full row count, and returned *today's revised numbers* — silently. Only the
vintage-aware endpoint truncated. The difference in value was small enough
that nobody would notice in a backtest and large enough to manufacture a signal
in a strategy that leans on revisions.

Rules:

1. **Use a vintage-aware source for any revised macro series.** Know which
   endpoint is which before you write the fetch.
2. **Assert the row count against the window you asked for.** If you requested
   data "as of" a date and got rows past that date, the vintage was ignored —
   fail loudly rather than trading on revised data.
3. **Default (latest-revision) endpoints are fine for live features and poison
   for historical ones.** The same fetch function usually needs a vintage-aware
   path for backfill and a current path for live; do not share the code blindly.
4. Series that matter for a metals instrument typically include the real-yield
   (inflation-indexed) curve, the broad dollar index, policy rate, inflation
   prints, and payrolls. Verify vintage behaviour on **each** series you join —
   it is not guaranteed to be uniform.

## A live endpoint proves nothing about history

The most expensive mistake in this class is choosing a data source because its
live/demo endpoint responds. Free tiers routinely advertise current quotes and
quietly limit or omit history, because history is the expensive part to serve.

**Verify with an actual historical query before planning anything around it.**
Not "does it return 200 now" but "does it return the window I asked for, from
the year I need".

For each candidate source, record: does a real historical query for an old
window return rows, what is the earliest available date, is there pagination,
what is the rate limit, and does the free tier include it at all.

### What free historical coverage actually looked like

Measured, not assumed — treat these as the shape of the problem, and re-verify
because tiers change:

- **Public event/news APIs** that index decades of global news are the hardest
  case. They rate-limit aggressively (one request per several seconds), and the
  limit applies per request window even when you ask for a narrow date range. A
  multi-year daily backfill at that rate is measured in **weeks of wall-clock**,
  not minutes. Either budget for that backfill explicitly or accept a paid tier.
- **Free retail FX/commodity tick archives** often start far later than the
  vendor implies — a free per-minute gold archive may begin around 2018 while
  the instrument's history goes back decades. Check the earliest month
  actually downloadable, month by month, not the marketing claim.
- **Free daily OHLCV** is generally plentiful and deep, and a futures proxy is
  usually available back decades. Accept that it is a *proxy*: futures and spot
  differ in basis and gap structure. Use it for research and volatility work,
  then re-verify on the venue's own data before believing a net result.
- **Reference data and macro series** are usually the cheapest and deepest
  tier, and are frequently reachable without a key at all.
- **Lexicons and model files** sometimes 403 on direct download while the host
  page returns 200. If a direct fetch fails, do not conclude the source is
  unusable — check whether the artifact is mirrored on a package registry.

## Price the backfill before designing around the source

Compute `windows × requests_per_window / rate_limit` before committing to a
source for a multi-year history. If the answer is weeks, the design needs a
caching layer and a resumable backfill from day one, or a different source.
Building the pipeline and discovering this during the first backfill means
rewriting the ingestion layer.

## You do not need a distributed time-series store

For a single-node retail system, a columnar file store with dated, diffable
snapshots plus an embedded query engine covers it. Sizing sanity, measured on
one instrument:

- Five years of per-minute bars is well under a tenth of a gigabyte.
- Five years of *tick* data is a few gigabytes raw, tens of gigabytes
  compressed — comfortable on a normal workstation, still fine.

A distributed append-only log makes replay and backtest/live parity **harder**
(there is no single dated snapshot to diff against a replay) without making it
more correct. Take the snapshot option, and make the snapshot date part of the
artifact identity.

## Point-in-time joins are the whole game

The ingestion engine's job is to make every feature reconstructable as of a
past timestamp. That means:

- macro joins carry a vintage/known-at timestamp, not just an observation date;
- news carries a publish timestamp and an ingest timestamp — they differ, and
  a headline available at decision time is the criterion;
- feature snapshots are versioned with the code/config that produced them, so a
  replay is exact;
- ingestion is **idempotent and re-runnable** — the same input window must
  produce byte-identical output, or nothing downstream is trustworthy.

If the ingestion step is not deterministic and idempotent, the backtest is a
claim you cannot audit. This is the concrete reason to keep models out of the
ingestion path (see `references/model-layer-boundaries.md`).