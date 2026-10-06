---
name: stakeholder-decision-doc
description: Write research as a document that wins a decision.
license: MIT
metadata:
  hermes:
    tags: [Writing, Decision, Stakeholder, Research, Documents]
    category: productivity
---

# Stakeholder decision documents

Class-level skill for the document whose purpose is a DECISION, not comprehension.
The reader is skimming, has partial context, and will act on what they read first.

Triggers: investment case, business case, decision paper, board memo, pitch deck,
"use case proposal", "something I can present to a stakeholder", "convince them we
should build this".

## First: is it a decision document or a spec?

They are different artifacts and mixing them kills both.

| | Decision document | Technical spec |
|---|---|---|
| Reader | stakeholder, exec, investor | engineer, architect, builder |
| Job | win approval / alignment | enable implementation |
| Opens with | recommendation + ask | scope and architecture |
| Contains | numbers, risks, corrections | field tables, thresholds, schemas |
| Length | 15-25pp | 25-40pp |

A spec sent to a stakeholder gets skimmed and misunderstood. A decision document
with schema tables in it gets skimmed past the recommendation. **When asked for
"a report to present", build the decision document and keep the spec as a separate
companion artifact** — do not merge them. Ship both and name the split.

## Procedure

1. **Lead with the ask, twice.** Put a one-sentence recommendation and the
   specific ask in a boxed callout ON THE COVER, and restate the whole argument
   in full on the first content page. The reader who stops after the cover and
   the reader who stops after page 4 must both reach the right decision.
2. **Build the case in four moves** — demand quantified, gap measured, approach
   named, position stated honestly. Each claim carries its evidence inline; do
   not make the reader cross-reference a source list to believe a number.
3. **Quantify demand with at least one figure the reader can repeat to their own
   boss.** A single memorable number ("0 of 143 listings in this space") lands
   harder than five qualified ones.
4. **State what you are NOT asking for.** Bounding the ask before anyone wonders
   about cost is the section that most often moves a proposal from "interesting"
   to "approved".
5. **Include the kill criteria.** "What would make us wrong", with severities AND
   the conditions under which you would stop. A decision document without this
   reads as advocacy; with it, it reads as a plan.
6. **Record your own reversals in the document.** If research changed your
   recommendation, add a short corrections section naming the original premise,
   what the evidence showed, and what changed as a result. Never quietly amend
   an earlier draft's claim — the reviewer who read v1 will notice, and the
   section buys credibility for everything around it.
7. **Verify every load-bearing claim before delivery** (see below), then state
   provenance honestly in a closing box.

## Standing rules

- **Scope geography explicitly.** A decision document that names a domain but no
  geography has a hole the reader will find. If the source is a jurisdiction
  other than the target, say so and justify it (usually: "built to the strictest
  standard we found, so easier regimes follow").
- **Distinguish verified from vendor-reported.** Label vendor performance and
  marketing numbers as such. If a figure could not be traced to a primary source,
  EXCLUDE it and say in the evidence box that you excluded it and why. A visible
  exclusion reads as rigor; a soft hedge reads as uncertainty.
- **Lead with the regulatory or mandatory driver when one exists.** It outranks
  speculation about customer demand, and it reframes the ROI conversation from
  "will they pay?" to "what happens if they don't comply?".
- **One accent colour, and audit the source file for it.** Restricting a
  document to a single brand hue means removing accents from artwork and inline
  SVG too, not just CSS. Grep the file, do not trust the render.
- **Do not claim work you have not done.** If no prototype exists, no pilot has
  run, or no customer has been asked, the document must say so — ideally as the
  reason the ask is scoped to validation rather than build.

## Explaining the domain to a non-expert reader

When the reader is new to the subject (the owner may own the platform without
knowing the industry), the document's opening section carries the whole burden:

- **Open with one plain analogy that captures the mechanism**, not the features.
  A concrete, everyday object beats a definition. "This is a dashcam for customer
  interactions" lands; "this is a conduct evidence capability" does not.
- **Gloss every domain noun in a two-column table** — the word, then what it
  means in plain English. Six or seven rows is usually right.
- **Give one worked example end to end**, concrete enough that the reader can
  picture the failure it prevents.
- **State what the product explicitly is NOT**, and make clear that the limits are
  deliberate design choices rather than gaps.
- **Separate "who we are" from "who uses it"** in any roles table; the build team
  and the buyer are different organisations and conflating them confuses who the
  document argues for.

## Verifying before delivery

Research recency beats research volume. Before shipping, check every load-bearing
claim and expect some to have moved:

- **Contradictions between your own sources are findings, not noise.** When two
  agents disagree on a date or a number, verify against the primary source and say
  plainly which one was wrong. A recommendation resting on a dead deadline is
  worse than no recommendation.
- **Re-run the vendor's own current claims.** Vendors rename products, ship
  features, and launch competing products faster than documentation updates. A
  capability described as absent in an earlier session may now exist, and one
  proposed as a "gap" may be their flagship. Check the vendor's own newsroom and
  product pages, not the cached research.
- **Pull the catalogue/registry from its API when one exists.** A JS-rendered
  marketing site yields a partial list; a content API returns the complete one.
  Complete-vs-partial changes every count you publish.
- **Look for the incumbent's adjacent listing's adoption.** An empty category is
  either an opportunity or a proven dud — a near-identical entry sitting at the
  bottom of the download table is evidence of the latter, and it must lower your
  score.
- **Gate the claims.** For high-stakes research, put the final claim list through a
  verification gate with the fetch outputs as evidence, and treat a non-clean
  verdict as "tighten the claims" rather than "ship anyway".

## Deliverable handling

- Keep a copy in `~/uploads/` when the user is on a surface that resolves media
  from there, and state the absolute path as well.
- Bump the version in BOTH the filename and the document's own cover/footer when
  you revise. A cover reading "v2.0" inside a file called v2.2 is the kind of
  detail a stakeholder notices.
- Version in the filename rather than overwriting: reviewers hold references to
  the exact file they read.

## Support files

- `references/research-to-decision.md` — argument structure, demand/position
  evidence tables, correction-section patterns, and the reviewer's likely
  objections with prepared answers.
