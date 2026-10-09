---
name: pricing-benchmark-research
description: "Use when asked what to charge or the market rate."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [pricing, research, benchmarks, saas]
    related_skills: [grounded-citations, structured-surface-emission]
---

# Pricing and market-rate research (cited benchmarks to a recommended rate card)

For "how much could I charge / what is the market rate / what do competitors cost" about a seat, plan or contract. The deliverable is a recommendation (a number first, plain words) built on benchmarks whose provenance is visible. Jitin's standing rules apply: research answers carry citations and links, evidence is shown, and nothing is stated as verified that was not opened.

## When to Use

Trigger on: "how much could I charge", "what is the market rate", "what do competitors cost", "price per seat/user/course", a rate card or contract-value question. Skip for the user's own cost-to-serve or budget questions with no market comparison.

## Procedure

1. Route once (`~/.tool-router/route`). Then fan out in ONE batch: vendor pricing pages, independent comparison articles, regional vendors that publish a local-currency list (an INR list for India), how rivals price the premium feature (credits add-on vs bundled), and a regional-discount heuristic.
2. Open the vendor's own page (`web_extract`) for every price you will quote; a search snippet supports only what it literally says. When the page hides the number (interactive calculator, quote-only), grep the saved page text before concluding it is absent, then label the figure "estimate" or "third-party" — never "published".
3. Normalise every price to one unit (USD per seat per month) and show annual contract value at the target seat counts with the arithmetic (`rate × seats × 12`). Convert flat-fee and minimum-commitment plans (e.g. $15k a year for 250 users is about $5 per user per month) so they compare, and show how any overage rate was applied.
4. Record the counting model per vendor (registered seats, monthly-active users, learner bands). It moves the effective price more than the headline rate; recommend one model and name the alternative a buyer may ask for.
5. Add a source-quality column: vendor page / vendor blog / third-party benchmark / single blog post. A practitioner heuristic ("region X pays a quarter of US prices") is weak evidence — use it to sanity-check your own number, never as the number, and tell the owner to validate with real prospects.
6. Keep market data apart from the recommendation. Recommend tiers (core, premium feature such as AI, enterprise) per region, using local-currency vendor lists rather than converting USD at an assumed rate, plus levers: minimum commitment, volume break, platform/setup fee, pilot discount in exchange for a case study, term length.
7. Check any usage-heavy premium against cost to serve (token spend, budget guard) before pricing it; prepaid provider plans show a near-zero cost that a pay-per-token backend would change.
8. State what could not be verified and what the number ignores (cost to serve, tax, payment fees, FX, competing bids). Say plainly that this is a recommended starting position, not a quote.

## Deliverable

One Astra card: callout with the answer (number first, per region), vendor anchor table with source quality, tier table, kpis for annual value at the target seat counts, warn callout for the caveats, references that say opened vs search excerpt. For citation mechanics use `grounded-citations`; for the card use `structured-surface-emission` and run its validator before sending.

## Pitfalls

- Quoting a figure from a snippet as if the page was read — open the page or label it an excerpt.
- Comparing a headline per-seat rate with a flat-fee plan without converting units — the ranking inverts.
- One regional heuristic presented as the regional price.
- Pricing an AI premium by copying a rival's credit add-on rather than by what the bundled feature costs to serve and what rivals charge for the equivalent.
