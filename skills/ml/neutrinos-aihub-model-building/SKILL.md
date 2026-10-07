---
name: neutrinos-aihub-model-building
description: Use when building AI Hub models or training datasets.
version: 1.0.0
author: Hermes Agent
license: Proprietary
metadata:
  hermes:
    tags: [aihub, ml, training-data, extraction, classification, no-code]
    category: ml
---

# Neutrinos AI Hub — model and dataset building

## When to Use

- Building or configuring any AI Hub model (Prediction Document/Text, Extraction Document/Text,
  Assistant) through the platform UI, with no code written.
- Sourcing, cleaning or auditing training data for those models.
- Advising on the extraction/tagging wizard: fields, data types, Table columns, feedback loops,
  confirmation floors.
- Choosing between the Text wizards when a dataset is row-shaped or span-shaped
  (`references/model-type-selection.md`).
- Auditing rule-derived labels before shipping a training set
  (`references/dataset-quality-gates.md`).
- Answering what a model's input, output or API contract looks like at runtime.
- Deciding whether a public dataset is actually usable as training data.

NOT for Neutrinos brand/media work (see neutrinos-brand-core, neutrinos-print, neutrinos-documents),
and NOT for Alpha/Pulse/Studio app development.

Building training data and configuring models on the AI Hub Model Hub through the UI, no code.
Covers corpus sourcing, field schema design, dataset generation, the training wizard, and the
runtime contract. The user's stated constraint across sessions: **no code is written — everything
is configured through the platform UI.**

Docs live behind the `neutrinos-docs` MCP (`search_docs`, `get_doc_page`, `list_publications`,
`get_code_samples`). Verify every wizard step and minimum against it before advising; the UI and the
docs drift.

## The five model types and their floors

| Type | Input | Output | Floor (doc-stated) |
|---|---|---|---|
| Prediction — Document | PDFs/images | one label + confidence | **≥2 per category AND ≥25 total** |
| Prediction — Text | Excel/CSV rows | one label + confidence | "recommended ≥25 entries" (not a hard floor) |
| Extraction — Document | PDF/TIFF/PNG/JPG | named fields + Table rows | **≥25 files, ≥25 field confirmations, ≥25 documents for Table** |
| Extraction — Text | Excel/CSV rows | named entities | **≥25 tagged extractions** (hard gate) |
| Assistant | chat + files + connectors | conversational or JSON | configured, not trained |

Two structural facts that shape designs:

- **Retention is 1–30 days, max.** AI Hub can never be the system of record for anything with a legal
  retention duty. Anything that must be kept goes to the customer's own system through a connector.
  This is why "file the record" is integration work, not a model.
- **Feedback loop is configured per field**, not per model — Always / Never / Confident+threshold.
  This is the mechanism that lets a stable field run unattended while a contested one is
  human-checked every time. Set it per field, on the Rules step after the fields page.

## Model type follows the data's shape, not the deck

The single decision that costs most to get wrong, because it is made early and discovered at the
tagging screen. The question is one: **what unit does the label attach to?**

- One label per whole row → **Prediction — Text**
- A span inside running text, several per row → **Extraction — Text**
- Fields pulled from a document, including table rows → **Extraction — Document**
- One label per uploaded file → **Prediction — Document**

Per-assertion labelling is the common reason people wrongly reach for Extraction — Text. It does not
imply span tagging; it implies one assertion per row, which is Prediction. Row-shaped data handed to
the span wizard shows its error immediately — words become individually clickable, because the
interface is hunting a boundary the data has no opinion about.

Read `references/model-type-selection.md` before specifying a model type, and never carry one over
from a stakeholder document without re-deriving it from the data.

## Choosing between the two Text wizards

Prediction — Text has **no manual tagging step** when categories come from the uploaded data — the
docs call that confirmation step optional. Extraction — Text requires 25 hand-tagged spans
regardless. The correct model type is usually also the cheaper one; say so when recommending it, so
a correction lands as an upgrade rather than a setback.

## Procedure

### 1. Source the corpus, and verify it on disk

Never accept a count from a report — check the bytes. See `references/corpus-sourcing.md` for the
full method, issuer-diversity test, and the cleaning classes that recur.

### 2. Design the field schema before opening the wizard

This is the step that most often goes wrong, and it is cheap to get right here. Read
`references/field-schema-design.md` before deciding fields.

The governing question for every field: **is this value printed in the document, or supplied by a
human?**

- Printed in the document → String field, or a Table column.
- Supplied by a human → String field only. **Never a Table column.**

### 3. Build the dataset, keeping text real and labels auditable

- Text comes from a real source. Never synthesise complaint text, policy wording, or staff notes.
- Labels not present in the source come from deterministic rules, and the rules ship alongside the
  data in plain text so every label can be audited or overwritten.
