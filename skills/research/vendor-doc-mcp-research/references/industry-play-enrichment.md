# Industry-play enrichment for vendor use-case documents

Session-tested 2026-09-05 (AI Hub doc, section 04): user asked for an industry
section that was "more detailed, more industry spec, actual paths that can be
explored" — researched the vendor docs MCP AND industry-standard automation
practice on the open web, then rebuilt the section as structured "plays".
Use when enriching any vendor use-case/market document past the summary-table
stage.

## The play structure (what made it land)

Per industry play (keep to 3–5, each one screen-plus):

1. **Play title + one-line subtitle** naming the business outcome (e.g.
   "Health claims straight-through processing" — "the speed play").
2. **The industry problem** — grounded in external benchmarks with citations
   (percentages, cycle times, false-positive rates). The vendor docs alone
   never carry this; pair `search_docs` with 2–4 web searches per play.
3. **The vendor platform path** — numbered build steps naming the vendor's
   EXACT model/capability types per step, each step cited to the vendor doc
   page that documents it. This is the fusion: industry problem → vendor
   mechanism.
4. **Spec panel** — a compact grid repeating the decision axes a presales
   engineer actually chooses between. For AI Hub: Model types · Invocation
   mode (and WHY) · Guardrails · Human-in-the-loop · Consumption pattern ·
   Model Hub starting prebuilts.

Close the section with the cross-play pattern (the shared pipeline) and the
one KPI the industry watches (STP rate) — it gives the section an argument,
not just four examples.

Add a pill navigation row at the top of the section (`#play-<name>` anchors)
and TOC sub-items so the plays are navigable.

## Source discipline

- Vendor claims → vendor docs MCP refs (existing rN entries; never renumber —
  see the renumbering pitfall in `branded-single-file-html.md`).
- Industry benchmarks → web_search results; each gets its own new rN entry
  with publisher, date, and the specific numbers cited. Attribute derived
  numbers honestly ("citing ScienceSoft 2026 research").
- A vendor-company blog (e.g. neutrinos.com resource-hub) counts as an
  external industry source, not product documentation — cite it as such.

## Recipe

- 2–3 `search_docs` calls per play on the vendor MCP (feature-level queries:
  "claims extraction FNOL", "underwriting document prediction"), plus
  `fetch_document` for the one page per play that becomes the backbone.
- 2–4 `web_search` calls per play for benchmarks (query shape:
  "<industry> <process> automation benchmarks <year>").
- Append new references after the last existing rN; verify the citation
  graph afterward (used set == defined set, brackets in sync).
- If the doc has an editorial voice/skill (claude-design's slop audit, brand
  skill tokens), rebuild the section through the same extract → restyle →
  rebuild pipeline rather than hand-editing the delivered file.
