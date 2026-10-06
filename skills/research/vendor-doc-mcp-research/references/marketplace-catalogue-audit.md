# Marketplace catalogue audit — what a vendor already sells, and what buyers actually buy

The deliverable is "which of these should we build?" answered against the vendor's
**live** catalogue rather than against the docs corpus or a stale capture. This is a
separate method from `capability-inventory.md`: that one enumerates what the
platform *can* do, this one establishes what the vendor *already sells* and which
listing shapes buyers adopt — the two inputs a build/no-build decision needs.

## Get the complete catalogue, not one rendered page

Vendor marketplaces are usually JS-rendered SPAs; a plain fetch returns a shell and
you will wrongly conclude the catalogue is small or empty. Find the backing CMS and
query its public API — this returns every record with pagination metadata, so you
can state a total with confidence.

The tell for a Vite/React SPA with no server-rendered data: the HTML body contains
only a footer. Then look for the API host referenced by the bundle or the network
tab, and hit its collection endpoint. Strapi is common and its shape is
predictable:

```
GET https://<cms-host>/api/<collection>
-> { "data": [ { "id": N, "attributes": { ... } } ], "meta": { "pagination": { "total": N } } }
```

Two things to capture from that payload:
- `meta.pagination.total` — the authoritative catalogue size, quoted in the report so
  the user can see the sweep was exhaustive rather than a first-page glance.
- every listing's category, title, description, and any engagement counter, saved
  to a scratch JSON file so later scoring re-reads the same evidence instead of
  re-querying.

**Report the count against the vendor's own marketing number.** A vendor claiming
"70+ assets" while the API returns 143 is worth stating plainly — it means the
marketing line understates the catalogue, which changes how much is really
contested.

## Keyword-sweep the whole catalogue for the candidate spaces

Build the candidate list first, then mechanically test each space against every
listing title + description. A table of `space → hits found → saturated/empty` is the
single most decision-relevant artifact in the whole exercise, and it is cheap: one
pass over the saved JSON.

Two traps:
- **Match on name and description together.** A listing titled generically
  ("Claims Summarisation Agent") still occupies the space its description claims.
- **Report zero as a finding, then immediately stress-test it.** An empty space is
  either opportunity or a signal that nobody buys that thing. See the adjacent-
  analogue rule below.

Cluster the catalogue and report per-cluster adoption, not just totals. A catalogue
that is 78% one line of business *and takes the majority of engagement* is telling
you where the vendor's customers actually are — which is the strongest available
evidence about demand, and it comes from the vendor's own install data rather than
from a market report you have to trust.

## Read adoption data as a statement about product shape

Engagement counters reveal what buyers pay for. Sort and cluster them:

- **Substrate vs finished unit — the counter is ambiguous, do not infer from it
  alone.** A per-listing engagement gap (e.g. 44 vs 27 mean) has at least two
  explanations that fit the identical data: (a) buyers prefer reusable substrate to
  finished units, or (b) finished units are harder to evaluate *before* a demo, so
  they are browsed more and adopted later. The counter cannot separate them.
  Disambiguate against external evidence before letting it shape a recommendation:
  find comparable marketplaces that chose each unit deliberately and check whether
  each won. When a component-first catalogue and an agent-first catalogue both
  report strong growth, the honest reading is that unit-of-sale is a packaging
  choice, not a demand signal — and that a marketplace's first engineering spend
  goes to listing-to-running friction (contract pricing, auth, install), not to
  catalogue composition. State the ambiguity rather than reporting the ratio as
  proof that components beat agents.
- **Orchestration vs raw capability.** If the top listings are routing, triage,
  summarisation and screening wrappers rather than the extraction/classification
  primitives, buyers pay for the judgement and routing layer. That reframes a
  platform build: the value is in the assistant/chaining layer over the models, not
  in the models alone. This inference is safer than the substrate one because both
  explanations ("they buy routing" and "primitives are boring") predict the same
  ordering — but still report it as an observation about the catalogue's top end
  rather than a law.
- **Badges are not signals.** Check whether a "trending"/"featured" flag correlates
  with engagement before trusting it. If flagged listings average *fewer* downloads
  than unflagged ones, the badge is editorial rank, not adoption — say so, because
  optimising for it is wasted effort.
- **Self-reported counters are directional.** A CMS engagement field with no install
  or download mechanism behind it counts something, not installs. State that limit
  in the report rather than quoting the number as installs.

## Check whether the catalogue can even be tried

Inspect every listing record for an install path, trial, sandbox link or import
action, not just the marketing CTA. If every record's sandbox/install field is null
and the only CTA is "request a demo", then no listing in the catalogue can be
self-served — which is a finding about the vendor's go-to-market that outranks most
individual use-case analysis, and often the highest-leverage thing you can tell the
user.

### Empty spaces cluster — cluster the catalogue before scoring any candidate

