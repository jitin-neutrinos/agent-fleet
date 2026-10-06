# NER dataset build (Discourse posts → AI Hub Text Extraction CSV)

Procedure for regenerating the entity-recognition training file when new posts are
ingested or the label vocabulary changes.

## Source and cleaning

- Start from `app/exports/training_priority.csv` (column `text`).
- Strip attachment noise before anything else: `Screenshot (55) 1920×1080 231 KB`, bare
  `N×N` resolutions, bare `N KB/MB` — the export concatenates Discourse attachment
  metadata into the body and it pollutes every downstream model.
- Drop rows shorter than 15 chars (leftover `[code]`, "Swagger UI" junk) and exact
  duplicate texts after cleaning.
- Do NOT clean `training_priority.csv` / `training_sentiment.csv` in place — the
  priority/sentiment models were trained on them as-is; clean into the NER output only.

## Annotation (pattern-based pre-labeling)

Priority order matters — label EMAIL before PRODUCT before PERSON, and skip any match
overlapping an already-claimed span:

1. `EMAIL`: `[\w.+-]+@[\w-]+\.[\w.-]*\w`
2. `PRODUCT`: case-insensitive alternation of the known-vocabulary list, longest-first
   (Neutrinos Studio, Neutrinos SSD, Neutrinos AI Hub, Alpha Platform, Alpha Sandbox,
   Neutrinos Kernel, Neutrinos LDAP, SSD, Alpha). Extend the vocabulary when new product
   names appear in posts — pattern matching cannot find unknown names.
3. `PERSON`: `@[\w.-]+` (Discourse @mentions).

Emit `ground_truth` as JSON per row: `{"LABEL": [{"label": "LABEL", "start": N,
"end": N}]}` — char offsets into the CLEANED text. Rows with no entities are kept with
`{}` — they are correct negatives and the model needs them.

## Outputs

- `app/exports/training_ner.csv` — columns `text,ground_truth`. This is the AI Hub
  upload file (Extraction → Add → Text → CSV).
- `app/exports/training_ner_flat.csv` — one row per entity (`text,entity,label,start,end`)
  plus clean copies of no-entity rows. Human-review copy only; never upload it.

## Verification gate (must pass before handing off)

Reload the written CSV, then for every span assert the slice round-trips to a real
entity: EMAIL slice contains `@`, PERSON slice starts with `@`, PRODUCT slice
lowercases into the vocabulary. Any miss means offsets were computed against stale text
(e.g. text cleaned after annotation) — fix the ordering, not the assertions.

## Known limits

Pre-labeling is pattern-based: exact for EMAIL/@mentions, only as good as the product
vocabulary for PRODUCT. Products referenced informally ("the studio", "sandbox") are
unmarked. The flat CSV exists so a human can hand-correct before upload; never
represent the file as human-annotated.

## Audit gotcha: @mention regex vs EMAIL spans

Checking "every @mention must be a PERSON" with a naive `@[\w.-]+` regex produces
~9% false gaps: email-local parts and domains match the pattern, so `@neutrinos.co`
inside a properly EMAIL-tagged span looks like an untagged PERSON. Treat any @-token
fully or partially inside an EMAIL span as covered; count only @-tokens that overlap
no tagged span as genuine gaps. Also expect a few correct omissions (asset tags like
`@IN-NEU-BL-L0450` are not people). The v2 per-column format (`text,PERSON,PRODUCT,
EMAIL`, JSON array per column) is the platform upload target; span-vs-text equality
and zero overlaps must pass before handoff.
