# Wizard sequences and the runtime contract

## Wizard — Prediction, Text

1. Prediction → Text → Add → Get Started → Text → Next
2. Upload Excel or CSV only.
3. Tick **Discard the First Row** if the file has a header.
4. Answer **Yes** to "is the dataset categorized", then pick the target column from the single
   dropdown. (No drops you into manual category entry.)
5. Verify the distinct categories listed. Model name + description.
6. Rules: Feedback Loop (Always / Never / Confident+threshold), Retention (1/5/15/25/30 or slider).
7. Gear on the Categories step: Advanced Configuration. **Multiple columns CAN be selected here** —
   this preprocessing screen is where the multi-select lives, not the target-category step.
8. Confirm ≥25 entries. Optional only when categories were detected from the data; mandatory when
   manually defined.

Hyperparameters (JSON): `validation_split` (default 0.2), `preset`
(best_quality/medium/highest), `training_time_limit` (25000s), `optimization.patience` (25),
`optimization.val_check_interval`, `optimization.top_k` (3),
`optimization.top_k_average_method` (`greedy_soup`), `optimization.max_epochs` (10),
`model.timm_image.checkpoint_name`, `model.hf_text.max_text_len` (truncates silently — set at or
above the 95th-percentile text length of the text column; for English prose estimate ~4 chars per
token, so a corpus with p95 ≈ 800 chars needs a max_text_len comfortably above 200 tokens, and any
sensible default clears it — the check is worth doing because truncation is the silent failure).

### Steps worth integrating from the clause-type-classifier build

For a classifier whose rows are one text string + one class label (e.g. clause text → clause
type), the exact sequence above works with three additional checks before Upload:

1. Column name the target unambiguously (e.g. `clause_type`) so the dropdown at Step 4 picks it
   without hunting among near-synonym columns.
2. Strip leading list-numbering prefixes (`1. `, `2. `) from the text column when present — the
   platform does not strip them and models can latch on to the numbering token as a feature.
3. Keep classes with a hard minimum of ~150 rows each. Below that floor a text classifier tends to
   overfit 1–2 surface tokens of the minority class ("waiting period" appears verbatim in most
   `waiting_period` rows, so it learns the token, not the concept) — which shows in the batch test
   as near-perfect precision on that class with poor recall everywhere else. Merge or re-label
   instead of training on a thin class.

## Wizard — Extraction, Document

1. Extraction → Document → Add → Get Started → Document → Next
2. Upload files (≥25). Record succeeded/failed counts; re-upload failures.
3. Model name + description.
4. **Add fields.** For each: Add Field, name it, and **double-click the rendered `String` to change
   the data type**. Table type reveals column definition.
5. Rules: Feedback Loop **per field** (Always / Never / Confident+threshold), Retention.
6. Tagging: String fields auto-fetch — click the field, validate against the document, Confirm.
   **Table fields are manual**: click the field → drag a rectangle over the table region → hover each
   column to annotate against the defined columns → Apply → Confirm. Repeat ≥25 documents.
7. Learning Progress hits 100% at 25 confirmations; Start Training appears.
8. If more files than 25 were uploaded, a pop-up offers to delete the unlabelled remainder — **click
   No** to keep them.

Advanced Configuration (Gear on the upload step): image preprocessing (Enhance Contrast, Mirroring,
Rotate, Resize, Remove Watermark, Gray Scale) and **Document Sensitivity Scoring** — Levenshtein
distance between the extracted value and the Review Hub correction; below a threshold (0.7 in the
docs example) the model scores negative. This is how retraining learns which field types fail.

Hyperparameters: `validation_split`, `preset`, `training_time_limit`, `env.per_gpu_batch_size`,
`env.batch_size`, `optimization.max_epochs` (10),
`model.mmdet_image.checkpoint_name` (YOLOX family: nano/tiny/s/m/l/x).

## Wizard — Extraction, Text

Same shape; add the entity names you will tag spans against. "Repeat the above two steps to perform
a minimum of 25 extractions... Once 25 entries are completed, the Start Training button will appear."
Hard gate.

Preprocessing applies at **row** level for extraction vs **column** level for prediction.

Hyperparameters: as above plus `model.hf_text.max_text_len` (truncates silently — set at or above
your 95th-percentile text length), `model.hf_text.text_trivial_aug_maxscale`,
`model.ner_text.checkpoint_name` (bert-base-uncased, roberta-large, distilbert-base-cased).

## Assistant

**Create the guardrail first.** Guardrails are a separate platform nav item, and the Assistants
option only becomes available once a guardrail exists.

1. Assistant → Create. Instruction tab: name, Directive, greeting, **Output format = Raw text or
   JSON** (JSON takes an inline schema: `{name, description, parameters: {type: object,
   properties: {...}, required: [...]}, additionalProperties: false}`).
2. Knowledge tab → Map Source, **max 10 sources per assistant**.
3. API Config: map endpoints; test with the assistant icon Test button.
4. Advanced: Allowed Domains, Translate Language, creativity %, PII Masking (defaults cover names,
   orgs, emails — add national ID and policy numbers as custom categories), retention.
5. Save → Publish. Test Version requires Publish first.

Guardrail rule types: Prompt Defense (L1/L2/L3), Content Moderation, PII, Unknown Links, Context
Filtering, Content Allow-List / Deny-List. Stages: Input, Output, or Input-and-Output.
**A rule set on the combined Input-and-Output stage cannot later be split** into separate Input and
Output rules — configure them separately from the start.

### Chaining

