# Portfolio / suite analysis (whole vendor corpus → cross-product report)

Recipe for the class of ask: *"research using <vendor> docs and give me a
detailed report on ALL their products — consumers, use cases, integrations,
and how they relate to each other and to external apps."*

Different from `platform-breakdowns.md` in three ways that change the method:
the unit of analysis is the **portfolio**, not one product; the deliverable's
load-bearing content is a **relationship graph** (product ↔ product edges), not
a section-per-feature narrative; and the biggest analytical risk is
**double-counting or misdating** the catalog, because vendor corpora keep
successive generations of the same product published side by side.

## Corpus reconnaissance (do this before planning any writing)

1. `list_publications`. Record every entry with its topic count and version.
   This is the single most informative call in the whole task — it reveals the
   product count, the version fan-out, and duplicate display names before you
   have read a single page.
2. **Build a display-name → slug map.** Every other tool needs the slug, and it
   is not derivable from the display name. `list_publications` returns
   `"Pulse"`, `"AI Hub"`, `"Data Fabric"`, `"Alpha Platform"`; the actual
   `publication` values are `pulse-publication`, `ai-hub`, `data-fabric-
   publication`, `alpha-platform`. Learn slugs from the `publication` field on
   `search_docs` hits, then cache the mapping for the whole task.
3. **Expect duplicate display names.** They mean distinct publications, often
   the same product at two lifecycle stages (a "Reels" publication with 53
   topics and another with 32). Do not merge them on name alone — resolve them
   by content and supersession, per the rules below.
4. **Sort the catalog by topic count.** The long tail of <15-topic publications
   is stubs, secondary modules, or FAQ pages; the 100+ topic publications are
   the real product surfaces. A per-publication fetch budget keeps the tail
   from eating the whole budget.

## Generation, rename and absorption — the analytical spine

A vendor corpus usually holds **two coexisting generations**: an older
componentized suite described as a flat list of products, and a newer unified
platform that has absorbed most of those products as named internal layers.
Report both and their relationship; flattening them into one alphabetical list
is the failure mode this section exists to prevent.

Three distinct signals, three distinct treatments:

- **Version fan-out → one product, N releases.** Parallel publications whose
  names differ only by a version suffix (`studio-guide-7` / `-8` / `-9`,
  `components-guide-6` / `-7` / `-8`). Report the CURRENT one as the product,
  list the rest as its release history, and never spend budget fetching each
  version's identical feature pages — one version's page answers the question.
- **Rename → one product, two names, identical text.** When the Overview of two
  differently-named publications is byte-identical, that is a rename, not two
  products. Quote the shared sentence as evidence and state the rename
  explicitly; do not present it as a portfolio with two data-layer products.
- **Absorption → the product still exists, but its home moved.** A component
  with its own publication that ALSO appears as a named layer inside a newer
  platform's architecture is absorbed. Its capabilities are current; its
  standalone framing is legacy. The report must give the current home
  ("Reels now ships inside Pulse") and keep the standalone publication as the
  deep-dive source for its own features.

Per-hit `superseded_by` metadata on `search_docs` results is the cheapest
corroboration for all three — capture it while harvesting. Absence of a
`superseded_by` field is not proof of currency: confirm with the version pages
or an explicit doc statement before calling anything "current".

## Fan-out to parallel subagents

A portfolio sweep is the case where delegating pays for itself: partition by
product family (one child per major publication or product cluster), not one
child per question — per-question children re-read the same hub pages.

Give every child, verbatim:

- the exact MCP tool names **and** the rule that each `tool_call` carries one
  entry (see SKILL.md) so they do not discover it by rejection;
- the anchor page URLs already discovered this session, so children start at
  the hub and spend their budget on leaves;
- the publication slug for their slice;
- the citation contract: every claim carries a source URL, unproven cells read
  "not documented", and the final summary must be self-contained — children
  cannot hand back a pointer to a file.

Split out one child for the **cross-cutting** work (integration matrix across
products, release/version timeline). Cross-cutting views need the whole
catalog in one reasoning context; a child that only ever saw its own slice
cannot find that Reels appears inside Pulse's stack. This is the same reason a
portfolio report cannot be assembled from six independent per-product reports
alone.

While children run, do the anchor fetches yourself — the platform overview
pages that frame the whole portfolio. That is work no child has, and it is
what lets you write the framing paragraph the moment results land.

## Delivering on an async surface

When the request arrives on a surface that may be backgrounded (phone app,
messaging), background delegation means the user may see nothing for minutes.
Emit a small progress card (`badges` + `kpi` + `progress` + `checklist`)
showing what is in flight, state the one or two findings already confirmed,
then end the turn. Do not leave an interactive prompt waiting, and do not
stream partial prose that the final report will contradict.

## Canvas shape for a portfolio report

The report is genuinely multi-card; 3–5 cards is normal here because each card
is a distinct section, not a fragment of one idea:

1. `badges` (corpus depth, currency) + `callout` (the thesis: what the suite is
   and which generation is current) + `kpi` row (publications, products,
   integrations catalogued).
2. `table` or `spreadsheet` — the product catalog: product, role in the suite,
   consumers, status (current / absorbed / renamed / legacy).
3. `diagram` (relationship, direction `lr`) for product-to-product edges, and
   `graph` when the map has more than ~8 entities or you want kind-filtering by
   layer. Cap `graph` at ~60 nodes; a portfolio catalog can exceed that, so put
   the extra detail in the table instead.
4. `table` — the integration matrix: product, consumes, consumed by, named
   external systems, each cell either a cited claim or "not documented".
   Unproven cells are the finding; never fill them by inference from a shared
   poster.
5. `tabs` per product family for the per-product detail (what it is, consumers,
   use cases), or `accordion` for long methodology and caveats.
6. `callout` warn for what would change the analysis, then `references` with a
   real href for every cited page.

Emit the editable surface (`document` / `spreadsheet`) when the report is a
working artifact the reader will revise or take away — a portfolio analysis
usually is. Validate the spec before shipping if unsure it parses; a repair
that invents a block is worse than plain prose.

## Pitfalls

- **Do not trust `list_publications` names as slugs.** Covered above; this one
  silently produces zero-result searches.
- **Do not spend budget on version siblings.** Three identical feature pages
  across `-7`/`-8`/`-9` is one product, not three.
- **A name on an architecture page is not an integration.** An edge requires a
  sentence stating the mechanism (API call, token, node, login, import). No
  mechanism sentence means "named, no how-to" — record it as such. Two products
  sharing a poster gets no edge.
- **Landing pages overstate scope** — see SKILL.md. In a portfolio report the
  overstatement compounds across every product, so corroborate each named
  capability against its own leaf page before it enters the catalog.
- **Marketing category claims need the mechanical restatement.** Vendor landing
  pages open with a positioning sentence; restate what the thing mechanically
  is beside the vendor's claim so the reader can reconcile them.
- **Say plainly which products are thinly documented.** A stub publication
  padded into a paragraph of guesses is worse than an honest "2 topics, no
  architecture page published".
