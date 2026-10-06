# Rebuilding the retrieval index from the corpus (bridge pattern)

When a scraping pipeline feeds an existing retrieval/RAG database, the lazy-correct
move is a pure conversion step plus the consumer's own build stages — never a forked
indexer that re-implements chunking/embedding.

## Rebuild-from-nothing beats incremental when the consumer supports it

If the consumer builds `db.new` from scratch and atomically swaps it in, use that:
a full rebuild of a ~10k-chunk corpus with CPU embeddings takes minutes, is
idempotent, and a failed build never touches the live DB. Incremental upsert into
a schema you don't own risks silent divergence. Back up the live DB before the
first bridge run regardless.

## The conversion contract

Produce exactly the consumer's expected input records from the scraper's cache +
state (markdown files + metadata). Map every field honestly:
- `lastmod`: keep FULL precision end-to-end (date-truncation loses same-day edits).
- `content_hash`: sha256 of the markdown; downstream delta logic keys on this.
- sections: split markdown on ATX headings; heading_path = chain of ancestor headings.
- links: resolve against the scraper's known pub/slug set; keep unresolved recorded.
- code samples: fenced blocks. CAUTION — if the consumer derives a `has_code`
  stratum from its own code-sample table, a bridge that under-fills that table
  silently starves downstream sampling/generation strata. Prefer deriving strata
  from chunk text (the `has_code` flag), and treat an order-of-magnitude drop in
  the code-sample count after a rebuild as a bridge bug.
- Skip near-empty topics from indexing (they pollute retrieval) but keep them in
  the corpus state.

## Automating the rebuild

Trigger on scraper success, not on a clock: watch the scraper's last-run status
file; run the conversion + consumer build stages only when state changed since the
last marker; write the marker only on verified success (including the consumer's
integrity check). Back off an hour on failure. A systemd user unit looping every
few minutes is enough — no cron, no extra scheduler.

## Verify after every rebuild

One assert script (run in the consumer's venv so its sqlite extensions load):
row counts match input records, vectors populated 1:1 with chunks, full-precision
lastmod present, FTS smoke query returns hits, version/link edges non-zero. Print
one PASS line naming the counts.
