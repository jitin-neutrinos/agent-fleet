---
name: public-dataset-sourcing
description: "Use when training data must come from real public sources."
version: 1.0.0
license: Proprietary
metadata:
  hermes:
    tags: [datasets, training-data, provenance, data-sourcing, no-synthetic]
---

# Public dataset sourcing (real data, no synthetic filler)

For "build me the training data for these models" where the corpus must be REAL and
publicly sourced — no design partner, no client data, no LLM-invented rows. This skill
is about finding out what genuinely exists, refusing what does not, and proving it.

## When to use

- "create the training datasets for these models" with no client and no design partner
- "find real data on the internet we can train on instead of synthetic"
- "review this dataset list and see if any of it is usable"
- any corpus where fabricated rows would be indistinguishable from real ones to the buyer

**If the data is coming out of chat/session history, use `agent-transcript-datasets`
instead.** That is ingestion. This is external sourcing.

## The rule that decides the whole task

**Zero synthetic rows.** Fabricated training data is worse than a short dataset,
because the stakeholder cannot tell the difference and the model will not.

When a needed corpus does not exist publicly, the deliverable is **real text plus
rule-derived labels**, with the rules shipped as a plain-text artefact so a human can
audit or overwrite every one. Say so in the dataset's own meta file, not only in chat.

## Order of work — do not reorder

1. **Probe reachability before investing.** The best-looking sources are often walled:
   regulator sites behind Cloudflare, Kaggle behind auth, forums behind bot walls. Probe
   `curl` first, then a real browser if curl fails. Record the result per source in the
   provenance artefact so the next session re-probes instead of rediscovering.
2. **Inspect schema BEFORE bulk download.** Most dataset hosts have a JSON API that
   answers "what columns, how many rows" for free. One call beats a 500 MB download that
   turns out to hold no text.
3. **Verify the biggest source is actually usable.** Size is not fitness. See below.
4. **Read the corpus's own label distribution** and count it. Never infer a corpus's
   domain from its name.
5. **Build**, then **verify with a script that re-reads every shipped file**.

## Pitfalls that cost real time

- **The largest public dataset can be useless and still look perfect.** A consumer
  complaint database held 18,191,687 records and its API returned *metadata only* —
  product, issue, company, dates — with no narrative text field at all. A 64k-row
  mirror of the same data carried the narrative text but zero rows in the target domain.
  Count the domain terms in the actual rows before planning around a source.
- **Name a dataset after what it holds, not what it is called.** A set named
  `customers-complaints` held credit-reporting and debt-collection rows and no
  complaints-as-text. Verify with `df['Product'].value_counts()`.
- **Parquet downloads redirect.** A direct `huggingface.co/api/datasets/<id>/parquet/...`
  returns `302` and writes a ~150-byte stub. Add `-L` and assert the file starts with
  `%PDF`/`PAR1` before parsing.
- **`wc -l` inflates on quoted newlines.** A CSV whose text field contains embedded
  newlines reports far more lines than rows. Verify row counts with a real parser
  (`pandas.read_csv`), never `wc -l`.
- **Oversample then dedupe silently undoes the balancing.** `pd.concat([df, sampled])`
  followed by `drop_duplicates()` collapses the oversampled rows back. Dedupe FIRST,
  then cap per class. Always print the post-build distribution — if the balance is
  identical to the pre-build one, the balancing code did not run.
- **Client-rendered tab content is absent from static HTML.** A policy page's
  "What's not covered" tab existed only in the browser. Before declaring the content
  unreachable, check for a Next.js flight payload
  (`self.__next_f.push([1,"…"])` chunks, decoded then grepped) and the site's asset CDN
  host, which often mirrors the document library. Serve-rendered pages are the ones
  worth crawling.