- Ship a meta file per dataset: source, licence, row counts, label distribution, and the known limits
  stated as limits rather than hedges.

Rule-derived labels have their own failure modes. Run the gates in
`references/dataset-quality-gates.md` before shipping: reject the null class, require context before
a domain word counts as opinion, read samples from every class, cap oversampling at ~2x rather than
flat-targeting it, and emit a stratified calibration slice for the user to check.

Sanitize every CSV to fully-ASCII before advising an upload — the user's standing requirement is
clean data with no special characters, and row count plus class distribution must survive the clean
unchanged. Replacement table and post-write audit: `references/dataset-sanitization.md`.

### 4. Configure the wizard

Full step sequences per model type are in `references/wizard-and-runtime.md`.

### 5. Tag, train, deploy

Train to Sandbox first, never Production on a first run. Deployment units need a licence key from
subscription@neutrinos.com. Tokens exist only for deployed models, are model-specific, and their
value is shown once.

## Pitfalls

- **Choose the model type from the data, and never inherit one from a stakeholder deck.** A deck
  saying "classifier" or "extraction" is a description of intent, not a spec. Derive it from what unit
  the label attaches to. See `references/model-type-selection.md`.

- **Verify design decisions against the live screen, and trust the screen over your own spec when they
  disagree.** Interface behaviour that the data cannot support means the design is wrong — change the
  design. The cost of this is asymmetric: correcting a spec before training is minutes, correcting a
  trained model is a rebuild. Every schema error that mattered was surfaced by the user noticing
  something on screen that the spec never accounted for.

- **When the interface contradicts the spec, say so plainly and stop the build.** Do not re-explain
  the original instruction and let the user keep hitting the same wall. Name the mismatch, name which
  side is wrong, and give the corrected step.

- **The confirmations floor is documents, not per-field.** Working document-by-document and
  confirming each field confirms all fields at once. Advising 25 × N fields invents hours of work.
  Read whether the floor is per-entry or per-document before quoting effort.

- **Never project your answer-key CSV columns into the platform schema.** An answer key is a
  verification artifact used to grade what the platform extracted; it is not a field list. Its
  columns are frequently not creatable as platform fields.

- **When the docs describe a single-select and the live UI says "choose multiples", identify which
  screen the user is on before instructing.** On Prediction the target-category step is a single
  dropdown; the multi-select is the Advanced Configuration preprocessing screen where you choose
  which column to clean. Sending the user "go back a step" on a guess costs them their place.

- **String fields auto-fetch; Table fields do not.** Straightforward fields populate for confirmation;
  a Table needs a rectangle drawn, columns annotated, Apply, then Confirm — per document. But a field
  whose text is not printed in the document never auto-fetches at all — no footer line means no
  candidate and no green marker, which is correct behaviour, not a stuck field.

- **The Table field's columns must exist as printed structure in the document — prose blocks are
  String fields, full stop.** The docs' Extract-From-Table example is an invoice whose columns are
  printed on the page, because at annotation the cursor positions over each printed column. A clause
  block (heading + paragraph) has no columns to position over; a one-column Table degenerates into
  exactly what a String field does, but with column-annotation friction. Verify the target document
  actually prints a table before adding any Table field.

- **Metadata the API response already carries needs no training field.** source_document and page
  arrive as `file_name` (top level) and `bbox` (per entity) at inference time — do not invent
  String fields for them and do not spend tagging effort on values the document never printed.
  This is the same printed-vs-supplied test, extended to response-time metadata.

- **A classifier for a label that is not printed in the input is a Prediction, never an Extraction
  field.** The tell is the wizard shape: a value typed by a human at confirmation time ("exclusion",
  "copay") trains an Extraction field on labels that will not exist at inference. Route it to a
  Prediction — Text model whose training rows reuse the extractor's already-labeled dataset — the
  same CSV rows reshaped as a text column + a target column, no new labeling. Before training,
  reconcile the classifier's class vocabulary against the consumer (assistant schema) — collapsing
  near-synonym classes (`condition` + `waiting_period` → `waiting_or_condition`) before training
  beats mapping them at assembly; one label set everywhere.

- **Correct platform-extracted text before confirming it.** Auto-fetched values can drop spaces
  between words the PDF renders with tight kerning, so a two-word heading arrives run together.
  Confirming that teaches the defect across every document in the corpus, because multi-word titles
  are everywhere. Read the auto-fetched value against the document before confirming, not after.

- **Use the shipped answer key to grade confirmations, not to build the schema.** Check what the
  platform extracted against the key at each confirmation. A confirmation made by reflex becomes
  training data that teaches the error, and it surfaces later in a batch test rather than here.

