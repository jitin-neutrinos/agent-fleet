# Capability inventory — "what can I build on this platform, with no code?"

The deliverable is a complete, buildable answer to "what kinds of models can be
built using the existing products". It is NOT a filtered read of the pages that
happen to match your current hypothesis. The user will notice the difference.

## Why selective reads fail here

A corpus read aimed at one question leaves whole capability pages unopened, and the
skipped pages are disproportionately the ones holding the non-obvious capability.
On the AI Hub corpus, 15 of 58 product pages had never been opened; they contained
table extraction (the single highest-value capability), per-field confidence
routing, and a structured JSON output schema. All three changed the answer.

## Procedure

1. **List the publication directory and filter to product pages.** Exclude generated
   SDK reference dumps by filename prefix — they share recognizable patterns and
   otherwise swamp the list:

   ```python
   import os, re
   SDK_NOISE = r'^(example|extends|extended-by|implements|enumeration|i[a-z]|properties-|methods-1?\d|constructor)'
   product = [f for f in sorted(os.listdir(base)) if not re.match(SDK_NOISE, f)]
   ```

   Then subtract service/usage/API-reference pages by substring (`*service*.md`,
   `api-readme`, `prerequisites`, `*service-usage*`). Report the count you arrived
   at, so the user can see the sweep was exhaustive.

2. **Read every remaining product page.** Budget the whole thing up front. Cheaper
   than a re-research round after the user asks what you missed.

3. **Structure the answer in three tiers, because they answer different questions:**
   - **Model types** — the finite set of things that are actually trained or
     configured. Open with "the whole platform is N model types; everything else is
     configuration." This is the sentence that makes a large platform feel finite.
   - **Composition** — how models become a product (chaining, context filtering,
     guardrails, structured output). This tier is where most platforms' real
     differentiation lives and where docs coverage is thinnest.
   - **Operational backbone** — environments, tokens, review queue, retraining,
     audit logs, RBAC, retention, BYOM, connectors, marketplace. Without this tier
     the answer reads as a demo, not a shippable product.

4. **Per type, give: input → output → training floor → what you configure →
   what you can build on it.** The "what you can build" list is the part the user
   actually reads; enumerate concrete use cases per type, not abstractions.

5. **Extract every hard constraint into one gate list.** These are the numbers that
   kill designs, and they are scattered across pages: training minimums, knowledge
   caps, retention ceilings, upload size/format limits, features that only work on
   non-primary entities, settings that cannot be reversed once staged, steps that
   require a licence key or a published version. Put them in one numbered list and
   cite the page each came from.

6. **Flag silent-failure traps separately from constraints.** Constraints announce
   themselves; silent ones cost a wasted training run. Examples from this corpus: a
   text model that truncates past a configured character limit with no warning, and
   an assistant test path that only works once a version is published (so
   test-version-correct + API-wrong means stale deployment, not a bad prompt).

7. **Mark which capability is genuinely untapped.** A live catalogue inventory plus
   the vendor's own shipped products tells you what already exists. Cross-check the
   catalogue against the vendor's marketing site — the catalogue lags. State capture
   date and staleness explicitly; a category count from two weeks ago is indicative,
   not current.

## Sourcing discipline

- Read the product pages for capability claims. Landing pages overstate scope, and
  an overview that names a capability the feature's own page never documents is an
  unconfirmed claim, not a finding.
- If the docs contradict a page title, trust the TOC and the body, and say so — a
  page titled for a buried section will mislead anyone reading top-down.
- One marketing claim to actively distrust: a platform page saying it uses
  "pre-trained models" for tenant-specific work. A published training minimum proves
  it trains per-tenant; the marketing line is wrong.

## Adjudicating research-stream contradictions

If parallel research streams contradict each other on a load-bearing fact, resolve
against the primary source yourself and state the correction to the user, including
which stream was wrong. Do not average or majority-vote. A stream that built an
entire recommendation on a superseded deadline is worse than no stream at all.

Run the queued claims through `done_gate(claims, evidence)` before presenting, with
the page-fetch outputs as evidence. A `supported` verdict carrying high
`fabrication_risk` means tighten the claims, not that you may proceed unchanged.