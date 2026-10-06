# Sizing a model build against AI Hub's documented gates

Doc-grounded, verified against the `neutrinos-docs` MCP (AI Hub publication, ~35
product pages). The full citation set lives in the conduct-evidence project's
`docs/AI-HUB-BUILD-MECHANICS.md`; this file is the condensed version that matters
when scoping work. Every number is quoted from a named documentation page.

## The five model types and their real gates

| Path | Gate | Notes |
|---|---|---|
| Prediction, Text | "recommended to confirm at least 25 entries" | A recommendation, not a hard floor. Mandatory only when categories are entered manually. |
| Prediction, Document | >=2 docs per category AND >=25 total | Hard minimums, doc-quoted. |
| Extraction, Document | >=25 files AND >=25 field confirmations | Learning Progress hits 100% at 25; Start Training appears then. Table fields need >=25 confirmed documents. |
| Extraction, Text | >=25 tagged extractions | Hard gate — the Start Training button is hidden until 25. |
| Assistant | no training | Configured only. |

**The trap:** file count gets quoted as the blocker, but for extraction the binding
gate is *confirmations*. Size an extraction build by confirmation count.

## Hard structural limits

- **Assistant knowledge sources: "up to 10".** Design around it. If the raw documents
  are numerous, have a model read them and hand the assistant structured rows — the
  assistant then needs only normative sources.
- **Guardrails are a SEPARATE platform nav item**, not an assistant tab. The Assistants
  option only becomes available *after* a guardrail exists, so build order is
  guardrail first, assistant second.
- **A guardrail rule set on the combined Input-and-Output stage cannot later be split**
  into separate Input and Output rules. Decide the staging before configuring.
- **Page-split exists on Prediction only.** No split step is documented on Extraction.
- **Context Filtering is unavailable on the primary assistant** (linked assistants only).
- **Retention is 1–30 days per model**; the platform purges within a 30-day maximum.
  Anything that must outlive that cannot be a model output — it is an integration to
  the customer's own storage. Audit logs survive model deletion for billing.

## Two features worth designing around

- **Per-field feedback routing.** Always / Never / Confident-per-threshold set
  *individually for each field* on extraction models. A stable field runs unattended
  while a messy one is forced to human review. Cleanest compliance mechanism in the
  no-code tooling space — lead with it.
- **Document Sensitivity Scoring (Levenshtein).** Distance between the extracted value
  and the Review-Hub correction; below a threshold (0.7 in the docs example) the model
  scores negative. This is how retraining learns which field types fail.

## Configuration fields that bite

- `model.hf_text.max_text_len` **truncates silently**. Check before training on
  paragraph-length text.
- Extraction preprocessing applies at ROW level; prediction at COLUMN level.
- Checkpoint selection: `model.mmdet_image.checkpoint_name` takes YOLOX names
  (nano→x) on document extraction; `model.ner_text.checkpoint_name` takes HF text
  models (`bert-base-uncased`, `roberta-large`); `model.timm_image.checkpoint_name`
  on document prediction.
- Assistant JSON output schema nests under `parameters` as a typed object
  `{type: "object", properties: {...}, required: [...]}` with `minItems` and
  `additionalProperties` supported. A bare map of field definitions is rejected.

## Deployment and tokens

- Deployment units need a **licence key from subscription@neutrinos.com**.
- Sandbox and Production are separate environments. Sandbox first, always.
- Tokens exist **only for deployed models**, are model- and version-specific, and the
  value is shown once. Expiry: 30 minutes / 3 hours / Never.
- `Test Version` requires Publish first. **Test-version correct but live API wrong means
  a stale deployment or token binding, not a prompt problem.**

## What the docs do NOT state

Do not invent these; they are unprovable from documentation:

- Which Model Hub categories are empty, and any per-category counts. Needs a live
  tenant login — an "our categories are unique" claim in a pitch deck has no
  documentation trail.
- A hard row minimum for text classification.
- Max fields per model, max columns per Table field, max guardrails per assistant.
- The full field data-type palette beyond the Table example.
- Exact accepted file-format lists and upload size limits.

## The improvement loop

Train → deploy → infer → Review Hub pools items per the feedback rule → reviewer
Confirm / Skip / Ignore → Versions → Retrain → "Data from Specific Version" pulls
**only Review-Hub-approved records** → new version → redeploy.

Retraining on unreviewed data is the failure mode; the platform also offers "Add New
Data", which comes back flagged "New" for confirmation. Prefer the approved-records
path when the point is that the model learns from corrections.

## Domain sources that worked, and the walls

Reachable: insurer sites that **server-render** policy wording; Indian government sites
(ESIC responded to curl and exposed PDFs under `/attachments/`); HuggingFace datasets
with a usable JSON row/size API.

Walled from this host: `content.naic.org` (Cloudflare), Kaggle (needs credentials),
Reddit. Re-probe rather than assume, and record the observed status in the provenance
artefact.

**Do not record a site as permanently unreachable on one probe.** A regulator site that
answered `blocked` to both curl and a real browser was later re-probed successfully and
served eight filed policy wordings as direct PDFs. The wall may be intermittent or
path-specific. Treat "unreachable" as a timestamped observation of one attempt, and
re-probe before it reaches a deliverable as a stated blocker — an owner who acts on a
false blocker chases a network problem that does not exist. This cuts both ways: never
drop a live source on a single failure.

**Government and public-institution benefit rule books are legitimate clause-extraction
training files** — CGHS, ESIC, PM-JAY package lists carry the same structural features
(benefit terms, eligibility conditions, exclusions, sub-limits, waiting periods,
room-rent caps, rate lists) as commercial wordings. Flag them as a separate class, not
as insurance policies.