Link models: type dropdown (Prediction / Extraction / Assistant) → Data Type → Model → Model Version
→ **mandatory Description**. The Description is context the assistant reads, not a label — write it
as an instruction. A sequence block that names the linked models and their roles in one sentence
per link is the fastest correct pattern: the assistant reads each Description verbatim at runtime.

**Attach, never rebuild, an existing guardrail.** If the tenant already has a configured guardrail,
the assistant setup attaches that one in its configuration — creating a second guardrail with
overlapping rules duplicates enforcement and can double-block. Custom PII categories (national ID,
policy numbers) live in the guardrail, not re-entered at the assistant level; the assistant-level
PII Masking switch is just the on/off for that layer.

Two invocation modes:

- **Assisted** (default) — the pipeline is defined in advance; the primary assistant invokes exactly
  the models you linked.
- **Autonomous** — the primary assistant decides at runtime which assistants to invoke and can spawn
  ones you never configured. The docs list it as harder to debug and more expensive.

For any evidence- or compliance-adjacent product use **Assisted**. An assistant choosing which
evidence to gather is the failure mode a regulator would object to.

### Knowledge sources

**The uploader's PDF parser is pdf-lib** — the error string `Expected instance of PDFDict, but got
instance of undefined` is its signature, and it rejects PDFs whose cross-reference structure it
cannot parse (compressed xref streams from InDesign exports do this; the document itself opens fine
everywhere else). Fix by canonically rewriting before upload: `pypdf` read → `PdfWriter().append()`
→ fresh write regenerates the xref and the file then passes pdf-lib. Do not hand-edit bytes; do not
assume "valid in a viewer" means "valid to the uploader" — verify against pdf-lib specifically
before re-delivering, since pdf.js and pypdf accept files pdf-lib refuses.

Baseline FCA guidance PDFs (FG21/1 vulnerability, FG22/5 Consumer Duty) both had this defect.

## Runtime

**Preconditions:** the model must be deployed (Sandbox or Production) and a model-specific token
must exist. Tokens: 30 minutes / 3 hours / Never; value shown once.

**Prediction, Text — request.** Body keys match the training columns:

```json
{ "input": { "text": "<complaint text>" } }
```

**Prediction — response.** `output.category` = `{name, confidence}`; `output.categories` = full
ranked list; `result.predictions` and `result.probabilities`; plus `review_status`,
`manual_review_flag`, `processing_time`.

**Extraction, Document — request.** Two mutually exclusive options: upload the file directly (only
the `file` field selected) OR pass a `file_id` from
`https://aihub-staging.neutrinos.com/inferenceservice/file/upload` (its `_id` is the file_id).

**Extraction — response.** `output[].entities[]` each with `name`, `value`, `confidence`, `bbox`;
grouped under `section_name`. `file_name` at the top level. `result` carries raw internals
(`bboxes_info`, `cropped_images_info`, `extracted_ocr_entites`) — use `output`.

`bbox` is what makes an extraction auditable: it is how the platform draws the highlight over the
document and how a reviewer checks the read without re-reading the page.

**Assistant — request (sync).** Two calls minimum: `assistant/conversation/create`
(`{metadata, translation_enabled}`) → returns `_id` (the conversation thread), then
`assistant/message/create` with `conversation_id` + `text` + (`file` XOR `file_id`) + optional
`sources` (knowledge-source `_id`s from `assistant/knowledge/find-all` — multiple ids as a
comma-separated array) + `metadata`. `file` (direct upload) and `file_id` (from the generic
`inferenceservice/file/upload` endpoint, which also returns `page_count`) are **mutually
exclusive per call** — pick one.

**Assistant — response.** `{output: {text | json}, status: "Completed", inference_time,
conversation_id, created_at, metadata}` — the output shape follows the assistant's configured
Output format; with JSON configured, `output` carries the schema-shaped object.

**Assistant — batch/async.** `assistant/conversation/create/batch`
(`{metadata, callback_url, translation_enabled}`) → `_id` → `assistant/message/upload/batch`
per message (each message uploaded individually, all treated as ONE conversation) → results
pushed to the `callback_url`. `translation_enabled` in the request only works if translation is
also enabled in the platform UI per assistant.

**Batch** is four calls: `classification/create/batch` → `classification/upload/batch/{id}` →
`classification/start/batch/{id}` (returns 201, PENDING) → `classification/batch/find/{id}`.
Status: PENDING → IN_PROGRESS → COMPLETED / FAILED. Pass `callback_url` on step 1 to receive results
by push; omitting it yields an expected `callback_info` error in the response, not a failure.
Batch responses include precision, recall, F1 and accuracy — the acceptance gate before promoting a
retrained version.

Document extraction uses `document/ner/create/batch` and equivalents; same four-step shape.

## Deploy, retrain, review

**Deploy:** Deployment page → Sandbox or Production → Add (name, licence key, description) → attach a
model version via the kebab menu → toggle Deploy → choose the unit → Submit. Status flips to
Running. Undeploy toggles it off.

**Review loop:** Review Hub has Pending / Verified / Skipped / Ignored / Audit History; actions are
Confirm, Skip, Ignore. Gated by the feedback rule — Always, or Confident below threshold. Retrain:
Versions page → Retrain → **Data from Specific Version** pulls only Review-Hub-approved records;
produces a new version; redeploy.

**Testing diagnostic:** Test Version correct but live API answer wrong means a stale deployment or a
token binding, not a prompt problem.

## Known-unreliable advice to check rather than repeat

- "IRDAI is firewalled" — observed twice in one session, cleared within the hour for a subagent.
  Re-test before repeating it.
- Whether guardrails predate or postdate the assistant wizard in the current release.
- The assistant's programmatic wire contract — documented far less explicitly than
  prediction/extraction. Read it off the Integration tab.