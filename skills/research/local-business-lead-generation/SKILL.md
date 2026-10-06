---
name: local-business-lead-generation
description: "Use when building a callable B2B prospect list near a pin."
version: 1.0.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [leads, prospecting, google-maps, justdial, apify, local-business, b2b]
    related_skills: [maps, xlsx]
---

# Local business lead generation (radius-scoped, callable)

## When to Use

Any request to build a list of nearby businesses to sell to — "phone numbers of
gyms/clinics/schools within N km of this map pin", door-to-door canvassing lists,
delivery-radius prospecting, local B2B campaign lists. Also when an earlier attempt
returned a mostly-empty phone column, which almost always means the source actor
masks numbers rather than the businesses lacking them.

## Non-negotiable: real numbers only

Never fabricate, infer, or pattern-generate phone numbers. A synthetic number cannot
be dialed, so it makes the whole deliverable worthless. Every row must trace to a
real published listing. Measure and report phone yield before promising volume.

## Procedure

1. **Resolve the anchor to coordinates first.** Expand any map short link
   (`curl -sIL`, read the `location:` header). Then reverse-geocode the lat/lon
   (`nominatim.openstreetmap.org/reverse?format=jsonv2`) to learn the REAL
   neighbourhood. Do not trust your own recollection of the city layout — a pin
   labelled with a famous Bengaluru neighbourhood was actually Allalasandra /
   Yelahanka, ~13 km away, and every early search went to the wrong catchment.
2. **Enumerate the true catchment** with Overpass instead of guessing:
   `node["place"~"^(suburb|quarter|neighbourhood|village|hamlet|locality|town)$"](around:RADIUS,lat,lon)`
   POST the query via `--data-binary @file`. This returns the actual neighbourhood
   names to search with.
3. **Benchmark phone yield per actor BEFORE scaling.** This is the decision that
   matters most and it is cheap. Run the same category against 2–4 candidate
   actors, count `rows with a real phone / rows returned`, and pick on that ratio.
   Yield varied 4% vs 86% between actors on identical input — a 20x difference that
   only a head-to-head pilot reveals. Store ratings and user counts do not predict it.
4. **Pilot for real unit economics.** Advertised per-item price is fiction; measured
   cost per query is what counts (observed ~24x the advertised per-item figure).
   Query the account usage endpoint, compute
   `affordable_queries = (budget - spent) / measured_cost_per_query`, and size the
   sweep to that. Do not launch the full matrix first.
5. **Let the source search broadly, then hard-filter by coordinates.** When the
   directory ignores locality in the query text, sweeping every locality is wasted
   spend. Request categories city-wide and drop anything outside the radius
   yourself using great-circle distance from the anchor.
6. **Sweep category x locality in parallel batches** (3 concurrent runs is a safe
   default), one run per query so a single failure is isolated. Append each result
   to a JSONL as it lands so the work is resumable and cost is auditable mid-flight.
7. **Audit the output before delivery.** Assert all of these in code: every phone
   matches `^[6-9]\d{9}$`; every distance is `> 0 and <= max_km`; zero duplicate
   business names; zero duplicate phones; no missing area/category/URL.
8. **Cross-check a sample independently,** then state the verification level
   honestly. "1 of 38 independently re-verified" is the truth; implying all 38 were
   confirmed is the failure mode.
9. **Deliver as .xlsx + .csv + .json.** Sheets: All Leads (with a per-segment pitch
   column), By Segment (with a count chart), Nearest First (a walk-in route), How
   to Use. Straight-line km understates real distance — say so and give the
   road-distance multiplier typical for the city.

## Pitfalls

- **Compare phone yield head-to-head before committing budget.** Actor popularity
  and store ratings are near-worthless predictors; measured yield per row is the
  whole decision.
- **Verify the anchor's actual locality** by reverse-geocoding the decoded
  coordinates. Assuming a well-known neighbourhood sends the sweep to the wrong
  city zone and reads as an empty result set.
- **Trust measured cost, not advertised per-item pricing.** Per-event store pages
  quote per-ITEM cost, but runs also burn proxy transfer and platform usage, so
  per-QUERY cost dominates. Always pilot, then size the matrix to the balance.
- **Dedup by business IDENTITY, not by coordinates.** The same business surfaces
  from several category queries with slightly different lat/lon, so a
  `(name, lat, lon)` key lets duplicates through. Key on the normalized name and
  keep the nearest listing.
- **Match segment keywords at word START only.** Plain substring matching files
  "HEART CLINIC" under Dance/Music because "art" is inside "he-art". Use
  `(?<![a-z])` + keyword with NO trailing boundary — a trailing one then wrongly
  rejects "ayurved" for "ayurveda" and "school" for "preschool".
- **Classify on the business name, not the category blob.** Directory category
  fields are long comma-joined tag lists (a clinic tagged "Hospitals, Clinics,
  Diagnostic Centers, …"), so matching the combined string produces nonsense
  segments. Name first, category as fallback.
- **Normalize phones to 10 digits** (strip `+91`, leading `0`, separators) before
  dedup, and write CSV with the `csv` module — hand-rolled join/quote loops drop or
  corrupt rows whose business names contain commas.
- **Stop at the budget ceiling and say so.** Free-tier credit is finite; report
  spend explicitly and name the top-up needed for the next ring instead of quietly
  stopping mid-list.

## References

- `references/apify-directory-scraping.md` — actor comparison, schema discovery when
  the input schema is not exposed via the API, and the cost model.