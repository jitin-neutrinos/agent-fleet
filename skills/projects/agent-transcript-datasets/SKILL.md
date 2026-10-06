---
name: agent-transcript-datasets
description: "Use when turning chat history into a fine-tuning dataset."
version: 1.0.0
metadata:
  hermes:
    tags: [datasets, fine-tuning, sft, session-archive, data-hygiene, ingestion]
---

# Agent transcripts → training datasets

Use when asked to archive chat/session history, ingest sessions automatically, or
build a training dataset from an agent's own transcripts for fine-tuning.

## When to use

- "archive chats older than N days" / retention policy
- "ingest every chat that has not been ingested"
- "build / maintain a training dataset from our chats"
- any pipeline feeding a local model fine-tune from session history

## Reuse the platform's native retention — never build a second archive

Before writing retention code, check whether the host already has it. Hermes
exposes `sessions.auto_archive` + `sessions.auto_archive_days` (soft-hide, never
delete, pinned sessions exempt), swept from the gateway's housekeeping tick and
the `hermes serve` session-list path. Set the config key and you are done.

A parallel archive tier in the app can only drift from the native one — two
systems deciding "archived" disagree the first time one is reconfigured. Note
the distinction the user may not make: **archive = soft-hide/recoverable**,
`sessions.retention_days` = hard delete. Confirm which one is being asked for.

## Dumping == ingesting: keep it one operation

A transcript is "ingested" the moment it lands in the archive table. Do not build
a separate ingest state machine that can disagree with the dump state — record
`ingested_at` on the same row write that stores the messages.

- **Backfill pre-existing rows on boot**, or every already-archived session reads
  as un-ingested forever and the counter never converges.
- **Skip active sessions** when sweeping (never snapshot a live transcript).
- Make the dump **idempotent** (upsert on `(session_id, row_id)`) so re-runs and
  retries are safe, and share ONE dump function between the manual path and the
  sweeper.
- Guard the sweep against re-entry: a second call while one is running should
  report "in progress", not start a duplicate.

## The archive is agent telemetry, not chat

This is the finding that matters. Measured on a real archive: **94% of all text
was tool output**, ~29k assistant rows carried no prose at all (they were pure
tool-call envelopes), and hundreds of sessions were automation. Training on that
teaches JSON escaping and noise.

### Hygiene rules, in the order they apply

| Rule | Why |
|---|---|
| Drop `role='tool'` rows | the result body is 94% of the bytes and none of the signal |
| Keep ONE compact heading per tool call | `terminal: grep -rn login` preserves the trace of what happened without the payload |
| Unwrap JSON envelopes | `{"output":…}` / `{"content":…}` → their text; a bare call envelope → `""` |
| Exclude automation sources | `cron` / `oneshot` / `tool` are machinery, not conversation |
| Exclude the pipeline's own sessions | a review/ingest agent runs as a one-shot session whose first user message is its prompt — match that marker |
| Strip harness scaffolding | `[System: …]`, `[System note: …]`, `[Surface: …]`, `[IMPORTANT: … background process …]`, `[Background process … heartbeat]`, `[OUT-OF-BAND USER MESSAGE …]`, `[STILL IN PROGRESS]`, `[CONTEXT COMPACTION]`, `REFERENCE ONLY` |
| Drop boilerplate turns | the greeting prompt, "request was not processed", interrupted/stopped replies |
| Merge same-role neighbours, THEN truncate once | truncating before merging lets a merged turn exceed the cap |
| Truncate oversized turns, marked | user ≤8k, assistant ≤6k, total ≤24k chars; append `[…truncated]` |
| Dedup by content hash | of the final conversation, after cleaning |

### Ordering trap in the filter chain

Check the **marker** before the **source** when a fixture must prove one branch.
A session whose source is already automation hits that filter first, so the
internal-marker branch never executes and the check goes green over nothing.

## Measure the output — a sample is not verification

The first sampled record looked perfect while 23 of the pipeline's own sessions
were still leaking into the set. Build a QA pass that COUNTS each failure class
on the written file:

- bad boundaries (first role ≠ user, last role ≠ assistant)
- same-role adjacencies (broken alternation)
- oversized turns
- scaffolding residuals
- boilerplate residuals

Zero across all five is the bar. Report the manifest counts (raw→kept chars,
reduction %, every exclusion reason) so a regression is visible rather than
inferred. A real run: 105 MB → 3.8 MB, 96.4% reduction, and the reduction is the
point — it is all noise.

Write one runnable assert-based check for the builder and pin it in the repo's
regression manifest if one exists.

## Dataset format

SFT: one JSON object per line, `{"messages":[{"role":"user|assistant","content":…}]}`,
user-first, assistant-last, strictly alternating. Drop tool/system rows entirely
rather than trying to represent them — a chat/behaviour dataset is not a
tool-trace set, and mixing the two needs a different format (and usually a
different model).

## Pitfalls

- **A list that does not match its own counters is a display bug.** A page
  listing every archived row reads as "a lot of items stuck in review" while the
  tiles above say zero. Split the list by what each row IS (never-reviewed /
  in-flight / closed) before investigating a phantom queue.
- **Fixture filters silently skip the branch under test.** A `min_messages`
  threshold dropped the very fixture meant to exercise the "no user turn" path.
  Assert the fixture's preconditions, not just the outcome.
- **Envelope unwrapping must return `""` for a call-only object**, not the JSON
  string — otherwise the raw envelope leaks back in as assistant prose.
- Run the dataset builder against a **scratch DB and scratch output dir**, then
  confirm the live DB row counts are unchanged.
