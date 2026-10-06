# Designing the field schema for an AI Hub extraction model

Read before specifying fields for a Document Extraction or Text Extraction model. Every
rule here was found at the tagging screen, where a wrong field design costs a rebuild.

## The one distinction that governs every field

**A String field is told its value. A Table field is shown where the value lives.**

- **String** — the platform reads a candidate from the document, shows it with an arrow
  to where it found it, and you confirm or correct it at that moment. Use it when the
  value is a single labelled item (a product name, a heading, a classification).
- **Table** — the platform extracts nothing until you draw a rectangle. Use it when one
  page holds many repeated rows.

A field whose value you *supply* (a label you type) must be String. A field that reads
repeated rows must be Table. Conflating the two is the most common and most expensive
error in this flow.

## Traps

- **A classifier label is never a Table column.** Table columns extract text that already
  exists in the document. A field like `clause_type` holds `condition` / `exclusion` —
  words that appear nowhere in a policy wording. As a Table column it returns empty every
  run, or worse grabs nearby text and mislabels every row. It must be its own **String**
  field, where the value is typed at confirmation and that typing *is* the training
  signal.
- **Metadata about the document is not an extractable field either.** `page`,
  `source_document`, `filename`, `document_id` — none of these are printed in the body of
  the document, so none can be extracted. You get them free: the API response carries
  `file_name` at top level and a `bbox` per entity. Do not spend a column on what the
  response already contains.
- **Correct the value when the platform under-reads it.** Multi-word headings often come
  back run together (`PersonalLiability` for `Personal Liability`) because the PDF's font
  has no inter-word gap. Confirming the run-together form teaches a defect that then
  appears on every future extraction. Read what is in front of you and correct it.
- **A one-column Table is still a Table.** Numbered exclusion lists look like prose, not a
  grid, and still extract as a single-column table: drag one rectangle, hover one column,
  annotate once. The platform reads regions you define; it does not detect ruling lines.
  Switching such a field to String caps the model at one row per document.
- **Never keep two fields reading the same region.** A Table plus a String over identical
  text teaches two inconsistent representations and doubles tagging effort.
- **Do not change a field's data type after creating it and expect the drawing mode to
  initialise cleanly.** The docs warn that changing a type requires a manual box plus an
  Accept step; a Table field changed late can end up selectable but inert. If it does not
  respond, delete and re-add it fresh with its column defined.
- **One region per field per document — the interface enforces it.** The docs describe a
  single `click the field → drag one rectangle → annotate → Apply → Confirm` cycle with
  no repeat, and the UI refuses a second region on the same page. Do not plan a tagging
  pass around several boxes per page; choose the one cleanest region per field. A field
  that shows nothing on click is behaving correctly when it is a Table (there is nothing
  to auto-fetch) and is not a bug — String fields go green with an arrow to the text
  they read, Table fields stay orange until you draw.
- **A "header" toggle on a Table column does not create a place to type a value.** It
  labels the column; it is not an input. Enabling it expecting to enter `condition` per
  row is reading it wrong.

## One field, one region, one confirm

The cycle is: select the field, draw one rectangle over the region, annotate, Apply,
Confirm. Then the document is done and you move on.

You are choosing **samples**, not annotating documents. Each document needs a handful of
good examples, not full coverage — 25 documents each contributing one clause region
satisfies the platform floor exactly. A page whose boundaries you cannot see is worth
skipping, not squinting at; there are always more documents than slots.

Do not confirm on a page that has no instance of the field's purpose. A document tagged
only on a product name still counts toward the 25 and teaches nothing about clauses.

Read the product name from the page, not from a generated table: the footer form
(`Product Name: X`), the title line sitting directly above `POLICY WORDING`, and the
issuer name are three different strings, and boxing the issuer teaches the model that
every policy belongs to one company.

## Confirming, not per field

Confirming a **document** confirms its fields. The Learning Progress bar tracks documents,
not fields. A field showing a green marker has a candidate value; orange means still
open. So "N documents × M fields" is not N×M confirmations — over-counting this is what
leads someone to believe they need 25 per field.

## Distribution is the training signal

**Spread the first documents across sources.** A model tagged 25 documents from one
supplier learns that supplier's house style. When the corpus has many issuers, draw the
first N from as many as possible — this is the same acceptance test as
`largest issuer share` on the corpus itself, applied to the labelled subset.

**Check what the platform proposes and overwrite it when it is wrong.** For a field you
supply the label for, the platform has no basis for a guess; accepting its proposal trains
the model on its own error.

## Two-column layouts

Common in Indian health wordings: roman-numbered conditions run down the left column
while the next benefit starts in the right column of the same visual row. A box drawn
across what looks like one block silently captures clauses from two sections. Draw one
tight box per numbered group and check visually what the rectangle caught.

## Before tagging starts

- Confirm the field list and types, and that the Table field has its column defined —
  a Table with no columns cannot be annotated and clicking it does nothing.
- Set the feedback loop **per field** on the Rules step; it is not a model-level setting.
- Check the **Images** tab on one document. It shows what the OCR actually ingested. A
  blank or garbled page is an OCR miss, and no amount of careful drawing fixes it — move
  to a different page rather than fighting the interface.

## Rule-derived labels: the fallback bucket is not a class

When labels come from regex over real text, the dangerous case is the catch-all. A label
like `unsupported` that means "no pattern matched" will silently become a large share of
the corpus (37% in one build) and every row under it is unvalidated — including plainly
factual sentences that simply did not trip a keyword.

**Never emit a fallback label. Drop the row.** A smaller set of defensible classes beats
a larger set with a meaningless one, because the model will learn to emit the fallback.

**A domain keyword is not automatically a class trigger.** In a complaint corpus `fraud`
and `scam` appear overwhelmingly in factual reports — "the Fraud Department called me",
"a fraudulent alias on my file". 815 rows were mislabelled as opinion purely on that
word. Narrow a trigger to the construction that actually carries the judgement: only
`they committed fraud` / `it is a scam` count as an accusation; everything else falls
through to fact.

**Read samples per class after rebuilding, not just the counts.** A healthy-looking
distribution can hide a whole mislabelled class. Print three rows from each label and
judge each one yourself; that pass is what caught the fraud trigger, the footer bleed
and the run-together headings.

**Rebalancing by capping is only honest if nothing was oversampled.** If a minority
class is under the cap, fix the *detection* first — better sentence splitting often
recovers thousands of rows you were about to duplicate — and report explicitly when a
build genuinely oversampled, because duplicated rows need human sign-off before use.

**Ship a calibration set beside the training set.** A stratified 40-rows-per-class file
that a human reviews against the shipped rules tells you the real label quality in
fifteen minutes, and it is the only artefact that makes a rule-derived set auditable
rather than merely inspectable.