- **One boundary box per field per document, then Confirm.** Multi-region tagging of the same field
  on one page is not supported — the box never turns green and nothing confirms. To capture several
  regions, return to the field and repeat the draw. Where one field's value comes from a human and
  another's from the document, both cover the SAME region: the Table reads the wording, the String
  field is told the label.

- **Click No on the unlabelled-files pop-up.** After 25 confirmations with more files uploaded, the
  platform offers to delete the remainder. Yes destroys documents that then need re-uploading.

- **A single negative reachability result is provisional.** A WAF block or firewall response observed
  twice in one session can clear within the hour — a subagent got through to the same host minutes
  later. Never harden one into "blocked" inside an artifact someone else will read. Re-test before
  writing it into a spec, and label it as a single-source observation if it must be recorded.

- **Verify delegated corpus deliverables by content, not extension or count.** A subagent reported 70
  verified PDFs; the directory held zero `*.pdf` because files were saved `.bin`. All 70 had valid
  `%PDF` headers and were fine — but the report would have read as "corpus is empty". Check magic
  bytes, page count and extractable text yourself before merging.

- **Bracket DataFrame column access when the name collides with a pandas method.** `sub.product`
  resolves to `DataFrame.product`, not the column; `df['product']` or `df.product` guarded is the
  only correct form.

- **Audit generated datasets by reading samples.** Recurring defect classes in extracted clause
  corpora: page footers (registered-office addresses) bleeding into the last block of each page, and
  keyword-matching fragments that match a type word while stating no clause. Filtering them costs
  rows — that is the right trade, because a human confirming by reflex is the real failure mode.

- **Check issuer/source distribution before calling a corpus adequate.** 68 documents from one insurer
  is not a dataset; it is a house style. Single-source bias is invisible in row counts and fatal to
  generalisation.

- **When a heuristic extraction over a large corpus will not validate, do not ship it with caveats.**
  Build the method against a hand-verified set first, require it to reproduce every verified row
  exactly, and add quality gates for the failure classes you have not seen yet. If it still leaks
  plausible-looking wrong values, report the honest covered count and stop — a table of wrong page
  numbers is worse than no table, because the user will act on it. Prefer reading a specific document
  on request over pre-computing all of them, and say which option you are offering.

- **A heuristic that passes its own gates can still be wrong in the cases you did not think of.**
  Each fix for a discovered bug creates new blind spots. Stop after the second round of
  bug-chasing-from-output rather than a third, and hand the remaining work back as manual review.

- **The wizard requires the header row to exist, and requires you to discard it.** A headerless CSV is rejected outright ('file has no <column> column. Use the sample file's columns') because the platform names its columns from row 1; always ship CSVs WITH the header row, and tick 'Discard the First Row' so the header is not read as a data row plus a phantom category. Ticking it on a headerless file instead silently eats a real row.

- **The knowledge-source uploader uses pdf-lib, which rejects many real-world PDFs.** Its signature error ('Expected instance of PDFDict, but got instance of undefined') hits designed documents (InDesign output, cross-reference streams) even when they open fine everywhere else. Fix by canonical rewrite — read the PDF and write a fresh copy (pypdf works); content is identical, the parser takes the rebuilt xref. Pre-empt the trap: rewrite EVERY externally-sourced knowledge PDF before the user uploads it, and verify with pdf-lib itself (node + `pdf-lib` load) rather than pypdf, which is too lenient to catch this.

- **'N chunks failed' on a knowledge upload means the chunker, not the data — flatten the document.** Designed PDFs yield irregular segments their embedder rejects. Rebuild as a uniform text PDF: extract the text page-by-page, normalize punctuation to ASCII, re-render through WeasyPrint under simple headings. If flatten-once is not enough, split into two uploads rather than iterating on rendering.

- **Watch for variable shadowing in parallel extraction scripts.** An inner loop reusing the outer
  loop's index variable silently corrupts page numbers — producing values beyond a document's page
  count, which is the tell. Assert `page <= total_pages` over the whole output rather than reading
  samples; the samples looked fine.

- **Run the model-testing artifacts via one seeded generator, not ad-hoc samples.** Draw 2–4 items per
  class from the real corpus with a fixed seed, ship them as: a JSON artifact (sample id, full input
  text, expected label) + a one-column CSV ready for the Batch tab + a README naming the model,
  nav path, pass criteria and the class's known failure mode. Examples of failure modes to embed:
  signal classifier 'none for everything' (natural-prior collapse), provenance 'fact for everything'
  (rebalance failed), clause-type class-spread collapse (minority classes didn't take). Separate
  smoke-testing from accuracy reporting in the artifact itself — drawing from the training corpus is
  fine for smoke tests; held-out splits from the data_split folders are for reported accuracy.