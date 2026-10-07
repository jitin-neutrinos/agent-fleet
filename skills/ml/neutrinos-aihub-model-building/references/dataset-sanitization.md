# Sanitizing a training CSV for AI Hub upload

The user's standing requirement: training data uploaded to AI Hub is **fully clean — no
special characters**. Apply this to every CSV before advising an upload.

## Procedure (one pass, then a post-write audit)

1. **Normalize unicode** (`NFKC`) — this alone collapses most lookalikes.
2. **Map printable typography to plain ASCII** with a fixed replacement table, not a
   per-file ad-hoc list:

   | Source | Replace with |
   |---|---|
   | `• ▪ ◦` (bullets) | `- ` |
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

## The audit (run it on the WRITTEN file, not the in-memory data)

- non-ASCII count in the final file = **0**
- row count identical to the input (cleaning must never drop rows — a row whose text
  empties entirely is a data defect to surface, not silently delete)
- class distribution unchanged vs the source (a clean that shifts the distribution
  deleted rows)

## Delivery conventions

- Ship as `<name>_clean.csv` next to the original — the unsanitized original stays the
  provenance artifact (the label rules reference it).
- Archive the clean file back into the repo's `processed/` dir as well as the upload
  destination; the chat copy is a transport, not the record.

## Why ASCII-clean specifically

Silent truncation and tokenizer quirks aside, the platform preview and any downstream
batch-test diffing render these characters unpredictably, and the user reads training
rows directly during wizard confirmation — a bullet fragment in a preview row costs
confidence in the whole dataset.
