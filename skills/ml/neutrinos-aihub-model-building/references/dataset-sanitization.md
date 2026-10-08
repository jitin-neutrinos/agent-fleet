# Sanitizing a training CSV for AI Hub upload

The user's standing requirement: training data uploaded to AI Hub is **fully clean — no
special characters**. Apply this to every CSV before advising an upload.

## Control characters are step ZERO, before typography

A worksheet-upload rejection ('cannot be used in worksheets') on an otherwise
well-formed CSV means control characters. Verified 2026-10-08: the rejected row
started `5. \x07Pre-Hospitalization Expenses:` — a BEL (0x07) left by PDF bullet
glyph extraction; the corpus also carried 0x03/0x04/0x12. Strip C0/C1 first
(`[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]`), then do typography.

Never let a clean pass EMIT control bytes: the first clean of the model5 dataset
mapped a Private Use Area bullet (U+F0xx) through a chain that produced 417 NUL
bytes (0x00) in the 'clean' file — worse than the original. The audit on the
WRITTEN bytes catches this; an in-memory check does not.

## Procedure (one pass, then a post-write audit)

0. **Strip C0/C1 control characters** (see above).

1. **Normalize unicode** (`NFKC`) — this alone collapses most lookalikes.
2. **Map printable typography to plain ASCII** with a fixed replacement table, not a
   per-file ad-hoc list:

   | Source | Replace with |
   |---|---|
   | `• ▪ ◦ ● ○ ■` (bullets) | `-` |
   | `– — ―` (en/em/horizontal bars) | `-` |
   | `“ ” „ ‟` (double quotes) | `"` |
   | `‘ ’ ‛` (single quotes) | `'` |
   | `…` | `...` |
   | `© ® ™` | `(c) (R) TM` |
   | `≥ ≤` | `>= <=` |
   | `× ÷` | `x /` |
   | `₹ € £` | `Rs / EUR / GBP ` |
   | NBSP, zero-width (`\u200b`), soft hyphen (`\xad`) | ` ` or drop |

3. **Drop remaining non-ASCII** outright (Greek/Coptic/math fragments that OCR noise
   produces survive step 2; they carry no signal). Expect a small tail — ~30 rows in
   5,000 — and log which characters were dropped so a repeated offender can be added to
   the table.
4. **Normalize whitespace**: collapse runs to single spaces, strip ends. This fixes
   PDF-extracted mid-line breaks.
5. **Normalize labels** separately: lowercase, `[a-z_]` only. `waiting_period` stays
   underscored — never re-invent label spellings mid-clean.

## Dropping a corrupt row (only with explicit user authorization)

Identify it by a unique text prefix, ASSERT the prefix matches exactly one row, and
assert the class-distribution delta is exactly the one expected row (e.g.
`{'limit': -1}`). Record the dropped text in the script output — a drop that cannot
be shown is a drop that did not happen.

## The audit (run it on the WRITTEN file, not the in-memory data)

- byte scan: printable ASCII + line endings ONLY — zero control bytes, zero bytes >0x7E
- non-ASCII count in the final file = **0**
- row count identical to the input minus authorized drops (cleaning must never drop
  rows on its own — a row whose text empties entirely is a data defect to surface,
  not silently delete)
- class distribution delta vs the source enumerated and explained

## Delivery conventions

- Ship as `<name>_clean.csv` next to the original — the unsanitized original stays the
  provenance artifact (the label rules reference it).
- Ship all wizard variants from ONE script over the untouched master (clean + noheader
  etc.), never patch variants independently — the first model5 pass drifted the
  variants apart.
- Keep the sanitize script in the repo `scripts/` — re-running it after any future
  dataset edit IS the regression check (it re-audits the written bytes).
- Archive the clean file back into the repo's `processed/` dir as well as the upload
  destination; the chat copy is a transport, not the record.

## Why ASCII-clean specifically

Silent truncation and tokenizer quirks aside, the platform preview and any downstream
batch-test diffing render these characters unpredictably, and the user reads training
rows directly during wizard confirmation — a bullet fragment in a preview row costs
confidence in the whole dataset. Control bytes are worse: they are hard-rejected by
worksheet parsers, so one bad row blocks the entire upload.
