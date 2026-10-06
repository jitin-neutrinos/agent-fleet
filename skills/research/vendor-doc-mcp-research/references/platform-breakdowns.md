# Platform breakdown deliverable (vendor-doc corpus → plain-English explainer)

Recipe for the class of ask: *"research using <vendor> MCP and give me a
detailed breakdown of <product>, I know the industry, explain in plain
English."* Output is prose/tables in chat (or a markdown doc) — NOT an HTML
artifact, NOT a PDF. Differentiates from `assistant-build-recipes.md`
(that one produces a paste-ready config spec) and from
`industry-play-enrichment.md` (that one enriches an existing doc's industry
section).

## Step order

1. **`list_publications` → locate the publication.** Note the topic count; a
   publication with <10 topics is a stub, look for the sibling publication
   (platform docs are often split across `<platform>` and `<platform>-workflow`).
2. **One broad `search_docs`** for the entry points. Harvest every hub/landing
   page title it returns — these are the sitemap.
3. **Fetch every hub page** (Overview, Architecture/Introduction, and each
   Manual landing page). Read their topic tables. This is the coverage map.
4. **Fetch the Architecture page in full.** It is the single highest-value
   fetch: it enumerates every UI surface, every backend service, every adapter,
   the cross-cutting infra components, and every user role with responsibilities.
   One page ≈ the skeleton of the whole deliverable.
5. **Fetch the leaf topics for the sections you will actually write** — 6–12
   more. Budget: hub pages + architecture + the leaf topics behind each
   numbered section. Never more than ~20 fetches for a "detailed breakdown";
   breadth comes from the architecture page, not from exhaustiveness.
6. **Cross-reference against sibling publications** when the architecture page
   names components that have their own publication (a rules engine, an
   analytics module, an identity server). One `search_docs` per named
   component. A name on the architecture page is not an interaction: an edge
   exists only when a page states the mechanism (API, token, node, or login).
   No such sentence means "named, no how-to" — do not describe a call. A
   product that only shares the same poster, with no "calls X" sentence, gets
   no edge.
7. **Write**, then run the citations check below.

## Section template that works for a platform explainer

1. What it actually is — marketing claim vs. mechanical truth, one table of
   floors/layers with an analogy each.
2. Architecture, service by service — front-end surfaces, backend services,
   adapters, cross-cutting infra. Tables. Name the underlying engine where the
   docs leak it.
3. User roles — one line per role, what they own.
4. Core data model — the nested objects everything hangs off, with the
   identifiers. **This is the section experienced readers care about most**;
   get it right and state the one operational gotcha attached to each object.
5. Runtime flow — design-time steps, then runtime steps, then the assignment /
   orchestration algorithm in prose.
6. UI construction model — how a screen is assembled from primitives.
7. Analytics / reporting.
8. The rules that will bite you — the doc's own warnings, promoted.
9. Honest assessment — real strengths, integrator watch-outs, doc-set defects.
10. Offer specific follow-up threads by name, not "let me know if you need more".

## Register rules (industry-experienced reader)

- Define every **vendor-specific** noun on first use; assume zero knowledge of
  **general industry** concepts (BPMN 2.0, CMIS, round-robin, BFF, skill-based
  routing need no expansion).
- No "imagine a restaurant". Analogies earn their place only where they replace
  a mechanical explanation of *this* system's wiring — a three-floor factory
  for platform/studio/runtime is fine; a sandwich shop for a database is not.
- Tables for anything enumerable (services, roles, data types, trigger types,
  auth modes). Prose only for flows, algorithms, and judgement calls.
- Keep API/curl examples and field-name tables OUT of the chat body unless
  asked — put paths and payloads in an artifact and speak in prose.
- Jargon check per sentence: if a term would need a second sentence to define
  and it is not vendor-specific, cut or rephrase it.

## Pitfalls

- **Landing pages overstate scope.** The Overview page here claimed
  "AI/ML Integration… predictive analytics, process mining" and "Automated
  Workflows" as headline features with no leaf page documenting them. Report
  them as positioning, not as shipped capability, or drop them.
- **Duplicated blocks are not corroboration.** See the rendering-artifacts rule
  in SKILL.md.
- **A feature's own page beats the roundup page** for scope limits. Every
  feature named in the deliverable gets its own fetch (the snippet rule).
- **Version/flag defaults are the highest-value trivia.** "Dashboard toggle is
  off by default", "project initialization is mandatory for Enquiry and
  Filters", "version before you migrate environments" — these default-off gates
  are what generate real support calls, and they live in leaf pages only.
  Collect them deliberately into the "rules that will bite you" section.
- **Least-explicit part of any platform is its integration handshake.** Search
  the leaf topics for the onboarding/register/link sequence and give it its own
  numbered call sequence. A named consumer is not that sequence — step 6.

## Citations (chat deliverable)

List the public doc pages actually read as a one-line "Docs read" preamble
before the body, each as a markdown link with its real title. Do not invent
`[n]` markers for a chat reply — inline links are enough and cheaper to verify.
For a markdown-file deliverable, use `[n]` + `[n] <url>` and run the
used==defined check described in SKILL.md.

## Worked example (Neutrinos Alpha Platform)

Corpus map that made this cheap: publication `alpha-platform` (68 topics) with
a sibling `alpha-workflow` (8). Four hub fetches covered the whole product —
`overview`, `introduction-alpha-platform` (architecture), `workbench-user-manual`,
`admin-user-manual`, `workflow-studio-manual` — each landing page carries a
topic table that enumerated its subtree. Leaf fetches then followed the tables:
model, projects, triggers, cases/onboard-process-and-case, layouts-categories-
and-forms, task-allocation, global-custom-code, change-tracking, dashboard,
environment-variables, workbench-glossary. ~15 fetches total covered a
nine-section breakdown. The architecture page alone supplied the service list,
the four user roles, and the case/process/task object hierarchy.