- **A brochure downloads as a PDF and reads like a wording.** `pdftotext` it and check
  for actual clause verbs — `not covered`, `deductible`, `waiting period`, `shall not`.
  Marketing prose keyword-matches clause regexes; filter on an *assertion* pattern
  (does the sentence state a cover position, exclusion, limit or condition?) and on
  length, not on a keyword alone.
- **Check `curl -o /dev/null -w '%{content_type}'` and the magic bytes.** A 200 that
  returns an HTML error page is not a document.
- **Verify a delegated corpus on disk, not from its report.** A stream reported "70 PDFs
  downloaded" and `find -name '*.pdf'` returned zero — they had been written with a
  non-`.pdf` extension. Count the files, check magic bytes on each, and cross-check the
  manifest's row count against the filesystem before merging. A subagent's summary is a
  claim about what it did, not evidence that the artefacts exist as described.
- **Fix your own script's parameter types before blaming the data.** Passing a placeholder
  string where a function was expected produced a `TypeError` mid-harvest that read like
  a data problem. Read the traceback's line number before re-running anything.
- **Watch for variable shadowing in loops that also carry an index.** A patch that
  renamed only some of a nested loop's variables left the inner loop rebinding the outer
  page counter, so a 30-page PDF reported regions on page 50. Assert the invariant
  directly after building any locator that emits a page number: `df[page_col] <= df[pages]`
  must hold for every row. An in-range number is still not necessarily a right number,
  but an out-of-range one is definitely wrong and cheap to catch.
- **Validate a generated guide against hand-verified ground truth before showing it.**
  Build a small dict of documents you have already read personally, assert the generator
  reproduces them exactly, and report the pass rate. Then scan the whole output for
  values that are structurally suspicious (a bare UIN, a section heading, a phone
  number, a slogan). Fixing only the cases you already know about leaves the blind
  spots in place — when a fix is followed by the same failure count, the fix missed the
  real cause.
- **Do not present a heuristic-generated table as guidance someone will act on.** If the
  validation does not pass, say so and offer the verified-by-hand alternative rather
  than shipping plausible-looking rows. A table with confident wrong page numbers costs
  more than no table, because every row is a place the owner will draw a box.
- **Do not fill a documentation gap with inference and present it as the spec.** The
  platform docs are thin on the tagging screens. Where they are silent, say the
  behaviour is undocumented and let the owner's UI answer it — a wrong instruction
  costs a rebuild, and repeated wrong instructions cost the owner's trust in all the
  others. When a documented sentence contradicts what you told the owner, the owner's
  screen wins and the instruction is what gets corrected.

## Verify before claiming done

One runnable check, assert-based, that re-reads each shipped artefact: parses, row
count against the platform's floor, duplicate rows, null text, label cardinality, and
that each PDF has extractable text. Run it and paste the real output.

**Audit label quality by reading samples, not by trusting counts.** Print a few rows
per class and judge them yourself — a 40% `unsupported` bucket may be a genuine
category or may be a broken rule. Then check that the *distribution itself* is
plausible: if one class is 77% of the corpus, you are looking at your scorer's
preference, not a property of the domain.

**A wrong label confirmed in the UI becomes training data that teaches the error.** So
a generated locator that tells someone where to draw is a correctness-critical
artefact, not documentation. Validate it against hand-verified documents before
shipping, and refuse to ship it if it fails.

**State every unreachable source and why** in the provenance artefact, with the HTTP
status you observed. The gap is part of the deliverable.

## Watch for the mis-specified component

Before building, check the platform's capability model can express the requirement.
A component described as "a classifier" that must label *every sentence inside* a
document, with speaker and timestamp, cannot be a classifier — classification returns
one label per row. That mismatch is a design error, not a config detail, and finding it
before the build saves the week.

## Deliverable shape

```
<project>/<datasets>/
  processed/    the CSVs + JSON config the platform ingests
  raw/          downloaded parquet/HTML/JSON, unedited
  docs/         training files (PDFs), specs, doc references
  _meta/        PROVENANCE.md, every labelling rule as plain text, source reviews
  scripts/      the builders, re-runnable
```

