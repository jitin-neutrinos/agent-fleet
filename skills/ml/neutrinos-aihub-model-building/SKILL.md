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

### 4. Configure the wizard

Full step sequences per model type are in `references/wizard-and-runtime.md`.

### 5. Tag, train, deploy

Train to Sandbox first, never Production on a first run. Deployment units need a licence key from
subscription@neutrinos.com. Tokens exist only for deployed models, are model-specific, and their
value is shown once.

## Pitfalls

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
  a Table needs a rectangle drawn, columns annotated, Apply, then Confirm — per document.

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