Two candidate spaces are rarely independent. Cluster every listing into functional
groups (decision-making, orchestration, extraction, surveillance, customer-facing) and
report adoption per cluster, not just per candidate. A catalogue that is mostly one
cluster *and* takes the majority of engagement is telling you where the vendor's
customers are, from the vendor's own install data rather than a market report.

The clustering also exposes the tail pattern cheaply: read the lowest-adoption listings
for the property they share. When consistently underperforming listings all make or
imply a decision, that property is a design constraint on your own candidate —
discovered for free from data you already hold.

### The adjacent-analogue check (run it before scoring any candidate)

Whitespace alone is not a case. For each candidate, find the **nearest existing
listing** — same input shape, same output shape, different domain — and read its
adoption.

- Adjacent listing healthy → whitespace is a credible opportunity.
- Adjacent listing in the bottom quartile → the *pattern* may be what buyers
  reject; being first into an empty space built on a weak pattern buys you a
  demonstration, not a product.
- Adjacent listing absent entirely — say so and lower confidence; there is no
  evidence either way.

Run this check on your own prior recommendation too, not only on new candidates. A
score built on whitespace alone is incomplete until the nearest neighbour's adoption
is in the arithmetic, and re-running it against a recommendation you already made is
how you catch it before the user spends work on the gap.

Then read the *tail* of the adoption distribution for what failed. Consistently
underperforming listings usually share a property — they make or imply a
decision, or they are surveillance-shaped, or they duplicate an incumbent. That
property is a design constraint on your own candidate, discovered for free from
data you already have.

### Check for pain evidence before you build a business case on pain

A demand argument usually rests on one of three legs: regulator attention, competitor
failure, or financial exposure. Check which legs actually carry weight, because the
one that is missing is often the one you were leaning on, and discovering that late
invalidates a whole framing.

- **Check whether the regulator is fining for the thing you are selling against.** Read
  the regulator's published enforcement and fine lists for the period, not the
  press coverage of them. Where the regime is handled Supervisoryly rather than
  financially, there may be **no penalty of that type at all** — and a business case
  built on fines collapses. Argue cost of evidence, cost of redress exposure, and
  supervisory risk instead.
- **The exposure usually sits in redress schemes, not fines.** Look for the compensation
  scheme attached to the conduct rather than the enforcement action. A redress levy
  reaching conduct from many years back is both a larger number and a better argument
  than any fine, because it prices the exact failure the product prevents.
- **Absence of published evidence is itself a finding, and sometimes the strongest one.**
  When no vendor, regulator or independent study publishes a success or failure rate for
  your category, do not fill the gap with a plausible number. Report the absence, then
  make publishing your own numbers a product asset — a first release that ships its
  per-segment performance becomes the reference the category lacks.
- **A regulatory gap is an opportunity only if someone is accountable for closing it.**
  Where a regulator has publicly stated it cannot measure something (a reporting
  vacuum, an unmonitored population), a product that produces that measurement has a
  defined customer. Confirm the admission is current and attributable before relying
  on it.

## Sourcing discipline

- Engagement and catalogue facts: your own saved API payload, stated as the count
  you computed.
- Vendor performance figures quoted in launch PRs: label them vendor claims and say
  whether you could find independent corroboration or only syndication of the same
  release.
- When the vendor's own case studies describe capabilities in the space you are
  proposing, that is direct evidence the space is occupied — cite the case study,
  not the marketing summary.

### Check the survey year inside the document, not the publication date

A trade article dated this year can restate a survey run years earlier, and the
restatement reads as current because the article is current. Always open the primary
report and read its methodology section for the fielding year and sample size before
quoting any survey percentage.

This goes wrong in both directions and both are embarrassing in a customer deck:
- **Stale-but-current-looking.** A trade piece re-presenting an older survey's
  figures as today's picture. Quote the original report with its year attached, and
  say plainly when a widely-circulated number is older than it appears.
- **Two numbers conflated.** The same percentage attributed to two different
  surveys or two different geographies by different write-ups. When two sources
  disagree on which vintage a figure comes from, resolve it from the report's own
  methodology before either figure enters a deliverable.

A related trap: trade press frequently compresses several regional or country-level
findings from one survey into a single headline. Verify that the entity named in a
claim is the entity the source actually studied — regional bodies, national
subsidiaries and global groups get conflated freely in coverage.

### Run the same verification on statistics your own subagents produced

A research stream's citation is not a verified claim. Streams report a figure and a
URL; the URL may be a trade article restating a decade-old survey, a vendor page
citing itself, or a paywalled secondary aggregator. For any statistic that will carry
a recommendation, re-derive it yourself: open the source named in the citation and
confirm the number, the year, the sample and the geography actually appear there.
Budget one search-and-extract per load-bearing number — it is the cheapest insurance
in the whole exercise, because a single mis-dated statistic discredits the
recommendations built on top of it.

Put the result in the deliverable's caveats section with its provenance class stated
plainly: verified yourself, verified by a stream against a primary source, or
single-sourced and unverified. Users act on these numbers in front of customers.