`_meta/PROVENANCE.md` must state, per dataset: source and URL, what was downloaded,
what the labels are and where they came from, what could NOT be used and why, and any
legal question you are flagging rather than clearing.

Score user-facing prose against `~/Work/slop-score/slop-score.mjs` before shipping —
but ignore hits that are unavoidable domain terminology and say so rather than mangling
the term.

## Design the platform schema before you design the corpus

A corpus you can build is not a model you can configure. Before specifying fields,
check each candidate against what the platform can actually hold:

- **A value you supply must be a String field** (typed at confirmation); **repeated rows
  read out of a page must be a Table field**. Mixing these up is the expensive error.
- **A label that is not printed in the document cannot be a Table column.** Classifier
  labels, page numbers, filenames and document IDs are either typed into a String field
  or already present in the API response (`file_name`, per-entity `bbox`) — none can be
  extracted from the page.
- Confirming a **document** confirms its fields; progress counts documents, not fields.
- Confirmations should be **spread across sources**, the same acceptance test as corpus
  diversity applied to the labelled subset.

Full rules, the confirmed-field behaviour and the two-column-layout hazard:
`references/aihub-field-schema-design.md`. Read it before specifying fields or walking an
owner through tagging.

## References

- `references/aihub-model-build-constraints.md` — AI Hub's documented per-model-type
  gates, the 10-knowledge-source and guardrail-staging constraints, the field
  configuration that bites, and what the docs are silent on. Read before sizing any
  AI Hub build or writing its wizard steps.
- `references/corpus-extraction-technique.md` — pulling real clause corpora out of
  documents and sites: sitemap crawling, splitting on clause numbering rather than HTML
  tags, ordered classification cascades, the page-footer and bare-fragment defects, and
  harvesting taxonomies from mirrors when the regulator is walled. Read before building a
  document-extraction corpus.
- `references/aihub-field-schema-design.md` — how to split a requirement across String
  and Table fields, which labels cannot be extracted at all, what confirming actually
  counts, and the two-column-layout hazard. Read before specifying an extraction model's
  fields or walking someone through tagging.

## Source-diversity is a first-class acceptance test

A corpus from one supplier is a house-style bias, not a dataset. Report the largest
single source's share of rows as a number (`largest issuer share: 16.4%`, was 100%), and
treat it as a defect until it is under ~25%. When a research stream can widen the corpus,
dispatch it *before* writing the build spec — the spec's dataset block goes stale the
moment the corpus improves, and a stale `entries_count` in a machine-readable spec is worse
than no number at all.

**Fix the spec when the corpus changes, both formats.** If a prose walkthrough and a
JSON spec both carry dataset counts, a corpus rebuild orphans both. Update the numbers and
rewrite any prose section that characterised the old weakness; do not delete the honesty
about what still remains.

## Prefer a mirror over a dead end when the prize is a taxonomy

A regulator site being firewalled does not mean its label set is unobtainable.
Taxonomies are republished by industry bodies, courts and ombudsman services. Look for
the rules document the regulator administers, then check the harvested categories against
any already written into a deliverable — invented but plausible category names survive
review until a statutory list arrives and proves half of them do not exist.

## Deliver the artefact, not just the summary

When the owner asks for a dataset, hand over a real file. Package the training inputs, a
README naming exactly which file to upload and which is only a reference, and the labelling
rules. Verify the archive end to end before sending it — `unzip -t`, then read each CSV
back out of the archive with a parser and check every PDF's magic bytes. A dataset
described in prose is not a dataset the owner can act on.

## Pitfalls

- Never claim a corpus is usable from its title. Read a sample row.
- Never present an aggregate-statistics source as if it were training rows.
- Never launder a legal question as a technical one; flag it for legal.
- Never touch a production tenant to "just check" — datasets get built and uploaded only
  when the owner says so.
